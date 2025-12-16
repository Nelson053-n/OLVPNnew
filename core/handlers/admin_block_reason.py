from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import traceback

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def command_block_reason(message: Message, state: FSMContext) -> None:
    """
    Обработчик для получения причины блокировки от администратора.
    Если в state есть pending_block_user или pending_block_key_id — выполняет блокировку с указанной причиной.
    Иначе просто игнорирует сообщение (не является командой блокировки).
    """
    try:
        # Только для админа
        if message.from_user.id != int(admin_tlg):
            return
        
        data = await state.get_data()
        # приоритет: блокировка конкретного ключа (по short_id или полному), затем пользователя целиком
        pending_key_short = data.get('pending_block_key_short_id')
        pending_key = data.get('pending_block_key_id')
        pending_user = data.get('pending_block_user')
        
        # Если нет pending-запроса — это обычное сообщение админа, просто игнорируем
        if not pending_key_short and not pending_key and not pending_user:
            return
        
        reason = message.text.strip()
        await state.clear()

        if pending_key_short:
            # Найти полный ID ключа по short_id
            from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys
            from core.handlers.handlers_keyboards.admin_block_key_handler import perform_block_userkey
            all_keys = await get_all_user_keys()
            k = next((uk for uk in all_keys if str(uk.id).endswith(pending_key_short)), None)
            if k:
                text, keyboard = await perform_block_userkey(key_id=str(k.id), admin_id=message.from_user.id, reason=reason)
                await message.answer(text=text, parse_mode=None)
            else:
                await message.answer('Ключ не найден.', parse_mode=None)
            return

        if pending_key:
            from core.handlers.handlers_keyboards.admin_block_key_handler import perform_block_userkey
            text, keyboard = await perform_block_userkey(key_id=pending_key, admin_id=message.from_user.id, reason=reason)
            await message.answer(text=text, parse_mode=None)
            return
        if pending_user:
            from core.handlers.handlers_keyboards.admin_block_key_handler import perform_block_user
            text, keyboard = await perform_block_user(user_id=pending_user, admin_id=message.from_user.id, reason=reason)
            await message.answer(text=text, parse_mode=None)
            return
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_block_reason error for admin {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer('Ошибка при обработке причины блокировки.', parse_mode=None)
        except:
            pass
