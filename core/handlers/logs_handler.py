"""
Хендлер для управления логами бота.
Просмотр информации о логах, очистка, сжатие.
"""
import os
import shutil
from types import SimpleNamespace
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from logs.log_main import RotatingFileLogger
from core.handlers.admin_keys import create_admin_main_menu_keyboard
from core.settings import admin_tlg
from core.handlers.get_db import command_get_db
from core.handlers.get_log_payments import command_get_log_pay
from core.sql.function_db_user_payments.users_payments import get_all_user_payments
from core.sql.function_db_user_vpn.users_vpn import get_user_data_from_table_users

router = Router()

# Проверяем наличие администратора
ADMIN_ID = admin_tlg


class _MessageProxy:
    def __init__(self, message: Message, user_id: int):
        self._message = message
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = message.chat
        self.text = message.text

    def __getattr__(self, item):
        return getattr(self._message, item)


def _as_message_from_callback(callback: CallbackQuery) -> _MessageProxy:
    return _MessageProxy(callback.message, callback.from_user.id)


def get_disk_usage(path: str = '/') -> dict:
    """
    Получить информацию о использовании диска.

    :param path: Путь для проверки
    :return: dict с информацией (total, used, free, percent)
    """
    try:
        total, used, free = shutil.disk_usage(path)
        percent = (used / total) * 100
        return {
            'total_gb': total / (1024 ** 3),
            'used_gb': used / (1024 ** 3),
            'free_gb': free / (1024 ** 3),
            'percent': percent
        }
    except Exception:
        return {
            'total_gb': 0,
            'used_gb': 0,
            'free_gb': 0,
            'percent': 0
        }


def get_logs_info() -> dict:
    """
    Получить информацию о логах.

    :return: dict с информацией о логах
    """
    try:
        base_logger = RotatingFileLogger('logs/log_settings_base.json')
        payments_logger = RotatingFileLogger('logs/log_settings_payments.json')

        base_files = base_logger.get_log_files()
        payments_files = payments_logger.get_log_files()

        return {
            'base': {
                'files': len(base_files),
                'size_mb': base_logger.get_logs_size_mb(),
                'backup_count': base_logger.backup_count
            },
            'payments': {
                'files': len(payments_files),
                'size_mb': payments_logger.get_logs_size_mb(),
                'backup_count': payments_logger.backup_count
            },
            'total_size_mb': base_logger.get_logs_size_mb() + payments_logger.get_logs_size_mb()
        }
    except Exception:
        return {
            'base': {'files': 0, 'size_mb': 0, 'backup_count': 7},
            'payments': {'files': 0, 'size_mb': 0, 'backup_count': 7},
            'total_size_mb': 0
        }


