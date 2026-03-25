from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import Session
import uuid

from core.sql.base import TrafficSnapshot
from core.sql.engine import engine
from logs.log_main import RotatingFileLogger

_logger = RotatingFileLogger()


async def save_snapshot(outline_id: str, region_server: str, bytes_total: int) -> bool:
    """
    Сохранить снапшот трафика ключа

    :param outline_id: ID ключа в Outline
    :param region_server: Регион сервера
    :param bytes_total: Кумулятивный трафик в байтах
    :return: True при успехе
    """
    with Session(engine) as session:
        try:
            record_id = f"ts_{outline_id}_{uuid.uuid4()}"
            snapshot = TrafficSnapshot(
                id=record_id,
                outline_id=outline_id,
                region_server=region_server,
                bytes_total=bytes_total,
                measured_at=datetime.now(),
            )
            session.add(snapshot)
            session.commit()
            return True
        except Exception as e:
            _logger.log('error', f"save_snapshot error for {outline_id}: {e}")
            return False


async def get_last_snapshot(outline_id: str, region_server: str) -> TrafficSnapshot | None:
    """
    Получить последний снапшот для ключа на конкретном сервере.
    Outline ID не уникальны глобально — один и тот же ID может быть на разных серверах.

    :param outline_id: ID ключа в Outline
    :param region_server: Регион сервера
    :return: TrafficSnapshot или None
    """
    with Session(engine) as session:
        return (
            session.query(TrafficSnapshot)
            .filter_by(outline_id=outline_id, region_server=region_server)
            .order_by(desc(TrafficSnapshot.measured_at))
            .first()
        )


async def get_top_traffic(hours: int = 24, limit: int = 10) -> list[dict]:
    """
    Top-N ключей по дельте трафика за указанный период.
    Сравнивает самый ранний и самый поздний снапшот каждого ключа за период.

    :param hours: Период в часах
    :param limit: Количество результатов
    :return: Список словарей с outline_id, region_server, delta_bytes, hours
    """
    since = datetime.now() - timedelta(hours=hours)
    with Session(engine) as session:
        snapshots = (
            session.query(TrafficSnapshot)
            .filter(TrafficSnapshot.measured_at >= since)
            .order_by(TrafficSnapshot.outline_id, TrafficSnapshot.measured_at)
            .all()
        )

    # Группируем по outline_id, берём первый и последний
    grouped = {}
    for s in snapshots:
        if s.outline_id not in grouped:
            grouped[s.outline_id] = {'first': s, 'last': s}
        else:
            grouped[s.outline_id]['last'] = s

    results = []
    for outline_id, data in grouped.items():
        first = data['first']
        last = data['last']
        delta = last.bytes_total - first.bytes_total
        elapsed = (last.measured_at - first.measured_at).total_seconds() / 3600
        if delta > 0:
            results.append({
                'outline_id': outline_id,
                'region_server': last.region_server,
                'delta_bytes': delta,
                'hours': elapsed if elapsed > 0 else hours,
            })

    results.sort(key=lambda x: x['delta_bytes'], reverse=True)
    return results[:limit]


async def cleanup_old_snapshots(days: int = 7) -> int:
    """
    Удалить снапшоты старше указанного количества дней

    :param days: Возраст в днях
    :return: Количество удалённых записей
    """
    cutoff = datetime.now() - timedelta(days=days)
    with Session(engine) as session:
        try:
            count = session.query(TrafficSnapshot).filter(TrafficSnapshot.measured_at < cutoff).delete()
            session.commit()
            return count
        except Exception as e:
            _logger.log('error', f"cleanup_old_snapshots error: {e}")
            return 0
