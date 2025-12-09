from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from core.api_s.outline.outline_api import OutlineManager
from core.bot import bot
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_data_from_table_users,
    set_premium_status,
    get_region_server
)


async def admin_block_key_handler(call: CallbackQuery) -> tuple[str, InlineKeyboardMarkup]:
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
