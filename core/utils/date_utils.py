from datetime import datetime


def days_left_display(expiry_date: datetime) -> str:
    """Возвращает строку с оставшимся временем, например ' (3 дн.)' или ' (2 ч.)'"""
    if not expiry_date:
        return ""
    delta = expiry_date - datetime.now()
    if delta.total_seconds() <= 0:
        return " (истёк)"
    if delta.days > 0:
        return f" ({delta.days} дн.)"
    hours = delta.seconds // 3600
    return f" ({hours} ч.)"


def format_date(dt: datetime) -> str:
    """Форматирует дату в ДД.ММ.ГГГГ - ЧЧ:ММ"""
    if not dt:
        return "—"
    return dt.strftime('%d.%m.%Y - %H:%M')
