# 📚 Документация бота Outline VPN

## 📖 Содержание
1. [Быстрый старт](#быстрый-старт)
2. [Команды администратора](#команды-администратора)
3. [Архитектура и вопросы разработки](#архитектура)
4. [Установка на сервер](#установка-на-сервер)

---

## 🚀 Быстрый старт

### Локально (Windows/Mac/Linux)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Nelson053-n/OneYearVpb.git
cd OneYearVpb

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Настроить переменные окружения
# Скопируйте .env.example в .env и заполните значения:
cp .env.example .env
# Отредактируйте .env:
# - API_KEY_TLG=ваш_токен_бота
# - ADMIN_TLG=ваш_telegram_id
# - YOUKASSA_ID=ваш_merchant_id
# - YOUKASSA_SECRET=ваш_secret

# 4. Запустить
python main.py
```

### На Linux сервере (systemd)

```bash
# 1. Клонировать и подготовить
git clone https://github.com/Nelson053-n/OneYearVpb.git
cd OneYearVpb

# 2. Создать systemd сервис
sudo cp olvpn-support-bot.service /etc/systemd/system/

# 3. Включить автозапуск
sudo systemctl daemon-reload
sudo systemctl enable olvpn-support-bot
sudo systemctl start olvpn-support-bot

# 4. Проверить статус
sudo systemctl status olvpn-support-bot
```

---

## 👨‍💼 Команды администратора

### 🎁 Программа лояльности

**`/promo`** - Выдать промо-ключи пользователям

Показывает пользователей, которые:
- ❌ Не имеют активных платных ключей
- ❌ Не имеют активных промо ключей

**Действия:**
```
Администратор → /promo
    ↓
📋 Список пользователей (без платных и без промо)
    ↓
Вариант 1: Нажать 🎁 для одного пользователя
    ↓
Вариант 2: Нажать 📢 Выдать ВСЕ для массовой раздачи
    ↓
Выбрать сервер (Nederland, Germany, France и т.д.)
    ↓
✅ Промо на 7 дней выдано всем подходящим пользователям
```

### 🔒 Управление ключами

**`/keyinfo <user_id>`** - Информация о ключах пользователя

Показывает:
- 📊 Трафик за 30 дней (в ГБ)
- 🌍 Регион сервера
- ✅ Статус активности ключа
- 📅 Дата окончания подписки

При клике на "🔒 Заблокировать ключ":
```
Админ видит: ✅ Да / ✍️ С причиной / ❌ Отмена
    ↓
Выбирает действие:
- ✅ Да → Блокировка без причины
- ✍️ С причиной → Ввод причины блокировки
- ❌ Отмена → Отмена операции
    ↓
Ключ удалён с Outline сервера
Статус в БД изменён на inactive
Пользователю отправлено уведомление об окончании подписки
Причина блокировки сохранена в таблицу BlockHistory
```

**`/activekeys`** - Список активных пользователей

Выводит:
- 🟢 Ключи ещё действительны более 3 дней
- 🟡 Ключи заканчиваются через 2-3 дня
- 🔴 Ключи заканчиваются завтра/сегодня

Сортировка: по дате окончания (ближайшие сначала)

**`/massblock`** - Блокировка всех просроченных ключей

Usage:
```bash
/massblock
```

Result: `✅ Массовая проверка выполнена. 🔒 Заблокировано просроченных ключей: 5`

### 💰 Платежи и учёт

**`/findpay <user_id>`** - Поиск платежей пользователя

Пример:
```bash
/findpay 123456789
```

Выводит все успешные платежи в YooKassa и локальные записи в БД.

**`/get_log_pay`** - Получить логи платежей (файл)

**`/get_db`** - Скачать базу данных SQLite

### 🌐 Серверы Outline

**`/addserver`** - Добавить новый сервер (интерактивно)

```
/addserver
    ↓
1️⃣ Выберите страну (кнопками)
    ↓
2️⃣ Введите регион название (например: germany)
    ↓
3️⃣ Введите API URL (например: https://1.2.3.4:443/key)
    ↓
4️⃣ Введите SHA256 сертификата (64 символа)
    ↓
✅ Сервер добавлен. Нужен перезапуск бота для активации.
```

**`/deleteserver`** - Удалить сервер

Удаляет сервер из конфигурации. Перезапуск бота обязателен.

**`/serverstats`** - Статистика нагрузки серверов

Показывает:
- Количество активных ключей на каждом сервере
- Объём трафика за последние 30 дней (ГБ)
- Процент загруженности

**`/migrateserver <from> <to>`** - Перенести пользователей между серверами

```bash
/migrateserver nederland germany
```

Автоматически:
- Удаляет ключи со старого сервера
- Создаёт новые ключи на новом сервере
- Уведомляет пользователей
- Сохраняет дату истечения и другие параметры

### 📝 Цены и настройки

**`/editprice`** - Изменить цены (интерактивно)

```
/editprice
    ↓
📊 Текущие цены:
 - День: 7₽
 - Неделя: 40₽
 - Месяц: 150₽
    ↓
Выберите период для редактирования
    ↓
Введите новую цену
    ↓
✅ Цена обновлена (без перезапуска)
```

### 🧪 Тестовые данные

**`/seed`** - Создать тестовых пользователей

Создаёт пользователя `test_XXXXX` с:
- 1 просроченный ключ (истёк вчера)
- 1 активный ключ (истекает через 1-3 часа)
- Запись о платеже в БД

```bash
/seed
/seed
/seed  # Можно создать несколько тестовых пользователей
```

**`/unseed`** - Удалить всех тестовых данных

```bash
/unseed
```

Удаляет всех пользователей с именем `test_*` и их ключи.

---

## 🏗️ Архитектура

### Структура проекта

```
OneYearVpb/
├── core/
│   ├── handlers/           # Обработчики команд
│   │   ├── give_promo.py   # Выдача промо ключей
│   │   ├── key_info.py     # Инфо о ключах
│   │   ├── mass_block.py   # Массовая блокировка
│   │   ├── add_server.py   # Добавление сервера
│   │   ├── migrate_server.py # Миграция пользователей
│   │   └── ...
│   ├── api_s/
│   │   ├── outline/        # API Outline
│   │   └── api_youkassa/   # Интеграция YooKassa
│   ├── sql/
│   │   ├── base.py         # ORM модели (Users, UserKey, BlockHistory)
│   │   └── function_db_user_vpn/
│   ├── templates/          # Jinja2 шаблоны (HTML)
│   ├── keyboards/          # Inline кнопки
│   ├── settings_prices.json # Цены на доступ
│   ├── check_time_subscribe.py # Фоновый процесс проверки подписок
│   └── bot.py              # Инициализация Dispatcher
├── outline_vpn/            # Модуль управления Outline (внешний)
├── logs/                   # Логи приложения
├── main.py                 # Точка входа (многопроцессность)
└── README.md
```

### Многопроцессная архитектура

Бот запускает **два параллельных процесса**:

1. **Процесс бота** (`run_bot()`)
   - Обрабатывает сообщения Telegram
   - Запускает обработчики команд
   - Обслуживает пользователей

2. **Процесс проверки** (`run_checker()`)
   - Запускает `check_time_subscribe.py`
   - Проверяет истечение подписок каждые 5 минут
   - Блокирует просроченные ключи
   - Уведомляет пользователей

### База данных (SQLite)

**Таблица `Users`** (основная информация):
- `account` (int, unique) - ID Telegram
- `account_name` (str) - Username (для логирования)
- `premium` (bool) - Есть ли активный ключ
- `date` (DateTime) - Дата окончания подписки
- `region_server` (str) - Регион текущего/последнего сервера

**Таблица `UserKey`** (новая система - поддержка нескольких ключей):
- `account` (FK) - ID пользователя
- `access_url` (str) - URL доступа к VPN
- `outline_id` (str) - Уникальный ID в Outline
- `region_server` (str) - На каком сервере создан ключ
- `premium` (bool) - Активный ли ключ
- `date` (DateTime) - Дата окончания
- `promo` (bool) - Промо ключ или платный?
- `created_at` (DateTime) - Когда создан

**Таблица `BlockHistory`** (история блокировок):
- `account` (int) - ID пользователя
- `admin_id` (int) - ID администратора
- `reason` (str) - Причина блокировки
- `key` (str) - Какой ключ заблокирован
- `timestamp` (DateTime) - Когда заблокирован

### Потоки данных

```
Пользователь → /start
    ↓
✅ Есть активный ключ? → Показать его
❌ Нет активного ключа? → Предложить купить
    ↓
Выбор длительности (день/неделя/месяц)
    ↓
Создание платежа в YooKassa
    ↓
Получение URL оплаты
    ↓
Пользователь платит → Вебхук от YooKassa
    ↓
OutlineManager создаёт ключ на Outline
    ↓
Ключ сохраняется в UserKey и Users (для совместимости)
    ↓
Пользователю отправляется ключ доступа
```

---

## 🖥️ Установка на сервер (подробно)

### Требования

- Linux (Ubuntu 20.04+)
- Python 3.9+
- Git

### Пошаговая инструкция

```bash
# 1. Обновить систему
sudo apt update && sudo apt upgrade -y

# 2. Установить зависимости
sudo apt install -y python3-pip python3-venv git

# 3. Создать директорию для бота
sudo mkdir -p /opt/olvpn
cd /opt/olvpn

# 4. Клонировать репозиторий
sudo git clone https://github.com/Nelson053-n/OneYearVpb.git .

# 5. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 6. Установить требования
pip install -r requirements.txt

# 7. Настроить .env файл
sudo nano .env
# Заполнить:
# API_KEY_TLG=ваш_токен
# ADMIN_TLG=ваш_telegram_id
# YOUKASSA_ID=merchant_id
# YOUKASSA_SECRET=secret

# 8. Установить systemd сервис
sudo cp olvpn-support-bot.service /etc/systemd/system/

# 9. Отредактировать пути в сервисе (если нужно)
sudo nano /etc/systemd/system/olvpn-support-bot.service

# 10. Запустить сервис
sudo systemctl daemon-reload
sudo systemctl enable olvpn-support-bot
sudo systemctl start olvpn-support-bot

# 11. Проверить статус
sudo systemctl status olvpn-support-bot

# 12. Просмотр логов
sudo journalctl -u olvpn-support-bot -f
```

### Обновление кода

```bash
cd /opt/olvpn
git fetch origin
git merge origin/newnew  # или нужная ветка
sudo systemctl restart olvpn-support-bot
```

### Резервная копия

```bash
# Создать архив
cd /opt
tar -czf olvpn-backup-$(date +%Y%m%d).tar.gz olvpn/

# Восстановить
tar -xzf olvpn-backup-20260218.tar.gz
```

---

## 🔧 Разработка

### Добавление новой команды администратора

1. **Создать обработчик** в `core/handlers/`:
```python
async def command_mycommand(message: Message) -> None:
    if not admin_tlg or message.from_user.id != int(admin_tlg):
        await message.answer("❌ Access denied", parse_mode=None)
        return
    
    # Ваша логика
    await message.answer("✅ Done", parse_mode=None)
```

2. **Зарегистрировать** в `core/bot.py`:
```python
from core.handlers.mycommand import command_mycommand
dp.message.register(command_mycommand, Command('mycommand'))
```

3. **Загрузить изменения**:
```bash
git add core/handlers/mycommand.py core/bot.py
git commit -m "Add command mycommand"
git push origin newnew
```

### Изменение текста ответа

Тексты хранятся в шаблонах (`core/templates/*.html`). Измените и сохраните - перезапуск не нужен!

### Работа с базой данных

```python
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    get_user_keys,
    add_user_key,
    delete_user_key_record,
)

# Получить всех пользователей
users = await get_all_records_from_table_users()

# Получить ключи пользователя
keys = await get_user_keys(account=user_id)

# Добавить новый ключ
await add_user_key(
    account=user_id,
    access_url=key_url,
    outline_id=outline_key_id,
    region_server='nederland',
    date_str='18.02.2026 - 23:59',
    promo=False
)
```

---

## ❓ Часто встречающиеся проблемы

### Бот не запускается

```bash
# Проверить логи
sudo journalctl -u olvpn-support-bot -n 50

# Проверить синтаксис
python3 -m py_compile core/handlers/*.py
```

### Ключи не создаются

- Проверить доступность Outline API
- Проверить правильность сертификата SHA256
- Посмотреть логи: `/get_log_pay` для платежей

### Пользователи закрыты, но не отправляются уведомления

- Проверить что пользователь не заблокировал бота
- Посмотреть логи в `logs/base/olvpnbot.log`

---

## 📞 Контакты и помощь

**Автор:** Nelson053  
**Email:** aksys.nel@gmail.com  
**GitHub:** https://github.com/Nelson053-n/OneYearVpb

**Latest Update:** февраль 18, 2026
