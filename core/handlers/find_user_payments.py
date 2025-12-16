from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
import traceback

from core.api_s.api_youkassa.youkassa_api import get_user_payments
from core.settings import admin_tlg
from core.sql.function_db_user_payments.users_payments import get_all_accounts_from_db
from core.sql.function_db_user_vpn.users_vpn import get_user_data_from_table_users
from core.utils.create_view import create_answer_from_html
from logs.log_main import RotatingFileLogger
from aiogram.enums import ParseMode

logger = RotatingFileLogger()


async def command_findpay(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /findpay <id>.
    Проверяет наличие записей о покупках пользователя по id
    Выдает их если есть с кнопкой для проверки ключа.

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        if message.from_user.id == int(admin_tlg):
            data = message.text.split(' ')
            if len(data) == 2:
                name_temp, id_find_user = data
                try:
                    id_find_user_int = int(id_find_user)
                except ValueError:
                    await message.answer("user_id должен быть числом", parse_mode=None)
                    return
                
                # Получаем платежи
                user_payments = await get_user_payments(find_id=id_find_user_int)
                # Получаем имя пользователя
                user_record = await get_user_data_from_table_users(account=id_find_user_int)
                user_name = user_record.account_name if user_record else "Unknown"
                
                # Формируем ответ
                payments_text = "\n".join(user_payments) if user_payments else "нет платежей"
                response = f"Пользователь: {user_name} (ID: {id_find_user_int})\n\nПлатежи:\n{payments_text}"
                
                # Создаём кнопку для проверки ключа
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="Проверить ключ /keyinfo", callback_data=f"chk_usr_{id_find_user_int}")
                
                await message.answer(text=response, reply_markup=keyboard.as_markup(), parse_mode=None)
            elif len(data) == 1:
                name_temp = data[0]
                users_who_paid = await get_all_accounts_from_db()
                
                if users_who_paid:
                    # Получаем имена для каждого пользователя
                    response = "Пользователи с платежами:\n\n"
                    keyboard = InlineKeyboardBuilder()
                    for user_id_str in users_who_paid:
                        try:
                            user_id_int = int(user_id_str)
                            user_record = await get_user_data_from_table_users(account=user_id_int)
                            user_name = user_record.account_name if user_record else "Unknown"
                            response += f"{user_name} (ID: {user_id_int})\n"
                            keyboard.button(text=f"{user_name} ({user_id_int})", callback_data=f"chk_usr_{user_id_int}")
                        except:
                            pass
                    keyboard.adjust(1)
                    await message.answer(text=response, reply_markup=keyboard.as_markup(), parse_mode=None)
                else:
                    await message.answer("Нет пользователей с платежами", parse_mode=None)
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_findpay error: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /findpay: {str(e)}", parse_mode=None)
        except:
            pass


