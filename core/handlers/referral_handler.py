"""
Реферальная программа - выдача бонусов и управление рефералами
"""
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback
from datetime import datetime, timedelta
import json
from pathlib import Path

from core.sql.function_db_user_vpn.users_vpn import (
    get_user_data_from_table_users,
    add_user_key,
    set_premium_status,
    set_date_to_table_users,
    get_region_server,
)
from core.sql.function_db_user_vpn.referrals import (
    get_referral_bonus_status,
    get_user_referrals,
    get_referral_count_by_user,
    get_referral_counts_for_users,
    mark_referral_bonus_given,
)
from core.api_s.outline.outline_api import OutlineManager, get_server_display_name
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger
import uuid

logger = RotatingFileLogger()


def fmt(dt: datetime) -> str:
    return dt.strftime('%d.%m.%Y - %H:%M')


async def command_referral(message: Message) -> None:
    """
    Команда /referral - информация о реферальной программе и бонусах
    """
    try:
        account = message.from_user.id
        
        # Получаем информацию о рефералах
        referral_count = await get_referral_count_by_user(account)
        bonus_given_count = await get_referral_count_by_user(account, only_with_bonus=True)
        
        # Загружаем настройки промо дней
        settings_path = Path(__file__).parent.parent / 'settings_prices.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        referral_bonus_days = prices.get('promo', {}).get('days', 7)
        
        text = (
            f"<b>👥 Реферальная программа</b>\n\n"
            f"Приглашайте друзей и получайте <b>{referral_bonus_days} дней бесплатного доступа</b>!\n\n"
            f"<b>Ваша статистика:</b>\n"
            f"📊 Всего приглашено: <b>{referral_count}</b>\n"
            f"✅ Бонусов выдано: <b>{bonus_given_count}</b>\n\n"
            f"<b>Как это работает:</b>\n"
            f"1️⃣ Друг начинает использовать вас как реферала\n"
            f"2️⃣ При первой покупке они получают ваш реф-бонус\n"
            f"3️⃣ Вы получаете <b>{referral_bonus_days} дней</b> бесплатного доступа\n"
            f"4️⃣ Можно приглашать много друзей! 🎉\n\n"
            f"<b>Ваша реф-ссылка:</b>\n"
            f"Поделитесь своим ID: <code>{account}</code>\n\n"
            f"<i>Друг должен указать ваш ID при первой покупке</i>"
        )
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'command_referral error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении информации о рефералах", parse_mode=None)


async def show_referral_info(callback: CallbackQuery) -> None:
    """
    Показать информацию о реферальной программе в callback (из меню)
    Вызывается при нажатии кнопки в главном меню
    """
    try:
        account = callback.from_user.id
        
        # Получаем информацию о рефералах
        referral_count = await get_referral_count_by_user(account)
        bonus_given_count = await get_referral_count_by_user(account, only_with_bonus=True)
        
        # Загружаем настройки промо дней
        settings_path = Path(__file__).parent.parent / 'settings_prices.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        referral_bonus_days = prices.get('promo', {}).get('days', 7)
        
        # Генерируем реферальную ссылку
        # Используем параметр deep link: /start?ref=USER_ID
        from core.settings import main_bot_username
        referral_link = f"https://t.me/{main_bot_username}?start=ref_{account}"
        
        text = (
            f"<b>🎁 Реферальная программа</b>\n\n"
            f"Пригласите друзей и получайте <b>{referral_bonus_days} дней бесплатного доступа</b>!\n\n"
            f"<b>Ваша статистика:</b>\n"
            f"📊 Всего приглашено: <b>{referral_count}</b>\n"
            f"✅ Бонусов выдано: <b>{bonus_given_count}</b>\n\n"
            f"<b>Как это работает:</b>\n"
            f"1️⃣ Друг переходит по вашей ссылке\n"
            f"2️⃣ При первой покупке вы автоматически становитесь его рефером\n"
            f"3️⃣ Вы получаете <b>{referral_bonus_days} дней</b> бесплатного доступа!\n"
            f"4️⃣ Ваш друг тоже получает <b>{referral_bonus_days} дней</b> бесплатного доступа! 🎉\n"
            f"5️⃣ Повторяйте и получайте много бонусов! 💰\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"<i>Нажмите на ссылку выше, скопируйте её и отправьте друзьям!</i>"
        )
        
        # Создаём клавиатуру с кнопками
        kb = InlineKeyboardBuilder()
        kb.button(text='📋 Скопировать ссылку', callback_data=f'copy_ref_{account}')
        kb.button(text='🔙 Назад в меню', callback_data='back_start')
        kb.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.log('error', f'show_referral_info error: {e}\n{traceback.format_exc()}')
        await callback.answer("❌ Ошибка при загрузке информации", show_alert=True)


