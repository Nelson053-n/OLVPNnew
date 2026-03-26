from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand, BotCommandScopeChat
import asyncio

from core.handlers.find_user_payments import command_findpay
from core.handlers.get_db import command_get_db
from core.handlers.get_log_payments import command_get_log_pay
from core.handlers.message_to_admin import send_admin_message
from core.handlers.give_promo import command_promo
from core.handlers.key_info import command_keyinfo
from core.handlers.active_keys import command_active_keys
from core.handlers.admin_block_reason import command_block_reason
from core.handlers.mass_block import command_mass_block
from core.handlers.seed_test_data import command_seed
from core.handlers.unseed_test_data import command_unseed
from core.handlers.server_stats import command_server_stats
from core.handlers.bot_statistics import command_stats
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
    callback_logs_download,
    callback_logs_db,
    callback_logs_all_payments,
    callback_logs_back,
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
from core.handlers.broadcast import (
    command_broadcast,
    broadcast_message_handler,
    BroadcastStates,
)
from core.handlers.traffic_monitor import command_trafficstats
from core.handlers.replace_key import replace_key_handler
from core.handlers.admin_keys import (
    command_keys,
    command_testdata,
    command_servers,
    callback_admin_main_menu,
    callback_admin_open_start,
    callback_admin_open_stats,
    callback_admin_open_referrals,
    callback_admin_open_logs,
    callback_admin_open_keys,
    callback_admin_open_support,
    callback_admin_open_testdata,
    callback_admin_open_servers,
    callback_admin_keys_action,
    callback_admin_support_action,
    callback_admin_testdata_action,
    callback_admin_servers_action,
)
from core.settings import api_key_tlg, admin_tlg
from core.handlers.handler_keyboard import build_and_edit_message
from core.handlers.start import command_start
from core.handlers.runtime_metrics import command_metrics
from core.monitoring.metrics_middleware import MetricsMiddleware
from core.monitoring.infra_alerts import InfraAlertsMonitor

router: Router = Router()
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
        BotCommand(command="metrics", description="📈 Runtime-метрики"),
        BotCommand(command="referrals", description="👥 Статистика рефералов"),
        BotCommand(command="logs", description="📁 Управление логами"),
        BotCommand(command="support", description="🆘 Поддержка"),
        BotCommand(command="keys", description="🔑 Ключи"),
        BotCommand(command="testdata", description="🧪 Тестовые данные"),
        BotCommand(command="servers", description="🖥️ Сервера"),
    ]
    
    # Устанавливаем команды для всех пользователей
    await bot.set_my_commands(user_commands)
    
    # Устанавливаем команды для администратора
    if admin_tlg:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_tlg)
            )
        except Exception as e:
            print(f"Не удалось установить команды для администратора: {e}")


async def start_bot():
    """Запуск бота"""
    dp: Dispatcher = Dispatcher()
    dp.include_router(router=router)

    # Middleware метрик для сообщений и callback
    dp.message.middleware(MetricsMiddleware())
    dp.callback_query.middleware(MetricsMiddleware())
    
    # Регистрация команд (порядок важен!)
    # 1. Команды с фильтрами Command регистрируются РАНЬШЕ
    dp.message.register(command_start, Command('start'))
    dp.message.register(command_stats, Command('stats'))
    dp.message.register(command_metrics, Command('metrics'))
    dp.message.register(command_docs, Command('docs'))
    dp.message.register(command_keys, Command('keys'))
    dp.message.register(command_testdata, Command('testdata'))
    dp.message.register(command_servers, Command('servers'))
    dp.message.register(lambda m: pin_disclaimer_handler(m, bot), Command('pindisclaimer'))
    dp.message.register(command_migrate, Command('migrate'))
    dp.message.register(command_check_migration_status, Command('checkstatus'))
    dp.message.register(command_fix_migration_dates, Command('fixmigration'))
    dp.message.register(command_debug_keys, Command('debugkeys'))
    dp.message.register(command_show_old_keys, Command('showoldkeys'))
    dp.message.register(command_findpay, Command('findpay'))
    dp.message.register(command_get_log_pay, Command('get_log_pay'))
    dp.message.register(command_get_db, Command('get_db'))
    dp.message.register(command_promo, Command('promo'))
    dp.message.register(command_keyinfo, Command('keyinfo'))
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
    dp.message.register(command_broadcast, Command('broadcast'))
    
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
    dp.message.register(command_trafficstats, Command('trafficstats'))  # Статистика трафика ключей (админ)
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
        callback_logs_download,
        lambda c: c.data == 'logs_download'
    )
    dp.callback_query.register(
        callback_logs_db,
        lambda c: c.data == 'logs_db'
    )
    dp.callback_query.register(
        callback_logs_all_payments,
        lambda c: c.data == 'logs_all_payments'
    )
    dp.callback_query.register(
        callback_logs_back,
        lambda c: c.data == 'logs_back'
    )

    # 4d. Callback'и админ-разделов и раздела ключей
    dp.callback_query.register(
        callback_admin_main_menu,
        lambda c: c.data == 'admin_main_menu'
    )
    dp.callback_query.register(
        callback_admin_open_start,
        lambda c: c.data == 'admin_open_start'
    )
    dp.callback_query.register(
        callback_admin_open_stats,
        lambda c: c.data == 'admin_open_stats'
    )
    dp.callback_query.register(
        callback_admin_open_referrals,
        lambda c: c.data == 'admin_open_referrals'
    )
    dp.callback_query.register(
        callback_admin_open_logs,
        lambda c: c.data == 'admin_open_logs'
    )
    dp.callback_query.register(
        callback_admin_open_keys,
        lambda c: c.data == 'admin_open_keys'
    )
    dp.callback_query.register(
        callback_admin_open_support,
        lambda c: c.data == 'admin_open_support'
    )
    dp.callback_query.register(
        callback_admin_open_testdata,
        lambda c: c.data == 'admin_open_testdata'
    )
    dp.callback_query.register(
        callback_admin_open_servers,
        lambda c: c.data == 'admin_open_servers'
    )
    dp.callback_query.register(
        callback_admin_keys_action,
        lambda c: c.data and c.data.startswith('admin_keys_')
    )
    dp.callback_query.register(
        callback_admin_support_action,
        lambda c: c.data and c.data.startswith('admin_support_')
    )
    dp.callback_query.register(
        callback_admin_testdata_action,
        lambda c: c.data and c.data.startswith('admin_testdata_')
    )
    dp.callback_query.register(
        callback_admin_servers_action,
        lambda c: c.data and c.data.startswith('admin_servers_')
    )
    
    # 5. Обработчик рассылки (FSM state)
    dp.message.register(broadcast_message_handler, BroadcastStates.waiting_for_message)

    # 6. Обработчик блокировки с причиной (БЕЗ фильтра, регистрируется ПОСЛЕДНИМ)
    dp.message.register(command_block_reason)
    
    # 6. Callback query обработчик (общий, регистрируется после специфичных)
    dp.callback_query.register(build_and_edit_message)

    infra_task = None
    try:
        # Устанавливаем команды бота в меню
        await setup_bot_commands(bot)

        # Фоновый мониторинг инфраструктуры
        infra_monitor = InfraAlertsMonitor(bot)
        infra_task = asyncio.create_task(infra_monitor.run())
        
        await send_admin_message(bot, "Бот был запущен.")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        if infra_task:
            infra_task.cancel()
            try:
                await infra_task
            except asyncio.CancelledError:
                pass
        await send_admin_message(bot, "Бот был остановлен.")
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(start_bot())