def create_logs_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру для управления логами"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🗑️ Очистить старше 7 дней",
                callback_data="logs_clean_7"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Очистить старше 14 дней",
                callback_data="logs_clean_14"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Очистить старше 30 дней",
                callback_data="logs_clean_30"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Обновить информацию",
                callback_data="logs_refresh"
            )
        ],
        [
            InlineKeyboardButton(
                text="📄 Скачать логи",
                callback_data="logs_download"
            )
        ],
        [
            InlineKeyboardButton(
                text="💾 Скачать БД",
                callback_data="logs_db"
            )
        ],
        [
            InlineKeyboardButton(
                text="💳 Все платежи",
                callback_data="logs_all_payments"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="logs_back"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def format_size(size_mb: float) -> str:
    """Форматировать размер в человекочитаемый вид"""
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    elif size_mb >= 1:
        return f"{size_mb:.2f} MB"
    else:
        return f"{size_mb * 1024:.2f} KB"


@router.message(Command("logs"))
async def cmd_logs(message: Message):
    """
    Команда /logs - показать информацию о логах.
    Доступно только администратору.
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде")
        return

    logs_info = get_logs_info()
    disk_info = get_disk_usage('/')

    text = (
        "📊 <b>Информация о логах</b>\n\n"
        "📁 <b>Основные логи (base):</b>\n"
        f"  • Файлов: {logs_info['base']['files']}\n"
        f"  • Размер: {format_size(logs_info['base']['size_mb'])}\n"
        f"  • Хранение: {logs_info['base']['backup_count']} дней\n\n"
        "💳 <b>Логи платежей (payments):</b>\n"
        f"  • Файлов: {logs_info['payments']['files']}\n"
        f"  • Размер: {format_size(logs_info['payments']['size_mb'])}\n"
        f"  • Хранение: {logs_info['payments']['backup_count']} дней\n\n"
        f"📈 <b>Общий размер:</b> {format_size(logs_info['total_size_mb'])}\n\n"
        "💾 <b>Дисковое пространство:</b>\n"
        f"  • Всего: {disk_info['total_gb']:.2f} GB\n"
        f"  • Занято: {disk_info['used_gb']:.2f} GB ({disk_info['percent']:.1f}%)\n"
        f"  • Свободно: {disk_info['free_gb']:.2f} GB\n\n"
        "🔽 <b>Действия:</b>"
    )

    keyboard = create_logs_keyboard()

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(F.data.startswith("logs_clean_"))
async def callback_logs_clean(callback: CallbackQuery):
    """Обработка очистки логов"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    days = int(callback.data.split("_")[-1])

    await callback.answer("⏳ Очистка логов...")

    try:
        base_logger = RotatingFileLogger('logs/log_settings_base.json')
        payments_logger = RotatingFileLogger('logs/log_settings_payments.json')

        base_deleted = base_logger.cleanup_old_logs(force=True)
        payments_deleted = payments_logger.cleanup_old_logs(force=True)

        total_deleted = base_deleted + payments_deleted

        logs_info = get_logs_info()
        disk_info = get_disk_usage('/')

        text = (
            f"✅ <b>Очистка завершена!</b>\n\n"
            f"🗑️ <b>Удалено файлов:</b> {total_deleted}\n"
            f"  • Base: {base_deleted}\n"
            f"  • Payments: {payments_deleted}\n\n"
            f"📊 <b>Текущее состояние:</b>\n"
            f"  • Файлов логов: {logs_info['base']['files'] + logs_info['payments']['files']}\n"
            f"  • Общий размер: {format_size(logs_info['total_size_mb'])}\n"
            f"  • Свободно на диске: {disk_info['free_gb']:.2f} GB\n\n"
            f"📅 <b>Очищено логов старше:</b> {days} дней"
        )

        keyboard = create_logs_keyboard()

        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "logs_refresh")
async def callback_logs_refresh(callback: CallbackQuery):
    """Обновление информации о логах"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer("🔄 Обновление...")

    logs_info = get_logs_info()
    disk_info = get_disk_usage('/')

    text = (
        "📊 <b>Информация о логах</b>\n\n"
        "📁 <b>Основные логи (base):</b>\n"
        f"  • Файлов: {logs_info['base']['files']}\n"
        f"  • Размер: {format_size(logs_info['base']['size_mb'])}\n"
        f"  • Хранение: {logs_info['base']['backup_count']} дней\n\n"
        "💳 <b>Логи платежей (payments):</b>\n"
        f"  • Файлов: {logs_info['payments']['files']}\n"
        f"  • Размер: {format_size(logs_info['payments']['size_mb'])}\n"
        f"  • Хранение: {logs_info['payments']['backup_count']} дней\n\n"
        f"📈 <b>Общий размер:</b> {format_size(logs_info['total_size_mb'])}\n\n"
        "💾 <b>Дисковое пространство:</b>\n"
        f"  • Всего: {disk_info['total_gb']:.2f} GB\n"
        f"  • Занято: {disk_info['used_gb']:.2f} GB ({disk_info['percent']:.1f}%)\n"
        f"  • Свободно: {disk_info['free_gb']:.2f} GB\n\n"
        "🔽 <b>Действия:</b>"
    )

    keyboard = create_logs_keyboard()

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(F.data == "logs_download")
async def callback_logs_download(callback: CallbackQuery):
    """Скачать файл логов платежей"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await command_get_log_pay(_as_message_from_callback(callback))


@router.callback_query(F.data == "logs_db")
async def callback_logs_db(callback: CallbackQuery):
    """Скачать файл БД"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await command_get_db(_as_message_from_callback(callback))


@router.callback_query(F.data == "logs_all_payments")
async def callback_logs_all_payments(callback: CallbackQuery):
    """Вывести все платежи из БД"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer("⏳ Собираю все платежи...")

    try:
        payments = await get_all_user_payments()

        if not payments:
            await callback.message.answer("💳 Платежи не найдены", parse_mode=None)
            return

        lines = [f"<b>💳 Все платежи ({len(payments)})</b>\n"]

        for index, pay in enumerate(payments, 1):
            account_id = getattr(pay, 'account_id', None)
            user_name = "Unknown"
            if account_id is not None:
                try:
                    user = await get_user_data_from_table_users(account=int(account_id))
                    if user and getattr(user, 'account_name', None):
                        user_name = user.account_name
                except Exception:
                    pass

            paykey = getattr(pay, 'paykey', '-') or '-'
            time_added = getattr(pay, 'time_added', None)
            time_str = time_added.strftime('%d.%m.%Y %H:%M') if time_added else '-'

            lines.append(
                f"<b>{index}.</b> <code>{account_id}</code> | <b>{user_name}</b>\n"
                f"   Время: {time_str}\n"
                f"   PayKey: <code>{paykey}</code>"
            )

        # Отправляем частями, чтобы не превысить лимит Telegram
        chunk = []
        current_len = 0
        for line in lines:
            line_len = len(line) + 1
            if current_len + line_len > 3800 and chunk:
                await callback.message.answer("\n".join(chunk), parse_mode='HTML')
                chunk = [line]
                current_len = line_len
            else:
                chunk.append(line)
                current_len += line_len

        if chunk:
            await callback.message.answer("\n".join(chunk), parse_mode='HTML')

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при получении платежей: {e}", parse_mode=None)


@router.callback_query(F.data == "logs_back")
async def callback_logs_back(callback: CallbackQuery):
    """Возврат назад (для интеграции с главным меню)"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        text="<b>🛠 Админ-разделы</b>\n\nВыберите нужный раздел:",
        parse_mode=ParseMode.HTML,
        reply_markup=create_admin_main_menu_keyboard(),
    )
