from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand, BotCommandScopeChat
import asyncio

from core.handlers.find_user_payments import command_findpay
from core.handlers.get_db import command_get_db
from core.handlers.message_to_admin import send_admin_message
from core.handlers.give_promo import command_promo
from core.handlers.active_keys import command_active_keys
from core.handlers.admin_block_reason import command_block_reason
from core.handlers.mass_block import command_mass_block
from core.handlers.seed_test_data import command_seed
from core.handlers.unseed_test_data import command_unseed
from core.handlers.server_stats import (
    command_server_stats,
    callback_serverstats_add,
    callback_serverstats_refresh,
)
from core.handlers.bot_statistics import command_stats
from core.handlers.bot_stats import command_stats as command_stats_new
from core.handlers.pin_disclaimer import pin_disclaimer_handler
from core.handlers.docs import command_docs
from core.handlers.referral_handler import (
    command_referral,
    command_referrals_admin,
)
from core.handlers.support_handler import (
    command_support,
    support_title_handler,
    support_category_handler,
    support_description_handler,
    command_support_my_tickets,
    admin_support_queue,
    admin_support_stats,
    SupportStates,
)
from core.handlers.vpn_status_handler import (
    command_vpn_status,
    admin_vpn_detailed_check,
)
from core.handlers.connection_limiter import (
    command_my_connections,
    admin_connection_stats,
)
from core.handlers.renewal_handler import (
    command_renewal_stats,
    admin_renewal_stats,
    admin_trigger_renewal_reminders,
)
from core.handlers.migrate_old_keys import (
    command_migrate,
    command_check_migration_status,
    command_fix_migration_dates,
    command_debug_keys,
    command_show_old_keys
)
from core.handlers.migrate_server import (
    command_migrate_server, 
    select_source_server,
    select_target_server,
    handle_migration_confirmation, 
    MigrateServerStates
)
from core.handlers.logs_handler import (
    cmd_logs,
    callback_logs_clean,
    callback_logs_refresh,
    callback_logs_back,
    callback_logs_download_db,
    callback_logs_download_logs,
    callback_logs_find_payment,
    callback_logs_test_data,
    callback_test_data,
)
from core.handlers.add_server import (
    command_addserver, 
    process_country_choice,
    process_country_ru_input,
    process_api_url_input, 
    process_cert_input,
    AddServerStates
)
from core.handlers.delete_server import (
    deleteserver_handler,
    confirm_delete_server,
    execute_delete_server,
    cancel_delete
)
from core.handlers.edit_price import (
    editprice_handler,
    select_period_to_edit,
    process_new_price,
    EditPriceStates
)
from core.handlers.test_key_broadcast import (
    command_testkey,
    process_testkey_server_choice,
    TestKeyStates
)
from core.handlers.replace_key import replace_key_handler
from core.settings import api_key_tlg, admin_tlg
from core.api_s.outline.outline_api import OutlineManager
from core.handlers.handler_keyboard import build_and_edit_message
from core.handlers.start import command_start

router: Router = Router()
olm = OutlineManager()
BOT_TOKEN = api_key_tlg
bot: Bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


