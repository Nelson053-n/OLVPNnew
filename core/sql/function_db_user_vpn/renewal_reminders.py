"""
Функции работы с напоминаниями об окончании подписки и продлением
"""
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import uuid

from core.sql.base import Base, RenewalReminder

DATABASE_URL = 'sqlite:///olvpnbot.db'
engine = create_engine(DATABASE_URL, echo=False)
Base.metadata.create_all(engine)


async def create_renewal_reminder(account: int, key_id: str, days_until_expiry: int) -> bool:
    """
    Создать напоминание о продлении подписки
    
    :param account: ID пользователя
    :param key_id: ID ключа
    :param days_until_expiry: Дни до истечения (7, 3 или 1)
    :return: bool
    """
    with Session(engine) as session:
        try:
            # Проверить что такое напоминание не создано
            existing = session.query(RenewalReminder).filter(
                RenewalReminder.account == account,
                RenewalReminder.key_id == key_id,
                RenewalReminder.days_until_expiry == days_until_expiry,
                RenewalReminder.sent == False
            ).first()
            
            if existing:
                return True  # Напоминание уже существует
            
            reminder = RenewalReminder(
                id=f"reminder_{account}_{key_id}_{days_until_expiry}d_{uuid.uuid4().hex[:8]}",
                account=account,
                key_id=key_id,
                days_until_expiry=days_until_expiry,
                sent=False
            )
            session.add(reminder)
            session.commit()
            return True
        except Exception as e:
            print(f"ERROR create_renewal_reminder: {e}")
            return False


async def get_unsent_reminders(days_filter: int = None) -> list[dict]:
    """
    Получить непосланные напоминания (для фонового процесса)
    
    :param days_filter: Фильтр по дням (опционально)
    :return: list с напоминаниями
    """
    with Session(engine) as session:
        try:
            query = session.query(RenewalReminder).filter_by(sent=False)
            if days_filter:
                query = query.filter_by(days_until_expiry=days_filter)
            
            reminders = query.order_by(RenewalReminder.reminded_at).all()
            result = []
            for reminder in reminders:
                result.append({
                    'id': reminder.id,
                    'account': reminder.account,
                    'key_id': reminder.key_id,
                    'days_until_expiry': reminder.days_until_expiry
                })
            return result
        except Exception as e:
            print(f"ERROR get_unsent_reminders: {e}")
            return []


async def mark_reminder_sent(reminder_id: str) -> bool:
    """
    Отметить напоминание как отправленное
    
    :param reminder_id: ID напоминания
    :return: bool
    """
    with Session(engine) as session:
        try:
            reminder = session.query(RenewalReminder).filter_by(id=reminder_id).one()
            reminder.sent = True
            reminder.sent_at = datetime.now()
            session.commit()
            return True
        except Exception as e:
            print(f"ERROR mark_reminder_sent: {e}")
            return False


async def get_user_reminders(account: int) -> list[dict]:
    """
    Получить все напоминания пользователя
    
    :param account: ID пользователя
    :return: list с напоминаниями
    """
    with Session(engine) as session:
        try:
            reminders = session.query(RenewalReminder).filter_by(account=account).all()
            result = []
            for reminder in reminders:
                result.append({
                    'id': reminder.id,
                    'key_id': reminder.key_id,
                    'days_until_expiry': reminder.days_until_expiry,
                    'sent': reminder.sent
                })
            return result
        except Exception as e:
            print(f"ERROR get_user_reminders: {e}")
            return []


async def cleanup_old_reminders(days_old: int = 30) -> int:
    """
    Удалить старые напоминания (отправленные более N дней назад)
    
    :param days_old: Возраст напоминания в днях
    :return: Количество удалённых напоминаний
    """
    with Session(engine) as session:
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            old_reminders = session.query(RenewalReminder).filter(
                RenewalReminder.sent == True,
                RenewalReminder.sent_at < cutoff_date
            ).all()
            
            count = len(old_reminders)
            for reminder in old_reminders:
                session.delete(reminder)
            session.commit()
            return count
        except Exception as e:
            print(f"ERROR cleanup_old_reminders: {e}")
            return 0
