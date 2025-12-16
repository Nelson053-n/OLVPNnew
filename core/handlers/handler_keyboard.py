import json
from typing import Callable, Tuple
import traceback

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
        # Handle special callbacks that perform side-effects (copy key, confirmations)
        if data.startswith('confirm_block_key_'):
            try:
                user_id = int(data.split('_')[-1])
                kb = InlineKeyboardBuilder()
                kb.button(text='✅ Да, заблокировать', callback_data=f'admin_block_key_{user_id}')
                kb.button(text='✍️ Заблокировать с причиной', callback_data=f'block_with_reason_{user_id}')
                kb.button(text='❌ Отмена', callback_data=f'cancel_block_{user_id}')
                kb.adjust(1)
                await call.message.answer(text=f'Вы уверены, что хотите заблокировать ключ пользователя {user_id}?', reply_markup=kb.as_markup())
            except Exception:
                pass
            return

        if data.startswith('cfm_blk_'):
            try:
                short_id = data.split('_')[-1]  # Последние 8 символов UUID
                kb = InlineKeyboardBuilder()
                kb.button(text='✅ Да, заблокировать', callback_data=f'adm_blk_{short_id}')
                kb.button(text='✍️ С причиной', callback_data=f'blk_rsn_{short_id}')
                kb.button(text='❌ Отмена', callback_data=f'cnl_blk_{short_id}')
                kb.adjust(1)
                await call.message.answer(text=f'Заблокировать выбранный ключ?', reply_markup=kb.as_markup())
            except Exception:
                pass
            return

        if data.startswith('block_with_reason_'):
            try:
                user_id = int(data.split('_')[-1])
                # store pending block request in state and ask admin to send reason
                await state.update_data(pending_block_user=user_id)
                await call.message.answer(text=f'Введите причину блокировки для пользователя {user_id}. Отправьте сообщение с текстом причины.', parse_mode=None)
            except Exception:
                pass
            return

        if data.startswith('blk_rsn_'):
            try:
                short_id = data.split('_')[-1]
                await state.update_data(pending_block_key_short_id=short_id)
                await call.message.answer(text='Введите причину блокировки для выбранного ключа.', parse_mode=None)
            except Exception:
                pass
            return

        if data.startswith('cancel_block_'):
            # simple cancel acknowledgement
            await call.message.answer(text='Операция блокировки отменена.', parse_mode=None)
            return

        if data.startswith('cnl_blk_'):
            await call.message.answer(text='Операция блокировки отменена.', parse_mode=None)
            return

        if data.startswith('copy_key_'):
            try:
                user_id = int(data.split('_')[-1])
                from core.sql.function_db_user_vpn.users_vpn import get_key_from_table_users
                key = await get_key_from_table_users(account=user_id)
                if key:
                    await call.message.answer(text=f"🔑 Ключ для копирования:\n{key}", parse_mode=None)
                else:
                    await call.message.answer(text="Ключ не найден.", parse_mode=None)
            except Exception:
                pass
            # do not edit the menu message
            return

        if data.startswith('cpy_k_'):
            try:
                short_id = data.split('_')[-1]
                from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys
                all_keys = await get_all_user_keys()
                k = next((uk for uk in all_keys if str(uk.id).endswith(short_id)), None)
                if k and k.access_url:
                    await call.message.answer(text=f"🔑 Ключ для копирования:\n{k.access_url}", parse_mode=None)
                else:
                    await call.message.answer(text="Ключ не найден.", parse_mode=None)
            except Exception:
                pass
            return
