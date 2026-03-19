from aiogram.fsm.context import FSMContext
from aiogram.types import Message
import traceback
import uuid
from datetime import datetime, timedelta
import json
from pathlib import Path

from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol
from core.keyboards.start_button import start_keyboard
from core.sql.function_db_user_vpn.users_vpn import (
    add_user_to_db, 
    get_user_data_from_table_users,
    set_key_to_table_users, 
    get_region_server,
    add_user_key,
    set_premium_status,
    set_date_to_table_users,
    get_user_keys,
    get_promo_status,
    set_promo_status,
    get_all_user_keys,
)
from core.utils.create_view import create_answer_from_html
from logs.log_main import RotatingFileLogger
from core.settings import admin_tlg
from aiogram.enums import ParseMode

logger = RotatingFileLogger()


def fmt(dt: datetime) -> str:
    return dt.strftime('%d.%m.%Y - %H:%M')


async def command_start(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    Проверяет наличие пользователя в БД и в Outline менеджере.
    Автоматически генерирует промо-ключ при первом входе.
    Обрабатывает реферальные параметры (ref_USER_ID).

    :param state: FSMContext - Объект FSMContext.
    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        id_user = message.from_user.id
        name_servers = get_name_all_active_server_ol()
        
        # Проверяем наличие ключей на серверах
        check_key = None
        for region_server in name_servers:
            try:
                olm = OutlineManager(region_server=region_server)
                check_key = olm.get_key_from_ol(id_user=str(id_user))
                if check_key:
                    break
            except Exception as region_error:
                logger.log('warning', f'Error checking key in region {region_server}: {region_error}')
                continue
        
        check_user = await get_user_data_from_table_users(account=id_user)
        
        # Обрабатываем реферальный параметр
        referrer_id = None
        if message.text and message.text.startswith('/start'):
            # Параметр передаётся как /start ref_123456789
            parts = message.text.split()
            if len(parts) > 1:
                param = parts[1]
                if param.startswith('ref_'):
                    try:
                        ref_parts = param.split('_')
                        if len(ref_parts) == 2:
                            candidate = int(ref_parts[1])
                            if candidate > 0 and candidate != id_user:
                                # Проверяем, существует ли реферер в БД
                                referrer_user = await get_user_data_from_table_users(account=candidate)
                                if referrer_user:
                                    referrer_id = candidate
                                    logger.log('info', f'Referral parameter detected: user {id_user} referred by {referrer_id}')
                                else:
                                    logger.log('warning', f'Invalid referrer (not found): {candidate}')
                    except (ValueError, IndexError):
                        pass
        
        # Создаем пользователя если его нет
        if check_user is None:
            name_user = f"{message.from_user.first_name}_{message.from_user.last_name}"
            await add_user_to_db(account=message.from_user.id, account_name=name_user)
            if check_key is not None:
                await set_key_to_table_users(account=id_user, value_key=check_key.access_url)
            
            # Если пришёл реферальный параметр, добавляем связь в БД
            if referrer_id:
                try:
                    from core.sql.function_db_user_vpn.referrals import add_referral
                    referral_added = await add_referral(referrer_id=referrer_id, referred_id=id_user)
                    if referral_added:
                        logger.log('info', f'Added referral: {id_user} → {referrer_id}')
                        # выдать бонус рефереру сразу (не зависит от оплаты)
                        try:
                            from core.handlers.referral_handler import give_referral_bonus
                            bonus_ok = await give_referral_bonus(account=id_user, referrer_id=referrer_id)
                            if bonus_ok:
                                logger.log('info', f'Immediate referral bonus given to {referrer_id}')
                            else:
                                logger.log('warning', f'Unable to give immediate referral bonus for {id_user} → {referrer_id}')
                        except Exception as e2:
                            logger.log('warning', f'Failed to grant immediate referral bonus: {e2}')
                    else:
                        logger.log('warning', f'Referral already exists: {id_user} → {referrer_id}')
                except Exception as e:
                    logger.log('warning', f'Failed to add referral: {e}')
        
        # Проверяем, есть ли у пользователя ключи
        user_keys = await get_user_keys(account=id_user)
        promo_key = None
        
        # Проверяем был ли промо-ключ выдан ранее (из таблицы Users)
        had_promo_before = await get_promo_status(account=id_user)
        
        # Проверяем наличие платных ключей
        has_paid_keys = False
        if user_keys:
            for key in user_keys:
                if not key.promo:  # Если ключ платный
                    has_paid_keys = True
                    break
        
        # Генерируем промо если:
        # 1. Пришёл реферальный параметр И это НОВЫЙ пользователь И нет платных ключей (бонус за реферал)
        # 2. ИЛИ нет ключей, нет платных ключей и НИКОГДА не было промо-ключа
        if (referrer_id and check_user is None and not has_paid_keys) or (not user_keys and not has_paid_keys and not had_promo_before):
            promo_key = await generate_promo_key(id_user)
            # Устанавливаем флаг что промо был выдан
            await set_promo_status(account=id_user, value_promo=True)
            if referrer_id:
                logger.log('info', f'Generated promo key for user {id_user} (referee bonus from {referrer_id})')
        elif user_keys and not has_paid_keys and not referrer_id:
            # Если ключи есть и нет реферального параметра - находим активный промо-ключ для показа
            from datetime import datetime
            now = datetime.now()
            for key in user_keys:
                if key.promo and key.date and key.date > now:  # Промо активен
                    promo_key = key.access_url
                    break
        # Если есть платные ключи - promo_key остается None
        
        # Формируем ответ
        content = await create_answer_from_html(
            name_temp='/start',
            promo_key=promo_key if promo_key else None
        )
        
        # Отправляем с отключенным предпросмотром
        await message.answer(
            text=content, 
            reply_markup=start_keyboard(),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_start error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /start: {str(e)}")
        except Exception:
            pass


async def get_least_loaded_server() -> str:
    """
    Определяет наименее загруженный сервер по количеству ключей
    
    :return: Название региона с минимальной нагрузкой
    """
    try:
        # Получаем список всех активных серверов
        active_servers = get_name_all_active_server_ol()
        
        if not active_servers:
            return 'nederland'  # Fallback на дефолтный
        
        # Получаем все ключи из БД
        all_keys = await get_all_user_keys()
        
        # Подсчитываем количество ключей на каждом сервере
        server_load = {server: 0 for server in active_servers}
        
        if all_keys:
            for key in all_keys:
                if key.region_server and key.region_server in server_load:
                    server_load[key.region_server] += 1
        
        # Находим сервер с минимальной нагрузкой
        min_server = min(server_load.items(), key=lambda x: x[1])
        
        logger.log('info', f'Server load distribution: {server_load}')
        logger.log('info', f'Selected least loaded server: {min_server[0]} ({min_server[1]} keys)')
        
        return min_server[0]
        
    except Exception as e:
        logger.log('error', f'Error selecting least loaded server: {e}')
        return 'nederland'  # Fallback


async def generate_promo_key(user_id: int) -> str:
    """
    Генерирует промо-ключ для нового пользователя на наименее загруженном сервере
    
    :param user_id: ID пользователя
    :return: URL ключа доступа
    """
    try:
        # Выбираем наименее загруженный сервер
        region = await get_least_loaded_server()
        
        # Загружаем настройки промо
        settings_path = Path(__file__).parent.parent / 'settings_prices.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        promo_days = prices.get('promo', {}).get('days', 7)
        
        # Дата истечения
        expiry_date = datetime.now() + timedelta(days=promo_days)
        
        # Создаем ключ на Outline сервере
        unique_name = f"{user_id}-promo-{uuid.uuid4().hex[:8]}"
        olm = OutlineManager(region_server=region)
        key_data = olm._client.create_key(name=unique_name)
        
        if not key_data or not getattr(key_data, 'access_url', None):
            raise Exception("Ошибка создания ключа на сервере")
        
        outline_id = str(key_data.key_id)
        
        # Сохраняем в БД
        await add_user_key(
            account=user_id,
            access_url=key_data.access_url,
            outline_id=outline_id,
            region_server=region,
            date_str=fmt(expiry_date),
            promo=True,
        )
        await set_premium_status(account=user_id, value_premium=True)
        await set_date_to_table_users(account=user_id, value_date=fmt(expiry_date))
        
        logger.log('info', f'Auto-generated promo key for new user {user_id}')
        return key_data.access_url
        
    except Exception as e:
        logger.log('error', f'Failed to generate promo key for user {user_id}: {e}')
        return None
