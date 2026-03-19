import functools
from datetime import datetime


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
                    await args[0].answer(f"Частые нажатия\nНужно ждать еще {remaining} сек", show_alert=True)
                    return

            _last_calls[user_id] = current_time
            return await func(*args, **kwargs)
        return wrapper
    return decorator