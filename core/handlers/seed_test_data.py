from aiogram.types import Message
from datetime import datetime, timedelta
import traceback
import random
import string

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_data_from_table_users,
    add_user_to_db,
    add_user_key,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    set_key_to_table_users,
)


def fmt(dt: datetime) -> str:
    return dt.strftime('%d.%m.%Y - %H:%M')


def generate_test_id() -> str:
    """Генерирует test_XXXXX где XXXXX - 5 случайных символов"""
    chars = string.ascii_lowercase + string.digits
    return 'test_' + ''.join(random.choice(chars) for _ in range(5))


async def command_seed(message: Message) -> None:
    """
    -- Админ-команда --
    /seed
    Создаёт тестового пользователя с ID и именем test_XXXXX (5 случайных символов).
    Добавляет 2 тестовых ключа:
    - 1 просроченный (истёк вчера)
    - 1 активный (истекает через 1-3 часа)
    - Создаёт тестовый платёж в БД
    Ключи создаются на реальном сервере Outline, но платёж не проходит через YooKassa.
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        # Генерируем уникальный test ID
        test_id_str = generate_test_id()
        # Используем числовой ID для Telegram (берем hash от строки и делаем положительным)
        test_user_id = abs(hash(test_id_str)) % (10 ** 10)  # 10-значное число
        
        # Проверяем, не существует ли уже пользователь
        user = await get_user_data_from_table_users(account=test_user_id)
        if user:
            await message.answer(f'❌ Тестовый пользователь с ID {test_user_id} уже существует.\nИспользуйте /unseed для очистки.', parse_mode=None)
            return

        # Создаем пользователя
        await add_user_to_db(account=test_user_id, account_name=test_id_str)

        # Выбираем регион (по умолчанию nederland)
        region = 'nederland'

        # Prepare dates
        now = datetime.now()
        # Активный ключ истекает через 1-3 часа
        hours_active = random.randint(1, 3)
        future_date = now + timedelta(hours=hours_active)
        # Просроченный ключ истёк вчера
        past_date = now - timedelta(days=1)

        # Создаем ключи на Outline сервере
        olm = OutlineManager(region_server=region)
        
        # 1. Создание активного ключа
        outline_id_active = f"test_{test_id_str}_active"
        try:
            key_data_active = olm.create_key_from_ol(id_user=outline_id_active)
            access_url_active = key_data_active.access_url if key_data_active else None
        except Exception as e:
            await message.answer(f'❌ Ошибка создания активного ключа на Outline: {e}', parse_mode=None)
            return

        if not access_url_active:
            await message.answer('❌ Не удалось создать активный ключ на Outline', parse_mode=None)
            return

        # 2. Создание просроченного ключа
        outline_id_expired = f"test_{test_id_str}_expired"
        try:
            key_data_expired = olm.create_key_from_ol(id_user=outline_id_expired)
            access_url_expired = key_data_expired.access_url if key_data_expired else None
        except Exception as e:
            await message.answer(f'❌ Ошибка создания просроченного ключа на Outline: {e}', parse_mode=None)
            # Удаляем созданный активный ключ
            try:
                olm.delete_key_by_id(outline_id_active)
            except:
                pass
            return

        if not access_url_expired:
            await message.answer('❌ Не удалось создать просроченный ключ на Outline', parse_mode=None)
            # Удаляем созданный активный ключ
            try:
                olm.delete_key_by_id(outline_id_active)
            except:
                pass
            return

        # Добавляем ключи в БД
        await add_user_key(
            account=test_user_id,
            access_url=access_url_active,
            outline_id=outline_id_active,
            region_server=region,
            date_str=fmt(future_date),
            promo=False,
        )

        await add_user_key(
            account=test_user_id,
            access_url=access_url_expired,
            outline_id=outline_id_expired,
            region_server=region,
            date_str=fmt(past_date),
            promo=False,
        )

        # Обновляем таблицу Users для совместимости
        await set_premium_status(account=test_user_id, value_premium=True)
        await set_region_server(account=test_user_id, value_region=region)
        await set_date_to_table_users(account=test_user_id, value_date=fmt(future_date))
        await set_key_to_table_users(account=test_user_id, value_key=access_url_active)

        # Создаем тестовый платёж
        from core.sql.function_db_user_payments.users_payments import add_payment_to_db
        test_payment_key = f"test_{test_id_str}_payment"
        try:
            await add_payment_to_db(
                account=test_user_id,
                paykey=test_payment_key
            )
        except Exception as e:
            from logs.log_main import RotatingFileLogger
            logger = RotatingFileLogger()
            logger.log('warning', f'Failed to create test payment for {test_user_id}: {e}')

        await message.answer(
            text=(
                '✅ Тестовые данные созданы\n\n'
                f'<b>ID пользователя:</b> <code>{test_user_id}</code>\n'
                f'<b>Имя:</b> {test_id_str}\n'
                f'<b>Регион:</b> {region}\n\n'
                f'<b>Ключ 1 (активный):</b>\n'
                f'  • Истекает: {fmt(future_date)} (~{hours_active}ч)\n\n'
                f'<b>Ключ 2 (просроченный):</b>\n'
                f'  • Истёк: {fmt(past_date)}\n\n'
                f'<b>Платёж:</b> {test_payment_key}\n\n'
                'Используйте /activekeys, /keyinfo или /massblock для тестирования.'
            ),
            parse_mode='HTML',
        )
    except Exception as e:
        tb = traceback.format_exc()
        from logs.log_main import RotatingFileLogger
        logger = RotatingFileLogger()
        logger.log('error', f'command_seed error: {e}\n{tb}')
        try:
            await message.answer(f'❌ Ошибка при создании тестовых данных:\n{str(e)}', parse_mode=None)
        except Exception:
            pass
