from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
import json
from datetime import datetime

from core.keyboards.choise_region_button import choise_region_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from core.sql.function_db_user_vpn.users_vpn import get_user_data_from_table_users, get_region_server, get_user_keys, get_all_user_keys
from core.utils.build_pay import build_pay
from core.utils.create_view import create_answer_from_html
from core.utils.get_region_name import get_region_name_from_json


PRICES_FILE = 'core/settings_prices.json'


def load_prices() -> dict:
    """Загрузить цены из JSON файла"""
    try:
        with open(PRICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Значения по умолчанию если файл не найден
        return {
            "day": {"amount": 7, "days": 1, "word_days": "день"},
            "month": {"amount": 150, "days": 30, "word_days": "дней"},
            "year": {"amount": 1500, "days": 365, "word_days": "дней"}
        }


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
    prices = load_prices()
    day_config = prices.get('day', {"amount": 7, "days": 1, "word_days": "день"})
    
    amount = day_config['amount']
    day_count = day_config['days']
    word_days = day_config['word_days']
    
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
    prices = load_prices()
    month_config = prices.get('month', {"amount": 150, "days": 30, "word_days": "дней"})
    
    amount = month_config['amount']
    day_count = month_config['days']
    word_days = month_config['word_days']
    
    content, url_pay_keyboard = await build_pay(state, id_user, amount, day_count, word_days)
    return content, url_pay_keyboard


async def year_key(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для получения ключа на год.
    Отправка на страницу оплаты

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    id_user = call.from_user.id
    prices = load_prices()
    year_config = prices.get('year', {"amount": 1500, "days": 365, "word_days": "дней"})
    
    amount = year_config['amount']
    day_count = year_config['days']
    word_days = year_config['word_days']
    
    content, url_pay_keyboard = await build_pay(state, id_user, amount, day_count, word_days)
    return content, url_pay_keyboard


async def replace_key_choose_server(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Показать выбор сервера для замены ключа
    
    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    from core.api_s.outline.outline_api import get_name_all_active_server_ol, get_server_display_name
    
    # Извлекаем короткий ID ключа из callback_data
    short_id = call.data.replace('replace_choose_', '')
    
    # Находим ключ по короткому ID
    all_keys = await get_all_user_keys()
    target_key = None
    for k in all_keys:
        if str(k.id)[-8:] == short_id:
            target_key = k
            break
    
    if not target_key:
        return ("❌ Ключ не найден", InlineKeyboardBuilder().as_markup())
    
    # Получаем список всех активных серверов
    all_servers = get_name_all_active_server_ol()
    current_server = target_key.region_server
    
    # Строим клавиатуру с доступными серверами (кроме текущего)
    kb = InlineKeyboardBuilder()
    text_lines = [
        f"🔄 <b>Замена ключа</b>\n",
        f"<b>Текущий сервер:</b> {get_server_display_name(current_server)}\n",
        f"Выберите новый сервер:"
    ]
    
    for server in all_servers:
        if server != current_server:
            server_display = get_server_display_name(server)
            kb.row(InlineKeyboardButton(
                text=server_display,
                callback_data=f'replace_do_{short_id}_{server}'
            ))
    
    kb.row(InlineKeyboardButton(text='❌ Отмена', callback_data='my_key'))
    
    return ("\n".join(text_lines), kb.as_markup())


async def replace_key_execute(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Выполнить замену ключа на выбранном сервере
    
    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    import uuid
    from core.api_s.outline.outline_api import OutlineManager, get_server_display_name
    from core.sql.function_db_user_vpn.users_vpn import delete_user_key_record, add_user_key
    from logs.log_main import RotatingFileLogger
    
    logger = RotatingFileLogger()
    
    try:
        # Парсим данные: replace_do_{short_id}_{new_server}
        # Формат: replace_do_abcd1234_nederland или replace_do_abcd1234_nederland2
        callback_data = call.data
        # Убираем префикс "replace_do_"
        parts = callback_data.replace('replace_do_', '', 1).split('_', 1)
        short_id = parts[0]  # короткий ID ключа (8 символов)
        new_server = parts[1] if len(parts) > 1 else None  # новый сервер (может содержать _)
        
        if not new_server:
            return ("❌ Ошибка: не указан сервер", InlineKeyboardBuilder().as_markup())
        
        # Находим ключ по короткому ID
        all_keys = await get_all_user_keys()
        target_key = None
        for k in all_keys:
            if str(k.id)[-8:] == short_id:
                target_key = k
                break
        
        if not target_key:
            return ("❌ Ключ не найден", InlineKeyboardBuilder().as_markup())
        
        user_id = target_key.account
        old_server = target_key.region_server
        old_outline_id = target_key.outline_id
        old_date = target_key.date  # Сохраняем дату истечения
        
        # Создаем новый ключ на новом сервере
        olm_new = OutlineManager(new_server)
        unique_name = f"{user_id}-replaced-{uuid.uuid4().hex[:8]}"
        new_key = olm_new._client.create_key(name=unique_name)
        
        if not new_key:
            return ("❌ Не удалось создать новый ключ", InlineKeyboardBuilder().as_markup())
        
        # Получаем данные нового ключа
        new_outline_id = str(getattr(new_key, 'key_id', None))
        new_access_url = getattr(new_key, 'access_url', None)
        
        if not new_outline_id or not new_access_url:
            return ("❌ Ошибка при получении данных нового ключа", InlineKeyboardBuilder().as_markup())
        
        # Используем старую дату истечения
        date_str = old_date.strftime('%d.%m.%Y - %H:%M') if old_date else None
        
        # Сохраняем новый ключ в БД
        success = await add_user_key(
            account=user_id,
            outline_id=new_outline_id,
            access_url=new_access_url,
            region_server=new_server,
            date_str=date_str,
            promo=target_key.promo
        )
        
        if not success:
            return ("❌ Не удалось сохранить новый ключ в БД", InlineKeyboardBuilder().as_markup())
        
        # Удаляем старый ключ из Outline
        try:
            olm_old = OutlineManager(old_server)
            olm_old.delete_key_by_id(old_outline_id)
            logger.log('info', f'Deleted old key {old_outline_id} from server {old_server}')
        except Exception as e:
            logger.log('warning', f'Failed to delete old key from Outline: {e}')
        
        # Удаляем старый ключ из БД
        await delete_user_key_record(target_key.id)
        
        # Формируем ответ
        old_display = get_server_display_name(old_server)
        new_display = get_server_display_name(new_server)
        
        days_left = ""
        if old_date:
            delta = old_date - datetime.now()
            days = delta.days
            hours = delta.seconds // 3600
            if days > 0:
                days_left = f" ({days} дн.)"
            elif days == 0 and hours >= 0:
                days_left = f" ({hours} ч.)"
            else:
                days_left = " (истёк)"
        
        date_display = old_date.strftime('%d.%m.%Y - %H:%M') if old_date else '—'
        
        text = (
            f"✅ <b>Ключ успешно заменен!</b>\n\n"
            f"<b>Старый сервер:</b> {old_display}\n"
            f"<b>Новый сервер:</b> {new_display}\n\n"
            f"<b>Новый ключ:</b>\n"
            f"<code>{new_access_url}</code>\n\n"
            f"<b>Действителен до:</b> {date_display}{days_left}"
        )
        
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text='🔙 К моим ключам', callback_data='my_key'))
        
        logger.log('info', f'Replaced key for user {user_id}: {old_server} -> {new_server}')
        
        return (text, kb.as_markup())
        
    except Exception as e:
        logger.log('error', f'Error replacing key: {e}')
        import traceback
        traceback.print_exc()
        return (f"❌ Ошибка при замене ключа: {str(e)}", InlineKeyboardBuilder().as_markup())


async def my_key(call: CallbackQuery, state: FSMContext) -> (str, InlineKeyboardMarkup):
    """
    Обработчик для кнопки "Мой ключ".
    Получение ключа, если он есть

    :param call: CallbackQuery - Объект CallbackQuery.
    :param state: FSMContext - Объект FSMContext.
    :return: Текст ответа и клавиатура.
    """
    from core.api_s.outline.outline_api import get_server_display_name
    
    id_user = call.from_user.id
    name_temp = call.data
    # Получаем все ключи пользователя (поддержка нескольких ключей)
    keys = await get_user_keys(account=id_user)
    if keys:
        # Собираем HTML-ответ со списком ключей
        lines = ["<b>🔑 Ваши доступы:</b>\n"]
        kb = InlineKeyboardBuilder()
        for idx, k in enumerate(keys, 1):
            # Получаем отображаемое имя с флагом
            server_display = get_server_display_name(k.region_server or 'nederland')
            
            # Вычисляем количество дней до истечения
            days_left = ""
            if k.date:
                delta = k.date - datetime.now()
                days = delta.days
                hours = delta.seconds // 3600
                if days > 0:
                    days_left = f" ({days} дн.)"
                elif days == 0 and hours >= 0:
                    days_left = f" ({hours} ч.)"
                else:
                    days_left = " (истёк)"
            
            date_str = k.date.strftime('%d.%m.%Y - %H:%M') if k.date else '—'
            
            # Строка по каждому ключу
            lines.append(f"<b>{idx}.</b> {server_display}")
            lines.append(f"<b>Действителен до:</b> {date_str}{days_left}")
            lines.append(f"<a href=\"{k.access_url}\"><code>{k.access_url}</code></a>\n")
            
            # Кнопки по каждому ключу: копировать / удалить / заменить (используем короткие ID)
            short_id = str(k.id)[-8:]  # Последние 8 символов UUID
            kb.row(
                InlineKeyboardButton(text=f'📋 Копировать {idx}', callback_data=f'cpy_k_{short_id}'),
                InlineKeyboardButton(text=f'🗑️ Удалить {idx}', callback_data=f'ask_del_{short_id}')
            )
            kb.row(
                InlineKeyboardButton(text=f'🔄 Заменить {idx}', callback_data=f'replace_choose_{short_id}')
            )
        # Добавляем кнопку назад
        kb.row(InlineKeyboardButton(text='🔙 Назад', callback_data='back'))
        content = "\n".join(lines)
        return content, kb.as_markup()

    # Fallback для пользователей без ключей — предлагаем выбрать регион и купить
    content = 'У вас нет ключа, но вы можете его купить\nВыберите регион'
    return content, choise_region_keyboard()
