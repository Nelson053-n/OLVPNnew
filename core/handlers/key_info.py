from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users
from core.utils.create_view import create_answer_from_html
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()

# Import ParseMode to disable HTML parsing for certain messages
from aiogram.enums import ParseMode


async def get_key_info_response(user_id: int) -> tuple:
    """
    Получить информацию о ключе пользователя.
    Возвращает (text, keyboard) для использования в разных контекстах.
    
    :param user_id: ID пользователя
    :return: tuple(text, keyboard)
    """
    try:
        # Получаем все записи из БД
        all_users = await get_all_records_from_table_users()
        user_record = None
        
        for user in all_users:
            if user.account == user_id:
                user_record = user
                break

        if not user_record:
            return (f"Пользователь с ID {user_id} не найден в БД", InlineKeyboardBuilder().as_markup())

        if not user_record.key:
            return (f"У пользователя {user_id} нет активного ключа", InlineKeyboardBuilder().as_markup())

        # Получаем информацию о ключе из Outline
        region_server = user_record.region_server or "nederland"
        try:
            olm = OutlineManager(region_server=region_server)
            outline_key = olm.get_key_from_ol(id_user=str(user_id))
            
            if not outline_key:
                return (f"Ключ пользователя {user_id} не найден на сервере {region_server}", InlineKeyboardBuilder().as_markup())

            # Форматируем информацию о трафике
            used_gb = outline_key.used_bytes / (1024**3)  # Конвертируем в ГБ
            telegram_name = user_record.account_name
            
            # Создаём ответ
            response_text = (
                f"Информация о ключе\n\n"
                f"Пользователь: {telegram_name} (ID: {user_id})\n"
                f"Регион: {region_server}\n"
                f"Трафик использован: {used_gb:.2f} ГБ\n"
                f"Статус: {'Активен' if user_record.premium else 'Неактивен'}"
            )
            
            # Создаём клавиатуру с кнопкой блокировки
            keyboard = create_key_info_keyboard(user_id)
            
            return (response_text, keyboard)

        except Exception as e:
            tb = traceback.format_exc()
            logger.log('error', f'get_key_info_response outline error: {e}\n{tb}')
            return (f"Ошибка при получении информации о ключе: {str(e)}", InlineKeyboardBuilder().as_markup())
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'get_key_info_response error: {e}\n{tb}')
        return (f"Ошибка при обработке: {str(e)}", InlineKeyboardBuilder().as_markup())


async def command_keyinfo(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /keyinfo <user_id>.
    Выводит информацию о ключе пользователя.

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        if message.from_user.id != int(admin_tlg):
            await message.answer("У вас нет доступа к этой команде", parse_mode=ParseMode.TEXT)
            return

        data = message.text.split(' ')
        
        if len(data) != 2:
            await message.answer("Ошибка использования команды\nИспользование: /keyinfo <user_id>", parse_mode=ParseMode.TEXT)
            return

        try:
            user_id = int(data[1])
        except ValueError:
            await message.answer("user_id должен быть числом", parse_mode=ParseMode.TEXT)
            return

        # Используем общую функцию
        response_text, keyboard = await get_key_info_response(user_id)
        await message.answer(text=response_text, reply_markup=keyboard, parse_mode=ParseMode.TEXT)

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_keyinfo error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /keyinfo: {str(e)}", parse_mode=ParseMode.TEXT)
        except:
            pass


def create_key_info_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с кнопкой блокировки ключа

    :param user_id: int - ID пользователя
    :return: InlineKeyboardMarkup - Клавиатура
    """
    keyboard_builder = InlineKeyboardBuilder()
    keyboard_builder.button(
        text='🔒 Заблокировать ключ',
        callback_data=f'admin_block_key_{user_id}'
    )
    return keyboard_builder.as_markup()
