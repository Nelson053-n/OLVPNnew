"""
Проверка статуса VPN серверов и здоровья системы
"""
from aiogram.types import Message
import traceback
import asyncio
from datetime import datetime
from pathlib import Path
import json

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def ping_outline_server(region_name: str) -> tuple[bool, str]:
    """
    Проверяем доступность Outline API сервера через OutlineManager
    Возвращает (is_alive, response_time_ms или сообщение об ошибке)
    """
    try:
        start = datetime.now()
        
        # Используем OutlineManager для проверки - это тот же способ что и при работе с ключами
        try:
            olm = OutlineManager(region_server=region_name)
            # Получаем информацию о сервере - самый простой тест доступности
            server_info = olm._client.get_server_information()
            
            elapsed = (datetime.now() - start).total_seconds() * 1000
            
            if server_info:
                return True, f"{int(elapsed)}ms"
            else:
                return False, "No server info"
                
        except Exception as e:
            error_str = str(e).lower()
            
            # Определяем тип ошибки
            if 'timeout' in error_str or 'timed out' in error_str:
                return False, "Timeout (5s)"
            elif 'connection' in error_str or 'refused' in error_str:
                return False, "Connection refused"
            elif 'ssl' in error_str or 'certificate' in error_str:
                # SSL ошибка - но сервер может быть живой, пробуем ещё раз
                return True, "SSL warning"
            else:
                logger.log('debug', f'ping_outline_server {region_name}: {error_str}')
                return False, str(e)[:40]
    
    except Exception as e:
        logger.log('error', f'ping_outline_server error: {e}\n{traceback.format_exc()}')
        return False, "Error"


async def command_vpn_status(message: Message) -> None:
    """
    Команда /vpnstatus - проверка здоровья всех серверов
    """
    try:
        # Загружаем конфиг серверов
        config_path = Path(__file__).parent.parent / 'api_s' / 'outline' / 'settings_api_outline.json'
        
        if not config_path.exists():
            await message.answer("❌ Конфиг серверов не найден", parse_mode=None)
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            servers = json.load(f)
        
        if not servers:
            await message.answer("❌ Нет доступных серверов", parse_mode=None)
            return
        
        # Отправляем статус "выполняю проверку"
        msg = await message.answer("🔍 Проверяю доступность серверов...", parse_mode=None)
        
        # Проверяем все серверы
        results = {}
        
        for server_name, config in servers.items():
            is_active = config.get('is_active', True)
            
            if not is_active:
                results[server_name] = {
                    'active': False,
                    'status': '⚫ Отключен',
                    'response_time': '-'
                }
            else:
                # Синхронно пингуем сервер
                is_alive, response_time = ping_outline_server(server_name)
                
                if is_alive:
                    results[server_name] = {
                        'active': True,
                        'status': '🟢 Живой',
                        'response_time': response_time
                    }
                else:
                    results[server_name] = {
                        'active': True,
                        'status': '🔴 Недоступен',
                        'response_time': response_time
                    }
        
        # Собираем результаты
        text = "<b>🌐 Статус VPN серверов</b>\n\n"
        
        alive_count = 0
        total_count = 0
        
        # Сортируем по названию
        for server_name in sorted(results.keys()):
            result = results[server_name]
            config = servers[server_name]
            display_name = config.get('name_ru', server_name)
            
            text += f"{result['status']} <b>{display_name}</b>\n"
            text += f"   Отклик: {result['response_time']}\n"
            
            if result['status'].startswith('🟢'):
                alive_count += 1
            
            total_count += 1
        
        text += f"\n📊 <b>Итого:</b> {alive_count}/{total_count} серверов живы\n"
        
        if alive_count == total_count:
            text += "✅ <b>Система работает нормально</b>"
        elif alive_count == 0:
            text += "❌ <b>Все серверы недоступны!</b>"
        else:
            text += f"⚠️ <b>{total_count - alive_count} сервер(ов) не работает</b>"
        
        # Редактируем сообщение с результатом
        try:
            await msg.edit_text(text)
        except Exception:
            await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'command_vpn_status error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при проверке статуса", parse_mode=None)


async def admin_vpn_detailed_check(message: Message) -> None:
    """
    Детальная проверка статуса каждого сервера (команда администратора)
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        from core.api_s.outline.outline_api import OutlineManager
        
        # Загружаем конфиг
        config_path = Path(__file__).parent.parent / 'api_s' / 'outline' / 'settings_api_outline.json'
        
        with open(config_path, 'r', encoding='utf-8') as f:
            servers = json.load(f)
        
        msg = await message.answer("🔍 Проверяю детальный статус всех серверов...", parse_mode=None)
        
        text = "<b>🔧 Детальный статус серверов (администратор)</b>\n\n"
        
        for server_name, config in servers.items():
            if not config.get('is_active', True):
                text += f"⚫ <b>{config.get('name_ru', server_name)}</b> - Отключен\n\n"
                continue
            
            display_name = config.get('name_ru', server_name)
            api_url = config.get('api_url', '')
            
            text += f"<b>{display_name}</b>\n"
            
            # Пытаемся подключиться к API
            try:
                olm = OutlineManager(region_server=server_name)
                
                # Проверяем доступность через получение серверной информации
                try:
                    # Это работает только если сервер живой
                    server_info = olm._client.get_server_information()
                    
                    text += f"✅ API доступен\n"
                    text += f"   Версия: {getattr(server_info, 'version', 'Unknown')}\n"
                    
                except Exception as e:
                    text += f"❌ API недоступен: {str(e)[:50]}\n"
                
            except Exception as e:
                text += f"❌ Ошибка подключения: {str(e)[:50]}\n"
            
            text += "\n"
        
        try:
            await msg.edit_text(text)
        except Exception:
            await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'admin_vpn_detailed_check error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при проверке статуса", parse_mode=None)
