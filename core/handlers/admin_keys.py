"""
Раздел админ-команд для операций с ключами.
"""
import traceback

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def _is_admin(user_id: int) -> bool:
    return bool(admin_tlg) and user_id == int(admin_tlg)


def create_admin_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_open_start")],
            [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_open_stats")],
            [InlineKeyboardButton(text="📁 Управление логами", callback_data="admin_open_logs")],
            [InlineKeyboardButton(text="🔑 Ключи", callback_data="admin_open_keys")],
        ]
    )


def create_admin_keys_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Выдать промоключ", callback_data="admin_keys_promo")],
            [InlineKeyboardButton(text="🎉 Рассылка тестовых ключей", callback_data="admin_keys_testkey")],
            [InlineKeyboardButton(text="📋 Активные ключи", callback_data="admin_keys_active")],
            [InlineKeyboardButton(text="ℹ️ Информация о ключе", callback_data="admin_keys_keyinfo_help")],
            [InlineKeyboardButton(text="🔒 Блокировка просроченных ключей", callback_data="admin_keys_massblock")],
            [InlineKeyboardButton(text="🔄 Перенос между серверами", callback_data="admin_keys_migrate")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main_menu")],
        ]
    )


async def command_keys(message: Message) -> None:
    """Показать раздел админ-команд для ключей."""
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        text = (
            "<b>🔑 Раздел: Ключи</b>\n\n"
            "Здесь собраны команды управления ключами.\n"
            "Для пункта \"Информация о ключе\" используйте формат:\n"
            "<code>/keyinfo USER_ID</code>"
        )
        await message.answer(text=text, parse_mode='HTML', reply_markup=create_admin_keys_keyboard())
    except Exception as e:
        logger.log('error', f'command_keys error: {e}\n{traceback.format_exc()}')
        await message.answer('❌ Ошибка открытия раздела ключей', parse_mode=None)


async def callback_admin_main_menu(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        text="<b>🛠 Админ-разделы</b>\n\nВыберите нужный раздел:",
        parse_mode='HTML',
        reply_markup=create_admin_main_menu_keyboard(),
    )


async def callback_admin_open_start(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer("🏠 Откройте главное меню командой /start", parse_mode=None)


async def callback_admin_open_stats(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    from core.handlers.bot_statistics import command_stats
    await command_stats(callback.message)


async def callback_admin_open_logs(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    from core.handlers.logs_handler import cmd_logs
    await cmd_logs(callback.message)


async def callback_admin_open_keys(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        text=(
            "<b>🔑 Раздел: Ключи</b>\n\n"
            "Выберите действие ниже.\n"
            "ℹ️ Информация о ключе: <code>/keyinfo USER_ID</code>"
        ),
        parse_mode='HTML',
        reply_markup=create_admin_keys_keyboard(),
    )


async def callback_admin_keys_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    data = callback.data or ""
    await callback.answer()

    if data == "admin_keys_promo":
        from core.handlers.give_promo import command_promo
        await command_promo(callback.message)
        return

    if data == "admin_keys_testkey":
        from core.handlers.test_key_broadcast import command_testkey
        await command_testkey(callback.message, state)
        return

    if data == "admin_keys_active":
        from core.handlers.active_keys import command_active_keys
        await command_active_keys(callback.message)
        return

    if data == "admin_keys_keyinfo_help":
        await callback.message.answer(
            "ℹ️ Использование: <code>/keyinfo USER_ID</code>",
            parse_mode='HTML'
        )
        return

    if data == "admin_keys_massblock":
        from core.handlers.mass_block import command_mass_block
        await command_mass_block(callback.message)
        return

    if data == "admin_keys_migrate":
        from core.handlers.migrate_server import command_migrate_server
        await command_migrate_server(callback.message, state)
        return
