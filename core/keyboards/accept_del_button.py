from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def accept_del_keyboard() -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для подтверждения или опровержения удаления ключа

    :return: InlineKeyboardMarkup - Объект InlineKeyboardMarkup, содержащий клавиатуру.
    """
    keyboard_builder = InlineKeyboardBuilder()
    keyboard_builder.button(text='✅ Подтверждаю', callback_data='del_key')
    keyboard_builder.button(text='❌ Отмена', callback_data='my_key')
    keyboard_builder.adjust(2)
    return keyboard_builder.as_markup()


def accept_del_userkey_keyboard(short_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения удаления конкретного ключа пользователя (по короткому ID)

    :param short_id: str - Короткий идентификатор записи UserKey (последние 8 символов UUID)
    :return: InlineKeyboardMarkup
    """
    keyboard_builder = InlineKeyboardBuilder()
    keyboard_builder.button(text='✅ Подтверждаю', callback_data=f'del_k_{short_id}')
    keyboard_builder.button(text='❌ Отмена', callback_data='my_key')
    keyboard_builder.adjust(2)
    return keyboard_builder.as_markup()