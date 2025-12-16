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
    Показывает список всех пользователей БЕЗ платного активного ключа.
    Для каждого пользователя показывает кнопку "Промо" для выдачи промо-ключа на 7 дней.
    
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

        # Фильтруем пользователей, у которых нет платных активных ключей
        now = datetime.now()
        users_without_paid_keys = []
        
        for user in all_users:
            user_keys = await get_user_keys(account=user.account)
            
            # Проверяем, есть ли у пользователя хотя бы один активный платный ключ
            has_paid_active_key = False
            for key in user_keys:
                # Ключ активен если дата в будущем
                if key.date and key.date > now:
                    # Ключ платный если promo = False
                    if not key.promo:
                        has_paid_active_key = True
                        break
            
            # Если нет платных активных ключей - добавляем в список
            if not has_paid_active_key:
                users_without_paid_keys.append(user)
        
        if not users_without_paid_keys:
            await message.answer("✅ Все пользователи уже имеют платные активные ключи", parse_mode=None)
            return

        # Формируем список с кнопками
        lines = ["<b>📋 Пользователи без платных ключей</b>\n"]
        kb = InlineKeyboardBuilder()
        
        for idx, user in enumerate(users_without_paid_keys, 1):
            uname = user.account_name or '—'
            lines.append(f"<b>{idx}.</b> <code>{user.account}</code> | <b>{uname}</b>")
            # Добавляем кнопку промо для каждого пользователя
            kb.button(text=f"🎁 Промо {user.account}", callback_data=f"give_promo_{user.account}")
        
        lines.append(f"\n<b>Всего пользователей:</b> {len(users_without_paid_keys)}")
        response_text = "\n".join(lines)
        
        # Настраиваем расположение кнопок (по 2 в ряд)
        kb.adjust(2)
        
        # Отправляем сообщение с кнопками
        if len(response_text) > 4096:
            # Если текст слишком длинный, отправляем частями
            chunk_size = 20
            for i in range(0, len(users_without_paid_keys), chunk_size):
                chunk = users_without_paid_keys[i:i+chunk_size]
                chunk_lines = [f"<b>📋 Пользователи без платных ключей ({i+1}-{min(i+chunk_size, len(users_without_paid_keys))} из {len(users_without_paid_keys)})</b>\n"]
                chunk_kb = InlineKeyboardBuilder()
                
                for idx, user in enumerate(chunk, i+1):
                    uname = user.account_name or '—'
                    chunk_lines.append(f"<b>{idx}.</b> <code>{user.account}</code> | <b>{uname}</b>")
                    chunk_kb.button(text=f"🎁 Промо {user.account}", callback_data=f"give_promo_{user.account}")
                
                chunk_kb.adjust(2)
                await message.answer("\n".join(chunk_lines), reply_markup=chunk_kb.as_markup())
        else:
            await message.answer(response_text, reply_markup=kb.as_markup())

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_promo error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /promo: {str(e)}", parse_mode=None)
        except:
            pass


async def give_promo_to_user(callback: CallbackQuery, target_user_id: int) -> None:
    """
    Выдает промо-ключ пользователю на 7 дней.
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

        # Получаем сгенерированный сервером outline_id
        outline_id = key_data.key_id

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
                f"🎁 <b>У вас появился промо-ключ!</b>\n\n"
                f"Вам выдан промо-доступ к VPN на 7 дней.\n"
                f"Регион: <b>{region}</b>\n"
                f"Действует до: <b>{fmt(expiry_date)}</b>\n\n"
                f"Используйте команду /start чтобы получить ключ доступа."
            )
            await bot.send_message(chat_id=target_user_id, text=notification_text)
        except Exception as notify_error:
            logger.log('warning', f'Failed to send promo notification to {target_user_id}: {notify_error}')

        # Уведомляем администратора об успешной выдаче
        await callback.answer(f'✅ Промо-ключ выдан пользователю {target_user_id}', show_alert=True)
        
        # Обновляем сообщение с кнопками, убирая выданный промо
        if callback.message:
            try:
                await callback.message.edit_text(
                    f"{callback.message.text}\n\n<b>✅ Промо выдан пользователю {target_user_id}</b>"
                )
            except:
                pass

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'give_promo_to_user error for user {target_user_id}: {e}\n{tb}')
        try:
            await callback.answer(f"Ошибка при выдаче промо: {str(e)}", show_alert=True)
        except:
            pass




