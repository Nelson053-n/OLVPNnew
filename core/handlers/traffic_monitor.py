import traceback
from datetime import datetime

from aiogram import Bot
from aiogram.types import Message

from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.settings import admin_tlg
from core.utils.admin_check import require_admin
from core.sql.base import UserKey, Users
from core.sql.engine import engine
from core.sql.function_db_user_vpn.traffic import save_snapshot, get_last_snapshot, get_top_traffic, cleanup_old_snapshots
from logs.log_main import RotatingFileLogger
from sqlalchemy.orm import Session

logger = RotatingFileLogger()

# Порог аномального трафика: 3 ГБ/час
TRAFFIC_THRESHOLD_BYTES_PER_HOUR = 3 * 1024**3


def _find_key_owner(outline_id: str) -> dict | None:
    """
    Найти владельца ключа по outline_id.
    Возвращает dict с account и account_name или None.
    """
    with Session(engine) as session:
        uk = session.query(UserKey).filter_by(outline_id=outline_id).first()
        if not uk:
            return None
        user = session.query(Users).filter_by(account=uk.account).first()
        if not user:
            return {'account': uk.account, 'account_name': 'N/A'}
        return {'account': user.account, 'account_name': user.account_name or 'N/A'}


async def notify_admin_traffic(bot: Bot, outline_id: str, server: str, delta_bytes: int, hours: float):
    """Отправить уведомление администратору об аномальном трафике"""
    owner = _find_key_owner(outline_id)
    delta_gb = delta_bytes / (1024**3)
    threshold_gb = TRAFFIC_THRESHOLD_BYTES_PER_HOUR / (1024**3)
    server_display = get_server_display_name(server)

    if owner:
        owner_text = f"{owner['account']} ({owner['account_name']})"
    else:
        owner_text = "не найден"

    speed_gb = (delta_gb / hours) if hours > 0 else 0
    if hours >= 1:
        period_text = f"{hours:.1f}ч"
    else:
        period_text = f"{hours * 60:.0f}мин"

    text = (
        f"⚠️ <b>Аномальный трафик</b>\n\n"
        f"Ключ: <code>{outline_id}</code> ({server_display})\n"
        f"Владелец: {owner_text}\n"
        f"Потребление: {delta_gb:.1f} ГБ за {period_text}\n"
        f"Скорость: {speed_gb:.1f} ГБ/ч\n"
        f"Порог: {threshold_gb:.0f} ГБ/ч"
    )

    try:
        await bot.send_message(chat_id=admin_tlg, text=text, parse_mode='HTML')
    except Exception as e:
        logger.log('warning', f'Failed to send traffic alert to admin: {e}')


async def check_traffic_anomalies(bot: Bot):
    """
    Снимает snapshot трафика со всех активных серверов,
    сравнивает с предыдущим замером, уведомляет админа при аномалиях.
    Также очищает старые снапшоты.
    """
    servers = get_name_all_active_server_ol()

    for server in servers:
        try:
            olm = OutlineManager(region_server=server)
            data = olm._client.get_transferred_data()
            transferred = data.get("bytesTransferredByUserId", {})

            for outline_id, total_bytes in transferred.items():
                prev = await get_last_snapshot(outline_id, server)
                await save_snapshot(outline_id, server, total_bytes)

                if prev:
                    delta = total_bytes - prev.bytes_total
                    elapsed_seconds = (datetime.now() - prev.measured_at).total_seconds()
                    hours = elapsed_seconds / 3600

                    # Минимум 20 минут между замерами, иначе деление на ~0 даёт ложные срабатывания
                    if hours >= 0.33 and delta > 0 and (delta / hours) > TRAFFIC_THRESHOLD_BYTES_PER_HOUR:
                        await notify_admin_traffic(bot, outline_id, server, delta, hours)

        except KeyError:
            continue
        except Exception as e:
            logger.log('warning', f'Traffic check failed for {server}: {e}')

    # Очистка старых снапшотов
    try:
        deleted = await cleanup_old_snapshots(days=7)
        if deleted > 0:
            logger.log('info', f'Cleaned up {deleted} old traffic snapshots')
    except Exception as e:
        logger.log('warning', f'Traffic cleanup failed: {e}')


@require_admin
async def command_trafficstats(message: Message):
    """
    Команда /trafficstats — Top-10 ключей по трафику за 24 часа.
    Доступна только администратору.
    """

    try:
        top = await get_top_traffic(hours=24, limit=10)

        if not top:
            await message.answer("📊 Нет данных о трафике за последние 24 часа.")
            return

        lines = ["📊 <b>Top-10 по трафику (24ч)</b>\n"]
        for i, item in enumerate(top, 1):
            delta_gb = item['delta_bytes'] / (1024**3)
            hours = item['hours']
            speed_gb = (item['delta_bytes'] / hours / (1024**3)) if hours > 0 else 0
            server_display = get_server_display_name(item['region_server'])

            owner = _find_key_owner(item['outline_id'])
            if owner:
                owner_text = f"{owner['account_name']}"
            else:
                owner_text = "—"

            lines.append(
                f"{i}. <code>{item['outline_id']}</code>\n"
                f"   {server_display} | {owner_text}\n"
                f"   {delta_gb:.2f} ГБ за {hours:.1f}ч ({speed_gb:.2f} ГБ/ч)"
            )

        text = "\n".join(lines)
        await message.answer(text=text, parse_mode='HTML')

    except Exception as e:
        logger.log('error', f'command_trafficstats error: {e}\n{traceback.format_exc()}')
        await message.answer(f"Ошибка: {e}")
