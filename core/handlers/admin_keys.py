"""
Раздел админ-команд для операций с ключами.
"""
import traceback
from types import SimpleNamespace

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.settings import admin_tlg
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def _is_admin(user_id: int) -> bool:
    return bool(admin_tlg) and user_id == int(admin_tlg)


class _MessageProxy:
    def __init__(self, message: Message, user_id: int):
        self._message = message
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = message.chat
        self.text = message.text

    def __getattr__(self, item):
        return getattr(self._message, item)


def _as_admin_message(callback: CallbackQuery) -> _MessageProxy:
    return _MessageProxy(callback.message, callback.from_user.id)


def create_admin_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_open_start")],
            [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_open_stats")],
            [InlineKeyboardButton(text="👥 Статистика рефералов", callback_data="admin_open_referrals")],
            [InlineKeyboardButton(text="📁 Управление логами", callback_data="admin_open_logs")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="admin_open_support")],
            [InlineKeyboardButton(text="🔑 Ключи", callback_data="admin_open_keys")],
            [InlineKeyboardButton(text="🧪 Тестовые данные", callback_data="admin_open_testdata")],
            [InlineKeyboardButton(text="🖥️ Сервера", callback_data="admin_open_servers")],
        ]
    )


def create_admin_keys_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Выдать промоключ", callback_data="admin_keys_promo")],
            [InlineKeyboardButton(text="🎉 Рассылка тестовых ключей", callback_data="admin_keys_testkey")],
            [InlineKeyboardButton(text="📋 Активные ключи", callback_data="admin_keys_active")],
            [InlineKeyboardButton(text="🔌 Статистика подключений", callback_data="admin_keys_connectstats")],
            [InlineKeyboardButton(text="💰 Редактировать цены", callback_data="admin_keys_editprice")],
            [InlineKeyboardButton(text="📈 Статистика продления", callback_data="admin_keys_renewalstats")],
            [InlineKeyboardButton(text="ℹ️ Информация о ключе", callback_data="admin_keys_keyinfo_help")],
            [InlineKeyboardButton(text="🔒 Блокировка просроченных ключей", callback_data="admin_keys_massblock")],
            [InlineKeyboardButton(text="🔄 Перенос между серверами", callback_data="admin_keys_migrate")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main_menu")],
        ]
    )


def create_admin_support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Очередь поддержки", callback_data="admin_support_queue")],
            [InlineKeyboardButton(text="📊 Статистика поддержки", callback_data="admin_support_stats")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main_menu")],
        ]
    )


def create_admin_testdata_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧪 Создать тестовые данные", callback_data="admin_testdata_seed")],
            [InlineKeyboardButton(text="📋 Отобразить тестовые данные", callback_data="admin_testdata_show")],
            [InlineKeyboardButton(text="🗑️ Удалить тестовые данные", callback_data="admin_testdata_unseed")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main_menu")],
        ]
    )


def create_admin_servers_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика серверов", callback_data="admin_servers_stats")],
            [InlineKeyboardButton(text="🌐 Доступность VPN серверов", callback_data="admin_servers_vpnstatus")],
            [InlineKeyboardButton(text="🖥️ Сервер бота", callback_data="admin_servers_host")],
            [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="admin_servers_add")],
            [InlineKeyboardButton(text="🗑️ Удалить сервер", callback_data="admin_servers_delete")],
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


async def command_support_admin(message: Message) -> None:
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        await message.answer(
            text="<b>🆘 Раздел: Поддержка</b>\n\nВыберите действие:",
            parse_mode='HTML',
            reply_markup=create_admin_support_keyboard(),
        )
    except Exception as e:
        logger.log('error', f'command_support_admin error: {e}\n{traceback.format_exc()}')
        await message.answer('❌ Ошибка открытия раздела поддержки', parse_mode=None)


async def command_testdata(message: Message) -> None:
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        await message.answer(
            text="<b>🧪 Раздел: Тестовые данные</b>\n\nВыберите действие:",
            parse_mode='HTML',
            reply_markup=create_admin_testdata_keyboard(),
        )
    except Exception as e:
        logger.log('error', f'command_testdata error: {e}\n{traceback.format_exc()}')
        await message.answer('❌ Ошибка открытия раздела тестовых данных', parse_mode=None)


async def command_servers(message: Message) -> None:
    try:
        if not _is_admin(message.from_user.id):
            await message.answer("❌ У вас нет доступа к этой команде", parse_mode=None)
            return

        await message.answer(
            text="<b>🖥️ Раздел: Сервера</b>\n\nВыберите действие:",
            parse_mode='HTML',
            reply_markup=create_admin_servers_keyboard(),
        )
    except Exception as e:
        logger.log('error', f'command_servers error: {e}\n{traceback.format_exc()}')
        await message.answer('❌ Ошибка открытия раздела серверов', parse_mode=None)


