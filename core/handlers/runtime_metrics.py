"""
Команда администратора для просмотра runtime-метрик.
"""
from aiogram.types import Message

from core.monitoring.runtime_metrics import get_metrics_snapshot, get_metrics_totals
from core.settings import admin_tlg


async def command_metrics(message: Message) -> None:
    if not admin_tlg or message.from_user.id != admin_tlg:
        await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
        return

    totals = get_metrics_totals()
    snapshot = get_metrics_snapshot(limit=20)

    text = (
        '<b>📈 Runtime-метрики хендлеров</b>\n\n'
        f"Хендлеров: {totals['handlers']}\n"
        f"Вызовов: {totals['calls']}\n"
        f"Ошибок: {totals['errors']}\n\n"
    )

    if not snapshot:
        text += 'Данных пока нет. Выполните несколько команд и повторите.'
        await message.answer(text, parse_mode='HTML')
        return

    text += '<b>Топ-20 по среднему времени:</b>\n'
    for index, (name, item, avg_ms) in enumerate(snapshot, 1):
        text += (
            f"{index}. <code>{name}</code>\n"
            f"   avg: {avg_ms:.1f} ms | max: {item.max_ms:.1f} ms | "
            f"calls: {item.count} | errors: {item.error_count}\n"
        )

    await message.answer(text, parse_mode='HTML')
