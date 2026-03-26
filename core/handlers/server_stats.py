"""
Команда для просмотра статистики по серверам Outline
"""
from aiogram.types import Message
import traceback

from core.utils.admin_check import require_admin
from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


@require_admin
async def command_server_stats(message: Message) -> None:
    """
    -- Админ-команда --
    /serverstats
    Показывает статистику по всем активным серверам Outline:
    - Количество ключей на сервере
    - Количество активных ключей
    - Общий трафик
    """
    try:

        # Получаем список всех активных серверов
        all_servers = get_name_all_active_server_ol()
        
        if not all_servers:
            await message.answer('❌ Нет активных серверов', parse_mode=None)
            return

        # Получаем все ключи из БД
        all_keys = await get_all_user_keys()
        
        # Группируем ключи по серверам
        keys_by_server = {}
        for server in all_servers:
            keys_by_server[server] = []
        
        for key in all_keys:
            if key.region_server in keys_by_server:
                keys_by_server[key.region_server].append(key)
        
        # Формируем ответ
        lines = ['<b>📊 Статистика серверов Outline</b>\n']
        
        # Переменная для подсчета общего трафика
        grand_total_traffic_bytes = 0
        
        for idx, server in enumerate(all_servers, 1):
            try:
                olm = OutlineManager(region_server=server)
                
                # Получаем все ключи с сервера
                server_keys = olm._client.get_keys()
                total_keys = len(server_keys) if server_keys else 0
                
                # Подсчитываем общий трафик
                total_traffic_bytes = 0
                if server_keys:
                    for sk in server_keys:
                        used = getattr(sk, 'used_bytes', 0) or 0
                        total_traffic_bytes += used
                
                total_traffic_gb = total_traffic_bytes / (1024**3)
                grand_total_traffic_bytes += total_traffic_bytes
                
                # Ключи в нашей БД для этого сервера
                db_keys = keys_by_server[server]
                active_db_keys = sum(1 for k in db_keys if k.premium)
                
                # Получаем отображаемое имя с флагом
                server_display = get_server_display_name(server)
                
                lines.append(
                    f'<b>{idx}.</b> {server_display}\n'
                    f'   Ключей на сервере: {total_keys}\n'
                    f'   Активных в БД: {active_db_keys} из {len(db_keys)}\n'
                    f'   Общий трафик: {total_traffic_gb:.2f} ГБ\n'
                )
                
            except Exception as e:
                logger.log('error', f'Error getting stats for server {server}: {e}')
                server_display = get_server_display_name(server)
                lines.append(
                    f'<b>{idx}.</b> {server_display}\n'
                    f'   ❌ Ошибка получения статистики: {str(e)}\n'
                )
        
        # Итоговая статистика
        grand_total_traffic_gb = grand_total_traffic_bytes / (1024**3)
        lines.append(f'\n<b>Всего серверов:</b> {len(all_servers)}')
        lines.append(f'<b>Всего ключей в БД:</b> {len(all_keys)}')
        lines.append(f'<b>Общий трафик:</b> {grand_total_traffic_gb:.2f} ГБ')
        
        await message.answer('\n'.join(lines), parse_mode='HTML')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_server_stats error: {e}\n{tb}')
        await message.answer(f'❌ Ошибка: {str(e)}', parse_mode=None)
