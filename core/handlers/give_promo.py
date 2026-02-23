from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import traceback

from core.services.key_service import key_service
from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    get_user_keys,
)
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


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
    Выдает промо-ключ пользователю.
    Вызывается при нажатии на кнопку промо.

    :param callback: CallbackQuery - объект callback запроса
    :param target_user_id: int - ID пользователя, которому выдается промо
    """
    try:
        from core.bot import bot

        result = await key_service.create_promo_key(user_id=target_user_id)

        if not result['success']:
            await callback.answer(f"❌ {result['error']}", show_alert=True)
            return

        # Отправляем уведомление пользователю
        try:
            notification_text = (
                f"🎁 <b>Тестовый доступ к демо-среде:</b>\n\n"
                f"Вам выдан тестовый доступ к выделенной сетевой среде на {result['days']} дней.\n"
                f"Регион дата-центра: <b>{result['server_display']}</b>\n"
                f"Действует до: <b>{result['expiry_date']}</b>\n\n"
                f"Используйте команду /start чтобы получить ключ доступа."
            )
            await bot.send_message(chat_id=target_user_id, text=notification_text)
        except Exception as notify_error:
            logger.log('warning', f'Failed to send promo notification to {target_user_id}: {notify_error}')

        await callback.answer(f'✅ Промо-доступ выдан пользователю {target_user_id}', show_alert=True)

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

        all_users = await get_all_records_from_table_users()
        now = datetime.now()
        users_to_promo = []

        for user in all_users:
            user_keys = await get_user_keys(account=user.account)
            has_paid_active_key = any(k.date and k.date > now and not k.promo for k in user_keys)
            has_promo_active_key = any(k.date and k.date > now and k.promo for k in user_keys)
            if not has_paid_active_key and not has_promo_active_key:
                users_to_promo.append(user)

        if not users_to_promo:
            await callback.answer("✅ Нет пользователей для выдачи промо", show_alert=True)
            return

        success_count = 0
        error_count = 0
        errors_list = []

        status_msg = await callback.message.edit_text(
            f"⏳ <b>Выдача промо...</b>\n"
            f"Всего пользователей: {len(users_to_promo)}\n"
            f"Сервер: <b>{region_server}</b>\n\n"
            f"Обработано: 0/{len(users_to_promo)}"
        )

        for idx, user in enumerate(users_to_promo, 1):
            try:
                result = await key_service.create_promo_key(
                    user_id=user.account,
                    server=region_server,
                )
                if result['success']:
                    success_count += 1
                    try:
                        notification_text = (
                            f"🎁 <b>Тестовый доступ:</b>\n\n"
                            f"Вам выдан тестовый доступ на <b>{result['days']} дней</b>.\n"
                            f"Регион: <b>{result['server_display']}</b>\n"
                            f"Действует до: <b>{result['expiry_date']}</b>\n\n"
                            f"Используйте /start чтобы получить ключ доступа."
                        )
                        await bot.send_message(chat_id=user.account, text=notification_text)
                    except Exception as notify_error:
                        logger.log('warning', f'Failed to send mass promo notification to {user.account}: {notify_error}')
                else:
                    error_count += 1
                    errors_list.append(f"User {user.account}: {result['error']}")
            except Exception as e:
                error_count += 1
                errors_list.append(f"User {user.account}: {str(e)}")
                logger.log('error', f'Mass promo error for user {user.account}: {e}')

            if idx % 5 == 0 or idx == len(users_to_promo):
                try:
                    await status_msg.edit_text(
                        f"⏳ <b>Выдача промо...</b>\n"
                        f"Сервер: <b>{region_server}</b>\n\n"
                        f"Обработано: {idx}/{len(users_to_promo)}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {error_count}"
                    )
                except Exception:
                    pass

        report_text = (
            f"<b>✅ Массовая раздача промо завершена</b>\n\n"
            f"🌍 Сервер: <b>{region_server}</b>\n"
            f"✅ Успешно выдано: <b>{success_count}/{len(users_to_promo)}</b>\n"
        )
        if error_count > 0:
            report_text += f"❌ Ошибок: <b>{error_count}</b>\n"
            if errors_list:
                report_text += f"\n<b>Детали ошибок:</b>\n"
                for err in errors_list[:10]:
                    report_text += f"• {err}\n"
                if len(errors_list) > 10:
                    report_text += f"... и ещё {len(errors_list) - 10} ошибок"

        await status_msg.edit_text(report_text)
        logger.log('info', f'Mass promo executed: {success_count} success, {error_count} errors on server {region_server}')

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'mass_promo_execute error: {e}\n{tb}')
        await callback.answer(f"Ошибка при массовой раздаче: {str(e)}", show_alert=True)





