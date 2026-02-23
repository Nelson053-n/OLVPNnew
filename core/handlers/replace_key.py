"""
Обработчик замены ключа пользователя
"""
import traceback
import uuid
from datetime import datetime, timedelta
from aiogram.types import CallbackQuery

from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_keys, 
    get_all_user_keys,
    delete_user_key_record,
    add_user_key,
    get_user_data_from_table_users,
    set_premium_status,
    set_date_to_table_users
)
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def replace_key_handler(callback: CallbackQuery) -> None:
    """
    Обработчик замены ключа пользователя
    Удаляет старый ключ и создает новый на другом сервере
    """
    try:
        await callback.answer()
        
        # Проверка прав администратора
        if str(callback.from_user.id) != str(admin_tlg):
            await callback.message.answer('❌ У вас нет доступа к этой функции', parse_mode=None)
            return
        
        # Извлекаем короткий ID ключа
        short_id = callback.data.replace('rpl_key_', '')
        logger.log('info', f'Replace key request: short_id={short_id}, from admin={callback.from_user.id}')
        
        # Находим полный ключ по короткому ID
        all_keys = await get_all_user_keys()
        logger.log('info', f'Total keys in DB: {len(all_keys)}')
        target_key = None
        for key in all_keys:
            key_id_str = str(key.id)
            if key_id_str.endswith(short_id):
                target_key = key
                logger.log('info', f'Found target key: id={key.id}, user={key.account}, server={key.region_server}')
                break
        
        if not target_key:
            await callback.message.edit_text(
                '❌ Ключ не найден в базе данных',
                parse_mode=None,
                reply_markup=None
            )
            return
        
        user_id = target_key.account
        old_server = target_key.region_server
        old_outline_id = target_key.outline_id
        old_key_url = target_key.access_url
        
        # Проверяем существование пользователя в БД
        user_data = await get_user_data_from_table_users(account=user_id)
        if not user_data:
            await callback.message.edit_text(
                f'❌ Пользователь {user_id} не найден в базе данных',
                parse_mode=None,
                reply_markup=None
            )
            return
        
        old_display = get_server_display_name(old_server)
        
        await callback.message.edit_text(
            f'⏳ Замена ключа для пользователя {user_id}...\n'
            f'Старый сервер: {old_display}',
            parse_mode='HTML',
            reply_markup=None
        )
        
        # Получаем список всех активных серверов, кроме старого
        all_servers = get_name_all_active_server_ol()
        available_servers = [s for s in all_servers if s != old_server]
        
        if not available_servers:
            await callback.message.edit_text(
                '❌ Нет доступных серверов для замены ключа\n'
                '(все серверы либо неактивны, либо это единственный сервер)',
                parse_mode=None,
                reply_markup=None
            )
            return
        
        # Выбираем первый доступный сервер
        new_server = available_servers[0]
        
        # Создаем новый ключ на новом сервере
        try:
            olm_new = OutlineManager(new_server)
            # Используем уникальное имя вместо key_id (чтобы избежать PUT запроса)
            unique_name = f"{user_id}-replaced-{uuid.uuid4().hex[:8]}"
            new_key = olm_new._client.create_key(name=unique_name)
            
            if not new_key:
                raise Exception("Failed to create new key")
            
            # Получаем данные нового ключа (конвертируем в строку)
            new_outline_id = str(getattr(new_key, 'key_id', None))
            new_access_url = getattr(new_key, 'access_url', None)
            
            if not new_outline_id or not new_access_url:
                raise Exception("New key missing required attributes")
            
            # Вычисляем дату истечения (копируем с старого ключа или +30 дней)
            if target_key.date and target_key.date > datetime.now():
                expiry_date = target_key.date
            else:
                expiry_date = datetime.now() + timedelta(days=30)
            
            # ИСПРАВЛЕНО: Форматируем дату в нужный формат для add_user_key
            date_str = expiry_date.strftime('%d.%m.%Y - %H:%M')
            
            logger.log('info', f'Creating new key: user={user_id}, server={new_server}, expiry={date_str}')
            
            # Сохраняем новый ключ в БД
            success = await add_user_key(
                account=user_id,
                outline_id=new_outline_id,
                access_url=new_access_url,
                region_server=new_server,
                date_str=date_str,
                promo=False
            )
            
            if not success:
                raise Exception("Failed to save key to database")
            
            logger.log('info', f'Created new key for user {user_id} on server {new_server}, outline_id={new_outline_id}')
            
            # Обновляем статус premium и дату в основной таблице Users
            await set_premium_status(account=user_id, value_premium=True)
            await set_date_to_table_users(account=user_id, value_date=date_str)
            
        except Exception as e:
            logger.log('error', f'Failed to create new key: {e}')
            await callback.message.edit_text(
                f'❌ Ошибка при создании нового ключа: {str(e)}',
                parse_mode=None,
                reply_markup=None
            )
            return
        
        # Удаляем старый ключ из Outline
        try:
            olm_old = OutlineManager(old_server)
            olm_old.delete_key_by_id(old_outline_id)
            logger.log('info', f'Deleted old key {old_outline_id} from server {old_server}')
        except Exception as e:
            logger.log('warning', f'Failed to delete old key from Outline: {e}')
        
        # Удаляем старый ключ из БД
        try:
            await delete_user_key_record(target_key.id)
            logger.log('info', f'Deleted old key record from DB: {target_key.id}')
        except Exception as e:
            logger.log('error', f'Failed to delete old key from DB: {e}')
        
        # Отправляем уведомление администратору
        new_display = get_server_display_name(new_server)
        result_message = (
            f'✅ <b>Доступ успешно заменен!</b>\n\n'
            f'<b>Пользователь:</b> {user_id}\n'
            f'<b>Старый сервер:</b> {old_display}\n'
            f'<b>Новый сервер:</b> {new_display}\n\n'
            f'<b>Новый ключ:</b>\n'
            f'<code>{new_access_url}</code>\n\n'
            f'<b>Срок действия:</b> {expiry_date.strftime("%d.%m.%Y %H:%M")}'
        )
        
        await callback.message.edit_text(
            text=result_message,
            parse_mode='HTML',
            reply_markup=None
        )
        
        # Отправляем уведомление пользователю
        try:
            from core.bot import bot
            user_message = (
                f'🔄 <b>Ваш доступ был заменен!</b>\n\n'
                f'<b>Новый сервер:</b> {new_display}\n'
                f'<b>Новый ключ доступа:</b>\n'
                f'<code>{new_access_url}</code>\n\n'
                f'Скопируйте новый ключ и добавьте его в приложение Outline.\n'
                f'Старый ключ больше не действителен.\n\n'
                f'<b>Срок действия:</b> {expiry_date.strftime("%d.%m.%Y %H:%M")}'
            )
            await bot.send_message(
                chat_id=user_id,
                text=user_message,
                parse_mode='HTML'
            )
            logger.log('info', f'Sent replacement notification to user {user_id}')
        except Exception as e:
            logger.log('warning', f'Failed to send notification to user {user_id}: {e}')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'replace_key_handler error: {e}\n{tb}')
        try:
            await callback.message.answer(f'❌ Ошибка при замене ключа: {str(e)}', parse_mode=None)
        except Exception:
            pass
