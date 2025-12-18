"""
Миграция старых ключей из Users.key в новую систему UserKey
"""

import uuid
from datetime import datetime
from aiogram import types
from aiogram.filters import Command

from core.api_s.outline.outline_api import OutlineManager
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    get_user_keys,
)
from core.sql.base import Users, UserKey
from core.settings import admin_tlg
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from logs.log_main import RotatingFileLogger

# Инициализируем движок БД и логгер
engine = create_engine('sqlite:///olvpnbot.db')
logger = RotatingFileLogger()


async def command_migrate(message: types.Message):
    """
    Команда миграции старых ключей в новую систему.
    Доступна только администратору.
    
    Процесс:
    1. Находит всех пользователей со старым полем Users.key
    2. Проверяет наличие ключа на Outline сервере
    3. Создает запись в UserKey с сохранением всех параметров
    4. НЕ удаляет старые данные (для безопасности)
    """
    # Проверка прав администратора
    if str(message.from_user.id) != admin_tlg:
        await message.answer("❌ Эта команда доступна только администратору")
        return

    await message.answer("🔄 Начинаю миграцию старых ключей...\n\n⏳ Сканирую базу данных...")

    # Статистика миграции
    stats = {
        'total_users': 0,
        'users_with_old_keys': 0,
        'already_migrated': 0,
        'successfully_migrated': 0,
        'failed_migrations': 0,
        'key_not_found_on_server': 0,
    }

    try:
        # Получаем всех пользователей
        all_users = await get_all_records_from_table_users()
        stats['total_users'] = len(all_users)

        logger.log('info', f"[MIGRATION] Начало миграции. Всего пользователей: {stats['total_users']}")

        # Список для детального отчета
        migration_details = []

        with Session(engine) as session:
            for user in all_users:
                # Проверяем наличие старого ключа
                if not user.key:
                    continue

                stats['users_with_old_keys'] += 1

                # Проверяем, есть ли уже ключи в новой системе
                existing_keys = get_user_keys(user.account)
                if existing_keys:
                    stats['already_migrated'] += 1
                    logger.log('info', f"[MIGRATION] Пользователь {user.account} уже имеет ключи в новой системе")
                    continue

                # Определяем регион сервера (из Users.region_server или дефолт)
                region_server = user.region_server if user.region_server else 'nederland'

                # Инициализируем Outline Manager для проверки ключа
                outline_manager = OutlineManager(region_server=region_server)

                # Попытка найти ключ на Outline сервере
                # Используем стратегию множественных попыток:
                try:
                    outline_key = None
                    search_strategies = []
                    
                    # Стратегия 1: Users.key содержит outline_id напрямую
                    if user.key.isdigit():
                        outline_key = outline_manager.get_key_by_id(user.key)
                        search_strategies.append(f"outline_id={user.key}")
                    
                    # Стратегия 2: Users.key содержит access_url, извлекаем из него ключ
                    if outline_key is None and user.key.startswith('ss://'):
                        # Парсим access_url для поиска похожего ключа
                        # Получаем все ключи с сервера и ищем совпадение по access_url
                        try:
                            # Используем метод get_key_from_ol который ищет по ID пользователя
                            outline_key = outline_manager.get_key_from_ol(str(user.account))
                            search_strategies.append(f"by_account={user.account}")
                        except Exception:
                            pass
                    
                    # Стратегия 3: Поиск по account ID (стандартный подход новой версии)
                    if outline_key is None:
                        outline_key = outline_manager.get_key_from_ol(str(user.account))
                        search_strategies.append(f"by_account={user.account}")
                    
                    # Стратегия 4: Поиск по UUID из Users.id
                    if outline_key is None and user.id:
                        outline_key = outline_manager.get_key_by_id(user.id)
                        search_strategies.append(f"by_uuid={user.id}")
                    
                    if outline_key is None:
                        stats['key_not_found_on_server'] += 1
                        strategies_str = " → ".join(search_strategies)
                        migration_details.append(
                            f"❌ @{user.account_name} (ID: {user.account}): "
                            f"ключ не найден на {region_server} (попытки: {strategies_str})"
                        )
                        logger.log('warning',
                            f"[MIGRATION] Ключ пользователя {user.account} не найден на {region_server}. "
                            f"Стратегии поиска: {strategies_str}, старый key={user.key[:50]}"
                        )
                        continue

                    # Создаем новую запись в UserKey
                    new_key_record = UserKey(
                        id=str(uuid.uuid4()),
                        account=user.account,
                        access_url=outline_key.access_url,
                        outline_id=outline_key.key_id,
                        region_server=region_server,
                        premium=user.premium,
                        date=user.date,
                        promo=user.promo_key,  # Если был промо, сохраняем флаг
                        created_at=datetime.now(),  # Не знаем реальную дату, ставим текущую
                    )

                    session.add(new_key_record)
                    session.commit()

                    stats['successfully_migrated'] += 1
                    migration_details.append(
                        f"✅ @{user.account_name} (ID: {user.account}): "
                        f"мигрирован на {region_server} (outline_id: {outline_key.key_id})"
                    )
                    logger.log('info',
                        f"[MIGRATION] Успешно мигрирован ключ пользователя {user.account} "
                        f"(outline_id: {outline_key.key_id}, region: {region_server}, "
                        f"premium: {user.premium}, date: {user.date})"
                    )

                except Exception as e:
                    stats['failed_migrations'] += 1
                    migration_details.append(
                        f"❌ @{user.account_name} (ID: {user.account}): ошибка - {str(e)[:50]}"
                    )
                    logger.log('error',
                        f"[MIGRATION] Ошибка миграции ключа пользователя {user.account}: {e}"
                    )
                    session.rollback()

        # Формируем финальный отчет
        report = f"""
📊 <b>Отчет о миграции ключей</b>

👥 Всего пользователей в БД: {stats['total_users']}
🔑 Пользователей со старыми ключами: {stats['users_with_old_keys']}

✅ Успешно мигрировано: {stats['successfully_migrated']}
🔄 Уже были мигрированы: {stats['already_migrated']}
❌ Ошибки миграции: {stats['failed_migrations']}
🔍 Ключей не найдено на сервере: {stats['key_not_found_on_server']}
"""

        # Если есть детали, добавляем их (макс 20 записей)
        if migration_details:
            report += "\n<b>Детальный отчет:</b>\n"
            for detail in migration_details[:20]:
                report += f"{detail}\n"
            
            if len(migration_details) > 20:
                report += f"\n... и ещё {len(migration_details) - 20} записей"

        await message.answer(report, parse_mode='HTML')
        logger.log('info', f"[MIGRATION] Миграция завершена. Статистика: {stats}")

    except Exception as e:
        error_msg = f"❌ Критическая ошибка при миграции: {str(e)}"
        await message.answer(error_msg)
        logger.log('error', f"[MIGRATION] Критическая ошибка: {e}")


async def command_check_migration_status(message: types.Message):
    """
    Проверка статуса миграции - сколько пользователей нуждаются в миграции.
    Доступна только администратору.
    """
    # Проверка прав администратора
    if str(message.from_user.id) != admin_tlg:
        await message.answer("❌ Эта команда доступна только администратору")
        return

    try:
        all_users = await get_all_records_from_table_users()
        
        need_migration = 0
        already_migrated = 0
        no_keys = 0

        for user in all_users:
            if not user.key:
                no_keys += 1
                continue

            existing_keys = get_user_keys(user.account)
            if existing_keys:
                already_migrated += 1
            else:
                need_migration += 1

        report = f"""
📊 <b>Статус миграции</b>

👥 Всего пользователей: {len(all_users)}

✅ Уже мигрированы: {already_migrated}
⏳ Требуют миграции: {need_migration}
📭 Без старых ключей: {no_keys}
"""

        if need_migration > 0:
            report += "\n💡 Используйте /migrate для миграции оставшихся ключей"

        await message.answer(report, parse_mode='HTML')

    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке статуса: {str(e)}")
        logger.log('error', f"[MIGRATION] Ошибка проверки статуса: {e}")