async def _show_test_data(message: Message) -> None:
    from datetime import datetime
    from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users, get_user_keys

    all_users = await get_all_records_from_table_users()
    test_users = [user for user in all_users if user.account_name and user.account_name.startswith('test_')]

    if not test_users:
        await message.answer('✅ Тестовые данные не найдены', parse_mode=None)
        return

    lines = [f"<b>🧪 Тестовые данные ({len(test_users)})</b>\n"]
    current_time = datetime.now()

    for index, user in enumerate(test_users[:30], 1):
        user_keys = await get_user_keys(account=user.account)
        active_keys = sum(1 for key in user_keys if key.date and key.date > current_time)
        lines.append(
            f"<b>{index}.</b> <code>{user.account}</code> | {user.account_name}\n"
            f"   Ключей: {len(user_keys)} | Активных: {active_keys}"
        )

    if len(test_users) > 30:
        lines.append(f"\n... и ещё {len(test_users) - 30}")

    await message.answer("\n".join(lines), parse_mode='HTML')


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
    msg = _as_admin_message(callback)
    from core.handlers.bot_statistics import command_stats
    await command_stats(msg)


async def callback_admin_open_referrals(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    msg = _as_admin_message(callback)
    from core.handlers.referral_handler import command_referrals_admin
    await command_referrals_admin(msg)


async def callback_admin_open_logs(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    msg = _as_admin_message(callback)
    from core.handlers.logs_handler import cmd_logs
    await cmd_logs(msg)


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


async def callback_admin_open_support(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        text="<b>🆘 Раздел: Поддержка</b>\n\nВыберите действие:",
        parse_mode='HTML',
        reply_markup=create_admin_support_keyboard(),
    )


async def callback_admin_open_testdata(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        text="<b>🧪 Раздел: Тестовые данные</b>\n\nВыберите действие:",
        parse_mode='HTML',
        reply_markup=create_admin_testdata_keyboard(),
    )


async def callback_admin_open_servers(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        text="<b>🖥️ Раздел: Сервера</b>\n\nВыберите действие:",
        parse_mode='HTML',
        reply_markup=create_admin_servers_keyboard(),
    )


async def callback_admin_keys_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    data = callback.data or ""
    await callback.answer()
    msg = _as_admin_message(callback)

    if data == "admin_keys_promo":
        from core.handlers.give_promo import command_promo
        await command_promo(msg)
        return

    if data == "admin_keys_testkey":
        from core.handlers.test_key_broadcast import command_testkey
        await command_testkey(msg, state)
        return

    if data == "admin_keys_active":
        from core.handlers.active_keys import command_active_keys
        await command_active_keys(msg)
        return

    if data == "admin_keys_connectstats":
        from core.handlers.connection_limiter import admin_connection_stats
        await admin_connection_stats(msg)
        return

    if data == "admin_keys_editprice":
        from core.handlers.edit_price import editprice_handler
        await editprice_handler(msg, state)
        return

    if data == "admin_keys_renewalstats":
        try:
            from core.handlers.renewal_handler import admin_renewal_stats
            await admin_renewal_stats(msg)
        except Exception as e:
            logger.log('error', f'admin_keys_renewalstats error: {e}\n{traceback.format_exc()}')
            await callback.message.answer('❌ Ошибка при открытии статистики продления', parse_mode=None)
        return

    if data == "admin_keys_keyinfo_help":
        await callback.message.answer(
            "ℹ️ Использование: <code>/keyinfo USER_ID</code>",
            parse_mode='HTML'
        )
        return

    if data == "admin_keys_massblock":
        from core.handlers.mass_block import command_mass_block
        await command_mass_block(msg)
        return

    if data == "admin_keys_migrate":
        from core.handlers.migrate_server import command_migrate_server
        await command_migrate_server(msg, state)
        return


async def callback_admin_support_action(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    data = callback.data or ""
    await callback.answer()
    msg = _as_admin_message(callback)

    if data == "admin_support_queue":
        from core.handlers.support_handler import admin_support_queue
        await admin_support_queue(msg)
        return

    if data == "admin_support_stats":
        from core.handlers.support_handler import admin_support_stats
        await admin_support_stats(msg)
        return


async def callback_admin_testdata_action(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    data = callback.data or ""
    await callback.answer()
    msg = _as_admin_message(callback)

    if data == "admin_testdata_seed":
        from core.handlers.seed_test_data import command_seed
        await command_seed(msg)
        return

    if data == "admin_testdata_show":
        await _show_test_data(msg)
        return

    if data == "admin_testdata_unseed":
        from core.handlers.unseed_test_data import command_unseed
        await command_unseed(msg)
        return


async def callback_admin_servers_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return

    data = callback.data or ""
    await callback.answer()
    msg = _as_admin_message(callback)

    if data == "admin_servers_stats":
        from core.handlers.server_stats import command_server_stats
        await command_server_stats(msg)
        return

    if data == "admin_servers_vpnstatus":
        from core.handlers.vpn_status_handler import command_vpn_status
        await command_vpn_status(msg)
        return

    if data == "admin_servers_host":
        from core.handlers.server_host_stats import command_server_host_stats
        await command_server_host_stats(msg)
        return

    if data == "admin_servers_add":
        from core.handlers.add_server import command_addserver
        await command_addserver(msg, state)
        return

    if data == "admin_servers_delete":
        from core.handlers.delete_server import deleteserver_handler
        await deleteserver_handler(msg)
        return
