from aiogram.types import Message, FSInputFile
from core.settings import admin_tlg
from core.sql.engine import _DB_PATH


async def command_get_db(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /get_db.
    Отправляет в ответ файл с БД SQLite

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    if message.from_user.id == admin_tlg:
        try:
            sending_db_file = FSInputFile(path=str(_DB_PATH), filename="olvpnbot.db")
        except Exception:
            await message.answer('Какая-то проблема с файлом БД')
        else:
            await message.answer_document(sending_db_file)
