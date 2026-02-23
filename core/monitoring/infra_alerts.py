"""
Фоновый монитор инфраструктуры и алерты администратору.
"""
import asyncio
import os
import shutil
from pathlib import Path

from aiogram import Bot

from core.api_s.outline.outline_api import get_name_all_active_server_ol
from core.handlers.vpn_status_handler import ping_outline_server
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


class InfraAlertsMonitor:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.enabled = os.getenv('INFRA_ALERTS_ENABLED', 'true').lower() == 'true'
        self.interval_sec = int(os.getenv('INFRA_ALERTS_INTERVAL_SEC', '300'))
        self.cpu_threshold = float(os.getenv('INFRA_ALERTS_CPU_THRESHOLD', '90'))
        self.disk_threshold = float(os.getenv('INFRA_ALERTS_DISK_THRESHOLD', '90'))
        self._active_issues: set[str] = set()

    async def run(self):
        if not self.enabled or not admin_tlg:
            logger.log('info', 'InfraAlertsMonitor disabled (env/admin)')
            return

        logger.log('info', 'InfraAlertsMonitor started')
        while True:
            try:
                issues = await self._collect_issues()
                await self._notify_diff(issues)
            except Exception as e:
                logger.log('warning', f'InfraAlertsMonitor loop error: {e}')
            await asyncio.sleep(self.interval_sec)

    async def _collect_issues(self) -> dict[str, str]:
        issues: dict[str, str] = {}

        disk_root = Path.cwd().anchor or '/'
        total, used, _ = shutil.disk_usage(disk_root)
        disk_percent = (used / total) * 100 if total else 0
        if disk_percent >= self.disk_threshold:
            issues['disk_high'] = f'💾 Диск загружен: {disk_percent:.1f}% (порог {self.disk_threshold:.1f}%)'

        cpu_percent = await asyncio.to_thread(self._get_cpu_percent)
        if cpu_percent is not None and cpu_percent >= self.cpu_threshold:
            issues['cpu_high'] = f'🧠 CPU загружен: {cpu_percent:.1f}% (порог {self.cpu_threshold:.1f}%)'

        for server in get_name_all_active_server_ol():
            alive, info = await asyncio.to_thread(ping_outline_server, server)
            if not alive:
                issues[f'vpn_down:{server}'] = f'🌐 VPN сервер недоступен: {server} ({info})'

        return issues

    def _get_cpu_percent(self) -> float | None:
        try:
            import psutil  # type: ignore
            return float(psutil.cpu_percent(interval=1))
        except Exception:
            try:
                if hasattr(os, 'getloadavg'):
                    load_1m = os.getloadavg()[0]
                    cpu_count = os.cpu_count() or 1
                    return max(0.0, min(100.0, (load_1m / cpu_count) * 100.0))
            except Exception:
                return None
        return None

    async def _notify_diff(self, issues: dict[str, str]) -> None:
        current = set(issues.keys())
        new_issues = current - self._active_issues
        recovered = self._active_issues - current

        if new_issues:
            lines = ['🚨 <b>Infra Alert</b>\n']
            for key in sorted(new_issues):
                lines.append(f'• {issues[key]}')
            await self.bot.send_message(chat_id=int(admin_tlg), text='\n'.join(lines), parse_mode='HTML')

        if recovered:
            lines = ['✅ <b>Infra Recovery</b>\n']
            for key in sorted(recovered):
                lines.append(f'• Восстановлено: <code>{key}</code>')
            await self.bot.send_message(chat_id=int(admin_tlg), text='\n'.join(lines), parse_mode='HTML')

        self._active_issues = current
