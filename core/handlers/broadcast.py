import asyncio
import traceback

from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()


async def command_broadcast(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    /broadcast
    Рассылка текстового сообщения всем пользователям бота.
    """
    if not admin_tlg or message.from_user.id != admin_tlg:
        await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        '📢 Отправьте сообщение для рассылки всем пользователям.\n\n'
        'Поддерживается текст, фото и HTML-разметка.\n'
        'Для отмены отправьте /cancel',
        parse_mode=None,
    )


async def broadcast_message_handler(message: Message, state: FSMContext) -> None:
    """Обработка сообщения для рассылки."""
    if message.text and message.text.strip() == '/cancel':
        await state.clear()
        await message.answer('❌ Рассылка отменена', parse_mode=None)
        return

    if not admin_tlg or message.from_user.id != admin_tlg:
        await state.clear()
        return

    from core.bot import bot

    all_users = await get_all_records_from_table_users()
    if not all_users:
        await state.clear()
        await message.answer('❌ В базе нет пользователей', parse_mode=None)
        return

    await state.clear()

    total = len(all_users)
    await message.answer(f'⏳ Начинаю рассылку {total} пользователям...', parse_mode=None)

    success = 0
    blocked = 0
    errors = 0

    for user in all_users:
        try:
            if message.photo:
                # Если сообщение с фото
                await bot.send_photo(
                    chat_id=user.account,
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                    parse_mode='HTML' if message.caption else None,
                )
            else:
                await bot.send_message(
                    chat_id=user.account,
                    text=message.text,
                    parse_mode='HTML',
                )
            success += 1
        except Exception as e:
            err_str = str(e).lower()
            if 'blocked' in err_str or 'deactivated' in err_str or 'not found' in err_str:
                blocked += 1
            else:
                errors += 1
                logger.log('warning', f'Broadcast error for {user.account}: {e}')

        # Пауза чтобы не упереться в лимиты Telegram API
        if (success + blocked + errors) % 25 == 0:
            await asyncio.sleep(1)

    await message.answer(
        f'✅ Рассылка завершена!\n\n'
        f'📊 Отправлено: {success}\n'
        f'🚫 Заблокировали бота: {blocked}\n'
        f'❌ Ошибок: {errors}\n'
        f'📋 Всего в базе: {total}',
        parse_mode=None,
    )
    logger.log('info', f'Broadcast by admin {message.from_user.id}: sent={success}, blocked={blocked}, errors={errors}')
