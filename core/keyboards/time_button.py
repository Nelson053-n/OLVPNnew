from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json


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
    
    # Кнопки в одну строку, текст центрирован с отступами
    buttons = [
        [
            InlineKeyboardButton(text=f'🪙\nДень\n{day_price}₽', callback_data='day'),
            InlineKeyboardButton(text=f'💵\nМесяц\n{month_price}₽', callback_data='month'),
            InlineKeyboardButton(text=f'💰\nГод\n{year_price}₽', callback_data='year')
        ],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='get_key')]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard