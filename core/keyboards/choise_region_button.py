import json

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.utils.server_config import check_server_key_limit


async def choise_region_keyboard() -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для выбора региона с информацией о доступности и лимите ключей

    :return: InlineKeyboardMarkup - Объект InlineKeyboardMarkup, содержащий клавиатуру.
    """
    keyboard_builder = InlineKeyboardBuilder()
    region_buttons = await create_region_button_from_json()
    if region_buttons:
        for button in region_buttons:
            keyboard_builder.button(text=button["text"], callback_data=button["callback_data"])
    keyboard_builder.button(text='🔙 Назад', callback_data='back')
    keyboard_builder.adjust(1)
    return keyboard_builder.as_markup()


async def create_region_button_from_json() -> list:
    """
    Генерация названия и call_back данных для клавиатуры с учетом доступности и лимита ключей

    :return: list - список с текстом кнопки и callback_data
    """
    config_file = 'core/api_s/outline/settings_api_outline.json'
    with open(config_file, 'r') as f:
        config = json.load(f)
    filtered_data = []
    for value in config.values():
        if value['is_active']:
            region_name = value["name_en"]
            
            # Проверяем лимит ключей
            is_available, current_keys, max_keys = await check_server_key_limit(region_name)
            
            # Определяем индикатор доступности
            if is_available:
                indicator = "🟢"
                status = f"({current_keys}/{max_keys})"
            else:
                indicator = "🔴"
                status = f"({current_keys}/{max_keys} - ПОЛНО)"
            
            # Формируем текст кнопки
            button_text = f"{indicator} {value['name_ru']} {status}"
            
            # Если сервер недоступен, добавляем обозначение в callback (но можно нажать для информации)
            callback_data = region_name if is_available else f"disabled_{region_name}"
            
            filtered_data.append({
                "callback_data": callback_data,
                "text": button_text,
                "is_available": is_available
            })
    return filtered_data