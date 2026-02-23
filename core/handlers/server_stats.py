"""
Команда для просмотра статистики по серверам Outline.
С кешированием, асинхронными запросами и пингом.
"""
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import asyncio
import traceback
import aiohttp
import time
from datetime import datetime

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager, get_name_all_active_server_ol, get_server_display_name
from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys
from core.utils.cache import server_stats_cache, server_ping_cache
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def ping_outline_server(api_url: str, timeout: int = 5) -> dict:
    """
    Проверка доступности сервера Outline.
    Пытается подключиться к API и проверить статус.
    """
    result = {
        'latency_ms': None,
        'is_online': False,
        'error': None
    }

    try:
        start = time.time()
        async with aiohttp.ClientSession() as session:
            # Пробуем сделать запрос к API Outline
            async with session.get(
                api_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False
            ) as resp:
                latency = (time.time() - start) * 1000
                # 200 = OK, 401/403 = сервер работает (нужна авторизация)
                result['is_online'] = resp.status in [200, 401, 403]
                result['latency_ms'] = round(latency, 2)
    except asyncio.TimeoutError:
        result['error'] = 'Timeout'
    except Exception as e:
        result['error'] = str(e)

    return result


async def fetch_server_data(server: str, all_keys: list) -> dict:
    """
    Получить данные по серверу (асинхронно).
    """
    try:
        loop = asyncio.get_event_loop()

        # Получаем данные с сервера Outline
        olm_data = await loop.run_in_executor(
            None,
            lambda: _get_ol_data(server)
        )

        # Считаем ключи из БД
        db_keys = [k for k in all_keys if k.region_server == server]
        active_db_keys = sum(1 for k in db_keys if k.premium)

        # Пинг (кешируется)
        ping_result = await server_ping_cache.get(
            f"ping_{server}",
            lambda: ping_outline_server(olm_data.get('api_url', '')),
            ttl=60
        )

        return {
            'server': server,
            'display_name': get_server_display_name(server),
            'total_keys': olm_data['total_keys'],
            'active_db_keys': active_db_keys,
            'total_traffic_gb': olm_data['total_traffic_gb'],
            'latency_ms': ping_result.get('latency_ms'),
            'is_online': ping_result.get('is_online', False),
            'error': None
        }

    except Exception as e:
        logger.log('error', f'Error fetching data for {server}: {e}')
        return {
            'server': server,
            'display_name': get_server_display_name(server),
            'total_keys': 0,
            'active_db_keys': 0,
            'total_traffic_gb': 0,
            'latency_ms': None,
            'is_online': False,
            'error': str(e)
        }


def _get_ol_data(server: str) -> dict:
    """
    Получить данные с сервера Outline (синхронно, для executor).
    """
    try:
        olm = OutlineManager(region_server=server)
        server_keys = olm._client.get_keys()

        total_keys = len(server_keys) if server_keys else 0

        # Считаем трафик
        total_traffic_bytes = 0
        if server_keys:
            for sk in server_keys:
                used = getattr(sk, 'used_bytes', 0) or 0
                total_traffic_bytes += used

        return {
            'total_keys': total_keys,
            'total_traffic_gb': total_traffic_bytes / (1024 ** 3),
            'api_url': olm._client._api_url
        }
    except Exception as e:
        logger.log('warning', f'Outline API error for {server}: {e}')
        return {
            'total_keys': 0,
            'total_traffic_gb': 0,
            'api_url': ''
        }


async def get_cached_server_stats(all_keys: list) -> list:
    """
    Получить кешированную статистику серверов.
    """
    async def fetch_all():
        all_servers = get_name_all_active_server_ol()

        # Параллельный запрос ко всем серверам
        tasks = [fetch_server_data(server, all_keys) for server in all_servers]
        results = await asyncio.gather(*tasks)

        return list(results)

    # Кешируем на 5 минут
    return await server_stats_cache.get('server_stats', fetch_all, ttl=300)


async def command_server_stats(message: Message):
    """
    -- Админ-команда --
    /serverstats
    Показывает статистику по всем активным серверам Outline.
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        await message.answer('⏳ Загрузка статистики серверов...', parse_mode=None)

        # Получаем все ключи из БД
        all_keys = await get_all_user_keys()

        # Получаем кешированную статистику
        server_data_list = await get_cached_server_stats(all_keys)

        if not server_data_list:
            await message.answer('❌ Нет активных серверов', parse_mode=None)
            return

        # Формируем ответ
        lines = ['<b>📊 Статистика серверов Outline</b>\n']
        grand_total_traffic_gb = 0
        grand_total_keys = 0

        for idx, data in enumerate(server_data_list, 1):
            if data['error']:
                continue

            grand_total_traffic_gb += data['total_traffic_gb']
            grand_total_keys += data['active_db_keys']

            # Статус сервера
            if data['is_online']:
                status_icon = '🟢'
                latency_text = f"{data['latency_ms']} ms" if data['latency_ms'] else "N/A"
            else:
                status_icon = '🔴'
                latency_text = "Offline"

            lines.append(
                f'<b>{idx}.</b> {status_icon} {data["display_name"]}\n'
                f'   🔑 Ключи в БД: {data["active_db_keys"]}\n'
                f'   🌐 На сервере: {data["total_keys"]}\n'
                f'   📊 Трафик: {data["total_traffic_gb"]:.2f} GB\n'
                f'   ⏱️ Пинг: {latency_text}\n'
            )

        lines.append(f'\n<b>📈 Итого:</b>')
        lines.append(f'   Активных ключей: {grand_total_keys}')
        lines.append(f'   Общий трафик: {grand_total_traffic_gb:.2f} GB')

        # Добавляем кнопку для добавления сервера
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить сервер",
                    callback_data="serverstats_add"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="serverstats_refresh"
                )
            ]
        ])

        # Очищаем кеш при ручном запросе (опционально)
        # await server_stats_cache.clear()

        await message.answer('\n'.join(lines), parse_mode='HTML', reply_markup=keyboard)

    except Exception as e:
        logger.log('error', f'command_server_stats error: {e}\n{traceback.format_exc()}')
        await message.answer("❌ Ошибка при получении статистики", parse_mode=None)


async def callback_serverstats_add(callback: CallbackQuery):
    """Обработка кнопки добавления сервера"""
    if callback.from_user.id != int(admin_tlg):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    # Запускаем процесс добавления сервера
    from core.handlers.add_server import command_addserver
    await command_addserver(callback.message)


async def callback_serverstats_refresh(callback: CallbackQuery):
    """Обработка кнопки обновления статистики"""
    if callback.from_user.id != int(admin_tlg):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer("🔄 Обновление...")

    # Очищаем кеш
    await server_stats_cache.clear()
    await server_ping_cache.clear()

    # Перезапускаем команду
    await command_server_stats(callback.message)
