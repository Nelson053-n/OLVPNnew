import functools
from datetime import datetime

from aiogram.types import CallbackQuery

# Максимум записей в per-user dict (защита от утечки памяти)
_MAX_THROTTLE_ENTRIES = 5000


def throttle(seconds: int) -> callable:
    """
    Декоратор для ограничения частоты нажатия на клавиатуру (per-user).

    :param seconds: float - Время в секундах, которое должно пройти между вызовами функции.
    :return: callable - Декоратор, который применяется к асинхронной функции.
    """
    def decorator(func):
        # Per-user throttle: {user_id: datetime последнего вызова}
        _last_calls: dict[int, datetime] = {}

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_time = datetime.now()
            # args[0] — CallbackQuery или Message
            user_id = getattr(getattr(args[0], 'from_user', None), 'id', None)
            if user_id is None:
                return await func(*args, **kwargs)

            last_call = _last_calls.get(user_id)
            if last_call is not None:
                time_since = (current_time - last_call).total_seconds()
                if time_since < seconds:
                    remaining = round(seconds - time_since, 2)
                    # show_alert только для CallbackQuery (у Message нет этого параметра)
                    if isinstance(args[0], CallbackQuery):
                        await args[0].answer(f"Частые нажатия\nНужно ждать еще {remaining} сек", show_alert=True)
                    return

            _last_calls[user_id] = current_time

            # Очистка: если dict разросся, удаляем самые старые записи
            if len(_last_calls) > _MAX_THROTTLE_ENTRIES:
                oldest = sorted(_last_calls, key=_last_calls.get)[:len(_last_calls) - _MAX_THROTTLE_ENTRIES]
                for uid in oldest:
                    del _last_calls[uid]

            return await func(*args, **kwargs)
        return wrapper
    return decorator
