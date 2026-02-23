"""
Модуль кеширования для статистики серверов.
Кеширует данные на указанное время (TTL).
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Dict


class CacheEntry:
    """Элемент кеша"""
    def __init__(self, data: Any, ttl_seconds: int):
        self.data = data
        self.cached_at = datetime.now()
        self.ttl_seconds = ttl_seconds

    def is_expired(self) -> bool:
        """Проверить, истекло ли время жизни"""
        return (datetime.now() - self.cached_at).total_seconds() > self.ttl_seconds


class SimpleCache:
    """
    Простой ин-мемори кеш с TTL.
    """
    def __init__(self, default_ttl: int = 300):
        """
        :param default_ttl: Время жизни кеша по умолчанию (секунды)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl

    async def get(self, key: str, fetch_func=None, ttl: int = None) -> Optional[Any]:
        """
        Получить значение из кеша.
        Если ключа нет или он истек, вызвать fetch_func и сохранить результат.

        :param key: Ключ
        :param fetch_func: Функция для получения данных (async)
        :param ttl: Время жизни (секунды), по умолчанию self.default_ttl
        :return: Данные или None
        """
        ttl = ttl or self.default_ttl

        # Проверяем кеш
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                return entry.data
            else:
                # Удаляем истекший
                del self._cache[key]

        # Если есть fetch_func, получаем данные
        if fetch_func:
            data = await fetch_func()
            self._cache[key] = CacheEntry(data, ttl)
            return data

        return None

    async def set(self, key: str, data: Any, ttl: int = None) -> None:
        """
        Сохранить значение в кеш.

        :param key: Ключ
        :param data: Данные
        :param ttl: Время жизни (секунды)
        """
        ttl = ttl or self.default_ttl
        self._cache[key] = CacheEntry(data, ttl)

    async def delete(self, key: str) -> bool:
        """
        Удалить ключ из кеша.

        :param key: Ключ
        :return: True если ключ был удален
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self) -> None:
        """Очистить весь кеш"""
        self._cache.clear()

    async def cleanup_expired(self) -> int:
        """
        Очистить истекшие ключи.

        :return: Количество удаленных ключей
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    def __len__(self) -> int:
        return len(self._cache)

    def __repr__(self) -> str:
        return f"SimpleCache(entries={len(self._cache)}, default_ttl={self.default_ttl})"


# Глобальный кеш для статистики серверов
server_stats_cache = SimpleCache(default_ttl=300)  # 5 минут

# Кеш для пинга серверов (короткий TTL)
server_ping_cache = SimpleCache(default_ttl=60)  # 1 минута
