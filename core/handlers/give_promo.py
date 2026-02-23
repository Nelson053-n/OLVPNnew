from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import traceback
import uuid

from core.api_s.outline.outline_api import OutlineManager
from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import (
    set_promo_status,
    set_key_to_table_users,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    get_promo_status,
    get_user_data_from_table_users,
    add_user_key,
    get_region_server,
    get_all_records_from_table_users,
    get_user_keys,
)
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def fmt(dt: datetime) -> str:
    return dt.strftime('%d.%m.%Y - %H:%M')


async def command_promo(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /promo.
    Показывает список всех пользователей БЕЗ платного активного ключа И БЕЗ промо ключа.
    Для каждого пользователя показывает кнопку "Промо" для выдачи промо-ключа на 7 дней.
    Добавлена кнопка для массовой выдачи со выбором сервера.
    
    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        # Получаем всех пользователей
        all_users = await get_all_records_from_table_users()
        if not all_users:
            await message.answer("❌ Нет пользователей в базе данных", parse_mode=None)
            return

        # Фильтруем пользователей: без платных активных ключей И без активных промо ключей
        now = datetime.now()
        users_without_paid_keys = []
        
        for user in all_users:
            user_keys = await get_user_keys(account=user.account)
            
            # Проверяем наличие активных ключей (платных и промо)
            has_paid_active_key = False
            has_promo_active_key = False
            
            for key in user_keys:
                # Проверяем что ключ активен (дата в будущем)
                if key.date and key.date > now:
                    if key.promo:  # Активный промо ключ
                        has_promo_active_key = True
                    else:  # Активный платный ключ
                        has_paid_active_key = True
            
            # Включаем в список только если нет активных платных И активных промо ключей
            if not has_paid_active_key and not has_promo_active_key:
                users_without_paid_keys.append(user)
        
        if not users_without_paid_keys:
            await message.answer("✅ Все пользователи уже имеют активные ключи (платные или промо)", parse_mode=None)
            return

        # Формируем список с кнопками
        lines = [
            f"<b>📋 Пользователи доступные для промо</b>",
            f"(без активных платных и без активных промо ключей)\n"
        ]
        kb = InlineKeyboardBuilder()
        
        for idx, user in enumerate(users_without_paid_keys, 1):
            uname = user.account_name or '—'
            lines.append(f"<b>{idx}.</b> <code>{user.account}</code> | <b>{uname}</b>")
            # Добавляем кнопку промо для каждого пользователя
            kb.button(text=f"🎁 {user.account}", callback_data=f"give_promo_{user.account}")
        
        lines.append(f"\n<b>Всего пользователей:</b> {len(users_without_paid_keys)}")
        lines.append("<b>Действие на 7 дней</b>\n")
        response_text = "\n".join(lines)
        
        # Добавляем кнопку для массовой раздачи
        kb.row()  # Новая строка
        kb.button(text="📢 Выдать ВСЕ", callback_data="mass_promo_select_server")
        
        # Настраиваем расположение обычных кнопок (по 3 в ряд)
        kb.adjust(3)
        
        # Отправляем сообщение с кнопками
        if len(response_text) > 4096:
            # Если текст слишком длинный, отправляем частями
            chunk_size = 20
            for i in range(0, len(users_without_paid_keys), chunk_size):
                chunk = users_without_paid_keys[i:i+chunk_size]
                chunk_lines = [
                    f"<b>📋 Пользователи без платных ключей</b>",
                    f"({i+1}-{min(i+chunk_size, len(users_without_paid_keys))} из {len(users_without_paid_keys)})\n"
                ]
                chunk_kb = InlineKeyboardBuilder()
                
                for idx, user in enumerate(chunk, i+1):
                    uname = user.account_name or '—'
                    chunk_lines.append(f"<b>{idx}.</b> <code>{user.account}</code> | <b>{uname}</b>")
                    chunk_kb.button(text=f"🎁 {user.account}", callback_data=f"give_promo_{user.account}")
                
                chunk_kb.adjust(3)
                if i + chunk_size >= len(users_without_paid_keys):  # Последний chunk
                    chunk_kb.row()
                    chunk_kb.button(text="📢 Выдать ВСЕ", callback_data="mass_promo_select_server")
                
                await message.answer("\n".join(chunk_lines), reply_markup=chunk_kb.as_markup())
        else:
            await message.answer(response_text, reply_markup=kb.as_markup())

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_promo error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /promo: {str(e)}", parse_mode=None)
        except Exception:
            pass


async def give_promo_to_user(callback: CallbackQuery, target_user_id: int) -> None:
    """
    Выдает промо-ключ пользователю на 14 дней.
    Вызывается при нажатии на кнопку промо.
    
    :param callback: CallbackQuery - объект callback запроса
    :param target_user_id: int - ID пользователя, которому выдается промо
    """
    try:
        from core.bot import bot
        
        # Check user exists
        user = await get_user_data_from_table_users(account=target_user_id)
        if not user:
            await callback.answer(f'❌ Пользователь {target_user_id} не найден в БД', show_alert=True)
            return

        # Determine region
        region = await get_region_server(account=target_user_id) or 'nederland'

        # Загружаем настройки промо из JSON
        import json
        from pathlib import Path
        settings_path = Path(__file__).parent.parent / 'settings_prices.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        promo_days = prices.get('promo', {}).get('days', 7)
        
        # Expiry date (промо период из настроек)
        expiry_date = datetime.now() + timedelta(days=promo_days)

        # Create key on Outline server (without key_id, let server generate it)
        # Use unique name for identification
        unique_name = f"{target_user_id}-promo-{uuid.uuid4().hex[:8]}"
        olm = OutlineManager(region_server=region)
        try:
            # Create key without key_id parameter - only with name
            key_data = olm._client.create_key(name=unique_name)
        except Exception as e:
            logger.log('error', f'Promo create_key error for {target_user_id}: {e}')
            await callback.answer(f'❌ Ошибка создания промо-ключа на сервере: {e}', show_alert=True)
            return

        if not key_data or not getattr(key_data, 'access_url', None):
            await callback.answer('❌ Ошибка создания промо-ключа на сервере', show_alert=True)
            return

        # Получаем сгенерированный сервером outline_id (конвертируем в строку)
        outline_id = str(key_data.key_id)

        # Update DB - add to UserKey table and update Users for compatibility
        await add_user_key(
            account=target_user_id,
            access_url=key_data.access_url,
            outline_id=outline_id,
            region_server=region,
            date_str=fmt(expiry_date),
            promo=True,
        )
        await set_premium_status(account=target_user_id, value_premium=True)
        await set_date_to_table_users(account=target_user_id, value_date=fmt(expiry_date))
        await set_region_server(account=target_user_id, value_region=region)
        await set_key_to_table_users(account=target_user_id, value_key=key_data.access_url)
        await set_promo_status(account=target_user_id, value_promo=True)

        # Отправляем уведомление пользователю
        try:
            notification_text = (
                f"🎁 <b>Тестовый доступ к демо-среде:</b>\n\n"
                f"Вам выдан тестовый доступ к выделенной сетевой среде на 7 дней.\n"
                f"Регион дата-центра: <b>{region}</b>\n"
                f"Действует до: <b>{fmt(expiry_date)}</b>\n\n"
                f"Используйте команду /start чтобы получить ключ доступа."
            )
            await bot.send_message(chat_id=target_user_id, text=notification_text)
        except Exception as notify_error:
            logger.log('warning', f'Failed to send promo notification to {target_user_id}: {notify_error}')

        # Уведомляем администратора об успешной выдаче
        await callback.answer(f'✅ Промо-доступ выдан пользователю {target_user_id}', show_alert=True)
        
        # Обновляем сообщение с кнопками, убирая выданный промо
        if callback.message:
            try:
                await callback.message.edit_text(
                    f"{callback.message.text}\n\n<b>✅ Промо выдан пользователю {target_user_id}</b>"
                )
            except Exception:
                pass

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'give_promo_to_user error for user {target_user_id}: {e}\n{tb}')
        try:
            await callback.answer(f"Ошибка при выдаче промо: {str(e)}", show_alert=True)
        except Exception:
            pass


