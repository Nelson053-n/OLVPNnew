"""
Runtime-метрики хендлеров бота.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass
class MetricItem:
    count: int = 0
    error_count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    last_ms: float = 0.0
    last_seen: datetime | None = None


MAX_METRIC_KEYS = 500

_METRICS: Dict[str, MetricItem] = {}


def record_metric(name: str, duration_ms: float, success: bool) -> None:
    item = _METRICS.get(name)
    if item is None:
        # Ограничиваем рост: удаляем самый старый, если лимит превышен
        if len(_METRICS) >= MAX_METRIC_KEYS:
            oldest_key = min(_METRICS, key=lambda k: _METRICS[k].last_seen or datetime.min)
            del _METRICS[oldest_key]
        item = MetricItem()
        _METRICS[name] = item

    item.count += 1
    if not success:
        item.error_count += 1
    item.total_ms += duration_ms
    item.last_ms = duration_ms
    item.max_ms = max(item.max_ms, duration_ms)
    item.last_seen = datetime.now()


def get_metrics_snapshot(limit: int = 20) -> List[tuple[str, MetricItem, float]]:
    rows: List[tuple[str, MetricItem, float]] = []
    for name, item in _METRICS.items():
        avg = (item.total_ms / item.count) if item.count else 0.0
        rows.append((name, item, avg))

    rows.sort(key=lambda x: x[2], reverse=True)
    return rows[:limit]


def get_metrics_totals() -> dict:
    total_calls = sum(item.count for item in _METRICS.values())
    total_errors = sum(item.error_count for item in _METRICS.values())
    return {
        'handlers': len(_METRICS),
        'calls': total_calls,
        'errors': total_errors,
    }
