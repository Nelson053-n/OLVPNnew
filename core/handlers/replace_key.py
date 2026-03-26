"""
Обработчик замены ключа пользователя
"""
import traceback
from aiogram.types import CallbackQuery

from core.api_s.outline.outline_api import get_server_display_name
from core.services.key_service import key_service
from core.sql.function_db_user_vpn.users_vpn import get_all_user_keys
from core.utils.admin_check import require_admin
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


@require_admin
async def replace_key_handler(callback: CallbackQuery) -> None:
    """
    Обработчик замены ключа пользователя.
    Удаляет старый ключ и создает новый на другом сервере.
    """
    try:
        await callback.answer()

        short_id = callback.data.replace('rpl_key_', '')
        logger.log('info', f'Replace key request: short_id={short_id}, from admin={callback.from_user.id}')

        all_keys = await get_all_user_keys()
        matches = [k for k in all_keys if str(k.id).endswith(short_id)]

        if len(matches) > 1:
            logger.log('warning', f'Short ID collision: {short_id} matches {len(matches)} keys')
            await callback.message.edit_text(
                f'❌ Найдено {len(matches)} ключей с таким ID — коллизия. Используйте полный ID.',
                parse_mode=None, reply_markup=None
            )
            return

        target_key = matches[0] if matches else None

        if not target_key:
            await callback.message.edit_text(
                '❌ Ключ не найден в базе данных',
                parse_mode=None,
                reply_markup=None
            )
            return

        user_id = target_key.account
        old_display = get_server_display_name(target_key.region_server)

        await callback.message.edit_text(
            f'⏳ Замена ключа для пользователя {user_id}...\n'
            f'Старый сервер: {old_display}',
            parse_mode='HTML',
            reply_markup=None
        )

        result = await key_service.replace_key(user_id=user_id)

        if not result['success']:
            await callback.message.edit_text(
                f'❌ Ошибка при замене ключа: {result["error"]}',
                parse_mode=None,
                reply_markup=None
            )
            return

        new_access_url = result.get('new_access_url')

        result_message = (
            f'✅ <b>Доступ успешно заменен!</b>\n\n'
            f'<b>Пользователь:</b> {user_id}\n'
            f'<b>Старый сервер:</b> {result["old_server_display"]}\n'
            f'<b>Новый сервер:</b> {result["new_server_display"]}\n\n'
            f'<b>Срок действия:</b> {result["expiry_date"]}'
        )
        if new_access_url:
            result_message += f'\n\n<b>Новый ключ:</b>\n<code>{new_access_url}</code>'

        await callback.message.edit_text(
            text=result_message,
            parse_mode='HTML',
            reply_markup=None
        )

        if new_access_url:
            try:
                from core.bot import bot
                user_message = (
                    f'🔄 <b>Ваш доступ был заменен!</b>\n\n'
                    f'<b>Новый сервер:</b> {result["new_server_display"]}\n'
                    f'<b>Новый ключ доступа:</b>\n'
                    f'<code>{new_access_url}</code>\n\n'
                    f'Скопируйте новый ключ и добавьте его в приложение Outline.\n'
                    f'Старый ключ больше не действителен.\n\n'
                    f'<b>Срок действия:</b> {result["expiry_date"]}'
                )
                await bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
                logger.log('info', f'Sent replacement notification to user {user_id}')
            except Exception as e:
                logger.log('warning', f'Failed to send notification to user {user_id}: {e}')

    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'replace_key_handler error: {e}\n{tb}')
        try:
            await callback.message.answer(f'❌ Ошибка при замене ключа: {str(e)}', parse_mode=None)
        except Exception:
            pass
