from datetime import datetime

from sqlalchemy import String, Column, DateTime, Integer, Boolean, ForeignKey
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
