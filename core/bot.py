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
from core.handlers.add_server import (
    command_addserver, 
    process_country_input, 
    process_api_url_input, 
    process_cert_input,
    AddServerStates
)
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
    
    # Команды для администратора
    admin_commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="promo", description="🎁 Выдать промо-ключ"),
        BotCommand(command="activekeys", description="📋 Активные ключи"),
        BotCommand(command="keyinfo", description="ℹ️ Информация о ключе"),
        BotCommand(command="massblock", description="🔒 Блокировка просроченных"),
        BotCommand(command="findpay", description="💳 Поиск платежей"),
        BotCommand(command="seed", description="🧪 Создать тестовые данные"),
        BotCommand(command="unseed", description="🗑️ Удалить тестовые данные"),
        BotCommand(command="addserver", description="➕ Добавить сервер"),
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
    dp.message.register(command_findpay, Command('findpay'))
    dp.message.register(command_get_log_pay, Command('get_log_pay'))
    dp.message.register(command_get_db, Command('get_db'))
    dp.message.register(command_promo, Command('promo'))
    dp.message.register(command_keyinfo, Command('keyinfo'))
    dp.message.register(command_active_keys, Command('activekeys'))
    dp.message.register(command_mass_block, Command('massblock'))
    dp.message.register(command_seed, Command('seed'))
    dp.message.register(command_unseed, Command('unseed'))
    dp.message.register(command_addserver, Command('addserver'))
    
    # 2. Обработчики состояний (FSM) для добавления сервера
    dp.message.register(process_country_input, AddServerStates.waiting_for_country)
    dp.message.register(process_api_url_input, AddServerStates.waiting_for_api_url)
    dp.message.register(process_cert_input, AddServerStates.waiting_for_cert)
    
    # 3. Обработчик блокировки с причиной (БЕЗ фильтра, регистрируется ПОСЛЕДНИМ)
    dp.message.register(command_block_reason)
    
    # 4. Callback query обработчик
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
