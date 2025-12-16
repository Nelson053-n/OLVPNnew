from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import SkipHandler
import traceback

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def command_block_reason(message: Message, state: FSMContext) -> None:
    """
    Обработчик для получения причины блокировки от администратора.
    Если в state есть pending_block_user — выполняет блокировку с указанной причиной.
    """
    try:
        if message.from_user.id != int(admin_tlg):
            raise SkipHandler
        data = await state.get_data()
        reason = message.text.strip()
        # приоритет: блокировка конкретного ключа, затем пользователя целиком
        pending_key = data.get('pending_block_key_id')
        pending_user = data.get('pending_block_user')
        await state.clear()

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
        raise SkipHandler
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_block_reason error for admin {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer('Ошибка при обработке причины блокировки.', parse_mode=None)
        except:
            pass
