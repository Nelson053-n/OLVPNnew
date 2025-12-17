from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json

from core.sql.function_db_user_vpn.users_vpn import get_promo_status


async def time_keyboard(id_user: int) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для выбора срока подписки.
    Есть проверка - выдавался ли пользователю промо-ключ, если да
    убирает кнопку "Промо"

    :return: InlineKeyboardMarkup - Объект InlineKeyboardMarkup, содержащий клавиатуру.
    """
    # Загружаем цены
    try:
        with open('core/settings_prices.json', 'r', encoding='utf-8') as f:
            prices = json.load(f)
    except:
        prices = {
            "day": {"amount": 7},
            "month": {"amount": 150},
            "year": {"amount": 1500}
        }
    
    day_price = prices.get('day', {}).get('amount', 7)
    month_price = prices.get('month', {}).get('amount', 150)
    year_price = prices.get('year', {}).get('amount', 1500)
    
    first_row = [
        InlineKeyboardButton(text=f'🪙 День - {day_price}₽', callback_data='day'),
        InlineKeyboardButton(text=f'💵 Месяц - {month_price}₽', callback_data='month'),
        InlineKeyboardButton(text=f'💰 Год - {year_price}₽', callback_data='year')
    ]
    second_row = [
        InlineKeyboardButton(text='🎁 Промо', callback_data='promo'),
        InlineKeyboardButton(text='🔙 Назад', callback_data='get_key')
    ]

    promo_status = await get_promo_status(account=id_user)
    if promo_status:
        second_row.pop(0)
    buttons = [
        first_row,
        second_row
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard