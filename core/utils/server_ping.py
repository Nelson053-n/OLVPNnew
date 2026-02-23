"""
Утилита для измерения пинга до серверов Outline.
Использует aiohttp для асинхронных запросов.
"""
import asyncio
import aiohttp
import time
from typing import Dict, Optional


async def ping_server(api_url: str, timeout: int = 5) -> Dict:
    """
    Измерить пинг до сервера Outline.
    Пытается подключиться к API URL сервера.

    :param api_url: URL API сервера (https://ip:port)
    :param timeout: Таймаут запроса в секундах
    :return: dict со статистикой пинга
    """
    result = {
        'api_url': api_url,
        'latency_ms': None,
        'status_code': 0,
        'is_online': False,
        'error': None
    }

    try:
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            # Пытаемся сделать запрос к API Outline
            # Используем /status или просто корень
            async with session.get(
                f"{api_url}/status",
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False  # Игнорируем SSL ошибки для self-signed сертификатов
            ) as response:
                latency = (time.time() - start_time) * 1000  # мс

                result['latency_ms'] = round(latency, 2)
                result['status_code'] = response.status
                result['is_online'] = response.status in [200, 401, 403]  # 401/403 = сервер онлайн, но нужна авторизация

    except asyncio.TimeoutError:
        result['error'] = f'Timeout after {timeout}s'
        result['is_online'] = False

    except aiohttp.ClientError as e:
        # Сервер доступен но SSL ошибка - это нормально для Outline
        if 'SSL' in str(e) or 'certificate' in str(e).lower():
            result['is_online'] = True
            result['latency_ms'] = 0
            result['error'] = 'SSL (но сервер онлайн)'
        else:
            result['error'] = f'Client error: {str(e)}'
            result['is_online'] = False

    except Exception as e:
        result['error'] = f'Error: {str(e)}'
        result['is_online'] = False

    return result


async def ping_multiple_servers(servers: list) -> Dict[str, Dict]:
    """
    Измерить пинг до нескольких серверов параллельно.

    :param servers: Список серверов [{'name': 'nederland', 'api_url': '...'}, ...]
    :return: dict с результатами пинга по серверам
    """
    async def ping_with_name(server_info: dict):
        name = server_info.get('name', 'unknown')
        api_url = server_info.get('api_url', '')
        result = await ping_server(api_url)
        return name, result

    # Запускаем все пинги параллельно
    tasks = [ping_with_name(server) for server in servers]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Собираем результаты
    results = {}
    for item in results_list:
        if isinstance(item, Exception):
            # Если была ошибка при выполнении задачи
            results[f'error_{id(item)}'] = {
                'error': str(item),
                'is_online': False
            }
        else:
            name, result = item
            results[name] = result

    return results


async def get_server_response_time(api_url: str, timeout: int = 10) -> Optional[float]:
    """
    Получить время отклика сервера для API запроса.
    Отличается от ping тем, что измеряет время выполнения реального API вызова.

    :param api_url: URL API сервера
    :param timeout: Таймаут в секундах
    :return: Время отклика в мс или None
    """
    try:
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_url}/v1.0/status",
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False
            ) as response:
                await response.json()  # Читаем ответ
                return round((time.time() - start_time) * 1000, 2)

    except Exception:
        return None


if __name__ == "__main__":
    # Тест
    async def main():
        servers = [
            {'name': 'nederland', 'api_url': 'https://127.0.0.1:8080'},
            {'name': 'france', 'api_url': 'https://127.0.0.1:8081'},
        ]

        print("Тест пинга серверов...")
        results = await ping_multiple_servers(servers)

        for name, result in results.items():
            status = "🟢" if result['is_online'] else "🔴"
            latency = f"{result['latency_ms']} ms" if result['latency_ms'] else "N/A"
            print(f"{status} {name}: {latency}")

    asyncio.run(main())
