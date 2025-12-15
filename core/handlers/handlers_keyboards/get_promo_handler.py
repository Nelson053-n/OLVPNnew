from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from datetime import datetime, timedelta

from core.keyboards.start_button import start_keyboard
from core.sql.function_db_user_vpn.users_vpn import (
    get_promo_status,
    set_promo_status,
    get_promo_issued_date,
    set_promo_issued_date,
    get_premium_status,
    get_key_from_table_users
)
from core.utils.create_view import create_answer_from_html
from core.utils.get_key_utils import get_future_date, get_ol_key_func
from core.utils.get_region_name import get_region_name_from_json


async def get_promo(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для получения промо-ключа.
    Предоставляет промо-ключ на 7 дней, можно получить раз в 30 дней.

    Логика:
    - Если у пользователя есть купленный ключ/активный premium, промо не предлагается.
    - Если последний промо был выдан меньше 30 дней назад, показывается дата следующей доступности.
    - Иначе выдается промо на 7 дней и фиксируется дата выдачи.

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    data = await state.get_data()
    id_user = call.from_user.id
    name_temp = call.data
    region_server = data.get('region_server', 'nederland')
    region_name = await get_region_name_from_json(region=region_server)

    # Если у пользователя уже есть купленный ключ или premium, не предлагаем промо
    premium = await get_premium_status(account=id_user)
    existing_key = await get_key_from_table_users(account=id_user)
    if premium or existing_key:
        content = "<b>У вас уже есть активный ключ. Промо недоступно.</b>"
        return content, start_keyboard()

    # Проверяем дату последнего промо
    last_issued = await get_promo_issued_date(account=id_user)
    now = datetime.now()
    if last_issued:
        next_available = last_issued + timedelta(days=30)
        if now < next_available:
            days_left = (next_available - now).days
            content = (
                f"<b>Промо-ключ уже выдан.</b>\n"
                f"Следующее доступно через: {days_left} дн. (с {next_available.strftime('%d.%m.%Y')})"
            )
            return content, start_keyboard()

    # Выдаём промо на 7 дней
    await set_promo_status(account=id_user, value_promo=True)
    await set_promo_issued_date(account=id_user, issued_date=now)
    add_day = 7
    untill_date = get_future_date(add_day=add_day)
    key_user = await get_ol_key_func(call=call, untill_date=untill_date, region_server=region_server)
    content = await create_answer_from_html(name_temp=name_temp, key_user=key_user.access_url,
                                            untill_date=untill_date, region_name=region_name)
    return content, start_keyboard()
