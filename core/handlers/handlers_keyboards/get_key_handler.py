from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from core.keyboards.choise_region_button import choise_region_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from core.sql.function_db_user_vpn.users_vpn import get_user_data_from_table_users, get_region_server, get_user_keys
from core.utils.build_pay import build_pay
from core.utils.create_view import create_answer_from_html
from core.utils.get_region_name import get_region_name_from_json


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
    amount = 7
    day_count = 1
    word_days = "день"
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
    amount = 40
    day_count = 7
    word_days = "дней"
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
    amount = 150
    day_count = 30
    word_days = "дней"
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
    id_user = call.from_user.id
    name_temp = call.data
    # Получаем все ключи пользователя (поддержка нескольких ключей)
    keys = await get_user_keys(account=id_user)
    if keys:
        # Собираем HTML-ответ со списком ключей
        lines = ["<b>🔑 Ваши ключи:</b>"]
        kb = InlineKeyboardBuilder()
        for k in keys:
            # region name via json
            region_name = await get_region_name_from_json(region=k.region_server or 'nederland')
            date_str = k.date.strftime('%d.%m.%Y - %H:%M') if k.date else '—'
            # Строка по каждому ключу
            lines.append(f"\n<b>🌍 Регион:</b> {region_name}")
            lines.append(f"<b>⏳ Действителен до:</b> {date_str}")
            lines.append(f"<a href=\"{k.access_url}\"><code>{k.access_url}</code></a>")
            # Кнопки по каждому ключу: копировать / удалить (используем короткие ID)
            short_id = str(k.id)[-8:]  # Последние 8 символов UUID
            kb.row(
                InlineKeyboardButton(text='📋 Копировать', callback_data=f'cpy_k_{short_id}'),
                InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'ask_del_{short_id}')
            )
        # Добавляем кнопку назад
        kb.row(InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
        content = "\n".join(lines)
        return content, kb.as_markup()

    # Fallback для пользователей без ключей — предлагаем выбрать регион и купить
    content = 'У вас нет ключа, но вы можете его купить\nВыберите регион'
    return content, choise_region_keyboard()
