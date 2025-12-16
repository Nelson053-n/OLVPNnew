from aiogram.types import Message
from datetime import datetime, timedelta
import traceback

from core.settings import admin_tlg
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


async def command_seed(message: Message) -> None:
    """
    -- Админ-команда --
    /seed [user_id]
    Создаёт пользователя (если отсутствует) и 2 тестовых ключа:
    - 1 активный (истекает через 2 дня)
    - 1 просроченный (истёк вчера)
    Ключи создаются только в БД (без обращения к Outline),
    что позволяет быстро проверить сценарии /activekeys, /keyinfo и фонового чекера.
    """
    try:
        if message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        parts = message.text.split()
        if len(parts) >= 2:
            try:
                target_user_id = int(parts[1])
            except ValueError:
                await message.answer('user_id должен быть числом', parse_mode=None)
                return
        else:
            target_user_id = message.from_user.id

        # ensure user exists
        user = await get_user_data_from_table_users(account=target_user_id)
        if not user:
            await add_user_to_db(account=target_user_id, account_name=f'seed_user_{target_user_id}')
            user = await get_user_data_from_table_users(account=target_user_id)

        # prepare dates
        now = datetime.now()
        future2 = now + timedelta(days=2)
        past1 = now - timedelta(days=1)

        # add two keys into UserKey table
        await add_user_key(
            account=target_user_id,
            access_url=f'https://seed.local/{target_user_id}/future2',
            outline_id=f'seed-{target_user_id}-future2',
            region_server='nederland',
            date_str=fmt(future2),
            promo=False,
        )

        await add_user_key(
            account=target_user_id,
            access_url=f'https://seed.local/{target_user_id}/past1',
            outline_id=f'seed-{target_user_id}-past1',
            region_server='nederland',
            date_str=fmt(past1),
            promo=False,
        )

        # keep Users backward compatibility
        await set_premium_status(account=target_user_id, value_premium=True)
        await set_region_server(account=target_user_id, value_region='nederland')
        await set_date_to_table_users(account=target_user_id, value_date=fmt(future2))
        await set_key_to_table_users(account=target_user_id, value_key=f'https://seed.local/{target_user_id}/future2')

        await message.answer(
            text=(
                '✅ Тестовые данные созданы\n'
                f'user_id: {target_user_id}\n'
                f'- Ключ 1: активен до {fmt(future2)}\n'
                f'- Ключ 2: истёк {fmt(past1)}\n\n'
                'Откройте /activekeys и кнопку ℹ️, затем протестируйте блокировки.'
            ),
            parse_mode=None,
        )
    except Exception as e:
        tb = traceback.format_exc()
        from logs.log_main import RotatingFileLogger
        logger = RotatingFileLogger()
        logger.log('error', f'command_seed error: {e}\n{tb}')
        try:
            await message.answer(f'Ошибка при создании тестовых данных:\n{str(e)}', parse_mode=None)
        except Exception:
            pass
