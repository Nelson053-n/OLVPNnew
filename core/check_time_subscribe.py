import asyncio
import traceback
from datetime import datetime
from aiogram import Bot

from core.api_s.outline.outline_api import OutlineManager

from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()


def check_time_subscribe(date) -> bool:
    """
    Проверка окончилась подписка или нет

    :param date: datetime - дата подписки
    :return: True в случае окончания, в противном False
    """
    if date is None:
        return False
    if datetime.now() < date:
        return False
    else:
        return True


async def get_and_check_records(all_records: list) -> list:
    """
    Отправка на проверку подписки каждой записи из БД
    :param all_records: Все записи из БД списком
    :return: Записи на которых закончилась подписка
    """
    finish_subscribe = []
    for record in all_records:
        if check_time_subscribe(record.date):
            finish_subscribe.append(record)
    return finish_subscribe


async def send_notification_to_user(bot: Bot, id_user: int) -> None:
    """
    Сообщение администратору о запуске и остановке бота
    :param bot: объект Bot, полученный при вызове команды.
    :param id_user: id пользователя
    :return: None
    """
    text = 'Действие вашего ключа завершено\nВы можете купить новый,\nчто бы продолжить пользоваться сервисом'
    await bot.send_message(chat_id=id_user, text=text)


async def finish_set_date_and_premium() -> int:
    """
    Изменение параметров (дата, премиум, ключ) в БД в случае окончания подписки
    Удаление ключа из Outline

    :return: int - Количество удалённых ключей
    """
    from core.sql.function_db_user_vpn.users_vpn import (
        get_all_records_from_table_users,
        set_date_to_table_users,
        set_key_to_table_users,
        get_all_user_keys,
        get_user_keys,
        delete_user_key_record,
        sync_premium_status,
    )
    from core.bot import bot

    deleted_count = 0

    # Сначала обрабатываем истекшие ключи на уровне UserKey
    all_keys = await get_all_user_keys()
    for uk in all_keys:
        if check_time_subscribe(uk.date):
            # Удалить ключ из Outline
            outline_deleted = False
            try:
                region = uk.region_server or 'nederland'
                olm = OutlineManager(region_server=region)
                olm.delete_key_by_id(uk.outline_id)
                outline_deleted = True
            except KeyError:
                # Сервер удалён из конфига — ключ уже недоступен
                outline_deleted = True
                logger.log('info', f'Server {uk.region_server} removed from config, skipping Outline delete for key {uk.id}')
            except Exception as e:
                err_msg = str(e).lower()
                if 'not found' in err_msg or '404' in err_msg:
                    outline_deleted = True
                    logger.log('warning', f'Key {uk.id} already absent from Outline, cleaning DB')
                else:
                    logger.log('error', f'Failed to delete key {uk.id} from Outline (will retry): {e}')
                    continue

            if outline_deleted:
                try:
                    await delete_user_key_record(uk.id)
                    deleted_count += 1
                except Exception as e:
                    logger.log('error', f'Failed to delete key record {uk.id} from DB: {e}\n{traceback.format_exc()}')
                    continue

            # Пересчитать premium-статус на основании оставшихся ключей
            has_active = await sync_premium_status(account=uk.account)
            if not has_active:
                await set_key_to_table_users(account=uk.account, value_key=None)
                await set_date_to_table_users(account=uk.account, value_date=None)
                try:
                    await send_notification_to_user(bot=bot, id_user=uk.account)
                except Exception as e:
                    logger.log('warning', f'Failed to notify user {uk.account}: {e}')

    # Совместимость: если где-то ещё сохраняется Users.date — обработаем и это
    all_records = await get_all_records_from_table_users()
    all_finish_records = await get_and_check_records(all_records)
    if all_finish_records:
        for record in all_finish_records:
            # если у пользователя ещё есть действующие ключи, пропускаем сброс флагов Users
            remaining = await get_user_keys(account=record.account)
            if remaining:
                continue
            has_active = await sync_premium_status(account=record.account)
            if not has_active:
                await set_key_to_table_users(account=record.account, value_key=None)
                await set_date_to_table_users(account=record.account, value_date=None)

                try:
                    region = record.region_server or 'nederland'
                    olm = OutlineManager(region_server=region)
                    olm.delete_key_from_ol(id_user=str(record.account))
                except KeyError:
                    # Сервер удалён из конфига — ключ уже недоступен, просто чистим БД
                    logger.log('info', f'Server {record.region_server} removed from config, skipping Outline delete for user {record.account}')
                except Exception as e:
                    logger.log('error', f'Failed to delete legacy key for user {record.account}: {e}')

                try:
                    await send_notification_to_user(bot=bot, id_user=record.account)
                except Exception as e:
                    logger.log('warning', f'Failed to notify user {record.account}: {e}')
    return deleted_count


async def main_check_subscribe() -> None:
    """
    Запуск цикла проверки БД на активную подписку
    и отправки напоминаний о продлении
    :return: None
    """
    from core.handlers.renewal_handler import send_renewal_reminders

    while True:
        try:
            # Блокируем истекшие ключи
            await finish_set_date_and_premium()
            
            # Отправляем напоминания о скором истечении (один раз в час)
            try:
                from core.bot import bot
                await send_renewal_reminders(bot)
            except Exception as e:
                logger.log('warning', f'Failed to send renewal reminders: {e}')
        except Exception as e:
            logger.log('error', f'main_check_subscribe error: {e}\n{traceback.format_exc()}')
            print(f'[check_subscribe] Error: {e}')
        await asyncio.sleep(5*60)  # Проверка раз в 5 минут


if __name__ == '__main__':
    asyncio.run(main_check_subscribe())