async def give_referral_bonus(account: int, referrer_id: int = None) -> bool:
    """
    Выдать реферальный бонус рефереру. Раньше вызывался после оплаты, теперь используется
    как резерв «если бонус ещё не был выдан». Функция гарантирует, что бонус выдаётся
    только один раз и не укоротит уже существующую подписку.
    
    :param account: ID приглашённого пользователя (реферала)
    :param referrer_id: ID реферера, можно передать явно
    :return: bool успешность (True если бонус выдан или уже был выдан)
    """
    try:
        from core.bot import bot
        # Получаем текущую запись реферала
        referral_info = None
        if not referrer_id:
            referral_info = await get_referral_bonus_status(account)
            if not referral_info:
                return False
            referrer_id = referral_info['referrer_id']
        else:
            referral_info = await get_referral_bonus_status(account)

        # если уже было выдано — ничего не делаем
        if referral_info and referral_info.get('bonus_given'):
            return False

        # Загружаем настройки и считаем дни бонуса
        settings_path = Path(__file__).parent.parent / 'settings_prices.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        bonus_days = prices.get('promo', {}).get('days', 7)

        # Выясняем текущую дату окончания у реферера, чтобы не укоротить
        old_expiry = None
        ref_user = await get_user_data_from_table_users(account=referrer_id)
        if ref_user and ref_user.date:
            old_expiry = ref_user.date  # Already a datetime object from SQLAlchemy Column(DateTime)

        # выдаём ключ (промо, бесплатный)
        region = await get_region_server(account=referrer_id) or 'nederland'
        promo_expiry = datetime.now() + timedelta(days=bonus_days)
        olm = OutlineManager(region_server=region)
        try:
            unique_name = f"{referrer_id}-ref-bonus-{uuid.uuid4().hex[:8]}"
            key_data = olm._client.create_key(name=unique_name)
        except Exception as e:
            logger.log('error', f'Failed to create referral bonus key: {e}')
            return False

        if not key_data or not getattr(key_data, 'access_url', None):
            logger.log('error', f'Failed to create referral bonus key: no key_data')
            return False

        outline_id = str(key_data.key_id)
        await add_user_key(
            account=referrer_id,
            access_url=key_data.access_url,
            outline_id=outline_id,
            region_server=region,
            date_str=fmt(promo_expiry),
            promo=True,
        )

        # обновляем дату пользователя, расширяя или устанавливая новую
        final_expiry = promo_expiry
        if old_expiry and old_expiry > datetime.now():
            final_expiry = old_expiry + timedelta(days=bonus_days)
        await set_premium_status(account=referrer_id, value_premium=True)
        await set_date_to_table_users(account=referrer_id, value_date=fmt(final_expiry))

        # Отмечаем что бонус выдан
        await mark_referral_bonus_given(account)

        # Отправляем уведомление рефереру
        try:
            notification = (
                f"🎉 <b>Реферальный бонус!</b>\n\n"
                f"Ваш друг (ID: {account}) зарегистрировался или оплатил подписку!\n"
                f"Вам выдан бонус: <b>{bonus_days} дней</b> бесплатного доступа 🎁\n"
                f"Действует до: <b>{fmt(final_expiry)}</b>\n\n"
                f"Используйте /start чтобы получить ключ доступа."
            )
            await bot.send_message(chat_id=referrer_id, text=notification)
        except Exception as e:
            logger.log('warning', f'Failed to send referral bonus notification: {e}')

        return True

    except Exception as e:
        logger.log('error', f'give_referral_bonus error: {e}\n{traceback.format_exc()}')
        return False


async def command_referrals_admin(message: Message) -> None:
    """
    Команда администратора для просмотра реферальной статистики
    """
    try:
        if not admin_tlg or message.from_user.id != admin_tlg:
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users
        
        all_users = await get_all_records_from_table_users()
        user_ids = [user.account for user in all_users]
        counts_map = await get_referral_counts_for_users(user_ids)
        
        top_referrers = []
        for user in all_users:
            count = counts_map.get(user.account, 0)
            if count > 0:
                top_referrers.append({
                    'account': user.account,
                    'name': user.account_name or f"User {user.account}",
                    'count': count
                })
        
        top_referrers.sort(key=lambda x: x['count'], reverse=True)
        
        text = "<b>📊 Статистика рефералов (администратор)</b>\n\n"
        
        if not top_referrers:
            text += "Рефералов не найдено"
        else:
            text += "<b>Топ рефереров:</b>\n"
            for idx, referrer in enumerate(top_referrers[:10], 1):
                text += f"{idx}. {referrer['name']} ({referrer['account']}) - {referrer['count']} человек\n"
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'command_referrals_admin error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении статистики", parse_mode=None)
