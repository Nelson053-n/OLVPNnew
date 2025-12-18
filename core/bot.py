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
from core.handlers.migrate_old_keys import (
    command_migrate,
    command_check_migration_status,
    command_fix_migration_dates
)
from core.handlers.migrate_server import (
    command_migrate_server, 
    select_source_server,
    select_target_server,
    handle_migration_confirmation, 
    MigrateServerStates
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
        BotCommand(command="migrate", description="🔄 Миграция старых ключей"),
        BotCommand(command="checkstatus", description="🔍 Статус миграции"),
        BotCommand(command="fixmigration", description="🛠️ Исправить даты миграции"),
        BotCommand(command="promo", description="🎁 Выдать промо-ключ"),
        BotCommand(command="testkey", description="🎉 Рассылка тестовых ключей"),
        BotCommand(command="activekeys", description="📋 Активные ключи"),
        BotCommand(command="keyinfo", description="ℹ️ Информация о ключе"),
        BotCommand(command="massblock", description="🔒 Блокировка просроченных"),
        BotCommand(command="serverstats", description="📊 Статистика серверов"),
        BotCommand(command="migrateserver", description="🔄 Перенос между серверами"),
        BotCommand(command="findpay", description="💳 Поиск платежей"),
        BotCommand(command="editprice", description="💰 Редактировать цены"),
        BotCommand(command="addserver", description="➕ Добавить сервер"),
        BotCommand(command="deleteserver", description="🗑️ Удалить сервер"),
        BotCommand(command="seed", description="🧪 Создать тестовые данные"),
        BotCommand(command="unseed", description="🗑️ Удалить тестовые данные"),
        BotCommand(command="get_db", description="💾 Скачать БД"),
        BotCommand(command="get_log_pay", description="📄 Скачать логи"),
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
    dp.message.register(command_migrate, Command('migrate'))
    dp.message.register(command_check_migration_status, Command('checkstatus'))
    dp.message.register(command_fix_migration_dates, Command('fixmigration'))
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
