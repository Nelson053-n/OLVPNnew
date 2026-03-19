# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

Telegram-бот для продажи и управления ключами Outline VPN. Интеграции: aiogram 3+, SQLAlchemy 2+ (SQLite), YooKassa, Jinja2-шаблоны. Вся документация и UI на русском языке.

## Команды

```bash
# Установка зависимостей
pip install -r requerements.txt

# Запуск бота (два процесса: бот + проверка подписок)
python main.py

# Запуск support-бота (отдельный сервис)
python support_bot.py

# Тесты
pytest tests/
pytest tests/test_key_service.py -v
pytest tests/test_payment_service.py -v

# Линтинг и форматирование
black .
isort .
flake8
mypy .
```

## Стиль кода

- Длина строки: 120 символов (black, isort, flake8)
- Target: Python 3.11
- isort: профиль black, known_first_party: `core`, `logs`, `outline_vpn`
- flake8 игнорирует: E203, W503; для `__init__.py`: F401, F403; для `tests/*`: E501

## Архитектура

### Многопроцессная модель (`main.py`)
- **Процесс бота** (`run_bot()`) — aiogram dispatcher, обработка Telegram-сообщений
- **Процесс проверки** (`run_checker()`) — `core/check_time_subscribe.py`, цикл каждые 5 минут: удаляет просроченные ключи из Outline, обновляет БД, уведомляет пользователей

### Обработка callback'ов (`core/handlers/handler_keyboard.py`)
- `build_and_edit_message()` маршрутизирует все inline-кнопки через словарь `switch_dict`
- Обработчики в `core/handlers/handlers_keyboards/` возвращают кортежи `(text, InlineKeyboardMarkup)`
- Специальные callback'и (префиксы `give_promo_`, `confirm_block_key_` и др.) обрабатываются напрямую с извлечением ID
- FSMContext для многошаговых админ-команд (`/addserver`, `/deleteserver`, `/editprice`)

### БД: async def, но синхронные сессии
Функции в `core/sql/` объявлены как `async def`, но используют синхронные вызовы `Session()`. Это **намеренное** решение — не "исправлять" на async без обсуждения.

### Шаблоны
Все ответы пользователям — через Jinja2 HTML-шаблоны из `core/templates/`. Не хардкодить текст в обработчиках. Рендеринг: `create_answer_from_html()` из `core/utils/create_view.py`.

### Telegram edit_text
При вызове `callback.message.edit_text()` для сообщений с inline-клавиатурой **обязательно** указывать `reply_markup=None`, иначе Telegram API вернёт ошибку "message not modified".

## Ключевые конфигурационные файлы

- `.env` — секреты: `API_KEY_TLG`, `ADMIN_TLG`, `YOUKASSA_ID`, `YOUKASSA_SECRET` (загружается через `core/settings.py`, fallback на `core/TEMP.env`)
- `core/api_s/outline/settings_api_outline.json` — конфиг серверов Outline (api_url, cert_sha256, is_active, name_ru)
- `core/settings_prices.json` — цены (day/week/month/promo), обновляются через `/editprice` без перезапуска
- Флаги стран определяются в `core/handlers/add_server.py` через словарь `COUNTRY_FLAGS`

## Добавление нового обработчика

1. Создать функцию в `core/handlers/handlers_keyboards/`, возвращающую `(str, InlineKeyboardMarkup)`
2. Добавить case в `switch_dict` в `handler_keyboard.py`
3. Создать кнопку в `core/keyboards/` с соответствующим callback_data
4. Зарегистрировать в `core/bot.py` (для команд — в dispatcher)
5. При необходимости — создать шаблон в `core/templates/`

## Замена ключей

Callback формат: `rpl_key_<short_id>` — последние 8 символов UUID ключа. Полный поиск по БД для сопоставления.

## Тестовые данные

- `/seed` — создаёт тестового пользователя `test_XXXXX` с ключами на **реальном** Outline сервере
- `/unseed` — удаляет всех `test_*` пользователей и их ключи из Outline
