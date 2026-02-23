"""
Статистика хоста, на котором запущен бот.
"""
import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from aiogram.types import Message

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def _format_bytes(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{value:.2f} B"


def _format_rate(bytes_per_sec: float) -> str:
    bits_per_sec = bytes_per_sec * 8
    mbps = bits_per_sec / (1024 * 1024)
    return f"{mbps:.2f} Mbps"


def _read_linux_net_bytes() -> tuple[int, int]:
    recv_total = 0
    sent_total = 0
    with open('/proc/net/dev', 'r', encoding='utf-8') as f:
        lines = f.readlines()[2:]
    for line in lines:
        if ':' not in line:
            continue
        _, data = line.split(':', 1)
        fields = data.split()
        if len(fields) < 9:
            continue
        recv_total += int(fields[0])
        sent_total += int(fields[8])
    return recv_total, sent_total


async def _get_network_load() -> tuple[float | None, float | None]:
    """Возвращает (recv_bytes_sec, sent_bytes_sec)."""
    try:
        import psutil  # type: ignore

        before = psutil.net_io_counters()
        await asyncio.sleep(1)
        after = psutil.net_io_counters()
        recv_bps = float(after.bytes_recv - before.bytes_recv)
        sent_bps = float(after.bytes_sent - before.bytes_sent)
        return recv_bps, sent_bps
    except Exception:
        pass

    try:
        if os.name == 'posix' and Path('/proc/net/dev').exists():
            recv_before, sent_before = _read_linux_net_bytes()
            await asyncio.sleep(1)
            recv_after, sent_after = _read_linux_net_bytes()
            return float(recv_after - recv_before), float(sent_after - sent_before)
    except Exception:
        pass

    try:
        if os.name == 'nt':
            cmd = [
                'powershell',
                '-NoProfile',
                '-Command',
                "(Get-Counter '\\Network Interface(*)\\Bytes Received/sec').CounterSamples | "
                "Measure-Object -Property CookedValue -Sum | Select-Object -ExpandProperty Sum"
            ]
            recv_raw = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            cmd[3] = (
                "(Get-Counter '\\Network Interface(*)\\Bytes Sent/sec').CounterSamples | "
                "Measure-Object -Property CookedValue -Sum | Select-Object -ExpandProperty Sum"
            )
            sent_raw = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            recv_bps = float(recv_raw) if recv_raw else 0.0
            sent_bps = float(sent_raw) if sent_raw else 0.0
            return recv_bps, sent_bps
    except Exception:
        pass

    return None, None


def _get_cpu_load_percent() -> float | None:
    try:
        import psutil  # type: ignore

        return float(psutil.cpu_percent(interval=1))
    except Exception:
        pass

    try:
        if os.name == 'nt':
            out = subprocess.check_output(
                ['wmic', 'cpu', 'get', 'loadpercentage', '/value'],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.startswith('LoadPercentage='):
                    value = line.split('=', 1)[1].strip()
                    if value:
                        return float(value)
    except Exception:
        pass

    try:
        if hasattr(os, 'getloadavg'):
            load_1m = os.getloadavg()[0]
            cpu_count = os.cpu_count() or 1
            return max(0.0, min(100.0, (load_1m / cpu_count) * 100.0))
    except Exception:
        pass

    return None


async def command_server_host_stats(message: Message) -> None:
    """
    -- Админ-команда --
    Статистика хоста: диск, CPU, нагрузка канала.
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        disk_root = Path.cwd().anchor or '/'
        total, used, free = shutil.disk_usage(disk_root)
        disk_percent = (used / total) * 100 if total else 0

        cpu_percent = _get_cpu_load_percent()
        recv_bps, sent_bps = await _get_network_load()

        cpu_text = f"{cpu_percent:.1f}%" if cpu_percent is not None else 'н/д'
        if recv_bps is None or sent_bps is None:
            channel_text = 'н/д'
            in_text = 'н/д'
            out_text = 'н/д'
        else:
            total_bps = recv_bps + sent_bps
            channel_text = _format_rate(total_bps)
            in_text = _format_rate(recv_bps)
            out_text = _format_rate(sent_bps)

        text = (
            '<b>🖥️ Сервер бота</b>\n\n'
            '<b>💾 Диск:</b>\n'
            f'• Свободно: {_format_bytes(free)}\n'
            f'• Использовано: {disk_percent:.1f}%\n'
            f'• Всего: {_format_bytes(total)}\n\n'
            '<b>🧠 Нагрузка CPU:</b>\n'
            f'• Текущая: {cpu_text}\n\n'
            '<b>📡 Нагрузка на канал:</b>\n'
            f'• Входящий трафик: {in_text}\n'
            f'• Исходящий трафик: {out_text}\n'
            f'• Суммарная нагрузка: {channel_text}'
        )

        await message.answer(text, parse_mode='HTML')
    except Exception as e:
        logger.log('error', f'command_server_host_stats error: {e}')
        await message.answer('❌ Ошибка получения статистики сервера', parse_mode=None)
