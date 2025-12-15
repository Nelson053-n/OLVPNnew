from aiogram.types import Message
from datetime import datetime

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users


async def command_active_keys(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /activekeys.
    Выводит список всех пользователей с активными ключами и датой окончания.
    Может отфильтровать по дате если указана опция.

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    if message.from_user.id != int(admin_tlg):
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    try:
        # Получаем всех пользователей из БД
        all_users = await get_all_records_from_table_users()
        
        # Фильтруем пользователей с активными ключами (premium=True)
        active_users = [user for user in all_users if user.premium and user.date]
        
        if not active_users:
            await message.answer("❌ Нет пользователей с активными ключами")
            return
        
        # Сортируем по дате окончания (ближайшие сначала)
        active_users.sort(key=lambda x: x.date)
        
        # Форматируем список
        response_lines = [
            "<b>📋 Список пользователей с активными ключами</b>\n"
        ]
        
        for idx, user in enumerate(active_users, 1):
            date_str = user.date.strftime("%d.%m.%Y %H:%M")
            remaining = user.date - datetime.now()
            days_remaining = remaining.days
            
            # Определяем эмодзи в зависимости от времени до окончания
            if days_remaining <= 1:
                emoji = "🔴"  # Завтра заканчивается
            elif days_remaining <= 3:
                emoji = "🟡"  # Скоро заканчивается
            else:
                emoji = "🟢"  # Ещё есть время
            
            response_lines.append(
                f"{emoji} <b>{idx}.</b> <code>{user.account}</code> | "
                f"<b>{user.account_name}</b>\n"
                f"   Регион: {user.region_server or 'не указан'} | "
                f"Окончание: {date_str}"
                f" ({days_remaining} дн.)\n"
            )
        
        response_lines.append(
            f"\n<b>Всего активных:</b> {len(active_users)}"
        )
        
        response_text = "\n".join(response_lines)
        
        # Если текст слишком длинный, отправляем частями
        if len(response_text) > 4096:
            # Отправляем по 10 пользователей за раз
            chunk_size = 10
            for i in range(0, len(active_users), chunk_size):
                chunk = active_users[i:i+chunk_size]
                chunk_lines = [
                    f"<b>📋 Список активных ключей ({i+1}-{min(i+chunk_size, len(active_users))} из {len(active_users)})</b>\n"
                ]
                
                for idx, user in enumerate(chunk, i+1):
                    date_str = user.date.strftime("%d.%m.%Y %H:%M")
                    remaining = user.date - datetime.now()
                    days_remaining = remaining.days
                    
                    if days_remaining <= 1:
                        emoji = "🔴"
                    elif days_remaining <= 3:
                        emoji = "🟡"
                    else:
                        emoji = "🟢"
                    
                    chunk_lines.append(
                        f"{emoji} <b>{idx}.</b> <code>{user.account}</code> | "
                        f"<b>{user.account_name}</b>\n"
                        f"   Регион: {user.region_server or 'не указан'} | "
                        f"Окончание: {date_str}"
                        f" ({days_remaining} дн.)\n"
                    )
                
                chunk_text = "\n".join(chunk_lines)
                await message.answer(text=chunk_text)
        else:
            await message.answer(text=response_text)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка: {str(e)}")
