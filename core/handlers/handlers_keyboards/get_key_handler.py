from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
import json

from core.keyboards.choise_region_button import choise_region_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from core.sql.function_db_user_vpn.users_vpn import get_user_data_from_table_users, get_region_server, get_user_keys
from core.utils.build_pay import build_pay
from core.utils.create_view import create_answer_from_html
from core.utils.get_region_name import get_region_name_from_json


PRICES_FILE = 'core/settings_prices.json'


def load_prices() -> dict:
    """Загрузить цены из JSON файла"""
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Значения по умолчанию если файл не найден
        return {
            "day": {"amount": 7, "days": 1, "word_days": "день"},
            "week": {"amount": 40, "days": 7, "word_days": "дней"},
            "month": {"amount": 150, "days": 30, "word_days": "дней"}
        }


async def choise_region(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для получения ключа.
    Отправка на выбор продолжительности действия ключа

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    name_temp = call.data
    content = await create_answer_from_html(name_temp=name_temp)
    await state.update_data(pay=(None, None))
    return content, choise_region_keyboard()


async def day_key(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для получения ключа на день.
    Отправка на страницу оплаты

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    id_user = call.from_user.id
    prices = load_prices()
    day_config = prices.get('day', {"amount": 7, "days": 1, "word_days": "день"})
    
    amount = day_config['amount']
    day_count = day_config['days']
    word_days = day_config['word_days']
    
    content, url_pay_keyboard = await build_pay(state, id_user, amount, day_count, word_days)
    return content, url_pay_keyboard


async def week_key(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для получения ключа на неделю.
    Отправка на страницу оплаты

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    id_user = call.from_user.id
    prices = load_prices()
    week_config = prices.get('week', {"amount": 40, "days": 7, "word_days": "дней"})
    
    amount = week_config['amount']
    day_count = week_config['days']
    word_days = week_config['word_days']
    
    content, url_pay_keyboard = await build_pay(state, id_user, amount, day_count, word_days)
    return content, url_pay_keyboard


async def month_key(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для получения ключа на месяц.
    Отправка на страницу оплаты

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    id_user = call.from_user.id
    prices = load_prices()
    month_config = prices.get('month', {"amount": 150, "days": 30, "word_days": "дней"})
    
    amount = month_config['amount']
    day_count = month_config['days']
    word_days = month_config['word_days']
    
    content, url_pay_keyboard = await build_pay(state, id_user, amount, day_count, word_days)
    return content, url_pay_keyboard


async def my_key(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для кнопки "Мой ключ".
    Получение ключа, если он есть

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    from datetime import datetime
    from core.api_s.outline.outline_api import get_server_display_name
    
    id_user = call.from_user.id
    name_temp = call.data
    # Получаем все ключи пользователя (поддержка нескольких ключей)
    keys = await get_user_keys(account=id_user)
    if keys:
        # Собираем HTML-ответ со списком ключей
        lines = ["<b>🔑 Ваши ключи:</b>\n"]
        kb = InlineKeyboardBuilder()
        for idx, k in enumerate(keys, 1):
            # Получаем отображаемое имя с флагом
            server_display = get_server_display_name(k.region_server or 'nederland')
            
            # Вычисляем количество дней до истечения
            days_left = ""
            if k.date:
                delta = k.date - datetime.now()
                days = delta.days
                hours = delta.seconds // 3600
                if days > 0:
                    days_left = f" ({days} дн.)"
                elif days == 0 and hours >= 0:
                    days_left = f" ({hours} ч.)"
                else:
                    days_left = " (истёк)"
            
            date_str = k.date.strftime('%d.%m.%Y - %H:%M') if k.date else '—'
            
            # Строка по каждому ключу
            lines.append(f"<b>{idx}.</b> {server_display}")
            lines.append(f"⏳ <b>Действителен до:</b> {date_str}{days_left}")
            lines.append(f"<a href=\"{k.access_url}\"><code>{k.access_url}</code></a>\n")
            
            # Кнопки по каждому ключу: копировать / удалить (используем короткие ID)
            short_id = str(k.id)[-8:]  # Последние 8 символов UUID
            kb.row(
                InlineKeyboardButton(text=f'📋 Копировать {idx}', callback_data=f'cpy_k_{short_id}'),
                InlineKeyboardButton(text=f'🗑️ Удалить {idx}', callback_data=f'ask_del_{short_id}')
            )
        # Добавляем кнопку назад
        kb.row(InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
        content = "\n".join(lines)
        return content, kb.as_markup()

    # Fallback для пользователей без ключей — предлагаем выбрать регион и купить
    content = 'У вас нет ключа, но вы можете его купить\nВыберите регион'
    return content, choise_region_keyboard()
