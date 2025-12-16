"""
Обработчик команды /deleteserver - удаление Outline сервера
"""
import json
import os
import traceback
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import get_all_records_from_table_users
from core.api_s.outline.outline_api import OutlineManager
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()

router = Router()


@router.message(Command('deleteserver'))
async def deleteserver_handler(message: Message) -> None:
    """
    Команда удаления Outline сервера (только для администратора)
    Показывает список активных серверов с количеством ключей
    """
    try:
        # Проверка прав администратора
        admin_tlg = os.getenv('ADMIN_TLG')
        if not admin_tlg or str(message.from_user.id) != str(admin_tlg):
            await message.answer('❌ Эта команда доступна только администратору', parse_mode=None)
            return

        # Читаем конфигурацию серверов
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
            await message.answer('❌ Нет активных серверов для удаления', parse_mode=None)
            return

        # Получаем данные всех пользователей для подсчета ключей
        all_users = await get_all_records_from_table_users()
        
        # Подсчитываем количество активных ключей на каждом сервере
        server_key_counts = {}
        for server_name in active_servers.keys():
            count = sum(1 for user in all_users 
                       if user.region_server == server_name and user.premium)
            server_key_counts[server_name] = count

        # Создаем клавиатуру с серверами
        builder = InlineKeyboardBuilder()
        for server_name, server_data in active_servers.items():
            name_ru = server_data.get('name_ru', server_name)
            key_count = server_key_counts.get(server_name, 0)
            
            button_text = f"{name_ru} ({key_count} ключей)"
            builder.button(
                text=button_text,
                callback_data=f"delsvr_{server_name}"
            )
        
        builder.adjust(1)  # Каждая кнопка на отдельной строке
        
        await message.answer(
            text=(
                '🗑️ <b>Удаление сервера</b>\n\n'
                'Выберите сервер для удаления.\n'
                'Будут удалены:\n'
                '• Все ключи пользователей на этом сервере\n'
                '• Конфигурация сервера из бота\n\n'
                '⚠️ <b>Это действие необратимо!</b>'
            ),
            reply_markup=builder.as_markup(),
            parse_mode='HTML'
        )

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'deleteserver_handler error: {e}\n{tb}')
        await message.answer('❌ Ошибка при загрузке списка серверов', parse_mode=None)


@router.callback_query(lambda c: c.data and c.data.startswith('delsvr_'))
async def confirm_delete_server(callback: CallbackQuery) -> None:
    """
    Обработчик выбора сервера для удаления
    Показывает информацию и запрашивает подтверждение
    """
    try:
        await callback.answer()
        
        # Извлекаем название сервера
        server_name = callback.data.replace('delsvr_', '')
        
        # Читаем конфигурацию
        config_file = 'core/api_s/outline/settings_api_outline.json'
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if server_name not in config:
            await callback.message.edit_text(
                '❌ Сервер не найден в конфигурации',
                parse_mode=None
            )
            return
        
        server_data = config[server_name]
        name_ru = server_data.get('name_ru', server_name)
        
        # Подсчитываем количество активных ключей
        all_users = await get_all_records_from_table_users()
        active_keys = [u for u in all_users 
                      if u.region_server == server_name and u.premium]
        key_count = len(active_keys)
        
        # Создаем клавиатуру подтверждения
        builder = InlineKeyboardBuilder()
        builder.button(text='✅ Да, удалить', callback_data=f'cfmdel_{server_name}')
        builder.button(text='❌ Отмена', callback_data='cancel_delete')
        builder.adjust(1)
        
        await callback.message.edit_text(
            text=(
                f'⚠️ <b>Подтверждение удаления сервера</b>\n\n'
                f'<b>Сервер:</b> {name_ru}\n'
                f'<b>Активных ключей:</b> {key_count}\n\n'
                f'При удалении:\n'
                f'• Все {key_count} ключей будут удалены из Outline VPN\n'
                f'• У пользователей будет отключена подписка\n'
                f'• Сервер будет удален из конфигурации бота\n\n'
                f'❓ Вы уверены, что хотите продолжить?'
            ),
            reply_markup=builder.as_markup(),
            parse_mode='HTML'
        )
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'confirm_delete_server error: {e}\n{tb}')
        await callback.message.edit_text('❌ Ошибка при обработке запроса', parse_mode=None)


@router.callback_query(lambda c: c.data and c.data.startswith('cfmdel_'))
async def execute_delete_server(callback: CallbackQuery) -> None:
    """
    Выполняет удаление сервера и всех связанных ключей
    """
    try:
        await callback.answer()
        
        # Извлекаем название сервера
        server_name = callback.data.replace('cfmdel_', '')
        
        await callback.message.edit_text(
            '⏳ Удаление сервера... Это может занять некоторое время.',
            parse_mode=None
        )
        
        # Читаем конфигурацию
        config_file = 'core/api_s/outline/settings_api_outline.json'
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if server_name not in config:
            await callback.message.edit_text(
                '❌ Сервер не найден в конфигурации',
                parse_mode=None
            )
            return
        
        server_data = config[server_name]
        name_ru = server_data.get('name_ru', server_name)
        
        # Получаем всех пользователей с ключами на этом сервере
        all_users = await get_all_records_from_table_users()
        users_on_server = [u for u in all_users if u.region_server == server_name]
        
        # Инициализируем Outline Manager для этого сервера
        olm = OutlineManager(server_name)
        
        deleted_keys = 0
        errors = 0
        
        # Удаляем ключи из Outline и обновляем БД
        for user in users_on_server:
            try:
                account_id = user.account
                outline_id = user.outline_id
                
                if outline_id:
                    # Удаляем ключ из Outline
                    try:
                        olm.delete_key_by_id(outline_id)
                        deleted_keys += 1
                    except Exception as e:
                        logger.log('warning', f'Failed to delete key {outline_id} from Outline: {e}')
                        errors += 1
                
                # Обновляем данные пользователя в БД
                from core.sql.function_db_user_vpn.users_vpn import set_premium_status
                await set_premium_status(account_id, value_premium=False)
                
            except Exception as e:
                logger.log('error', f'Error deleting key for user {user.account}: {e}')
                errors += 1
        
        # Удаляем сервер из конфигурации
        del config[server_name]
        
        # Сохраняем обновленную конфигурацию
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # Формируем итоговое сообщение
        result_text = (
            f'✅ <b>Сервер удален</b>\n\n'
            f'<b>Сервер:</b> {name_ru}\n'
            f'<b>Удалено ключей:</b> {deleted_keys}\n'
        )
        
        if errors > 0:
            result_text += f'<b>Ошибок:</b> {errors}\n'
        
        result_text += '\n⚠️ Для применения изменений требуется перезапуск бота'
        
        await callback.message.edit_text(
            text=result_text,
            parse_mode='HTML'
        )
        
        logger.log('info', f'Server {server_name} deleted. Keys removed: {deleted_keys}, errors: {errors}')
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'execute_delete_server error: {e}\n{tb}')
        await callback.message.edit_text(
            '❌ Ошибка при удалении сервера. Проверьте логи.',
            parse_mode=None
        )


@router.callback_query(lambda c: c.data == 'cancel_delete')
async def cancel_delete(callback: CallbackQuery) -> None:
    """Отмена удаления сервера"""
    try:
        await callback.answer()
        await callback.message.edit_text(
            '✅ Удаление сервера отменено',
            parse_mode=None
        )
    except Exception as e:
        logger.log('error', f'cancel_delete error: {e}')
