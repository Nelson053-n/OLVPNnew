from aiogram.types import Message, FSInputFile, BufferedInputFile
import os
from core.settings import admin_tlg


async def command_get_log_pay(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /get_log_pay.
    Отправляет в ответ файл с логами оплаты в UTF-8 кодировке

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    if message.from_user.id == int(admin_tlg):
        log_path = 'logs/payments/olvpnbot.log'
        try:
            if not os.path.exists(log_path):
                await message.answer('Файл логов не найден')
                return
            
            # Читаем файл с явным указанием кодировки UTF-8
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Создаем BufferedInputFile с UTF-8 байтами
            file_bytes = content.encode('utf-8')
            sending_log_file = BufferedInputFile(file_bytes, filename="olvpnbot.log")
            
            await message.answer_document(sending_log_file, caption='📄 Логи платежей (UTF-8)')
        except Exception as e:
            await message.answer(f'Ошибка при отправке файла логов: {str(e)}')
