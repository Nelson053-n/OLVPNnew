# 📊 Анализ и предложения по улучшению

## 1. Статистика подключений (connection_limiter.py)

### 🔍 Текущее состояние

**Что отслеживается:**
- Всего подключений (за всё время)
- Активные подключения (за последние 30 минут)
- Уникальные IP адреса
- Лимит одновременных подключений (3)

**Таблица БД: `key_connections`**
```sql
CREATE TABLE key_connections (
    id INTEGER PRIMARY KEY,
    key_id INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    status TEXT,  -- 'active' | 'disconnected' | 'blocked'
    last_activity DATETIME,
    created_at DATETIME
)
```

### ⚠️ Проблемы

1. **Нет реального отслеживания подключений**
   - Outline API не предоставляет информацию о активных подключениях
   - Отслеживаем только логи подключений, а не реальные сессии
   - Статус "active" выставляется автоматически, но не обновляется

2. **Неточная статистика**
   - 30 минутный порог произвольный
   - Нет информации о том, кто реально использует VPN сейчас

3. **Медленная загрузка**
   - Запрос к БД с `func.count()` и `func.distinct()`
   - Нет индексов на полях `key_id`, `status`, `last_activity`

### ✅ Предлагаемые решения

#### Решение 1: Реальное отслеживание через Outline API

```python
# core/api_s/outline/outline_api.py
class OutlineManager:
    def get_transfer_stats(self, key_id: str) -> dict:
        """
        Получить статистику трафика по ключу
        Возвращает: bytes_used, last_access
        """
        key = self._client.get_key(key_id)
        return {
            'bytes_used': key.traffic_used,
            'last_access': key.last_access
        }
```

**Проблема:** Outline API не предоставляет информацию о активных подключениях в реальном времени.

#### Решение 2: Умное логирование с кешированием

```python
# core/handlers/connection_limiter.py
from functools import lru_cache
import asyncio

# Кеширование на 1 минуту
@lru_cache(maxsize=100)
async def get_cached_connection_stats(key_id: int, ttl: int = 60):
    """
    Кешированная статистика подключений
    """
    # Запрос к БД
    active = await count_active_connections(key_id)
    return {'active': active, 'cached_at': datetime.now()}
```

#### Решение 3: Heartbeat система

```python
# Клиент отправляет heartbeat каждые 10 секунд
async def update_heartbeat(key_id: int):
    await log_connection(
        key_id=key_id,
        ip_address="heartbeat",
        user_agent="heartbeat",
        is_heartbeat=True
    )

# Считаем активными тех, у кого heartbeat < 1 минуты
cutoff_time = datetime.now() - timedelta(minutes=1)
active = await count_heartbeats(key_id, cutoff_time)
```

**Проблема:** Требует модификации клиента (невозможно).

#### Решение 4: Статистика по трафику (РЕАЛИЗУЕМОЕ)

```python
async def get_traffic_stats(key_id: int) -> dict:
    """
    Статистика по трафику вместо подключений
    """
    # Запрос к Outline API
    stats = olm.get_key_transfer(key_id)
    return {
        'bytes_used': stats.bytes_used,
        'last_seen': stats.last_access,
        'is_active': (datetime.now() - stats.last_access) < timedelta(minutes=5)
    }
```

---

## 2. Статистика серверов (server_stats.py)

### 🔍 Текущее состояние

**Что отображается:**
- Количество пользователей на каждом сервере
- Количество активных ключей
- Нагрузка на сервер

**Проблемы:**
- Медленная загрузка (запросы к каждому серверу Outline)
- Нет кеширования
- Нет информации о пинге/времени отклика

### ✅ Предлагаемые решения

#### Решение 1: Кеширование статистики серверов

```python
# core/handlers/server_stats.py
from functools import lru_cache
from datetime import datetime, timedelta

# Глобальный кеш
_server_stats_cache = {
    'data': None,
    'cached_at': None,
    'ttl': 300  # 5 минут
}

async def get_cached_server_stats():
    """
    Кешированная статистика серверов (5 минут)
    """
    now = datetime.now()

    if (_server_stats_cache['data'] and
        _server_stats_cache['cached_at'] and
        (now - _server_stats_cache['cached_at']) < timedelta(seconds=_server_stats_cache['ttl'])):
        return _server_stats_cache['data']

    # Получаем свежую статистику
    stats = await fetch_server_stats()

    _server_stats_cache['data'] = stats
    _server_stats_cache['cached_at'] = now

    return stats
```

