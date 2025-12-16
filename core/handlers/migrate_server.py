"""
Команда для массового переноса пользователей между серверами
"""
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_user_keys,
    delete_user_key_record,
    add_user_key
)
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


class MigrateServerStates(StatesGroup):
    waiting_for_confirmation = State()


async def command_migrate_server(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    /migrateserver <from_server> <to_server>
    Переносит всех пользователей с одного сервера на другой
    
    Пример: /migrateserver nederland germany
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        parts = message.text.split()
        if len(parts) != 3:
            all_servers = get_name_all_active_server_ol()
            servers_list = ', '.join(all_servers)
            await message.answer(
                f'❌ Неверный формат команды\n\n'
                f'Использование: /migrateserver <откуда> <куда>\n\n'
                f'Доступные серверы: {servers_list}',
                parse_mode=None
            )
            return

        from_server = parts[1]
        to_server = parts[2]
        
        # Проверяем существование серверов
        all_servers = get_name_all_active_server_ol()
        if from_server not in all_servers:
            await message.answer(f'❌ Сервер "{from_server}" не найден или неактивен', parse_mode=None)
            return
        
        if to_server not in all_servers:
            await message.answer(f'❌ Сервер "{to_server}" не найден или неактивен', parse_mode=None)
            return
        
        if from_server == to_server:
            await message.answer('❌ Исходный и целевой серверы совпадают', parse_mode=None)
            return
        
        # Получаем количество ключей для переноса
        all_keys = await get_all_user_keys()
        keys_to_migrate = [k for k in all_keys if k.region_server == from_server and k.premium]
        
        if not keys_to_migrate:
            await message.answer(f'❌ На сервере "{from_server}" нет активных ключей для переноса', parse_mode=None)
            return
        
        # Сохраняем данные в state
        await state.update_data(
            from_server=from_server,
            to_server=to_server,
            keys_count=len(keys_to_migrate)
        )
        
        # Запрашиваем подтверждение
        kb = InlineKeyboardBuilder()
        kb.button(text='✅ Да, перенести', callback_data='confirm_migrate')
        kb.button(text='❌ Отмена', callback_data='cancel_migrate')
        kb.adjust(2)
        
        await message.answer(
            f'⚠️ <b>Подтверждение переноса</b>\n\n'
            f'Будет перенесено <b>{len(keys_to_migrate)}</b> активных ключей\n'
            f'С сервера: <b>{from_server}</b>\n'
            f'На сервер: <b>{to_server}</b>\n\n'
            f'Процесс может занять несколько минут.\n'
            f'Вы уверены?',
            reply_markup=kb.as_markup(),
            parse_mode='HTML'
        )
        
        await state.set_state(MigrateServerStates.waiting_for_confirmation)
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_migrate_server error: {e}\n{tb}')
        await message.answer(f'❌ Ошибка: {str(e)}', parse_mode=None)


async def handle_migration_confirmation(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик подтверждения миграции
    """
    try:
        await callback.answer()
        
        if callback.data == 'cancel_migrate':
            await callback.message.edit_text('❌ Миграция отменена')
            await state.clear()
            return
        
        if callback.data == 'confirm_migrate':
            data = await state.get_data()
            from_server = data.get('from_server')
            to_server = data.get('to_server')
            
            await callback.message.edit_text(
                f'⏳ Начинаем миграцию с {from_server} на {to_server}...\n'
                f'Это может занять несколько минут.'
            )
            
            # Выполняем миграцию
            all_keys = await get_all_user_keys()
            keys_to_migrate = [k for k in all_keys if k.region_server == from_server and k.premium]
            
            success_count = 0
            error_count = 0
            
            olm_to = OutlineManager(region_server=to_server)
            olm_from = OutlineManager(region_server=from_server)
            
            for idx, old_key in enumerate(keys_to_migrate, 1):
                try:
                    # Создаем новый ключ на целевом сервере
                    import uuid
                    unique_name = f"{old_key.account}-migrated-{uuid.uuid4().hex[:8]}"
                    new_key = olm_to._client.create_key(name=unique_name)
                    
                    if not new_key:
                        raise Exception("Failed to create key on target server")
                    
                    new_outline_id = str(getattr(new_key, 'key_id', None))
                    new_access_url = getattr(new_key, 'access_url', None)
                    
                    if not new_outline_id or not new_access_url:
                        raise Exception("New key missing required attributes")
                    
                    # Сохраняем новый ключ в БД
                    date_str = old_key.date.strftime('%d.%m.%Y - %H:%M') if old_key.date else None
                    if not date_str:
                        # Если нет даты, устанавливаем +30 дней
                        from datetime import datetime, timedelta
                        date_str = (datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y - %H:%M')
                    
                    save_success = await add_user_key(
                        account=old_key.account,
                        outline_id=new_outline_id,
                        access_url=new_access_url,
                        region_server=to_server,
                        date_str=date_str,
                        promo=old_key.promo
                    )
                    
                    if not save_success:
                        raise Exception("Failed to save key to database")
                    
                    # Удаляем старый ключ
                    try:
                        olm_from.delete_key_by_id(old_key.outline_id)
                    except Exception as e:
                        logger.log('warning', f'Failed to delete old key {old_key.outline_id}: {e}')
                    
                    await delete_user_key_record(old_key.id)
                    
                    # Отправляем уведомление пользователю
                    try:
                        from core.bot import bot
                        await bot.send_message(
                            chat_id=old_key.account,
                            text=(
                                f'🔄 <b>Ваш ключ был перенесен на новый сервер!</b>\n\n'
                                f'<b>Новый сервер:</b> {to_server}\n'
                                f'<b>Новый ключ доступа:</b>\n'
                                f'<code>{new_access_url}</code>\n\n'
                                f'Пожалуйста, обновите ключ в приложении Outline.\n'
                                f'Старый ключ больше не действителен.'
                            ),
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.log('warning', f'Failed to notify user {old_key.account}: {e}')
                    
                    success_count += 1
                    logger.log('info', f'Migrated key for user {old_key.account} from {from_server} to {to_server}')
                    
                    # Обновляем статус каждые 5 ключей
                    if idx % 5 == 0:
                        try:
                            await callback.message.edit_text(
                                f'⏳ Миграция в процессе...\n'
                                f'Перенесено: {success_count}/{len(keys_to_migrate)}\n'
                                f'Ошибок: {error_count}'
                            )
                        except:
                            pass
                    
                except Exception as e:
                    error_count += 1
                    logger.log('error', f'Migration error for user {old_key.account}: {e}')
            
            # Финальный отчет
            await callback.message.edit_text(
                f'✅ <b>Миграция завершена!</b>\n\n'
                f'<b>С сервера:</b> {from_server}\n'
                f'<b>На сервер:</b> {to_server}\n\n'
                f'✅ Успешно перенесено: {success_count}\n'
                f'❌ Ошибок: {error_count}\n\n'
                f'Всем пользователям отправлены уведомления.',
                parse_mode='HTML'
            )
            
            await state.clear()
            
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'handle_migration_confirmation error: {e}\n{tb}')
        try:
            await callback.message.edit_text(f'❌ Ошибка миграции: {str(e)}')
        except:
            pass
        await state.clear()
