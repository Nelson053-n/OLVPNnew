"""
Обработчик для отправки и закрепления сообщения с дисклеймером
"""
from aiogram.types import Message
from aiogram import Bot
from core.utils.create_view import create_answer_from_html
from core.utils.admin_check import require_admin
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


@require_admin
async def pin_disclaimer_handler(message: Message, bot: Bot) -> None:
    """
    Отправляет и закрепляет сообщение с юридическим дисклеймером.
    Доступно только администратору.

    :param message: Message - объект сообщения
    :param bot: Bot - объект бота
    """
    
    try:
        # Загружаем шаблон дисклеймера
        content = await create_answer_from_html(name_temp='/pinned_disclaimer')
        
        # Отправляем сообщение
        sent_message = await message.answer(
            text=content,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        # Закрепляем сообщение
        await bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=sent_message.message_id,
            disable_notification=False
        )
        
        logger.log('info', f'Disclaimer pinned by admin {message.from_user.id}')
        
    except Exception as e:
        logger.log('error', f'Error pinning disclaimer: {e}')
        await message.answer("Ошибка при закреплении сообщения")
