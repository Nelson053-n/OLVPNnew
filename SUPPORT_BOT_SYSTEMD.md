# Настройка systemd для автозапуска бота техподдержки

## Шаг 1: Подготовка systemd сервиса

Файл `olvpn-support-bot.service` уже существует в проекте.

### Отредактируйте параметры под вашу систему

```bash
# Откройте файл
nano olvpn-support-bot.service
```

Замените следующие значения:

```ini
# Было:
User=YOUR_USER
Group=YOUR_GROUP
WorkingDirectory=/path/to/OLVPNnew
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python /path/to/OLVPNnew/support_bot.py

# Стало (пример):
User=root
Group=root
WorkingDirectory=/root/OLVPNnew
Environment="PATH=/root/OLVPNnew/venv/bin"
ExecStart=/root/OLVPNnew/venv/bin/python /root/OLVPNnew/support_bot.py
```

## Шаг 2: Установка сервиса

```bash
# Скопируйте файл в systemd
sudo cp olvpn-support-bot.service /etc/systemd/system/

# Перезагрузите конфигурацию systemd
sudo systemctl daemon-reload

# Включите автозапуск
sudo systemctl enable olvpn-support-bot.service
```

## Шаг 3: Управление сервисом

### Запуск
```bash
sudo systemctl start olvpn-support-bot
```

### Остановка
```bash
sudo systemctl stop olvpn-support-bot
```

### Перезапуск
```bash
sudo systemctl restart olvpn-support-bot
```

### Проверка статуса
```bash
sudo systemctl status olvpn-support-bot
```

Вы должны увидеть:
```
● olvpn-support-bot.service - OLVPN Support Bot - Telegram Support Service
     Loaded: loaded (/etc/systemd/system/olvpn-support-bot.service; enabled)
     Active: active (running) since ...
```

## Шаг 4: Просмотр логов

### Через journalctl
```bash
# Последние логи
sudo journalctl -u olvpn-support-bot -n 50

# Следить за логами в реальном времени
sudo journalctl -u olvpn-support-bot -f

# Логи за сегодня
sudo journalctl -u olvpn-support-bot --since today
```

### Проверка уведомлений

После запуска сервиса проверьте Telegram:
- Вы должны получить сообщение "🟢 Бот техподдержки запущен"
- Если нет - проверьте логи

## Шаг 5: Проверка автозапуска

```bash
# Проверьте, что сервис включен
sudo systemctl is-enabled olvpn-support-bot

# Должно вывести: enabled
```

### Тест автозапуска

```bash
# Перезагрузите сервер
sudo reboot

# После перезагрузки проверьте
sudo systemctl status olvpn-support-bot

# Должен быть active (running)
```

## Одновременный запуск с основнымботом

Оба бота могут работать одновременно:

```bash
# Основной бот VPN
sudo systemctl start olvpn

# Бот техподдержки
sudo systemctl start olvpn-support-bot

# Проверка обоих
sudo systemctl status olvpn
sudo systemctl status olvpn-support-bot
```

## Типичные проблемы

### Сервис не запускается

```bash
# Проверьте логи
sudo journalctl -u olvpn-support-bot -n 100

# Проверьте права на файлы
ls -la /root/OLVPNnew/support_bot.py
ls -la /root/OLVPNnew/.env
```

### Бот не получает токен

```bash
# Проверьте .env файл
cat /root/OLVPNnew/.env | grep SUPPORT_BOT_TOKEN

# Или
cat /root/OLVPNnew/core/TEMP.env | grep SUPPORT_BOT_TOKEN
```

### Нет уведомления администратору

1. **Проверьте:** Сервис запущен?
   ```bash
   sudo systemctl status olvpn-support-bot
   ```

2. **Проверьте:** Логи на ошибки
   ```bash
   sudo journalctl -u olvpn-support-bot -n 50
   ```

3. **Проверьте:** ADMIN_TLG правильный?
   ```bash
   cat /root/OLVPNnew/.env | grep ADMIN_TLG
   ```

## Удаление сервиса

Если нужно удалить:

```bash
# Остановите и отключите
sudo systemctl stop olvpn-support-bot
sudo systemctl disable olvpn-support-bot

# Удалите файл сервиса
sudo rm /etc/systemd/system/olvpn-support-bot.service

# Перезагрузите systemd
sudo systemctl daemon-reload
```

## Мониторинг

### Скрипт для проверки работы обоих ботов

Создайте файл `check_bots.sh`:

```bash
#!/bin/bash
echo "=== Статус основного бота ==="
sudo systemctl status olvpn --no-pager | head -n 5

echo ""
echo "=== Статус бота техподдержки ==="
sudo systemctl status olvpn-support-bot --no-pager | head -n 5

echo ""
echo "=== Последние логи техподдержки ==="
sudo journalctl -u olvpn-support-bot -n 5 --no-pager
```

Сделайте исполняемым:
```bash
chmod +x check_bots.sh
./check_bots.sh
```

---

**Дата:** 20 декабря 2025  
**Версия:** 1.0
