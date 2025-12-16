from aiogram.types import Message
import traceback

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_user_keys,
    get_user_keys,
    delete_user_key_record,
    set_key_to_table_users,
    set_premium_status,
    set_region_server,
    set_date_to_table_users,
)


def is_seed_key(access_url: str | None, outline_id: str | None) -> bool:
    if access_url and 'seed.local/' in access_url:
        return True
    if outline_id and outline_id.startswith('seed-'):
        return True
    return False


async def _reset_user_if_no_keys(user_id: int):
    remaining = await get_user_keys(account=user_id)
    if not remaining:
        await set_key_to_table_users(account=user_id, value_key=None)
        await set_premium_status(account=user_id, value_premium=False)
        await set_region_server(account=user_id, value_region=None)
        await set_date_to_table_users(account=user_id, value_date=None)


async def command_unseed(message: Message) -> None:
    """
    -- Админ-команда --
    /unseed [user_id|all]
    Удаляет все seed-ключи из БД (созданные /seed). Outline не трогаем.
    Если у пользователя после удаления не остаётся ключей — сбрасываются поля Users.*
    """
    try:
        if message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        parts = message.text.split()
        scope_all = False
        target_user_id: int | None = None
        if len(parts) >= 2:
            if parts[1].lower() == 'all':
                scope_all = True
            else:
                try:
                    target_user_id = int(parts[1])
                except ValueError:
                    await message.answer('user_id должен быть числом или используйте "all"', parse_mode=None)
                    return

        to_delete = []
        all_keys = await get_all_user_keys()
        for k in all_keys:
            if not is_seed_key(getattr(k, 'access_url', None), getattr(k, 'outline_id', None)):
                continue
            if scope_all or (target_user_id is None and k.account == message.from_user.id) or (target_user_id == k.account):
                to_delete.append(k)

        if not to_delete:
            await message.answer('Нет seed-ключей под указанный фильтр', parse_mode=None)
            return

        count = 0
        affected_users: set[int] = set()
        for k in to_delete:
            await delete_user_key_record(k.id)
            affected_users.add(k.account)
            count += 1

        # sync Users table for affected users
        for uid in affected_users:
            await _reset_user_if_no_keys(uid)

        await message.answer(f'✅ Удалено seed-ключей: {count}. Пользователи обновлены: {len(affected_users)}', parse_mode=None)
    except Exception as e:
        tb = traceback.format_exc()
        from logs.log_main import RotatingFileLogger
        logger = RotatingFileLogger()
        logger.log('error', f'command_unseed error: {e}\n{tb}')
        try:
            await message.answer(f'Ошибка при удалении seed-данных:\n{str(e)}', parse_mode=None)
        except Exception:
            pass
