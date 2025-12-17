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
        
        # Создаем пользователя если его нет
        if check_user is None:
            name_user = f"{message.from_user.first_name}_{message.from_user.last_name}"
            await add_user_to_db(account=message.from_user.id, account_name=name_user)
            if check_key is not None:
                await set_key_to_table_users(account=id_user, value_key=check_key.access_url)
        
        # Проверяем, есть ли у пользователя ключи
        user_keys = await get_user_keys(account=id_user)
        promo_key = None
        
        # Проверяем наличие платных ключей и истории промо-ключей
        has_paid_keys = False
        had_promo_before = False  # Был ли промо-ключ когда-либо
        
        if user_keys:
            for key in user_keys:
                if not key.promo:  # Если ключ платный
                    has_paid_keys = True
                if key.promo:  # Если когда-либо был промо
                    had_promo_before = True
        
        # Генерируем промо только если:
        # 1. Нет ключей вообще
        # 2. Нет платных ключей
        # 3. НИКОГДА не было промо-ключа (выдаем только один раз в истории)
        if not user_keys and not has_paid_keys and not had_promo_before:
            promo_key = await generate_promo_key(id_user)
        elif user_keys and not has_paid_keys and had_promo_before:
            # Если ключи есть и промо был раньше - находим активный промо-ключ для показа
            from datetime import datetime
            now = datetime.now()
            for key in user_keys:
                if key.promo and key.date and key.date > now:  # Промо активен
                    promo_key = key.access_url
                    break
        # Если есть платные ключи ИЛИ промо уже был выдан - promo_key остается None
        
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
        except:
            pass


async def generate_promo_key(user_id: int) -> str:
    """
    Генерирует промо-ключ для нового пользователя
    
    :param user_id: ID пользователя
    :return: URL ключа доступа
    """
    try:
        # Определяем регион
        region = await get_region_server(account=user_id) or 'nederland'
        
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