async def mass_promo_select_server(callback: CallbackQuery) -> None:
    """
    Показывает список серверов для выбора при массовой раздаче промо.
    
    :param callback: CallbackQuery - объект callback запроса
    """
    try:
        from core.api_s.outline.outline_api import get_name_all_active_server_ol, get_server_display_name
        
        active_servers = get_name_all_active_server_ol()
        if not active_servers:
            await callback.answer("❌ Нет активных серверов", show_alert=True)
            return
        
        kb = InlineKeyboardBuilder()
        for server in active_servers:
            display_name = get_server_display_name(server)
            kb.button(text=display_name, callback_data=f"mass_promo_exec_{server}")
        
        kb.adjust(2)
        
        await callback.message.edit_text(
            "🌍 <b>Выберите сервер для массовой раздачи промо (7 дней):</b>",
            reply_markup=kb.as_markup()
        )
        
    except Exception as e:
        logger.log('error', f'mass_promo_select_server error: {e}')
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)


async def mass_promo_execute(callback: CallbackQuery, region_server: str) -> None:
    """
    Массовая выдача промо всем пользователям без платных активных ключей.
    
    :param callback: CallbackQuery - объект callback запроса
    :param region_server: str - выбранный регион сервера
    """
    try:
        from core.bot import bot
        import json
        from pathlib import Path
        
        # Получаем пользователей без платных активных ключей И без активных промо ключей
        all_users = await get_all_records_from_table_users()
        now = datetime.now()
        users_to_promo = []
        
        for user in all_users:
            user_keys = await get_user_keys(account=user.account)
            
            has_paid_active_key = False
            has_promo_active_key = False
            
            for key in user_keys:
                if key.date and key.date > now:
                    if key.promo:  # Активный промо ключ
                        has_promo_active_key = True
                    else:  # Активный платный ключ
                        has_paid_active_key = True
            
            # Включаем в список только если нет активных платных И активных промо ключей
            if not has_paid_active_key and not has_promo_active_key:
                users_to_promo.append(user)
        
        if not users_to_promo:
            await callback.answer("✅ Нет пользователей для выдачи промо", show_alert=True)
            return
        
        # Загружаем настройки промо
        settings_path = Path(__file__).parent.parent / 'settings_prices.json'
        with open(settings_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        promo_days = prices.get('promo', {}).get('days', 7)
        
        # Expiry date для всех ключей
        expiry_date = datetime.now() + timedelta(days=promo_days)
        
        # Инициализируем Outline Manager для выбранного сервера
        olm = OutlineManager(region_server=region_server)
        
        # Статистика выполнения
        success_count = 0
        error_count = 0
        errors_list = []
        
        # Отправляем статус
        status_msg = await callback.message.edit_text(
            f"⏳ <b>Выдача промо на {promo_days} дней...</b>\n"
            f"Всего пользователей: {len(users_to_promo)}\n"
            f"Сервер: <b>{region_server}</b>\n\n"
            f"Обработано: 0/{len(users_to_promo)}"
        )
        
        # Выдаём промо каждому пользователю
        for idx, user in enumerate(users_to_promo, 1):
            try:
                # Create key on Outline server
                unique_name = f"{user.account}-promo-{uuid.uuid4().hex[:8]}"
                
                key_data = olm._client.create_key(name=unique_name)
                
                if not key_data or not getattr(key_data, 'access_url', None):
                    error_count += 1
                    errors_list.append(f"User {user.account}: create_key returned None")
                    continue
                
                outline_id = str(key_data.key_id)
                
                # Update DB
                await add_user_key(
                    account=user.account,
                    access_url=key_data.access_url,
                    outline_id=outline_id,
                    region_server=region_server,
                    date_str=fmt(expiry_date),
                    promo=True,
                )
                await set_premium_status(account=user.account, value_premium=True)
                await set_date_to_table_users(account=user.account, value_date=fmt(expiry_date))
                await set_region_server(account=user.account, value_region=region_server)
                await set_key_to_table_users(account=user.account, value_key=key_data.access_url)
                await set_promo_status(account=user.account, value_promo=True)
                
                success_count += 1
                
                # Отправляем уведомление пользователю
                try:
                    notification_text = (
                        f"🎁 <b>Тестовый доступ:</b>\n\n"
                        f"Вам выдан тестовый доступ на <b>{promo_days} дней</b>.\n"
                        f"Регион: <b>{region_server}</b>\n"
                        f"Действует до: <b>{fmt(expiry_date)}</b>\n\n"
                        f"Используйте /start чтобы получить ключ доступа."
                    )
                    await bot.send_message(chat_id=user.account, text=notification_text)
                except Exception as notify_error:
                    logger.log('warning', f'Failed to send mass promo notification to {user.account}: {notify_error}')
                
            except Exception as e:
                error_count += 1
                errors_list.append(f"User {user.account}: {str(e)}")
                logger.log('error', f'Mass promo error for user {user.account}: {e}')
            
            # Обновляем статус каждые 5 пользователей
            if idx % 5 == 0 or idx == len(users_to_promo):
                try:
                    await status_msg.edit_text(
                        f"⏳ <b>Выдача промо на {promo_days} дней...</b>\n"
                        f"Сервер: <b>{region_server}</b>\n\n"
                        f"Обработано: {idx}/{len(users_to_promo)}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {error_count}"
                    )
                except Exception:
                    pass
        
        # Финальный отчёт
        report_text = (
            f"<b>✅ Массовая раздача промо завершена</b>\n\n"
            f"🎁 Количество дней: <b>{promo_days}</b>\n"
            f"🌍 Сервер: <b>{region_server}</b>\n"
            f"✅ Успешно выдано: <b>{success_count}/{len(users_to_promo)}</b>\n"
        )
        
        if error_count > 0:
            report_text += f"❌ Ошибок: <b>{error_count}</b>\n"
            if errors_list:
                report_text += f"\n<b>Детали ошибок:</b>\n"
                for err in errors_list[:10]:  # Показываем первые 10 ошибок
                    report_text += f"• {err}\n"
                if len(errors_list) > 10:
                    report_text += f"... и ещё {len(errors_list) - 10} ошибок"
        
        await status_msg.edit_text(report_text)
        logger.log('info', f'Mass promo executed: {success_count} success, {error_count} errors on server {region_server}')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'mass_promo_execute error: {e}\n{tb}')
        await callback.answer(f"Ошибка при массовой раздаче: {str(e)}", show_alert=True)





