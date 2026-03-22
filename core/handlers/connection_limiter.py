"""
Управление одновременными подключениями - ограничение до 3 максимум
"""
from aiogram.types import Message
import traceback
from datetime import datetime, timedelta

from core.sql.function_db_user_vpn.key_connections import (
    log_connection,
    get_active_connections,
    count_active_connections,
    disconnect_oldest_connection,
    disconnect_connection,
    block_connection,
)
from core.sql.function_db_user_vpn.users_vpn import (
    get_user_keys,
    get_user_data_from_table_users,
)
from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()

MAX_CONCURRENT_CONNECTIONS = 3


async def check_and_enforce_connection_limit(key_id: int, user_ip: str = None, user_agent: str = None) -> bool:
    """
    Проверяет и применяет ограничение на одновременные подключения
    Если превышен лимит, отключает самое старое подключение
    
    :param key_id: ID ключа в БД
    :param user_ip: IP адрес подключающегося пользователя
    :param user_agent: User agent устройства
    :return: bool успешность логирования нового подключения
    """
    try:
        # Логируем новое подключение
        await log_connection(
            key_id=key_id,
            ip_address=user_ip or "unknown",
            user_agent=user_agent or "unknown"
        )
        
        # Проверяем количество активных подключений
        active_count = await count_active_connections(key_id=key_id)
        
        if active_count > MAX_CONCURRENT_CONNECTIONS:
            # Отключаем самое старое
            eldest_conn_id = await disconnect_oldest_connection(key_id=key_id)
            
            if eldest_conn_id:
                logger.log(
                    'info',
                    f'Disconnected eldest connection {eldest_conn_id} for key {key_id} '
                    f'(active: {active_count})'
                )
                # Уведомляем пользователя (если это не первое подключение)
                # await send_notification_to_user(...)
        
        return True
        
    except Exception as e:
        logger.log('warning', f'check_and_enforce_connection_limit error: {e}')
        return False


async def command_my_connections(message: Message) -> None:
    """
    Команда /myconnections - просмотр своих активных подключений
    """
    try:
        account = message.from_user.id
        
        # Получаем все ключи пользователя
        keys = await get_user_keys(account=account)
        
        if not keys:
            await message.answer(
                "🔌 У вас нет активных ключей\n\n"
                "Используйте /start для получения доступа",
                parse_mode=None
            )
            return
        
        text = "<b>🔌 Ваши активные подключения</b>\n\n"
        
        has_connections = False
        
        for key in keys:
            if not key.premium:
                continue
            
            connections = await get_active_connections(
                key_id=key.id,
                max_age_minutes=30
            )
            
            if connections:
                has_connections = True
                text += f"<b>Регион:</b> {key.region_server}\n"
                text += f"📊 <b>Активные подключения: {len(connections)}/{MAX_CONCURRENT_CONNECTIONS}</b>\n\n"
                
                for idx, conn in enumerate(connections, 1):
                    last_activity = conn['last_activity'] or conn['connected_at']

                    # Вычисляем время со последней активности
                    if last_activity:
                        elapsed = (datetime.now() - last_activity).total_seconds()
                        if elapsed < 60:
                            time_str = "только что"
                        elif elapsed < 3600:
                            mins = int(elapsed / 60)
                            time_str = f"{mins} мин назад"
                        else:
                            hours = int(elapsed / 3600)
                            time_str = f"{hours}ч назад"
                    else:
                        time_str = "Unknown"

                    status_emoji = "🟢" if conn.get('status', 'active') == 'active' else "⚫"
                    text += f"{status_emoji} #{idx} | {conn['ip_address']} | {time_str}\n"
                
                text += "\n"
        
        if not has_connections:
            text = (
                "🔌 <b>Активных подключений не найдено</b>\n\n"
                "Подключаться будут логироваться автоматически при использовании VPN"
            )
        
        text += f"\n<i>ℹ️ Максимум одновременных подключений: {MAX_CONCURRENT_CONNECTIONS}</i>"
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'command_my_connections error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении информации о подключениях", parse_mode=None)


async def admin_connection_stats(message: Message) -> None:
    """
    Команда администратора для просмотра статистики подключений
    """
    try:
        if not admin_tlg or message.from_user.id != admin_tlg:
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return
        
        from core.sql.base import KeyConnection
        from sqlalchemy import func
        from sqlalchemy.orm import Session
        from core.sql.engine import engine
        
        # Получаем статистику
        with Session(engine) as s:
            total_connections = s.query(func.count(KeyConnection.id)).scalar() or 0
            
            # Активные подключения (за последние 30 минут)
            cutoff_time = datetime.now() - timedelta(minutes=30)
            active_connections = s.query(func.count(KeyConnection.id)).filter(
                KeyConnection.last_activity >= cutoff_time,
                KeyConnection.status == 'active'
            ).scalar() or 0
            
            # Уникальные IP адреса
            unique_ips = s.query(func.count(func.distinct(KeyConnection.ip_address))).scalar() or 0
        
        text = (
            "<b>🔌 Статистика подключений (администратор)</b>\n\n"
            f"📊 Всего подключений: {total_connections}\n"
            f"🟢 Активных за 30 минут: {active_connections}\n"
            f"🌐 Уникальных IP: {unique_ips}\n\n"
            f"⚙️ Лимит одновременных подключений: {MAX_CONCURRENT_CONNECTIONS}"
        )
        
        await message.answer(text)
        
    except Exception as e:
        logger.log('error', f'admin_connection_stats error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении статистики", parse_mode=None)


async def admin_block_connection(message: Message, connection_id: int, reason: str = None) -> bool:
    """
    Администратор может заблокировать подозрительное подключение
    
    :param message: Объект сообщения
    :param connection_id: ID подключения
    :param reason: Причина блокировки
    :return: bool успешность
    """
    try:
        if not admin_tlg or message.from_user.id != admin_tlg:
            return False
        
        result = await block_connection(connection_id=connection_id)
        
        if result:
            logger.log('info', f'Admin {message.from_user.id} blocked connection {connection_id}: {reason}')
            await message.answer(
                f"✅ Подключение #{connection_id} заблокировано\n"
                f"Причина: {reason or 'Не указана'}",
                parse_mode=None
            )
        else:
            await message.answer("❌ Не удалось заблокировать подключение", parse_mode=None)
        
        return result
        
    except Exception as e:
        logger.log('error', f'admin_block_connection error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при блокировке подключения", parse_mode=None)
        return False
