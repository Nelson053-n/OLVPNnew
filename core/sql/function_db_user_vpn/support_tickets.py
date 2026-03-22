"""
Функции работы с поддержкой (тикеты)
"""
from datetime import datetime
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
import uuid

from core.sql.base import SupportTicket
from core.sql.engine import engine


async def create_ticket(account: int, title: str, description: str, category: str = 'general', priority: str = 'normal') -> str | None:
    """
    Создать новый тикет поддержки
    
    :param account: ID пользователя
    :param title: Заголовок
    :param description: Описание проблемы
    :param category: Категория (bug, feature, payment, access, other)
    :param priority: Приоритет (critical, high, normal, low)
    :return: ID тикета или None
    """
    with Session(engine) as session:
        try:
            ticket_id = f"ticket_{account}_{uuid.uuid4().hex[:8]}"
            ticket = SupportTicket(
                id=ticket_id,
                account=account,
                title=title,
                description=description,
                category=category,
                priority=priority,
                status='open'
            )
            session.add(ticket)
            session.commit()
            return ticket_id
        except Exception as e:
            print(f"ERROR create_ticket: {e}")
            return None


async def get_ticket(ticket_id: str) -> dict | None:
    """
    Получить информацию о тикете
    
    :param ticket_id: ID тикета
    :return: dict с информацией или None
    """
    with Session(engine) as session:
        try:
            ticket = session.query(SupportTicket).filter_by(id=ticket_id).one()
            return {
                'id': ticket.id,
                'account': ticket.account,
                'title': ticket.title,
                'description': ticket.description,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'created_at': ticket.created_at,
                'admin_response': ticket.admin_response
            }
        except NoResultFound:
            return None


async def update_ticket_status(ticket_id: str, status: str) -> bool:
    """
    Обновить статус тикета
    
    :param ticket_id: ID тикета
    :param status: Новый статус (open, in_progress, resolved, closed)
    :return: bool
    """
    with Session(engine) as session:
        try:
            ticket = session.query(SupportTicket).filter_by(id=ticket_id).one()
            ticket.status = status
            if status == 'resolved':
                ticket.resolved_at = datetime.now()
            ticket.updated_at = datetime.now()
            session.commit()
            return True
        except Exception as e:
            print(f"ERROR update_ticket_status: {e}")
            return False


async def add_admin_response(ticket_id: str, response: str) -> bool:
    """
    Добавить ответ администратора к тикету
    
    :param ticket_id: ID тикета
    :param response: Текст ответа
    :return: bool
    """
    with Session(engine) as session:
        try:
            ticket = session.query(SupportTicket).filter_by(id=ticket_id).one()
            ticket.admin_response = response
            ticket.updated_at = datetime.now()
            session.commit()
            return True
        except Exception as e:
            print(f"ERROR add_admin_response: {e}")
            return False


async def get_user_tickets(account: int, status: str = None) -> list[dict]:
    """
    Получить тикеты пользователя
    
    :param account: ID пользователя
    :param status: Фильтр по статусу (опционально)
    :return: list с тикетами
    """
    with Session(engine) as session:
        try:
            query = session.query(SupportTicket).filter_by(account=account)
            if status:
                query = query.filter_by(status=status)
            tickets = query.order_by(SupportTicket.created_at.desc()).all()
            result = []
            for ticket in tickets:
                result.append({
                    'id': ticket.id,
                    'title': ticket.title,
                    'priority': ticket.priority,
                    'status': ticket.status,
                    'created_at': ticket.created_at
                })
            return result
        except Exception as e:
            print(f"ERROR get_user_tickets: {e}")
            return []


async def get_open_tickets() -> list[dict]:
    """
    Получить все открытые тикеты (для администратора)
    
    :return: list с открытыми тикетами
    """
    with Session(engine) as session:
        try:
            tickets = session.query(SupportTicket).filter_by(status='open').order_by(
                SupportTicket.priority.desc(),
                SupportTicket.created_at.asc()
            ).all()
            result = []
            for ticket in tickets:
                result.append({
                    'id': ticket.id,
                    'account': ticket.account,
                    'title': ticket.title,
                    'priority': ticket.priority,
                    'category': ticket.category,
                    'created_at': ticket.created_at
                })
            return result
        except Exception as e:
            print(f"ERROR get_open_tickets: {e}")
            return []


async def get_ticket_stats() -> dict:
    """
    Получить статистику по тикетам
    
    :return: dict со статистикой
    """
    with Session(engine) as session:
        try:
            total = session.query(SupportTicket).count()
            open_count = session.query(SupportTicket).filter_by(status='open').count()
            in_progress = session.query(SupportTicket).filter_by(status='in_progress').count()
            resolved = session.query(SupportTicket).filter_by(status='resolved').count()
            
            return {
                'total': total,
                'open': open_count,
                'in_progress': in_progress,
                'resolved': resolved
            }
        except Exception as e:
            print(f"ERROR get_ticket_stats: {e}")
            return {}
