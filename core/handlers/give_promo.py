from aiogram.types import Message
import traceback

from core.settings import admin_tlg
from core.sql.function_db_user_vpn.users_vpn import (
    set_promo_status,
    set_key_to_table_users,
    set_premium_status,
    set_date_to_table_users,
    get_region_server,
    set_region_server,
)
from core.api_s.outline.outline_api import OutlineManager
from core.utils.get_key_utils import get_future_date
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


async def command_promo(message: Message) -> None:
    """
    -- Админ-команда --
    Обработчик команды /promo <id>.
    Дает пользователю возможность получить промо - по id

    :param message: Message - Объект Message, полученный при вызове команды.
    """
    try:
        if message.from_user.id == int(admin_tlg):
            data = message.text.split(' ')
            if len(data) == 2:
                name_temp, id_find_user = data
                try:
                    user_id = int(id_find_user)
                except ValueError:
                    await message.answer("❌ Неверный USER_ID", parse_mode=None)
                    return

                # Попробуем взять предпочитаемый регион пользователя, иначе используем nederland
                region = await get_region_server(account=user_id) or 'nederland'
                olm = OutlineManager(region_server=region)

                # Создаём ключ на сервере Outline
                try:
                    key_obj = olm.create_key_from_ol(id_user=str(user_id))
                except Exception as e:
                    logger.log('error', f'Give promo create_key error for {user_id}: {e}')
                    await message.answer(f"❌ Ошибка создания промо-ключа на сервере: {e}", parse_mode=None)
                    return

                # Записываем ключ и статус в БД
                access_url = getattr(key_obj, 'access_url', None)
                set_key_ok = False
                if access_url:
                    set_key_ok = await set_key_to_table_users(account=user_id, value_key=access_url)

                premium_ok = await set_premium_status(account=user_id, value_premium=True)
                date_ok = await set_date_to_table_users(account=user_id, value_date=get_future_date(1))
                region_ok = await set_region_server(account=user_id, value_region=region)
                promo_ok = await set_promo_status(account=user_id, value_promo=True)

                if all((set_key_ok, premium_ok, date_ok, region_ok, promo_ok)):
                    content = f"Пользователю {user_id} успешно выдан промо-ключ"
                else:
                    content = f"Пользователю {user_id} выдан промо-ключ, но запись в БД не полностью обновилась"

                await message.answer(text=content, parse_mode=None)
            else:
                await message.answer("❌ Ошибка использования команды\nИспользование: /promo USER_ID", parse_mode=None)
        else:
            await message.answer("❌ У вас нет доступа к этой команде")
    except Exception as e:
        tb = traceback.format_exc()
        logger.log('error', f'command_promo error for user {message.from_user.id}: {e}\n{tb}')
        try:
            await message.answer(f"Ошибка при обработке /promo: {str(e)}", parse_mode=None)
        except:
            pass