async def setup_bot_commands(bot: Bot):
    """Установка команд для меню бота"""
    # Команды для обычных пользователей
    user_commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
    ]
    
    # Администрирование:
    admin_commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="stats", description="📊 Статистика бота"),
        BotCommand(command="logs", description="📁 Управление логами"),
        BotCommand(command="pindisclaimer", description="📌 Закрепить дисклеймер"),
        BotCommand(command="promo", description="🎁 Выдать промо-ключ"),
        BotCommand(command="testkey", description="🎉 Рассылка тестовых ключей"),
        BotCommand(command="activekeys", description="📋 Активные ключи"),
        BotCommand(command="massblock", description="🔒 Блокировка просроченных"),
        BotCommand(command="serverstats", description="📊 Статистика серверов"),
        BotCommand(command="migrateserver", description="🔄 Перенос между серверами"),
        BotCommand(command="vpnstatus", description="🌐 Статус VPN серверов"),
        BotCommand(command="supportqueue", description="📞 Очередь поддержки"),
        BotCommand(command="supportstats", description="📊 Статистика поддержки"),
        BotCommand(command="renewalstats", description="📋 Статистика продлений"),
        BotCommand(command="connectstats", description="🔌 Статистика подключений"),
        BotCommand(command="referrals", description="👥 Статистика рефералов"),
        BotCommand(command="editprice", description="💰 Редактировать цены"),
        BotCommand(command="addserver", description="➕ Добавить сервер"),
        BotCommand(command="deleteserver", description="🗑️ Удалить сервер"),
        BotCommand(command="seed", description="🧪 Создать тестовые данные"),
        BotCommand(command="unseed", description="🗑️ Удалить тестовые данные"),
        BotCommand(command="get_db", description="💾 Скачать БД"),
    ]
    
    # Устанавливаем команды для всех пользователей
    await bot.set_my_commands(user_commands)
    
    # Устанавливаем команды для администратора
    if admin_tlg:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=int(admin_tlg))
            )
        except Exception as e:
            print(f"Не удалось установить команды для администратора: {e}")


