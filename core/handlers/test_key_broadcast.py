from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import traceback
import json

from core.settings import admin_tlg
from core.api_s.outline.outline_api import OutlineManager
from core.sql.function_db_user_vpn.users_vpn import (
    get_all_records_from_table_users,
    add_user_key,
    set_premium_status,
    set_date_to_table_users,
    set_region_server,
    set_key_to_table_users,
)
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def fmt(dt: datetime) -> str:
    return dt.strftime('%d.%m.%Y - %H:%M')


class TestKeyStates(StatesGroup):
    waiting_for_server = State()


async def command_testkey(message: Message, state: FSMContext) -> None:
    """
    -- Админ-команда --
    /testkey
    Создает тестовые ключи на 14 дней на выбранном сервере и рассылает всем пользователям.
    Используется для промо-акций при добавлении нового сервера.
    """
    try:
        if not admin_tlg or message.from_user.id != int(admin_tlg):
            await message.answer('❌ У вас нет доступа к этой команде', parse_mode=None)
            return

        # Получаем список активных серверов
        config_file = 'core/api_s/outline/settings_api_outline.json'
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            await message.answer('❌ Файл конфигурации серверов не найден', parse_mode=None)
            return

        # Фильтруем только активные серверы
        active_servers = {k: v for k, v in config.items() if v.get('is_active', False)}
        
        if not active_servers:
            await message.answer('❌ Нет активных серверов', parse_mode=None)
            return

        # Создаем клавиатуру с выбором сервера
        kb = InlineKeyboardBuilder()
        for server_key, server_data in active_servers.items():
            server_name = server_data.get('name_ru', server_key)
            kb.button(text=server_name, callback_data=f"testkey_srv_{server_key}")
        
        kb.button(text="❌ Отмена", callback_data="testkey_cancel")
        kb.adjust(2)

        await state.set_state(TestKeyStates.waiting_for_server)
        await message.answer(
            text=(
                '🎁 <b>Создание тестовых ключей для рассылки</b>\n\n'
                'Выберите сервер для создания тестовых ключей на 14 дней:\n\n'
                '⚠️ Ключи будут разосланы <b>ВСЕМ</b> пользователям в базе!'
            ),
            reply_markup=kb.as_markup(),
            parse_mode='HTML'
        )

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_testkey error: {e}\n{tb}')
        await message.answer('❌ Ошибка при запуске команды', parse_mode=None)


async def process_testkey_server_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработка выбора сервера для создания тестовых ключей
    """
    try:
        from core.bot import bot
        
        if callback.data == "testkey_cancel":
            await state.clear()
            await callback.message.edit_text("❌ Создание тестовых ключей отменено")
            await callback.answer()
            return

        # Извлекаем название сервера из callback_data
        server_key = callback.data.replace("testkey_srv_", "")
        
        await callback.message.edit_text(
            f"⏳ Начинаю создание тестовых ключей на сервере <b>{server_key}</b>...\n"
            f"Это может занять некоторое время.",
            parse_mode='HTML'
        )
        await callback.answer()

        # Получаем всех пользователей
        all_users = await get_all_records_from_table_users()
        
        if not all_users:
            await callback.message.edit_text("❌ В базе данных нет пользователей")
            await state.clear()
            return

        # Дата истечения - через 14 дней
        expiry_date = datetime.now() + timedelta(days=14)
        
        # Создаем менеджер Outline для выбранного сервера
        olm = OutlineManager(region_server=server_key)
        
        success_count = 0
        error_count = 0
        
        for user in all_users:
            try:
                user_id = user.account
                
                # Создаем уникальный ID для тестового ключа
                outline_id = f"testkey_{user_id}_{server_key}"
                
                # Создаем ключ на Outline сервере
                try:
                    key_data = olm.create_key_from_ol(id_user=outline_id)
                    access_url = getattr(key_data, 'access_url', None) if key_data else None
                    if not access_url:
                        error_count += 1
                        logger.log('warning', f'Failed to create test key for user {user_id}')
                        continue
                except Exception as e:
                    error_count += 1
                    logger.log('error', f'Outline error for user {user_id}: {e}')
                    continue

                # Добавляем ключ в БД
                await add_user_key(
                    account=user_id,
                    access_url=access_url,
                    outline_id=outline_id,
                    region_server=server_key,
                    date_str=fmt(expiry_date),
                    promo=True,
                )

                # Обновляем статусы пользователя
                await set_premium_status(account=user_id, value_premium=True)
                await set_date_to_table_users(account=user_id, value_date=fmt(expiry_date))
                await set_region_server(account=user_id, value_region=server_key)
                await set_key_to_table_users(account=user_id, value_key=access_url)

                # Отправляем уведомление пользователю
                try:
                    notification_text = (
                        f"🎉 <b>Добавили новый сервер выделенной сетевой среды.</b>\n\n"
                        f"Вам выдан тестовый доступ на 14 дней:\n\n"
                        f"<code>{access_url}</code>\n\n"
                        f"📍 Регион сервера: <b>{server_key}</b>\n"
                        f"⏰ Действует до: <b>{fmt(expiry_date)}</b>\n\n"
                        f"Используйте команду /start для управления доступами."
                    )
                    await bot.send_message(chat_id=user_id, text=notification_text, parse_mode='HTML')
                    success_count += 1
                except Exception as notify_error:
                    # Ключ создан, но уведомление не отправлено - не критично
                    success_count += 1
                    logger.log('warning', f'Failed to notify user {user_id}: {notify_error}')

            except Exception as e:
                error_count += 1
                logger.log('error', f'Error processing user {user.account}: {e}')
                continue

        # Отчет администратору
        await callback.message.edit_text(
            f"✅ <b>Рассылка тестовых доступов завершена!</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {error_count}\n"
            f"📍 Сервер: {server_key}\n"
            f"⏰ Срок действия: 14 дней (до {fmt(expiry_date)})",
            parse_mode='HTML'
        )
        
        await state.clear()
        logger.log('info', f'Admin {callback.from_user.id} broadcasted test keys: success={success_count}, errors={error_count}')

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'process_testkey_server_choice error: {e}\n{tb}')
        try:
            await callback.message.edit_text(f'❌ Ошибка при создании доступов: {str(e)}')
        except Exception:
            pass
        await state.clear()
