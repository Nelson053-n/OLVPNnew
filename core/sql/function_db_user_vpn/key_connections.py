"""
Функции работы с подключениями (для ограничения одновременных подключений)
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import uuid

from core.sql.base import KeyConnection
from core.sql.engine import engine
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def log_connection(key_id: str, ip_address: str, user_agent: str = None) -> str | None:
    """
    Зарегистрировать новое подключение
    
    :param key_id: ID ключа из таблицы user_keys
    :param ip_address: IP адрес подключения
    :param user_agent: user-agent (опционально)
    :return: ID подключения или None
    """
    with Session(engine) as session:
        try:
            connection_id = str(uuid.uuid4())
            connection = KeyConnection(
                id=connection_id,
                key_id=key_id,
                ip_address=ip_address,
                user_agent=user_agent,
                status='active'
            )
            session.add(connection)
            session.commit()
            return connection_id
        except Exception as e:
            logger.log('error', f"ERROR log_connection: {e}")
            return None


async def get_active_connections(key_id: str, max_age_minutes: int = 30) -> list[dict]:
    """
    Получить активные подключения для ключа (за последние N минут)
    
    :param key_id: ID ключа
    :param max_age_minutes: Максимальный возраст подключения в минутах
    :return: list с активными подключениями
    """
    with Session(engine) as session:
        try:
            cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
            connections = session.query(KeyConnection).filter(
                KeyConnection.key_id == key_id,
                KeyConnection.status == 'active',
                KeyConnection.last_activity >= cutoff_time
            ).all()
            
            result = []
            for conn in connections:
                result.append({
                    'id': conn.id,
                    'ip_address': conn.ip_address,
                    'connected_at': conn.connected_at,
                    'last_activity': conn.last_activity
                })
            return result
        except Exception as e:
            logger.log('error', f"ERROR get_active_connections: {e}")
            return []


async def update_connection_activity(connection_id: str) -> bool:
    """
    Обновить время последней активности подключения
    
    :param connection_id: ID подключения
    :return: bool
    """
    with Session(engine) as session:
        try:
            connection = session.query(KeyConnection).filter_by(id=connection_id).one()
            connection.last_activity = datetime.now()
            session.commit()
            return True
        except Exception as e:
            logger.log('error', f"ERROR update_connection_activity: {e}")
            return False


async def disconnect_connection(connection_id: str) -> bool:
    """
    Отметить подключение как отключённое
    
    :param connection_id: ID подключения
    :return: bool
    """
    with Session(engine) as session:
        try:
            connection = session.query(KeyConnection).filter_by(id=connection_id).one()
            connection.status = 'disconnected'
            session.commit()
            return True
        except Exception as e:
            logger.log('error', f"ERROR disconnect_connection: {e}")
            return False


async def block_connection(connection_id: str) -> bool:
    """
    Заблокировать подключение
    
    :param connection_id: ID подключения
    :return: bool
    """
    with Session(engine) as session:
        try:
            connection = session.query(KeyConnection).filter_by(id=connection_id).one()
            connection.status = 'blocked'
            session.commit()
            return True
        except Exception as e:
            logger.log('error', f"ERROR block_connection: {e}")
            return False


async def count_active_connections(key_id: str, max_age_minutes: int = 30) -> int:
    """
    Получить количество активных подключений
    
    :param key_id: ID ключа
    :param max_age_minutes: Максимальный возраст подключения
    :return: int количество активных подключений
    """
    with Session(engine) as session:
        try:
            cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
            count = session.query(KeyConnection).filter(
                KeyConnection.key_id == key_id,
                KeyConnection.status == 'active',
                KeyConnection.last_activity >= cutoff_time
            ).count()
            return count
        except Exception as e:
            logger.log('error', f"ERROR count_active_connections: {e}")
            return 0


async def disconnect_oldest_connection(key_id: str) -> str | None:
    """
    Отключить самое старое подключение для ключа
    
    :param key_id: ID ключа
    :return: IP адрес отключённого подключения или None
    """
    with Session(engine) as session:
        try:
            oldest = session.query(KeyConnection).filter(
                KeyConnection.key_id == key_id,
                KeyConnection.status == 'active'
            ).order_by(KeyConnection.connected_at.asc()).first()
            
            if oldest:
                ip = oldest.ip_address
                oldest.status = 'disconnected'
                session.commit()
                return ip
            return None
        except Exception as e:
            logger.log('error', f"ERROR disconnect_oldest_connection: {e}")
            return None
