from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_keyboard() -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для стартового меню.

    :return: InlineKeyboardMarkup - Объект InlineKeyboardMarkup, содержащий клавиатуру.
    """
    keyboard_builder = InlineKeyboardBuilder()
    keyboard_builder.button(text='🏢 Заказать доступ', callback_data='get_key')
    keyboard_builder.button(text='🔧 Мои подключения', callback_data='my_key')
    keyboard_builder.button(text='📄 Документация', callback_data='docs')
    keyboard_builder.adjust(2, 1)  # 2 кнопки в первом ряду, 1 во втором
    return keyboard_builder.as_markup()