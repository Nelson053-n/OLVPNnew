"""
Middleware для сбора runtime-метрик хендлеров.
"""
from time import perf_counter

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from core.monitoring.runtime_metrics import record_metric
from logs.log_main import RotatingFileLogger

_mw_logger = RotatingFileLogger()


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
            _mw_logger.log('info', f'[MW] CallbackQuery user={event.from_user.id} data={event.data}')
        else:
            bucket = type(event).__name__.lower()

        started = perf_counter()
        success = False
        try:
            result = await handler(event, data)
            success = True
            return result
        except Exception as exc:
            _mw_logger.log('error', f'[MW] handler error bucket={bucket}: {exc}')
            raise
        finally:
            elapsed_ms = (perf_counter() - started) * 1000
            record_metric(bucket, elapsed_ms, success)
