"""
Хендлер для управления логами бота.
Просмотр информации о логах, очистка, сжатие.
"""
import os
import shutil
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from logs.log_main import RotatingFileLogger
from core.settings import admin_tlg

router = Router()

# Проверяем наличие администратора
ADMIN_ID = int(admin_tlg) if admin_tlg else None


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


@router.callback_query(F.data == "logs_back")
async def callback_logs_back(callback: CallbackQuery):
    """Возврат назад (для интеграции с главным меню)"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    # Здесь можно добавить импорт и вызов главного меню
    await callback.message.answer("🔙 Возврат в главное меню...")
