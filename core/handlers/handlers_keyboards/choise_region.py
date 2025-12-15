import json

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from core.keyboards.time_button import time_keyboard
from core.keyboards.choise_region_button import choise_region_keyboard
from core.utils.create_view import create_answer_from_html
from core.utils.get_region_name import get_region_name_from_json
from core.utils.server_config import check_server_key_limit


async def region_handler(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для выбора региона
    Проверяет доступность сервера и количество ключей

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    id_user = call.from_user.id
    region_data = call.data
    
    # Проверяем, является ли это недоступным сервером
    if region_data.startswith("disabled_"):
        region_name = region_data.replace("disabled_", "")
        is_available, current_keys, max_keys = await check_server_key_limit(region_name)
        region_display = await get_region_name_from_json(region=region_name)
        
        content = (
            f"❌ <b>Сервер недоступен</b>\n\n"
            f"{region_display}\n"
            f"<b>Использовано ключей:</b> {current_keys}/{max_keys}\n\n"
            f"Лимит достигнут. Пожалуйста, выберите другой регион."
        )
        return content, await choise_region_keyboard()
    
    # Проверяем доступность выбранного региона
    is_available, current_keys, max_keys = await check_server_key_limit(region_data)
    if not is_available:
        region_display = await get_region_name_from_json(region=region_data)
        content = (
            f"❌ <b>Сервер недоступен</b>\n\n"
            f"{region_display}\n"
            f"<b>Использовано ключей:</b> {current_keys}/{max_keys}\n\n"
            f"Лимит достигнут. Пожалуйста, выберите другой регион."
        )
        return content, await choise_region_keyboard()
    
    # Регион доступен - показываем информацию о нём
    name_temp = 'choise_region'
    region_name = await get_region_name_from_json(region=region_data)
    await state.update_data(region_server=region_data)
    
    # Добавляем информацию о лимите в контекст для шаблона
    content = await create_answer_from_html(
        name_temp=name_temp,
        region_name=region_name,
        current_keys=current_keys,
        max_keys=max_keys
    )
    return content, await time_keyboard(id_user=id_user)

