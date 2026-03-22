from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
from pathlib import Path

PRICES_FILE = Path(__file__).resolve().parent.parent / 'settings_prices.json'


async def time_keyboard(id_user: int) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для выбора срока подписки.
    Есть проверка - выдавался ли пользователю промо-ключ, если да
    убирает кнопку "Промо"

    :return: InlineKeyboardMarkup - Объект InlineKeyboardMarkup, содержащий клавиатуру.
    """
    # Загружаем цены
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            prices = json.load(f)
    except Exception:
        prices = {
            "day": {"amount": 7},
            "month": {"amount": 150},
            "year": {"amount": 1500}
        }
    
    day_price = prices.get('day', {}).get('amount', 7)
    month_price = prices.get('month', {}).get('amount', 150)
    year_price = prices.get('year', {}).get('amount', 1500)
    
    # Кнопки в одну строку, текст компактный без тире
    buttons = [
        [
            InlineKeyboardButton(text=f'🪙 День {day_price}₽', callback_data='day'),
            InlineKeyboardButton(text=f'Месяц {month_price}₽', callback_data='month'),
            InlineKeyboardButton(text=f'💰 Год {year_price}₽', callback_data='year')
        ],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='get_key')]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard