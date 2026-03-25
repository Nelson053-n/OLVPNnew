from datetime import datetime

from sqlalchemy import String, Column, DateTime, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """
    Базовый класс для объявления структуры таблиц в SQLAlchemy.
    """
    pass


class Users(Base):
    """
    Таблица с данными о пользователях.

    Attributes:
    - id (str): Идентификатор пользователя (первичный ключ).
    - account (int): Идентификатор пользователя телеграм (уникальный).
    - account_name (str): Имя пользователя телеграм.
    - promo_key (bool): Флаг получения промо-ключа (по умолчанию False).
    - premium (bool): Флаг премиум-статуса (по умолчанию False).
    - date (DateTime): Дата до которой длится премиум.
    - key (str): Ключ пользователя.
    - region_server (str): Регион выбранного сервера
    - referal_link (str): Реферальная ссылка. (На будущее)
    """
    __tablename__ = 'users_vpn'
    id = Column(String, primary_key=True)
    account = Column(Integer, unique=True)
    account_name = Column(String)
    promo_key = Column(Boolean, default=False)
    premium = Column(Boolean, default=False)
    date = Column(DateTime, nullable=True)
    key = Column(String, nullable=True)
    region_server = Column(String, nullable=True)
    referal_link = Column(String)

    user_payments = relationship('UserPay', back_populates='user')


class UserPay(Base):
    """
    Таблица с данными о платежах пользователей.

    Attributes:
    - id (str): Идентификатор пользователя (первичный ключ).
    - account_id (int): Идентификатор пользователя телеграм (уникальный).
    - paykey (str): Ключ платежа юкассы
    - last_updated (datetime): Время последнего апдейта
    """
    __tablename__ = 'users_payments'
    id = Column(String, primary_key=True)
    account_id = Column(Integer, ForeignKey('users_vpn.account'), unique=True)
    paykey = Column(String, nullable=True)
    time_added = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, onupdate=datetime.now)

    user = relationship('Users', back_populates='user_payments')


class UserKey(Base):
    """
    Таблица с несколькими ключами пользователя
    """
    __tablename__ = 'user_keys'
    __table_args__ = (
        Index('ix_userkey_account', 'account'),
        Index('ix_userkey_region_server', 'region_server'),
    )
    id = Column(String, primary_key=True)
    account = Column(Integer, ForeignKey('users_vpn.account'))
    access_url = Column(String, nullable=False)
    outline_id = Column(String, nullable=False)  # id ключа в Outline
    region_server = Column(String, nullable=True)
    premium = Column(Boolean, default=True)
    date = Column(DateTime, nullable=True)
    promo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class BlockHistory(Base):
    """
    История блокировок ключей
    """
    __tablename__ = 'block_history'
    id = Column(String, primary_key=True)
    account = Column(Integer, ForeignKey('users_vpn.account'))
    admin_id = Column(Integer)
    reason = Column(String, nullable=True)
    key = Column(String, nullable=True)
    blocked_at = Column(DateTime, default=datetime.now)

class Referral(Base):
    """
    Реферальная программа
    """
    __tablename__ = 'referrals'
    id = Column(String, primary_key=True)
    referrer_id = Column(Integer, ForeignKey('users_vpn.account'))  # ID пригласившего
    referred_id = Column(Integer, ForeignKey('users_vpn.account'), unique=True)  # ID приглашённого
    bonus_days = Column(Integer, default=7)  # Бонус в днях
    bonus_given = Column(Boolean, default=False)  # Выдан ли бонус
    referral_date = Column(DateTime, default=datetime.now)
    bonus_date = Column(DateTime, nullable=True)  # Когда выдан бонус


class SupportTicket(Base):
    """
    票 поддержки (тикеты)
    """
    __tablename__ = 'support_tickets'
    id = Column(String, primary_key=True)
    account = Column(Integer, ForeignKey('users_vpn.account'))
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String)  # bug, feature, payment, access, etc.
    priority = Column(String, default='normal')  # critical, high, normal, low
    status = Column(String, default='open')  # open, in_progress, resolved, closed
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    resolved_at = Column(DateTime, nullable=True)
    admin_response = Column(String, nullable=True)


class KeyConnection(Base):
    """
    Отслеживание одновременных подключений к ключу
    """
    __tablename__ = 'key_connections'
    id = Column(String, primary_key=True)
    key_id = Column(String, ForeignKey('user_keys.id'))
    ip_address = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
    connected_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)
    status = Column(String, default='active')  # active, disconnected, blocked


class RenewalReminder(Base):
    """
    Напоминания о продлении подписки
    """
    __tablename__ = 'renewal_reminders'
    id = Column(String, primary_key=True)
    account = Column(Integer, ForeignKey('users_vpn.account'))
    key_id = Column(String, ForeignKey('user_keys.id'))
    days_until_expiry = Column(Integer)  # 7, 3, 1 день
    reminded_at = Column(DateTime, default=datetime.now)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)


class TrafficSnapshot(Base):
    """
    Снапшоты трафика ключей для обнаружения аномалий (шеринга)
    """
    __tablename__ = 'traffic_snapshots'
    __table_args__ = (
        Index('ix_traffic_outline_id', 'outline_id'),
    )
    id = Column(String, primary_key=True)
    outline_id = Column(String, nullable=False)
    region_server = Column(String, nullable=False)
    bytes_total = Column(Integer, nullable=False)
    measured_at = Column(DateTime, default=datetime.now)