'):
            try:
                short_id = data.split('_')[-1]
                from core.keyboards.accept_del_button import accept_del_userkey_keyboard
                from core.utils.create_view import create_answer_from_html
                content = await create_answer_from_html(name_temp='ask_del_key', result='Подтверждаете удаление ключа?')
                await call.message.edit_text(text=content, reply_markup=accept_del_userkey_keyboard(shortудаление ключа?')
                await call.message.edit_text(text=content, reply_markup=accept_del_userkey_keyboard(key_id), parse_mode='HTML')
            except Exception:
                # fallback notify
                try:
                    await call.message.answer(text='Не удалось сформировать подтверждение удаления.', parse_mode=None)
                except Exception:
                    pass
            return
k_'):
            try:
                short_id = data.split('_')[-1]
                from core.sql.function_db_user_vpn.users_vpn import (
                    get_all_user_keys,
                    get_user_key_by_id,
                    delete_user_key_record,
                    get_user_keys,
                    set_key_to_table_users,
                    set_premium_status,
                    set_region_server,
                    set_date_to_table_users,
                )
                from core.api_s.outline.outline_api import OutlineManager

                # Найдем ключ по short_id
                all_keys = await get_all_user_keys()
                k = next((uk for uk in all_keys if str(uk.id).endswith(short_id)), None)
                if not k:
                    await call.message.answer(text='Ключ не найден.', parse_mode=None)
                    return

                # Удаляем на сервере Outline по outline_id
                olm = OutlineManager(region_server=k.region_server or 'nederland')
                try:
                    olm.delete_key_by_id(k.outline_id)
                except Exception:
                    # Игнорируем ошибки сервера, продолжаем чистить БД
                    pass

                # Удаляем запись из БД
                await delete_user_key_record(str(k.id))

                # Синхронизируем поле users_vpn.key и статусы
                remaining = await get_user_keys(account=k.account)
                if remaining:
                    # Если в users_vpn.key был удалённый ключ — заменим на любой оставшийся
                    try:
                        await set_key_to_table_users(account=k.account, value_key=remaining[0].access_url)
                    except Exception:
                        pass
                    # Перерисовываем список ключей
                    from core.handlers.handlers_keyboards.get_key_handler import my_key as my_key_view
                    text, reply_markup = await my_key_view(call, state)
                    parse_mode = 'HTML' if any(tag in text for tag in ('<a ', '<code>', '<b>', '<i>', '<pre>')) else None
                    await call.message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    # Ключей больше нет — сбрасываем флаги пользователя
                    await set_key_to_table_users(account=k.account, value_key=None)
                    await set_premium_status(account=k.account, value_premium=False)
                    await set_region_server(account=k.account, value_region=None)
                    await set_date_to_table_users(account=k.account, value_date=None)

                    from core.utils.create_view import create_answer_from_html
                    from core.keyboards.start_button import start_keyboard
                    content = await create_answer_from_html(name_temp='del_key', result='удален.')
                    await call.message.edit_text(text=content, reply_markup=start_keyboard(), parse_mode=None)
            except Exception:
                tb = traceback.format_exc()
                logger.log('error', f'del_k
                logger.log('error', f'del_userkey error for user {call.from_user.id}, data={call.data}: {tb}')
                try:
                    await call.message.answer(text='Ошибка при удалении ключа.', parse_mode=None)
                except Exception:
                    pass
            return

        text, reply_markup = await switch_menu(data, call, state)
        if text != call.message.text:
            # Choose parse_mode automatically when templates contain HTML tags
            parse_mode = 'HTML' if any(tag in text for tag in ('<a ', '<code>', '<b>', '<i>', '<pre>')) else None
            await call.message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
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
        if case_number.startswith('adm_blk_'):
            short_id = case_number.split('_')[-1]
            from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys
            from core.handlers.handlers_keyboards.admin_block_key_handler import perform_block_userkey
            # Найти ключ по короткому ID
            all_keys = await get_all_user_keys()
            k = next((uk for uk in all_keys if str(uk.id).endswith(short_id)), None)
            if k:
                text, keyboard = await perform_block_userkey(key_id=str(k.id), admin_id=call.from_user.id)
                return (text, keyboard)
            return ("Ключ не найден", InlineKeyboardBuilder().as_markup())
        
        # Обработка callback для проверки ключа пользователя (из activekeys)
        if case_number.startswith('chk_usr_'):
            user_id = int(case_number.split('_')[-1])
            # Вызываем логику keyinfo
            from core.handlers.key_info import get_key_info_response
            response_text, keyboard = await get_key_info_response(user_id)
            return (response_text, keyboard)
        
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
