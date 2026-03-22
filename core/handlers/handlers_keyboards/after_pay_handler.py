import asyncio
import uuid
import traceback

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from core.api_s.api_youkassa.youkassa_api import check_payment
from core.api_s.outline.outline_api import OutlineManager
from core.keyboards.start_button import start_keyboard
from core.keyboards.url_pay_button import url_pay_keyboard_build
from core.sql.function_db_user_payments.users_payments import add_payment_to_db, is_payment_exists
from core.sql.function_db_user_vpn.users_vpn import (
    set_key_to_table_users,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    add_user_key,
)
from core.utils.create_view import create_answer_from_html
from core.utils.get_key_utils import get_future_date, get_ol_key_func
from core.utils.get_region_name import get_region_name_from_json
from logs.log_main import RotatingFileLogger

# Use a dedicated payments logger here to avoid circular imports with main
logger_payments = RotatingFileLogger(config_file='logs/log_settings_payments.json')

# Хранилище активных polling-задач: {user_id: asyncio.Task}
_polling_tasks: dict[int, asyncio.Task] = {}

# Lock для атомарной проверки/обработки платежей (защита от двойной генерации ключа)
_payment_lock = asyncio.Lock()
# In-memory кэш обработанных платежей (быстрая проверка перед обращением к БД)
_processed_payments: set[str] = set()
_MAX_PROCESSED_CACHE = 5000  # Лимит кэша; при превышении сбрасываем (БД — основная защита)

POLL_INTERVAL = 12  # секунды между проверками
POLL_MAX_ATTEMPTS = 50  # 50 * 12с = 10 минут


def _mask_access_url(url: str) -> str:
    """Полностью маскирует VPN access_url для логирования."""
    if not url:
        return '[REDACTED]'
    return '[REDACTED_VPN_URL]'


async def _try_claim_payment(payment_id: str) -> bool:
    """
    Атомарно проверяет и помечает payment_id как обработанный.
    Использует asyncio.Lock + проверку в БД для защиты от дублей
    (в т.ч. после рестарта приложения).
    Возвращает True если платёж ещё не был обработан (можно генерировать ключ).
    """
    async with _payment_lock:
        # Быстрая проверка по in-memory кэшу
        if payment_id in _processed_payments:
            return False
        # Проверка в БД (переживает рестарт)
        if await is_payment_exists(payment_id):
            _processed_payments.add(payment_id)
            return False
        _processed_payments.add(payment_id)
        # Очистка кэша при переполнении (БД остаётся основной защитой)
        if len(_processed_payments) > _MAX_PROCESSED_CACHE:
            _processed_payments.clear()
            _processed_payments.add(payment_id)
        return True


async def after_pay(call: CallbackQuery, state: FSMContext) -> str:
    """
    Обработчик после успешной проверки оплаты.

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    name_temp = 'responce_key'
    data = await state.get_data()
    add_day = data.get('day_count', 0)
    word_days = data.get('word_days')
    region_server = data.get('region_server', 'back')
    region_name = await get_region_name_from_json(region=region_server)
    untill_date = get_future_date(add_day=add_day)
    key_user = await get_ol_key_func(call=call, region_server=region_server, untill_date=untill_date)
    content = await create_answer_from_html(name_temp=name_temp, key_user=key_user.access_url,
                                            day_count=add_day, word_days=word_days,
                                            untill_date=untill_date, region_name=region_name)
    logger_payments.log('info', f'\tRegion: {region_server}\n\tKey: {_mask_access_url(key_user.access_url)}')
    await state.update_data(pay=(None, None))
    return content


async def pay_check_key(call: CallbackQuery, state: FSMContext) -> tuple:
    """
    Обработчик проверки оплаты (ручная проверка).
    В случае удачи отправка на генерацию ответа с данными в after_pay
    и сохранение записи о покупке в БД.
    При успехе отменяет фоновую polling-задачу.

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    data = await state.get_data()
    payment_url, payment = data.get('pay', (None, None))
    region_server = data.get('region_server', 'back')
    id_user = call.from_user.id
    if payment_url and payment:
        result_pay = await check_payment(payment.id)
        if result_pay:
            # Отменяем фоновый polling — оплата подтверждена вручную
            cancel_payment_polling(id_user)

            # Защита от двойной генерации ключа
            if not await _try_claim_payment(payment.id):
                logger_payments.log('warning', f'{id_user} - Payment {payment.id} already processed (manual duplicate)')
                content = await create_answer_from_html(name_temp='error_pay')
                return content, start_keyboard()

            content = await after_pay(call, state)
            await add_payment_to_db(account=id_user, payment_key=payment.id, payment_date=payment.created_at)
            logger_payments.log('info', f'{id_user} - Successful payment\n\tPayment ID: {payment.id}\n\tDate & Time: {payment.created_at}')

            # backup: если бонус реферера ещё не был выдан, попробуем дать его сейчас
            try:
                from core.handlers.referral_handler import give_referral_bonus
                bonus_result = await give_referral_bonus(account=id_user)
                if bonus_result:
                    logger_payments.log('info', f'{id_user} triggered referral bonus on payment backup')
            except Exception as e:
                logger_payments.log('warning', f'Error running backup referral bonus for {id_user}: {e}')

            return content, start_keyboard()
        else:
            name_temp = 'error_pay'
            content = await create_answer_from_html(name_temp=name_temp)
            url_pay_keyboard = url_pay_keyboard_build(url_payment=payment_url, back_button=region_server)
            logger_payments.log('info', f'{id_user} - Payment not confirmed\n\tPayment ID: {(payment.id if payment else None)}')
            return content, url_pay_keyboard


