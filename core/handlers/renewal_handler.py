"""
Система автоматического продления и напоминаний о скором истечении
"""
from aiogram.types import Message
import traceback
from datetime import datetime
from pathlib import Path
import json

from core.sql.function_db_user_vpn.renewal_reminders import (
    create_renewal_reminder,
    get_unsent_reminders,
    mark_reminder_sent,
    get_user_reminders,
    cleanup_old_reminders,
)
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    get_user_keys,
    get_user_data_from_table_users,
)
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def fmt(dt: datetime) -> str:
    if not dt:
        return "Unknown"
    return dt.strftime('%d.%m.%Y - %H:%M')


async def setup_renewal_reminders() -> None:
    """
    Создаёт напоминания для всех пользователей с активными ключами
    Вызывается один раз при запуске бота или от администратора
    """
    try:
        all_users = await get_all_records_from_table_users()
        
        reminders_created = 0
        
        for user in all_users:
            keys = await get_user_keys(account=user.account)
            
            for key in keys:
                if not key.premium or not key.date:
                    continue
                
                # Вычисляем дни до истечения
                days_until_expiry = (key.date - datetime.now()).days
                
                # Создаём напоминания для 7, 3 и 1 дня
                for days_threshold in [7, 3, 1]:
                    if days_until_expiry <= days_threshold and days_until_expiry > days_threshold - 1:
                        created = await create_renewal_reminder(
                            account=user.account,
                            key_id=key.id,
                            days_until_expiry=days_threshold
                        )
                        if created:
                            reminders_created += 1
        
        logger.log('info', f'Setup renewal reminders: created {reminders_created} reminders')
        
    except Exception as e:
        logger.log('error', f'setup_renewal_reminders error: {e}\n{traceback.format_exc()}')


async def send_renewal_reminders(bot) -> int:
    """
    Отправляет все неотправленные напоминания пользователям
    Вызывается периодически из check_time_subscribe.py
    
    :param bot: Экземпляр бота для отправки сообщений
    :return: Количество sent напоминаний
    """
    try:
        reminders = await get_unsent_reminders()
        
        sent_count = 0
        failed_count = 0
        
        for reminder in reminders:
            try:
                # Получаем информацию о ключе и пользователе
                user = await get_user_data_from_table_users(account=reminder.account)
                if not user:
                    continue
                
                keys = await get_user_keys(account=reminder.account)
                key = next((k for k in keys if k.id == reminder.key_id), None)
                
                if not key:
                    continue
                
                # Составляем сообщение
                days = reminder.days_until_expiry
                
                if days == 7:
                    emoji = "🟡"
                    text = f"{emoji} <b>Напоминание: подписка истекает через неделю</b>\n\n"
                elif days == 3:
                    emoji = "🟠"
                    text = f"{emoji} <b>Внимание: подписка истекает через 3 дня</b>\n\n"
                elif days == 1:
                    emoji = "🔴"
                    text = f"{emoji} <b>СРОЧНО: подписка истекает завтра!</b>\n\n"
                else:
                    text = f"⚠️ <b>Подписка истекает через {days} дней</b>\n\n"
                
                text += (
                    f"Регион: <b>{key.region_server}</b>\n"
                    f"Действует до: <b>{fmt(key.date)}</b>\n\n"
                    f"💳 Чтобы продлить подписку, используйте команду /start"
                )
                
                # Отправляем сообщение
                await bot.send_message(chat_id=reminder.account, text=text)
                
                # Помечаем как отправленное
                await mark_reminder_sent(reminder.id)
                sent_count += 1
                
            except Exception as e:
                logger.log('warning', f'Failed to send reminder {reminder.id}: {e}')
                failed_count += 1
        
        logger.log('info', f'Sent {sent_count} renewal reminders (failed: {failed_count})')
        return sent_count
        
    except Exception as e:
        logger.log('error', f'send_renewal_reminders error: {e}\n{traceback.format_exc()}')
        return 0