#### Решение 2: Асинхронные запросы к серверам

```python
# Вместо последовательных запросов
async def fetch_server_stats():
    servers = get_name_all_active_server_ol()

    # Последовательно (МЕДЛЕННО)
    for server in servers:
        olm = OutlineManager(server)
        stats = olm.get_server_stats()  # 2-3 секунды на запрос

    # Параллельно (БЫСТРО)
    async def get_server_load(server):
        olm = OutlineManager(server)
        return await asyncio.to_thread(olm.get_server_stats)

    results = await asyncio.gather(*[get_server_load(s) for s in servers])
    # Все запросы выполняются параллельно (2-3 секунды всего)
```

#### Решение 3: Пинг и время отклика

```python
# core/utils/server_ping.py
import asyncio
import aiohttp
import time

async def ping_server(api_url: str) -> dict:
    """
    Измерить пинг до сервера Outline
    """
    try:
        start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/health", timeout=5) as resp:
                latency = (time.time() - start) * 1000  # мс
                return {
                    'status': resp.status,
                    'latency_ms': round(latency, 2),
                    'is_online': resp.status == 200
                }
    except asyncio.TimeoutError:
        return {'status': 0, 'latency_ms': None, 'is_online': False}
    except Exception as e:
        return {'status': 0, 'latency_ms': None, 'is_online': False, 'error': str(e)}
```

#### Решение 4: Объединение с меню добавления сервера

```python
# Вместо отдельной команды /addserver
# Сделать кнопку в /serverstats

@router.callback_query(F.data == "serverstats_add")
async def callback_add_server(callback: CallbackQuery):
    """Добавить сервер из статистики"""
    await callback.answer()
    await callback.message.answer(
        "➕ <b>Добавить новый сервер</b>\n\n"
        "Выберите страну:",
        reply_markup=country_keyboard()
    )
```

---

## 3. Итоговый план улучшений

### Приоритет 1 (Кеширование)
```python
# 1. Добавить кеширование для server_stats (5 минут)
# 2. Добавить индексы в БД для connection_limiter
# 3. Использовать asyncio.gather для параллельных запросов
```

### Приоритет 2 (Пинг серверов)
```python
# 1. Создать core/utils/server_ping.py
# 2. Добавить ping в статистику серверов
# 3. Отображать latency_ms для каждого сервера
```

### Приоритет 3 (Объединение меню)
```python
# 1. Добавить кнопку "➕ Добавить сервер" в /serverstats
# 2. Убрать отдельную команду /addserver из меню
# 3. Переместить в inline клавиатуру
```

### Приоритет 4 (Статистика подключений)
```python
# 1. Изменить формулировку "Активных сейчас" → "Активных за 30 мин"
# 2. Добавить статистику по трафику из Outline API
# 3. Добавить "Последняя активность" для каждого ключа
```

---

## 📋 Конкретные изменения в код

### 1. Индексы для БД

```sql
-- core/sql/base.py
class KeyConnection(Base):
    __tablename__ = 'key_connections'

    # Добавить индексы:
    __table_args__ = (
        Index('ix_key_id', 'key_id'),
        Index('ix_status', 'status'),
        Index('ix_last_activity', 'last_activity'),
    )
```

### 2. Кеширование server_stats

```python
# core/handlers/server_stats.py
from functools import lru_cache
import asyncio

class ServerStatsCache:
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl

    async def get(self, key: str, fetch_func):
        if key in self.cache:
            data, cached_at = self.cache[key]
            if (datetime.now() - cached_at).total_seconds() < self.ttl:
                return data

        data = await fetch_func()
        self.cache[key] = (data, datetime.now())
        return data

server_stats_cache = ServerStatsCache(ttl=300)
```

### 3. Асинхронный пинг

```python
# core/handlers/server_stats.py
async def ping_server(api_url: str) -> float:
    """Измерить пинг до сервера в мс"""
    import aiohttp
    import time

    try:
        start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/health", timeout=5) as resp:
                return (time.time() - start) * 1000
    except:
        return None
```

---

**Дата:** 23 февраля 2026
**Статус:** Готово к реализации
