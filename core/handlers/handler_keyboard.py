import json
from typing import Callable, Tuple
import traceback

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.handlers.handlers_keyboards.after_pay_handler import pay_check_key
from core.handlers.handlers_keyboards.back_key_handler import back_key
from core.handlers.handlers_keyboards.get_key_handler import choise_region, day_key, week_key, month_key, my_key
from core.handlers.handlers_keyboards.del_key_handler import del_key, ask_del_key
from core.handlers.handlers_keyboards.get_promo_handler import get_promo
from core.handlers.handlers_keyboards.choise_region import region_handler
from core.handlers.handlers_keyboards.admin_block_key_handler import admin_block_key_handler
from core.utils.throttle import throttle
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


@throttle(seconds=0.2)
async def build_and_edit_message(call: CallbackQuery, state: FSMContext):
    """
    Обработчик для вывода меню и редактирования сообщения.

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    """
    try:
        await call.answer()
        data = call.data
        text, reply_markup = await switch_menu(data, call, state)
        if text != call.message.text:
            await call.message.edit_text(text=text, reply_markup=reply_markup)
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'build_and_edit_message error for user {call.from_user.id}, data={call.data}: {e}\n{tb}')


async def switch_menu(case_number: str, call: CallbackQuery, state: FSMContext) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Выбор обработчика, основываясь на callback-ключе.

    :param case_number: str - Ключ для определения необходимого обработчика.
    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Результат работы соответствующего обработчика.
    """
    try:
        # Обработка admin callback'ов для блокировки ключей
        if case_number.startswith('admin_block_key_'):
            return await admin_block_key_handler(call)
        
        switch_dict = {
            'get_key': choise_region,
            'del_key': del_key,
            'ask_del_key': ask_del_key,
            'day': day_key,
            'week': week_key,
            'month': month_key,
            'back': back_key,
            'pay_check': pay_check_key,
            'my_key': my_key,
            'promo': get_promo,
        }
        region_handler_switch = create_region_handler_from_json()
        if region_handler_switch:
            for region_switch in region_handler_switch:
                name = region_switch[0]
                handler = region_switch[1]
                switch_dict[name] = handler
        default_handler: Callable[[CallbackQuery, FSMContext],
                         Tuple[str, InlineKeyboardMarkup]] = \
                        lambda call, state: ("", InlineKeyboardMarkup())

        handler: Callable[[CallbackQuery, FSMContext],
                 Tuple[str, InlineKeyboardMarkup]] = (
                switch_dict.get(case_number, default_handler))

        return await handler(call, state)
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'switch_menu error for user {call.from_user.id}, case={case_number}: {e}\n{tb}')
        return ("Ошибка при обработке команды", InlineKeyboardBuilder().as_markup())


def create_region_handler_from_json() -> list:
    """
    Добавление call-back данных и обработку в switch_menu
    в зависимости от выбранного региона сервера

    Поиск осуществляется в settings_api_outline.json
    В случае если параметр is_active true, добавляет в список
    :return: list - список с call-back данными и обработчиком
    """
    config_file = 'core/api_s/outline/settings_api_outline.json'
    with open(config_file, 'r') as f:
        config = json.load(f)
    filtered_data = []
    for value in config.values():
        if value['is_active']:
            filtered_data.append((value["name_en"], region_handler))
    return filtered_data
