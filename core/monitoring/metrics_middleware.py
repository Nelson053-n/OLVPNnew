"""
Middleware для сбора runtime-метрик хендлеров.
"""
from time import perf_counter

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from core.monitoring.runtime_metrics import record_metric


def _callback_bucket(data: str) -> str:
    if not data:
        return 'empty'
    parts = data.split('_')
    return '_'.join(parts[:2]) if len(parts) >= 2 else parts[0]


class MetricsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            text = (event.text or '').strip()
            if text.startswith('/'):
                bucket = f"cmd:{text.split()[0][1:]}"
            else:
                bucket = "msg:text"
        elif isinstance(event, CallbackQuery):
            bucket = f"cb:{_callback_bucket(event.data or '')}"
        else:
            bucket = type(event).__name__.lower()

        started = perf_counter()
        success = False
        try:
            result = await handler(event, data)
            success = True
            return result
        finally:
            elapsed_ms = (perf_counter() - started) * 1000
            record_metric(bucket, elapsed_ms, success)
