import traceback
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import Message

from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.settings import admin_tlg
from core.utils.admin_check import require_admin
from core.sql.base import UserKey, Users
from core.sql.engine import engine
from core.sql.function_db_user_vpn.traffic import save_snapshot, get_top_traffic, cleanup_old_snapshots
from logs.log_main import RotatingFileLogger
from sqlalchemy.orm import Session

logger = RotatingFileLogger()

# Порог аномального трафика: 20 ГБ за 24 часа
TRAFFIC_THRESHOLD_BYTES_PER_DAY = 20 * 1024**3

# Множество ключей, по которым уже отправлен алерт сегодня (outline_id:server)
_alerted_today: set[str] = set()
_last_alert_reset: datetime = datetime.now()


def _find_key_owner(outline_id: str, region_server: str = None) -> dict | None:
    """
    Найти владельца ключа по outline_id (и опционально region_server).
    Возвращает dict с account, account_name, key_id, access_url или None.
    """
    with Session(engine) as session:
        q = session.query(UserKey).filter_by(outline_id=outline_id)
        if region_server:
            q = q.filter_by(region_server=region_server)
        uk = q.first()
        if not uk:
            return None
        user = session.query(Users).filter_by(account=uk.account).first()
        account_name = user.account_name if user else 'N/A'
        return {
            'account': uk.account,
            'account_name': account_name or 'N/A',
            'key_id': uk.id,
            'access_url': uk.access_url,
        }


def _reset_daily_alerts():
    """Сброс кеша алертов раз в сутки."""
    global _alerted_today, _last_alert_reset
    if datetime.now() - _last_alert_reset > timedelta(hours=24):
        _alerted_today = set()
        _last_alert_reset = datetime.now()


async def notify_admin_daily_traffic(bot: Bot, outline_id: str, server: str, delta_gb: float):
    """Отправить суточный отчёт об аномальном трафике"""
    owner = _find_key_owner(outline_id, region_server=server)
    threshold_gb = TRAFFIC_THRESHOLD_BYTES_PER_DAY / (1024**3)
    server_display = get_server_display_name(server)

    if owner:
        owner_text = f"<b>{owner['account_name']}</b> (<code>{owner['account']}</code>)"
        key_text = f"<code>{owner['key_id'][-8:]}</code>"
    else:
        owner_text = "не найден"
        key_text = f"outline #{outline_id}"

    text = (
        f"⚠️ <b>Аномальный трафик (сутки)</b>\n\n"
        f"Владелец: {owner_text}\n"
        f"Ключ: {key_text} | {server_display}\n"
        f"Потребление за 24ч: <b>{delta_gb:.1f} ГБ</b>\n"
        f"Порог: {threshold_gb:.0f} ГБ/сутки"
    )

    try:
        await bot.send_message(chat_id=admin_tlg, text=text, parse_mode='HTML')
    except Exception as e:
        logger.log('warning', f'Failed to send traffic alert to admin: {e}')


async def collect_traffic_snapshots():
    """
    Снимает snapshot трафика со всех серверов.
    Вызывается каждые 30 минут — просто собирает данные.
    """
    servers = get_name_all_active_server_ol()

    for server in servers:
        try:
            olm = OutlineManager(region_server=server)
            data = olm._client.get_transferred_data()
            transferred = data.get("bytesTransferredByUserId", {})

            for outline_id, total_bytes in transferred.items():
                await save_snapshot(outline_id, server, total_bytes)

        except KeyError:
            continue
        except Exception as e:
            logger.log('warning', f'Traffic snapshot failed for {server}: {e}')


async def check_daily_anomalies(bot: Bot):
    """
    Проверяет суточный трафик и алертит админа при превышении порога.
    Вызывается раз в сутки. Один алерт на ключ в день.
    """
    _reset_daily_alerts()

    try:
        top = await get_top_traffic(hours=24, limit=50)

        for item in top:
            key = f"{item['outline_id']}:{item['region_server']}"
            if key in _alerted_today:
                continue

            if item['delta_bytes'] > TRAFFIC_THRESHOLD_BYTES_PER_DAY:
                delta_gb = item['delta_bytes'] / (1024**3)
                await notify_admin_daily_traffic(
                    bot, item['outline_id'], item['region_server'], delta_gb
                )
                _alerted_today.add(key)

    except Exception as e:
        logger.log('warning', f'Daily traffic check failed: {e}')

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

        threshold_gb = TRAFFIC_THRESHOLD_BYTES_PER_DAY / (1024**3)
        lines = [f"📊 <b>Top-10 по трафику (24ч)</b>\n<i>Порог: {threshold_gb:.0f} ГБ/сутки</i>\n"]
        for i, item in enumerate(top, 1):
            delta_gb = item['delta_bytes'] / (1024**3)
            server_display = get_server_display_name(item['region_server'])

            owner = _find_key_owner(item['outline_id'], region_server=item['region_server'])
            if owner:
                owner_text = f"{owner['account_name']} (<code>{owner['account']}</code>)"
                key_short = owner['key_id'][-8:]
            else:
                owner_text = "—"
                key_short = f"ol#{item['outline_id']}"

            flag = "🔴" if item['delta_bytes'] > TRAFFIC_THRESHOLD_BYTES_PER_DAY else "🟢"

            lines.append(
                f"{flag} {i}. {owner_text}\n"
                f"   {server_display} | ключ <code>{key_short}</code>\n"
                f"   <b>{delta_gb:.2f} ГБ</b> за 24ч"
            )

        text = "\n".join(lines)
        await message.answer(text=text, parse_mode='HTML')

    except Exception as e:
        logger.log('error', f'command_trafficstats error: {e}\n{traceback.format_exc()}')
        await message.answer(f"Ошибка: {e}")
