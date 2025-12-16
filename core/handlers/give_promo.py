from aiogram.types import Message
from datetime import datetime, timedelta
import traceback
import uuid

from core.api_s.outline.outline_api import OutlineManager
from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import (
    set_promo_status,
    set_key_to_table_users,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    get_promo_status,
    get_user_data_from_table_users,
    add_user_key,
    get_region_server,
)
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def fmt(dt: datetime) -> str:
    return dt.strftime('%d.%m.%Y - %H:%M')


async def command_promo(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /promo <id>.
    Даёт пользователю промо-ключ на 1 день.

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        if message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        data = message.text.split(' ')
        if len(data) != 2:
            await message.answer("❌ Использование: /promo USER_ID", parse_mode=None)
            return

        try:
            target_user_id = int(data[1])
        except ValueError:
            await message.answer("❌ Неверный USER_ID", parse_mode=None)
            return

        # Check user exists
        user = await get_user_data_from_table_users(account=target_user_id)
        if not user:
            await message.answer(f'❌ Пользователь {target_user_id} не найден в БД', parse_mode=None)
            return

        # Check if already had promo
        had_promo = await get_promo_status(account=target_user_id)
        if had_promo:
            await message.answer(f'❌ Пользователь {target_user_id} уже получал промо-ключ', parse_mode=None)
            return

        # Determine region
        region = await get_region_server(account=target_user_id) or 'nederland'

        # Expiry date (1 day from now)
        expiry_date = datetime.now() + timedelta(days=1)

        # Create key on Outline server with unique outline_id
        outline_id = f"{target_user_id}-promo-{uuid.uuid4().hex[:8]}"
        olm = OutlineManager(region_server=region)
        try:
            key_data = olm.create_key_from_ol(id_user=outline_id)
        except Exception as e:
            logger.log('error', f'Promo create_key error for {target_user_id}: {e}')
            await message.answer(f'❌ Ошибка создания промо-ключа на сервере: {e}', parse_mode=None)
            return

        if not key_data or not getattr(key_data, 'access_url', None):
            await message.answer('❌ Ошибка создания промо-ключа на сервере', parse_mode=None)
            return

        # Update DB - add to UserKey table and update Users for compatibility
        await add_user_key(
            account=target_user_id,
            access_url=key_data.access_url,
            outline_id=outline_id,
            region_server=region,
            date_str=fmt(expiry_date),
            promo=True,
        )
        await set_premium_status(account=target_user_id, value_premium=True)
        await set_date_to_table_users(account=target_user_id, value_date=fmt(expiry_date))
        await set_region_server(account=target_user_id, value_region=region)
        await set_key_to_table_users(account=target_user_id, value_key=key_data.access_url)
        await set_promo_status(account=target_user_id, value_promo=True)

        await message.answer(
            f'✅ Пользователю {target_user_id} выдан промо-ключ\nРегион: {region}\nИстекает: {fmt(expiry_date)}',
            parse_mode=None
        )

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_promo error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /promo: {str(e)}", parse_mode=None)
        except:
            pass



