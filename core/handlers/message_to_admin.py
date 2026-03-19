from aiogram import Bot

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

_logger = RotatingFileLogger()


async def send_admin_message(bot: Bot, text: str) -> None:
    """
    Сообщение администратору о запуске и остановке бота
    :param bot: объект Bot, полученный при вызове команды.
    :param text: Текст сообщения для администратора
    :return: None
    """
    if not admin_tlg:
        _logger.log('warning', 'send_admin_message: admin_tlg is not set')
        return
    try:
        await bot.send_message(chat_id=admin_tlg, text=text)
    except Exception as e:
        _logger.log('error', f'Failed to send admin message: {e}')
