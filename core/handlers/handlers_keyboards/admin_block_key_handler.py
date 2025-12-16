from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from core.api_s.outline.outline_api import OutlineManager
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_data_from_table_users,
    set_premium_status,
    get_region_server,
    set_key_to_table_users,
    set_date_to_table_users,
    set_region_server,
)
from core.sql.function_db_user_vpn.users_vpn import add_block_record
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def perform_block_user(user_id: int, admin_id: int = None, reason: str = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Выполняет логику блокировки (удаление на сервере + обновление БД + запись истории)
    """
    try:
        user_record = await get_user_data_from_table_users(account=user_id)
        if not user_record:
            return "❌ Пользователь не найден в БД", InlineKeyboardBuilder().as_markup()
        if not user_record.key:
            return "❌ У пользователя нет активного ключа", InlineKeyboardBuilder().as_markup()

        region_server = user_record.region_server or "nederland"
        olm = OutlineManager(region_server=region_server)
        delete_result = olm.delete_key_from_ol(id_user=str(user_id))

        # Update DB regardless of server result
        await set_premium_status(account=user_id, value_premium=False)
        await set_region_server(account=user_id, value_region=None)
        await set_date_to_table_users(account=user_id, value_date=None)
        await set_key_to_table_users(account=user_id, value_key=None)

        # Record history
        try:
            await add_block_record(account=user_id, admin_id=admin_id or 0, reason=reason, key=user_record.key)
        except Exception:
            logger.log('warning', f'Failed to write block history for {user_id}')

        # Notify user (append reason if provided)
        notification_text = 'Действие вашего ключа завершено\nВы можете купить новый,\nчто бы продолжить пользоваться сервисом'
        if reason:
            notification_text += f"\n\nПричина: {reason}"
        try:
            from core.bot import bot
            await bot.send_message(chat_id=user_id, text=notification_text)
        except Exception:
            pass

        return f"✅ Ключ пользователя {user_id} успешно заблокирован\n<b>Telegram:</b> {user_record.account_name}", InlineKeyboardBuilder().as_markup()
    except Exception as e:
        logger.log('error', f'perform_block_user error: {e}')
        return f"❌ Ошибка при блокировке ключа: {str(e)}", InlineKeyboardBuilder().as_markup()


async def perform_block_userkey(key_id: str, admin_id: int = None, reason: str = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Блокировка (удаление) конкретного ключа пользователя по записи UserKey.id
    - Удаляет ключ на Outline по outline_id
    - Удаляет запись из UserKey
    - Обновляет Users.* поля: если остались ключи — сохраняет премиум, иначе сбрасывает и уведомляет
    - Пишет историю блокировок
    """
    try:
        from core.sql.function_db_user_vpn.users_vpn import (
            get_user_key_by_id,
            delete_user_key_record,
            get_user_keys,
            set_key_to_table_users,
            set_premium_status,
            set_region_server,
            set_date_to_table_users,
        )

        k = await get_user_key_by_id(key_id)
        if not k:
            return "❌ Ключ не найден", InlineKeyboardBuilder().as_markup()

        # Удаляем на сервере Outline по outline_id
        try:
            olm = OutlineManager(region_server=k.region_server or 'nederland')
            olm.delete_key_by_id(k.outline_id)
        except Exception:
            pass

        # История блокировок
        try:
            await add_block_record(account=k.account, admin_id=admin_id or 0, reason=reason, key=k.access_url)
        except Exception:
            pass

        # Удаляем запись о ключе
        await delete_user_key_record(key_id)

        remaining = await get_user_keys(account=k.account)
        if remaining:
            # Обновить Users.key на один из оставшихся, сохраняем premium
            try:
                await set_key_to_table_users(account=k.account, value_key=remaining[0].access_url)
            except Exception:
                pass
            return "✅ Ключ заблокирован (остались другие ключи)", InlineKeyboardBuilder().as_markup()
        else:
            # Сбросить статусы и уведомить пользователя
            await set_key_to_table_users(account=k.account, value_key=None)
            await set_premium_status(account=k.account, value_premium=False)
            await set_region_server(account=k.account, value_region=None)
            await set_date_to_table_users(account=k.account, value_date=None)

            notification_text = 'Действие вашего ключа завершено\nВы можете купить новый,\nчто бы продолжить пользоваться сервисом'
            if reason:
                notification_text += f"\n\nПричина: {reason}"
            try:
                from core.bot import bot
                await bot.send_message(chat_id=k.account, text=notification_text)
            except Exception:
                pass
            return "✅ Ключ заблокирован", InlineKeyboardBuilder().as_markup()
    except Exception as e:
        logger.log('error', f'perform_block_userkey error: {e}')
        return f"❌ Ошибка при блокировке ключа: {str(e)}", InlineKeyboardBuilder().as_markup()


async def admin_block_key_handler(call: CallbackQuery) -> tuple[str, InlineKeyboardMarkup]:
    """
    Обработчик callback'а для немедленной блокировки (callback_data: admin_block_key_<id>)
    """
    user_id = int(call.data.split('_')[-1])
    return await perform_block_user(user_id=user_id, admin_id=call.from_user.id)
    """
    Обработчик для блокировки ключа администратором
    Удаляет ключ из Outline и выставляет premium статус на False
    Отправляет уведомление пользователю об окончании подписки

    :param call: CallbackQuery - объект callback запроса
    :return: tuple[str, InlineKeyboardMarkup] - текст ответа и клавиатура
    """
    # Извлекаем user_id из callback_data (формат: admin_block_key_<user_id>)
    user_id = int(call.data.split('_')[-1])
    
    try:
        # Получаем данные пользователя
        user_record = await get_user_data_from_table_users(account=user_id)
        
        if not user_record:
            return "❌ Пользователь не найден в БД", InlineKeyboardBuilder().as_markup()
        
        if not user_record.key:
            return "❌ У пользователя нет активного ключа", InlineKeyboardBuilder().as_markup()
        
        # Получаем регион сервера
        region_server = user_record.region_server or "nederland"
        
        # Удаляем ключ из Outline
        olm = OutlineManager(region_server=region_server)
        delete_result = olm.delete_key_from_ol(id_user=str(user_id))
        
        if delete_result:
            # Выставляем premium статус на False
            await set_premium_status(account=user_id, value_premium=False)
            
            # Отправляем уведомление пользователю
            notification_text = 'Действие вашего ключа завершено\nВы можете купить новый,\nчто бы продолжить пользоваться сервисом'
            try:
                from core.bot import bot
                await bot.send_message(chat_id=user_id, text=notification_text)
            except Exception as e:
                # Если не удалось отправить сообщение, продолжаем
                pass
            
            text = f"✅ Ключ пользователя {user_id} успешно заблокирован\n<b>Telegram:</b> {user_record.account_name}"
        else:
            text = f"⚠️ Ошибка при удалении ключа из Outline для пользователя {user_id}"
        
        return text, InlineKeyboardBuilder().as_markup()
        
    except Exception as e:
        return f"❌ Ошибка при блокировке ключа: {str(e)}", InlineKeyboardBuilder().as_markup()
