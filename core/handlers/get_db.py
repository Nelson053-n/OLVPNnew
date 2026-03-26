from aiogram.types import Message, FSInputFile
from core.utils.admin_check import require_admin
from core.sql.engine import _DB_PATH


@require_admin
async def command_get_db(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /get_db.
    Отправляет в ответ файл с БД SQLite

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        sending_db_file = FSInputFile(path=str(_DB_PATH), filename="olvpnbot.db")
    except Exception:
        await message.answer('Какая-то проблема с файлом БД')
    else:
        await message.answer_document(sending_db_file)
