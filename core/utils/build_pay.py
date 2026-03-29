import json
from pathlib import Path

from aiogram.types import InlineKeyboardMarkup

from core.api_s.api_youkassa.youkassa_api import create_payment
from core.keyboards.url_pay_button import url_pay_keyboard_build
from core.utils.create_view import create_answer_from_html
from logs.log_main import RotatingFileLogger

_logger = RotatingFileLogger()

PRICES_FILE = Path(__file__).resolve().parent.parent / 'settings_prices.json'


def _get_valid_amounts() -> set[int]:
    """Загружает допустимые суммы из settings_prices.json."""
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        return {v['amount'] for v in prices.values() if 'amount' in v}
    except Exception:
        return {7, 150, 1500}


async def build_pay(*args) -> (str, InlineKeyboardMarkup):
    """
    Запрос на создание платежа и запуск фонового polling проверки оплаты.

    :param args:
                state: Объект CallbackQuery
                id_user: id пользователя (для создания комментария к платежу)
                amount: цена
                day_count: кол-во дней
                word_days: правильное склонение слова "день"
    :return: Текст ответа и клавиатура.
    """
    state, id_user, amount, day_count, word_days = args

    # Валидация суммы по таблице цен
    valid_amounts = _get_valid_amounts()
    if not isinstance(amount, (int, float)) or amount <= 0 or int(amount) not in valid_amounts:
        _logger.log('warning', f'{id_user} - Invalid payment amount: {amount}')
        content = await create_answer_from_html(name_temp='error')
        from core.keyboards.start_button import start_keyboard
        return content, start_keyboard()

    data = await state.get_data()
    name_temp = 'day'
    current = "руб"
    payment_url, payment = data.get('pay', (None, None))
    region_server = data.get('region_server', 'back')
    new_payment = False
    if payment_url is None or payment is None or amount != int(payment.amount.value):
        payment_url, payment = await create_payment(amount_value=amount, count_day=day_count,
                                                    word_day=word_days, id_user=id_user)
        new_payment = True
    url_pay_keyboard = url_pay_keyboard_build(url_payment=payment_url, back_button=region_server)
    content = await create_answer_from_html(name_temp=name_temp, amount=amount, current=current,
                                            day_count=day_count, word_days=word_days)
    await state.update_data(pay=(payment_url, payment))
    await state.update_data(day_count=day_count)
    await state.update_data(word_days=word_days)
    await state.update_data(payment_amount=int(amount))

    # Запускаем фоновый polling проверки оплаты
    if new_payment and payment:
        from core.handlers.handlers_keyboards.after_pay_handler import start_payment_polling
        from core.bot import bot
        start_payment_polling(
            bot=bot,
            user_id=id_user,
            payment_id=payment.id,
            payment_date=payment.created_at,
            state_data={
                'region_server': region_server,
                'day_count': day_count,
                'word_days': word_days,
                'payment_amount': int(amount),
            },
        )

    return content, url_pay_keyboard