async def start_bot():
    """Запуск бота"""
    dp: Dispatcher = Dispatcher()
    dp.include_router(router=router)
    
    # Регистрация команд (порядок важен!)
    # 1. Команды с фильтрами Command регистрируются РАНЬШЕ
    dp.message.register(command_start, Command('start'))
    dp.message.register(command_stats, Command('stats'))
    dp.message.register(command_docs, Command('docs'))
    dp.message.register(lambda m: pin_disclaimer_handler(m, bot), Command('pindisclaimer'))
    dp.message.register(command_migrate, Command('migrate'))
    dp.message.register(command_check_migration_status, Command('checkstatus'))
    dp.message.register(command_fix_migration_dates, Command('fixmigration'))
    dp.message.register(command_debug_keys, Command('debugkeys'))
    dp.message.register(command_show_old_keys, Command('showoldkeys'))
    dp.message.register(command_get_db, Command('get_db'))
    dp.message.register(command_promo, Command('promo'))
    dp.message.register(command_active_keys, Command('activekeys'))
    dp.message.register(command_mass_block, Command('massblock'))
    dp.message.register(command_server_stats, Command('serverstats'))
    dp.message.register(command_migrate_server, Command('migrateserver'))
    dp.message.register(command_seed, Command('seed'))
    dp.message.register(command_unseed, Command('unseed'))
    dp.message.register(command_addserver, Command('addserver'))
    dp.message.register(deleteserver_handler, Command('deleteserver'))
    dp.message.register(editprice_handler, Command('editprice'))
    dp.message.register(command_testkey, Command('testkey'))
    
    # Новые команды для функций платформы:
    dp.message.register(command_referral, Command('ref'))  # Информация о рефералах для пользователей
    dp.message.register(command_referrals_admin, Command('referrals'))  # Статистика рефералов для админа
    dp.message.register(command_support, Command('support'))  # Создание тикета поддержки
    dp.message.register(command_support_my_tickets, Command('mytickets'))  # Мои тикеты
    dp.message.register(admin_support_queue, Command('supportqueue'))  # Очередь поддержки (админ)
    dp.message.register(admin_support_stats, Command('supportstats'))  # Статистика поддержки (админ)
    dp.message.register(command_vpn_status, Command('vpnstatus'))  # Статус VPN серверов
    dp.message.register(admin_vpn_detailed_check, Command('vpndetail'))  # Детальная проверка (админ)
    dp.message.register(command_my_connections, Command('myconnections'))  # Мои подключения
    dp.message.register(admin_connection_stats, Command('connectstats'))  # Статистика подключений (админ)
    dp.message.register(command_renewal_stats, Command('renewalstats'))  # Мои напоминания о продлении
    dp.message.register(admin_renewal_stats, Command('renewalstats_admin'))  # Статистика продлений (админ)
    dp.message.register(admin_trigger_renewal_reminders, Command('trigger_reminders'))  # Ручная отправка напоминаний (админ)
    dp.message.register(cmd_logs, Command('logs'))  # Управление логами (админ)
    
    # 2. Обработчики состояний (FSM) для добавления сервера
    dp.callback_query.register(
        process_country_choice,
        lambda c: c.data.startswith('addsvr_')
    )
    dp.message.register(process_country_ru_input, AddServerStates.waiting_for_country_ru)
    dp.message.register(process_api_url_input, AddServerStates.waiting_for_api_url)
    dp.message.register(process_cert_input, AddServerStates.waiting_for_cert)
    
    # 2a. Обработчики состояний (FSM) для редактирования цен
    dp.callback_query.register(
        select_period_to_edit,
        lambda c: c.data.startswith('edprc_')
    )
    dp.message.register(process_new_price, EditPriceStates.waiting_for_new_price)
    
    # 2b. Обработчики состояний (FSM) для поддержки
    dp.message.register(support_title_handler, SupportStates.waiting_for_title)
    dp.callback_query.register(support_category_handler, SupportStates.waiting_for_category)
    dp.message.register(support_description_handler, SupportStates.waiting_for_description)
    
    # 3. Обработчики для тестовых ключей (callback для выбора сервера)
    dp.callback_query.register(
        process_testkey_server_choice,
        lambda c: c.data.startswith('testkey_')
    )
    
    # 4. Callback'и для удаления сервера
    dp.callback_query.register(
        confirm_delete_server,
        lambda c: c.data.startswith('delsvr_')
    )
    dp.callback_query.register(
        execute_delete_server,
        lambda c: c.data.startswith('cfmdel_')
    )
    dp.callback_query.register(
        cancel_delete,
        lambda c: c.data == 'cancel_delete'
    )
    
    # 4a. Callback для замены ключа
    dp.callback_query.register(
        replace_key_handler,
        lambda c: c.data.startswith('rpl_key_')
    )
    
    # 4b. Callback'и для миграции сервера
    dp.callback_query.register(
        select_source_server,
        lambda c: c.data.startswith('migrate_from_')
    )
    dp.callback_query.register(
        select_target_server,
        lambda c: c.data.startswith('migrate_to_')
    )
    dp.callback_query.register(
        handle_migration_confirmation,
        lambda c: c.data in ['confirm_migrate', 'cancel_migrate']
    )

    # 4d. Callback'и для статистики серверов
    dp.callback_query.register(
        callback_serverstats_add,
        lambda c: c.data == 'serverstats_add'
    )
    dp.callback_query.register(
        callback_serverstats_refresh,
        lambda c: c.data == 'serverstats_refresh'
    )

    # 4c. Callback'и для управления логами
    dp.callback_query.register(
        callback_logs_clean,
        lambda c: c.data.startswith('logs_clean_')
    )
    dp.callback_query.register(
        callback_logs_refresh,
        lambda c: c.data == 'logs_refresh'
    )
    dp.callback_query.register(
        callback_logs_back,
        lambda c: c.data == 'logs_back'
    )
    dp.callback_query.register(
        callback_logs_download_db,
        lambda c: c.data == 'logs_download_db'
    )
    dp.callback_query.register(
        callback_logs_download_logs,
        lambda c: c.data == 'logs_download_logs'
    )
    dp.callback_query.register(
        callback_logs_find_payment,
        lambda c: c.data == 'logs_find_payment'
    )
    dp.callback_query.register(
        callback_logs_test_data,
        lambda c: c.data == 'logs_test_data'
    )
    dp.callback_query.register(
        callback_test_data,
        lambda c: c.data.startswith('test_data_')
    )
    
    # 5. Обработчик блокировки с причиной (БЕЗ фильтра, регистрируется ПОСЛЕДНИМ)
    dp.message.register(command_block_reason)
    
    # 6. Callback query обработчик (общий, регистрируется после специфичных)
    dp.callback_query.register(build_and_edit_message)

    try:
        # Устанавливаем команды бота в меню
        await setup_bot_commands(bot)
        
        await send_admin_message(bot, "Бот был запущен.")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await send_admin_message(bot, "Бот был остановлен.")
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(start_bot())