def start_payment_polling(bot: Bot, user_id: int, payment_id: str, payment_date: str, state_data: dict) -> None:
    """
    Запускает фоновую задачу polling для проверки оплаты.
    Если для пользователя уже есть активная задача — отменяет предыдущую.

    :param bot: объект Bot для отправки сообщений
    :param user_id: ID пользователя Telegram
    :param payment_id: ID платежа в YooKassa
    :param payment_date: дата создания платежа
    :param state_data: данные из FSMContext (region_server, day_count, word_days)
    """
    cancel_payment_polling(user_id)
    task = asyncio.create_task(_poll_payment_status(bot, user_id, payment_id, payment_date, state_data))
    _polling_tasks[user_id] = task


def cancel_payment_polling(user_id: int) -> None:
    """Отменяет фоновую polling-задачу для пользователя, если она есть."""
    task = _polling_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()


async def _poll_payment_status(bot: Bot, user_id: int, payment_id: str, payment_date: str, state_data: dict) -> None:
    """
    Фоновый polling YooKassa каждые POLL_INTERVAL секунд, максимум POLL_MAX_ATTEMPTS попыток (10 минут).
    При успешной оплате — генерирует ключ и уведомляет пользователя.
    """
    region_server = state_data.get('region_server', 'nederland')
    day_count = state_data.get('day_count', 0)
    word_days = state_data.get('word_days', 'дней')

    for attempt in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            if await check_payment(payment_id):
                # Защита от двойной генерации ключа
                if not await _try_claim_payment(payment_id):
                    logger_payments.log('info', f'{user_id} - Payment {payment_id} already processed (polling skipped)')
                    _polling_tasks.pop(user_id, None)
                    return

                logger_payments.log('info', f'{user_id} - Payment auto-confirmed (attempt {attempt + 1})\n\tPayment ID: {payment_id}')

                # Генерируем ключ
                untill_date = get_future_date(add_day=day_count)
                olm = OutlineManager(region_server)
                unique_name = f"{user_id}-{uuid.uuid4().hex[:8]}"
                # Using _client directly because OutlineManager.create_key_from_ol() uses PUT with fixed ID
                key_user = olm._client.create_key(name=unique_name)
                outline_id = str(key_user.key_id)

                # Сохраняем в БД
                await set_premium_status(account=user_id, value_premium=True)
                await set_date_to_table_users(account=user_id, value_date=untill_date)
                await set_region_server(account=user_id, value_region=region_server)
                await add_user_key(
                    account=user_id,
                    access_url=key_user.access_url,
                    outline_id=outline_id,
                    region_server=region_server,
                    date_str=untill_date,
                    promo=False,
                )
                await set_key_to_table_users(account=user_id, value_key=key_user.access_url)

                # Записываем платёж
                await add_payment_to_db(account=user_id, payment_key=payment_id, payment_date=payment_date)

                # Реферальный бонус
                try:
                    from core.handlers.referral_handler import give_referral_bonus
                    await give_referral_bonus(account=user_id)
                except Exception as e:
                    logger_payments.log('warning', f'Referral bonus error for {user_id}: {e}')

                # Формируем сообщение пользователю
                region_name = await get_region_name_from_json(region=region_server)
                content = await create_answer_from_html(
                    name_temp='responce_key',
                    key_user=key_user.access_url,
                    day_count=day_count,
                    word_days=word_days,
                    untill_date=untill_date,
                    region_name=region_name,
                )

                await bot.send_message(chat_id=user_id, text=content, parse_mode='HTML')
                logger_payments.log('info', f'{user_id} - Key auto-generated\n\tRegion: {region_server}\n\tKey: {_mask_access_url(key_user.access_url)}')

                _polling_tasks.pop(user_id, None)
                return

        except asyncio.CancelledError:
            logger_payments.log('info', f'{user_id} - Payment polling cancelled')
            return
        except Exception as e:
            logger_payments.log('warning', f'{user_id} - Payment poll error (attempt {attempt + 1}): {e}')
            continue

    # Таймаут — 10 минут прошло, оплата не подтверждена
    logger_payments.log('info', f'{user_id} - Payment polling timed out\n\tPayment ID: {payment_id}')
    _polling_tasks.pop(user_id, None)
