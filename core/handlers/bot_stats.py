"""
Статистика и аналитика бота
"""
from aiogram.types import Message
import traceback
from datetime import datetime, timedelta

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    get_user_keys,
)
from core.sql.function_db_user_vpn.support_tickets import get_ticket_stats
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def command_stats(message: Message) -> None:
    """
    Команда администратора для просмотра статистики бота
    """
    try:
        if not admin_tlg or message.from_user.id != admin_tlg:
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        # Получаем всех пользователей
        all_users = await get_all_records_from_table_users()
        
        if not all_users:
            await message.answer("❌ Нет данных", parse_mode=None)
            return

        now = datetime.now()
        
        # Считаем статистику
        total_users = len(all_users)
        active_users = 0
        inactive_users = 0
        premium_users = 0
        promo_users = 0
        expiring_soon = []
        total_traffic = 0.0
        
        for user in all_users:
            user_keys = await get_user_keys(account=user.account)
            
            # Проверяем активные ключи
            has_active_key = False
            for key in user_keys:
                if key.date and key.date > now:
                    has_active_key = True
                    if not key.promo:
                        premium_users += 1
                    else:
                        promo_users += 1
                    
                    # Проверяем ключи заканчивающиеся в течение 3 дней
                    if key.date <= now + timedelta(days=3):
                        expiring_soon.append({
                            'account': user.account,
                            'days': (key.date - now).days
                        })
            
            if has_active_key:
                active_users += 1
            else:
                inactive_users += 1
        
        # Формируем ответ
        stats_text = (
            f"<b>📊 Статистика бота</b>\n\n"
            f"<b>Пользователи:</b>\n"
            f"👥 Всего: {total_users}\n"
            f"✅ Активных (с ключами): {active_users}\n"
            f"❌ Неактивных: {inactive_users}\n\n"
            f"<b>Ключи:</b>\n"
            f"💳 Платных: {premium_users}\n"
            f"🎁 Промо: {promo_users}\n\n"
            f"<b>⏰ Требуют внимания:</b>\n"
            f"🔴 Заканчиваются в течение 3 дней: {len(expiring_soon)}\n"
        )
        
        # Добавляем информацию о тикетах если есть
        try:
            ticket_stats = await get_ticket_stats()
            if ticket_stats:
                stats_text += (
                    f"\n<b>🎫 Тикеты поддержки:</b>\n"
                    f"📋 Всего: {ticket_stats.get('total', 0)}\n"
                    f"🔴 Открытых: {ticket_stats.get('open', 0)}\n"
                    f"🟡 В процессе: {ticket_stats.get('in_progress', 0)}\n"
                    f"✅ Решённых: {ticket_stats.get('resolved', 0)}\n"
                )
        except Exception:
            pass
        
        # Добавляем процент активности
        if total_users > 0:
            activity_percent = (active_users / total_users) * 100
            stats_text += (
                f"\n<b>📈 Метрики:</b>\n"
                f"Активность: <b>{activity_percent:.1f}%</b>\n"
            )
        
        await message.answer(stats_text)
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_stats error: {e}\n{tb}')
        await message.answer("❌ Ошибка при получении статистики", parse_mode=None)
