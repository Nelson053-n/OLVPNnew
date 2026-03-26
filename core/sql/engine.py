"""Centralized SQLAlchemy engine and session factory."""
import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from core.sql.base import Base

# Use absolute path for SQLite database
_DB_PATH = Path(__file__).resolve().parent.parent.parent / 'olvpnbot.db'
DATABASE_URL = f'sqlite:///{_DB_PATH}'
SQL_ECHO = os.getenv('SQL_ECHO', 'false').lower() == 'true'

engine = create_engine(
    DATABASE_URL, echo=SQL_ECHO,
    connect_args={"timeout": 30},
    pool_size=5, max_overflow=10,
    pool_recycle=3600, pool_pre_ping=True,
)


# Enable WAL mode for better concurrent access
@event.listens_for(engine, "connect")
def _set_sqlite_wal(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

# Миграция: создать индексы для существующей БД (если таблица уже есть)
with engine.connect() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_userkey_date ON user_keys (date)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_userkey_premium_date ON user_keys (premium, date)"))
    conn.commit()
