from functools import wraps

from aiogram.types import Message, CallbackQuery

from core.settings import admin_tlg


def is_admin(user_id: int) -> bool:
    return bool(admin_tlg) and user_id == admin_tlg


def require_admin(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        event = next((a for a in args if isinstance(a, (Message, CallbackQuery))), None)
        # Поддержка _MessageProxy из admin_keys.py (не является instanceof Message)
        if event is None:
            event = next((a for a in args if hasattr(a, 'from_user') and hasattr(a, 'answer')), None)
        if event is None:
            return
        user_id = event.from_user.id if event.from_user else None
        if not is_admin(user_id):
            if isinstance(event, (Message, CallbackQuery)):
                if isinstance(event, Message):
                    await event.answer("У вас нет доступа к этой команде", parse_mode=None)
                else:
                    await event.answer("Нет доступа", show_alert=True)
            else:
                # _MessageProxy — try answer
                try:
                    await event.answer("У вас нет доступа к этой команде", parse_mode=None)
                except Exception:
                    pass
            return
        return await func(*args, **kwargs)
    return wrapper
