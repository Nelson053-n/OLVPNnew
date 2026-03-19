"""
Обработчик команды /stats - статистика бота
"""
from aiogram.types import Message
from datetime import datetime, timedelta
import traceback

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users, get_all_user_keys
from core.sql.function_db_user_payments.users_payments import get_all_user_payments
from core.api_s.outline.outline_api import get_server_display_name
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def command_stats(message: Message) -> None:
    """
    Команда администратора для просмотра статистики бота
    """
    try:
        # Проверка прав администратора
        if not admin_tlg or message.from_user.id != admin_tlg:
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        # Получаем данные из БД
        all_users = await get_all_records_from_table_users()
        all_keys = await get_all_user_keys()
        all_payments = await get_all_user_payments()
        
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # === ПОЛЬЗОВАТЕЛИ ===
        total_users = len(all_users) if all_users else 0
        
        # Новые пользователи (по created_at если есть, иначе примерная оценка)
        new_today = 0
        new_week = 0
        new_month = 0
        
        # === КЛЮЧИ ===
        total_keys = len(all_keys) if all_keys else 0
        active_keys = 0
        expired_keys = 0
        paid_keys = 0
        promo_keys_total = 0
        promo_keys_active = 0
        
        # Распределение по серверам (только активные ключи)
        server_distribution = {}
        
        if all_keys:
            for key in all_keys:
                # Проверяем активность
                is_active = key.date and key.date > now
                
                if is_active:
                    active_keys += 1
                else:
                    expired_keys += 1
                
                # Тип ключа
                if key.promo:
                    promo_keys_total += 1
                    if is_active:
                        promo_keys_active += 1
                else:
                    paid_keys += 1
                
                # Распределение по серверам - ТОЛЬКО АКТИВНЫЕ КЛЮЧИ
                if is_active:
                    server = key.region_server or 'unknown'
                    # Используем отображаемое имя с флагом
                    server_display = get_server_display_name(server) if server != 'unknown' else 'unknown'
                    server_distribution[server_display] = server_distribution.get(server_display, 0) + 1
                
                # Новые ключи
                if key.created_at:
                    if key.created_at >= today_start:
                        new_today += 1
                    if key.created_at >= week_ago:
                        new_week += 1
                    if key.created_at >= month_ago:
                        new_month += 1
        
        # === ПЛАТЕЖИ ===
        total_payments = len(all_payments) if all_payments else 0
        payments_today = 0
        payments_week = 0
        payments_month = 0
        
        if all_payments:
            for payment in all_payments:
                if payment.time_added:
                    if payment.time_added >= today_start:
                        payments_today += 1
                    if payment.time_added >= week_ago:
                        payments_week += 1
                    if payment.time_added >= month_ago:
                        payments_month += 1
        
        # === АКТИВНОСТЬ ===
        premium_users = sum(1 for u in all_users if u.premium) if all_users else 0
        
        # Формируем сообщение
        stats_text = (
            f"📊 <b>Статистика бота</b>\n"
            f"<i>Обновлено: {now.strftime('%d.%m.%Y %H:%M')}</i>\n\n"
            
            f"👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
            f"• Всего зарегистрировано: <b>{total_users}</b>\n"
            f"• С активной подпиской: <b>{premium_users}</b>\n\n"
            
            f"🔑 <b>КЛЮЧИ</b>\n"
            f"• Всего ключей: <b>{total_keys}</b>\n"
            f"• Активных: <b>{active_keys}</b> 🟢\n"
            f"• Истекших: <b>{expired_keys}</b> 🔴\n"
            f"• Платных: <b>{paid_keys}</b> 💰\n"
            f"• Промо (всего): <b>{promo_keys_total}</b> 🎁\n"
            f"• Промо (активных): <b>{promo_keys_active}</b>\n\n"
            
            f"📈 <b>НОВЫЕ КЛЮЧИ</b>\n"
            f"• За сегодня: <b>{new_today}</b>\n"
            f"• За неделю: <b>{new_week}</b>\n"
            f"• За месяц: <b>{new_month}</b>\n\n"
            
            f"💳 <b>ПЛАТЕЖИ</b>\n"
            f"• Всего: <b>{total_payments}</b>\n"
            f"• За сегодня: <b>{payments_today}</b>\n"
            f"• За неделю: <b>{payments_week}</b>\n"
            f"• За месяц: <b>{payments_month}</b>\n\n"
        )
        
        # Добавляем распределение по серверам (только активные)
        if server_distribution:
            stats_text += f"🌍 <b>РАСПРЕДЕЛЕНИЕ ПО СЕРВЕРАМ</b>\n"
            stats_text += f"<i>(только активные ключи)</i>\n"
            # Сортируем по количеству ключей (по убыванию)
            sorted_servers = sorted(server_distribution.items(), key=lambda x: x[1], reverse=True)
            for server_display, count in sorted_servers:
                # Процент от активных ключей, а не от всех
                percentage = (count / active_keys * 100) if active_keys > 0 else 0
                stats_text += f"• {server_display}: <b>{count}</b> ({percentage:.1f}%)\n"
        
        await message.answer(stats_text, parse_mode='HTML')
        logger.log('info', f'Stats viewed by admin {message.from_user.id}')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_stats error: {e}\n{tb}')
        await message.answer('❌ Ошибка при получении статистики', parse_mode=None)
