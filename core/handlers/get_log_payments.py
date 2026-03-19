from aiogram.types import Message, FSInputFile, BufferedInputFile
import os
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger


async def command_get_log_pay(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /get_log_pay.
    Отправляет в ответ файл с логами оплаты в UTF-8 кодировке

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    if message.from_user.id == admin_tlg:
        try:
            payments_logger = RotatingFileLogger('logs/log_settings_payments.json')
            log_files = payments_logger.get_log_files()

            if not log_files:
                await message.answer('Файл логов не найден')
                return

            # Берем самый свежий лог
            log_path = str(log_files[0])

            # Читаем файл с явным указанием кодировки UTF-8
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Создаем BufferedInputFile с UTF-8 байтами
            file_bytes = content.encode('utf-8')
            sending_log_file = BufferedInputFile(file_bytes, filename=os.path.basename(log_path))

            await message.answer_document(
                sending_log_file,
                caption=f'📄 Логи платежей (UTF-8)\nФайл: {os.path.basename(log_path)}'
            )
        except Exception as e:
            await message.answer(f'Ошибка при отправке файла логов: {str(e)}')
