from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users, get_user_keys
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

        # Получаем ключи пользователя (возможны несколько)
        user_keys = await get_user_keys(account=user_id)
        if not user_keys:
            return (f"У пользователя {user_id} нет активных ключей", InlineKeyboardBuilder().as_markup())

        # Собираем информацию по каждому ключу
        parts = [f"📊 Информация о ключах\n\nПользователь: {user_record.account_name} (ID: {user_id})"]
        keyboard = InlineKeyboardBuilder()
        for uk in user_keys:
            try:
                olm = OutlineManager(region_server=uk.region_server or 'nederland')
                outline_key = olm.get_key_by_id(uk.outline_id)
                used_bytes = getattr(outline_key, 'used_bytes', 0) or 0
                used_gb = used_bytes / (1024**3)
                parts.append(
                    f"\n— Регион: {uk.region_server}\n"
                    f"  Трафик использован: {used_gb:.2f} ГБ\n"
                    f"  Статус: {'Активен' if uk.premium else 'Неактивен'}\n"
                    f"  Истекает: {uk.date.strftime('%d.%m.%Y - %H:%M') if uk.date else '—'}\n"
                    f"  URL: {uk.access_url}"
                )
            except Exception:
                parts.append(
                    f"\n— Регион: {uk.region_server} (ключ не найден на сервере)\n"
                    f"  URL: {uk.access_url}"
                )
            # Добавляем кнопку блокировки для конкретного ключа (используем короткий ID)
            short_id = str(uk.id)[-8:]  # Последние 8 символов UUID
            keyboard.button(text=f"🔒 Заблокировать ключ", callback_data=f"cfm_blk_{short_id}")
        keyboard.adjust(1)
        return ("\n".join(parts), keyboard.as_markup())
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
            await message.answer("У вас нет доступа к этой команде", parse_mode=None)
            return

        data = message.text.split(' ')
        
        if len(data) != 2:
            await message.answer("Ошибка использования команды\nИспользование: /keyinfo USER_ID", parse_mode=None)
            return

        try:
            user_id = int(data[1])
        except ValueError:
            await message.answer("user_id должен быть числом", parse_mode=None)
            return

        # Используем общую функцию
        response_text, keyboard = await get_key_info_response(user_id)
        await message.answer(text=response_text, reply_markup=keyboard, parse_mode=None)

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_keyinfo error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /keyinfo: {str(e)}", parse_mode=None)
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
        callback_data=f'confirm_block_key_{user_id}'
    )
    return keyboard_builder.as_markup()
