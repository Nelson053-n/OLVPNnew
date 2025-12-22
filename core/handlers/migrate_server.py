"""
Команда для массового переноса пользователей между серверами
"""
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_user_keys,
    delete_user_key_record,
    add_user_key
)
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


class MigrateServerStates(StatesGroup):
    waiting_for_source_server = State()
    waiting_for_target_server = State()


async def command_migrate_server(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    /migrateserver
    Переносит всех пользователей с одного сервера на другой через кнопки выбора
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        # Получаем список активных серверов
        all_servers = get_name_all_active_server_ol()
        
        if len(all_servers) < 2:
            await message.answer(
                '❌ Недостаточно серверов для миграции\n'
                'Требуется минимум 2 активных сервера',
                parse_mode=None
            )
            return
        
        # Создаем кнопки для выбора исходного сервера
        kb = InlineKeyboardBuilder()
        for server in all_servers:
            server_display = get_server_display_name(server)
            kb.button(text=server_display, callback_data=f"migrate_from_{server}")
        kb.adjust(2)  # 2 кнопки в ряд
        kb.row(InlineKeyboardBuilder().button(text='❌ Отмена', callback_data='cancel_migrate').as_markup().inline_keyboard[0][0])
        
        await message.answer(
            '<b>🔄 Миграция пользователей между серверами</b>\n\n'
            '<b>Шаг 1 из 2:</b> Выберите сервер, <u>откуда</u> переносить пользователей:',
            reply_markup=kb.as_markup(),
            parse_mode='HTML'
        )
        
        await state.set_state(MigrateServerStates.waiting_for_source_server)
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_migrate_server error: {e}\n{tb}')
        await message.answer(f'❌ Ошибка: {str(e)}', parse_mode=None)


async def select_source_server(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора исходного сервера
    """
    try:
        await callback.answer()
        
        from_server = callback.data.replace('migrate_from_', '')
        
        # Сохраняем выбранный сервер
        await state.update_data(from_server=from_server)
        
        # Получаем количество ключей на этом сервере
        all_keys = await get_all_user_keys()
        keys_count = len([k for k in all_keys if k.region_server == from_server and k.premium])
        
        if keys_count == 0:
            await callback.message.edit_text(
                f'❌ На сервере "{get_server_display_name(from_server)}" нет активных ключей для переноса',
                parse_mode='HTML'
            )
            await state.clear()
            return
        
        # Создаем кнопки для выбора целевого сервера (исключая исходный)
        all_servers = get_name_all_active_server_ol()
        available_servers = [s for s in all_servers if s != from_server]
        
        kb = InlineKeyboardBuilder()
        for server in available_servers:
            server_display = get_server_display_name(server)
            kb.button(text=server_display, callback_data=f"migrate_to_{server}")
        kb.adjust(2)  # 2 кнопки в ряд
        kb.row(InlineKeyboardBuilder().button(text='❌ Отмена', callback_data='cancel_migrate').as_markup().inline_keyboard[0][0])
        
        await callback.message.edit_text(
            f'<b>🔄 Миграция пользователей</b>\n\n'
            f'<b>Выбран исходный сервер:</b> {get_server_display_name(from_server)}\n'
            f'<b>Количество ключей:</b> {keys_count}\n\n'
            f'<b>Шаг 2 из 2:</b> Выберите сервер, <u>куда</u> переносить пользователей:',
            reply_markup=kb.as_markup(),
            parse_mode='HTML'
        )
        
        await state.set_state(MigrateServerStates.waiting_for_target_server)
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'select_source_server error: {e}\n{tb}')
        await callback.message.answer(f'❌ Ошибка: {str(e)}', parse_mode=None)
        await state.clear()


async def select_target_server(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора целевого сервера и подтверждения миграции
    """
    try:
        await callback.answer()
        
        to_server = callback.data.replace('migrate_to_', '')
        data = await state.get_data()
        from_server = data.get('from_server')
        
        # Получаем количество ключей для миграции
        all_keys = await get_all_user_keys()
        keys_to_migrate = [k for k in all_keys if k.region_server == from_server and k.premium]
        
        # Сохраняем данные
        await state.update_data(to_server=to_server, keys_count=len(keys_to_migrate))
        
        # Запрашиваем подтверждение
        kb = InlineKeyboardBuilder()
        kb.button(text='✅ Да, перенести', callback_data='confirm_migrate')
        kb.button(text='❌ Отмена', callback_data='cancel_migrate')
        kb.adjust(2)
        
        await callback.message.edit_text(
            f'⚠️ <b>Подтверждение переноса</b>\n\n'
            f'<b>С сервера:</b> {get_server_display_name(from_server)}\n'
            f'<b>На сервер:</b> {get_server_display_name(to_server)}\n'
            f'<b>Будет перенесено:</b> {len(keys_to_migrate)} активных ключей\n\n'
            f'⚠️ Процесс может занять несколько минут.\n'
            f'Всем пользователям будут отправлены уведомления.\n\n'
            f'<b>Вы уверены?</b>',
            reply_markup=kb.as_markup(),
            parse_mode='HTML'
        )
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'select_target_server error: {e}\n{tb}')
        await callback.message.answer(f'❌ Ошибка: {str(e)}', parse_mode=None)
        await state.clear()


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
            
            from_display = get_server_display_name(from_server)
            to_display = get_server_display_name(to_server)
            
            await callback.message.edit_text(
                f'⏳ Начинаем миграцию...\n'
                f'С {from_display} → {to_display}\n\n'
                f'Это может занять несколько минут.',
                parse_mode='HTML'
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
                                f'🔄 <b>Ваш VPN-ключ был автоматически перенесен на новый сервер!</b>\n\n'
                                f'<b>Старый сервер:</b> {from_display}\n'
                                f'<b>Новый сервер:</b> {to_display}\n\n'
                                f'<b>🔑 Ваш новый ключ доступа:</b>\n'
                                f'<code>{new_access_url}</code>\n\n'
                                f'<b>📱 Что нужно сделать:</b>\n'
                                f'1️⃣ Скопируйте новый ключ выше\n'
                                f'2️⃣ Откройте приложение Outline\n'
                                f'3️⃣ Добавьте новый ключ\n'
                                f'4️⃣ Удалите старый ключ\n\n'
                                f'⚠️ <i>Старый ключ больше не работает!</i>\n\n'
                                f'❓ Если возникли проблемы, обратитесь в поддержку.'
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
                                f'С {from_display} → {to_display}\n\n'
                                f'Перенесено: {success_count}/{len(keys_to_migrate)}\n'
                                f'Ошибок: {error_count}',
                                parse_mode='HTML'
                            )
                        except:
                            pass
                    
                except Exception as e:
                    error_count += 1
                    logger.log('error', f'Migration error for user {old_key.account}: {e}')
            
            # Финальный отчет
            await callback.message.edit_text(
                f'✅ <b>Миграция завершена!</b>\n\n'
                f'<b>С сервера:</b> {from_display}\n'
                f'<b>На сервер:</b> {to_display}\n\n'
                f'✅ Успешно перенесено: {success_count}\n'
                f'❌ Ошибок: {error_count}\n\n'
                f'📧 Всем пользователям отправлены уведомления с инструкциями.',
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