async def command_renewal_stats(message: Message) -> None:
    """
    Команда /renewalstats - информация о напоминаниях о продлении
    """
    try:
        account = message.from_user.id
        
        reminders = await get_user_reminders(account=account)
        
        if not reminders:
            await message.answer(
                "✅ У вас нет активных напоминаний о продлении\n"
                "Все ваши подписки ещё действительны!",
                parse_mode=None
            )
            return
        
        text = f"<b>📋 Ваши напоминания о продлении ({len(reminders)})</b>\n\n"
        
        for reminder in reminders:
            days = reminder.days_until_expiry
            
            if days == 7:
                emoji = "🟡"
                status = "Напомню на неделю раньше"
            elif days == 3:
                emoji = "🟠"
                status = "Напомню за 3 дня"
            elif days == 1:
                emoji = "🔴"
                status = f"Критично! Последний день"
            else:
                emoji = "❓"
                status = f"Напомню через {days} дней"
            
            sent_status = "✅ Отправлено" if reminder.sent_at else "⏳ Ожидает отправки"
            
            text += (
                f"{emoji} <b>Ключ #{reminder.key_id}</b>\n"
                f"   {status}\n"
                f"   {sent_status}\n\n"
            )
        
        text += "Используйте /start для быстрого продления"
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'command_renewal_stats error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении информации", parse_mode=None)


async def admin_renewal_stats(message: Message) -> None:
    """
    Команда администратора для просмотра статистики напоминаний
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        from core.sql.base import RenewalReminder
        from core.sql.function_db_user_vpn.renewal_reminders import engine
        from sqlalchemy.orm import Session
        from sqlalchemy import func
        
        # Статистика по дням (всего)
        with Session(engine) as s:
            stats_total = s.query(
                RenewalReminder.days_until_expiry,
                func.count(RenewalReminder.id).label('count')
            ).group_by(RenewalReminder.days_until_expiry).all()

            # Статистика по дням (отправленные)
            stats_sent = s.query(
                RenewalReminder.days_until_expiry,
                func.count(RenewalReminder.id).label('sent')
            ).filter(
                RenewalReminder.sent_at.isnot(None)
            ).group_by(RenewalReminder.days_until_expiry).all()

        sent_map = {days: sent for days, sent in stats_sent}
        
        text = "<b>📊 Статистика напоминаний (администратор)</b>\n\n"
        
        if not stats_total:
            text += "Напоминаний не найдено"
        else:
            total = 0
            sent_total = 0
            
            for days, count in sorted(stats_total, key=lambda x: x[0]):
                emoji_map = {7: "🟡", 3: "🟠", 1: "🔴"}
                emoji = emoji_map.get(days, "❓")
                
                sent = sent_map.get(days, 0) or 0
                text += f"{emoji} За {days} дней: {count} (отправлено: {sent})\n"
                
                total += count
                sent_total += sent
        
            text += f"\n📈 Всего: {total} напоминаний\n"
            text += f"✅ Отправлено: {sent_total}\n"
            text += f"⏳ Ожидает: {total - sent_total}\n"
        
        # Очистка старых напоминаний
        cleaned = await cleanup_old_reminders(days_old=7)
        text += f"\n🗑️ Очищено старых напоминаний: {cleaned}"
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'admin_renewal_stats error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении статистики", parse_mode=None)


async def admin_trigger_renewal_reminders(message: Message) -> None:
    """
    Команда администратора для ручной отправки напоминаний (без ожидания расписания)
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        from core.bot import bot
        
        msg = await message.answer("📤 Отправляю напоминания...", parse_mode=None)
        
        sent = await send_renewal_reminders(bot)
        
        await msg.edit_text(
            f"✅ Напоминания отправлены\n\n"
            f"📤 Отправлено: {sent}"
        )
        
    except Exception as e:
        logger.log('error', f'admin_trigger_renewal_reminders error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при отправке напоминаний", parse_mode=None)
