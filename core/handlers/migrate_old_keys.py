"""
Миграция старых ключей из Users.key в новую систему UserKey
"""

import uuid
from datetime import datetime, timedelta
from aiogram import types
from aiogram.filters import Command

from core.api_s.outline.outline_api import OutlineManager
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    get_user_keys,
    get_all_user_keys,
)
from core.sql.function_db_user_payments.users_payments import get_all_user_payments
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
        'with_payment_date': 0,
        'estimated_date': 0,
    }

    try:
        # Получаем всех пользователей и платежи
        all_users = await get_all_records_from_table_users()
        all_payments = await get_all_user_payments()
        stats['total_users'] = len(all_users)
        
        # Создаем мапу платежей по account_id
        payment_map = {}
        for payment in all_payments:
            if payment.time_added:
                payment_map[payment.account_id] = payment.time_added

        logger.log('info', f"[MIGRATION] Начало миграции. Всего пользователей: {stats['total_users']}, платежей: {len(all_payments)}")

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

                    # Определяем дату создания ключа
                    # Приоритет 1: Реальная дата из платежей
                    if user.account in payment_map:
                        estimated_created = payment_map[user.account]
                        stats['with_payment_date'] += 1
                    # Приоритет 2: Вычисляем по дате истечения
                    elif user.date:
                        # Предполагаем что ключ был создан за 30 дней до истечения
                        estimated_created = user.date - timedelta(days=30)
                        stats['estimated_date'] += 1
                    # Приоритет 3: Ставим старую дату
                    else:
                        estimated_created = datetime.now() - timedelta(days=365)
                        stats['estimated_date'] += 1

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
                        created_at=estimated_created,  # Используем реальную или вычисленную дату
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
  📅 С реальной датой покупки: {stats['with_payment_date']}
  📊 С вычисленной датой: {stats['estimated_date']}
🔄 Уже были мигрированы: {stats['already_migrated']}
❌ Ошибки миграции: {stats['failed_migrations']}
🔍 Ключей не найдено на сервере: {stats['key_not_found_on_server']}

💡 Даты покупки взяты из таблицы платежей где возможно
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


async def command_fix_migration_dates(message: types.Message):
    """
    Исправление дат created_at для уже мигрированных ключей.
    Используется если миграция прошла, но даты установились неправильно.
    Доступна только администратору.
    """
    # Проверка прав администратора
    if str(message.from_user.id) != admin_tlg:
        await message.answer("❌ Эта команда доступна только администратору")
        return

    await message.answer("🔄 Начинаю исправление дат мигрированных ключей...")

    try:
        all_users = await get_all_records_from_table_users()
        all_keys = await get_all_user_keys()
        all_payments = await get_all_user_payments()
        
        # Создаем мапу платежей по account_id
        payment_map = {}
        for payment in all_payments:
            if payment.time_added:
                payment_map[payment.account_id] = payment.time_added
        
        updated_count = 0
        skipped_count = 0
        with_real_date = 0
        with_estimated_date = 0
        details = []
        
        now = datetime.now()
        
        with Session(engine) as session:
            for key in all_keys:
                old_created = key.created_at
                
                # Вычисляем правильную дату created_at
                # Приоритет 1: Реальная дата из платежей
                if key.account in payment_map:
                    estimated_created = payment_map[key.account]
                    with_real_date += 1
                    date_type = "💳 реальная"
                # Приоритет 2: Вычисляем по дате истечения
                elif key.date:
                    estimated_created = key.date - timedelta(days=30)
                    with_estimated_date += 1
                    date_type = "📊 вычисленная"
                # Приоритет 3: Ставим старую дату
                else:
                    estimated_created = now - timedelta(days=365)
                    with_estimated_date += 1
                    date_type = "📊 дефолт"
                
                # Проверяем нужно ли обновление
                # Обновляем если разница больше 1 дня
                if old_created and abs((old_created - estimated_created).total_seconds()) < 86400:
                    skipped_count += 1
                    continue
                
                # Обновляем запись
                session.query(UserKey).filter(UserKey.id == key.id).update({
                    'created_at': estimated_created
                })
                updated_count += 1
                
                # Добавляем в детали первые 10 записей
                if len(details) < 10:
                    date_str = key.date.strftime("%d.%m.%Y") if key.date else "нет даты"
                    details.append(
                        f"  • ID: {key.account} | {key.region_server} | "
                        f"истекает: {date_str} | создан: {estimated_created.strftime('%d.%m.%Y')} {date_type}"
                    )
            
            session.commit()
        
        report = f"""
📊 <b>Отчет об исправлении дат</b>

✅ Обновлено ключей: {updated_count}
  💳 С реальной датой покупки: {with_real_date}
  📊 С вычисленной датой: {with_estimated_date}
⏭️ Пропущено (корректные даты): {skipped_count}
📅 Всего ключей в БД: {len(all_keys)}

<b>Примеры обновленных:</b>
{chr(10).join(details) if details else "нет"}

💡 Теперь команды /activekeys и /stats должны работать корректно.
💡 Даты покупки взяты из реальной истории платежей где возможно!
"""
        await message.answer(report, parse_mode='HTML')
        logger.log('info', f"[MIGRATION] Исправление дат завершено. Обновлено: {updated_count} (реальных: {with_real_date}, вычисленных: {with_estimated_date})")

    except Exception as e:
        await message.answer(f"❌ Ошибка при исправлении дат: {str(e)}")
        logger.log('error', f"[MIGRATION] Ошибка исправления дат: {e}")


async def command_debug_keys(message: types.Message):
    """
    Диагностика - показать все ключи из БД с полной информацией.
    Доступна только администратору.
    """
    # Проверка прав администратора
    if str(message.from_user.id) != admin_tlg:
        await message.answer("❌ Эта команда доступна только администратору")
        return

    try:
        all_users = await get_all_records_from_table_users()
        all_keys = await get_all_user_keys()
        
        now = datetime.now()
        
        # Создаем мапу пользователей
        user_map = {u.account: u for u in all_users}
        
        # Группируем ключи
        active_keys = []
        expired_keys = []
        
        for key in all_keys:
            user = user_map.get(key.account)
            username = getattr(user, 'account_name', 'unknown') if user else 'unknown'
            
            days_left = (key.date - now).days if key.date and key.date > now else 0
            is_active = key.date and key.date > now
            
            key_info = {
                'account': key.account,
                'username': username,
                'region': key.region_server or 'unknown',
                'date': key.date.strftime("%d.%m.%Y %H:%M") if key.date else 'нет',
                'created': key.created_at.strftime("%d.%m.%Y") if key.created_at else 'нет',
                'days_left': days_left,
                'promo': '🎁' if key.promo else '💳',
                'premium': key.premium
            }
            
            if is_active:
                active_keys.append(key_info)
            else:
                expired_keys.append(key_info)
        
        # Сортируем активные по дате истечения
        active_keys.sort(key=lambda x: x['days_left'])
        
        report_lines = [
            f"<b>🔍 Диагностика ключей в БД</b>\n",
            f"📊 Всего ключей: {len(all_keys)}",
            f"✅ Активных: {len(active_keys)}",
            f"❌ Истекших: {len(expired_keys)}\n"
        ]
        
        if active_keys:
            report_lines.append("<b>Активные ключи:</b>")
            for idx, k in enumerate(active_keys[:20], 1):  # Первые 20
                report_lines.append(
                    f"{idx}. <code>{k['account']}</code> @{k['username']}\n"
                    f"   {k['promo']} {k['region']} | истекает: {k['date']} ({k['days_left']}д)\n"
                    f"   создан: {k['created']} | premium: {k['premium']}"
                )
            
            if len(active_keys) > 20:
                report_lines.append(f"\n... и ещё {len(active_keys) - 20} активных")
        
        if expired_keys and len(expired_keys) <= 5:
            report_lines.append(f"\n<b>Истекшие ключи ({len(expired_keys)}):</b>")
            for k in expired_keys:
                report_lines.append(
                    f"• <code>{k['account']}</code> @{k['username']} | {k['region']} | {k['date']}"
                )
        
        report = "\n".join(report_lines)
        
        # Разбиваем если слишком длинное
        if len(report) > 4000:
            # Отправляем по частям
            for i in range(0, len(report_lines), 30):
                chunk = "\n".join(report_lines[i:i+30])
                await message.answer(chunk, parse_mode='HTML')
        else:
            await message.answer(report, parse_mode='HTML')
        
        logger.log('info', f"[MIGRATION] Диагностика ключей: {len(all_keys)} всего, {len(active_keys)} активных")

    except Exception as e:
        await message.answer(f"❌ Ошибка при диагностике: {str(e)}")
        logger.log('error', f"[MIGRATION] Ошибка диагностики: {e}")
