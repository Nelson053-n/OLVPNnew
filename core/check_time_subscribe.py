import asyncio
import traceback
from datetime import datetime
from aiogram import Bot

from core.api_s.outline.outline_api import OutlineManager

from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()

# Множество пользователей, которым уже отправлено уведомление об истечении ключа
# (защита от повторной отправки при ошибках обработки)
_notified_users: set[int] = set()

# Множество пользователей, заблокировавших бота (не пытаемся слать повторно)
_blocked_users: set[int] = set()


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


async def send_notification_to_user(bot: Bot, id_user: int) -> bool:
    """
    Отправка уведомления пользователю об истечении ключа.
    Проверяет кэш уже уведомлённых и заблокировавших бота.

    :param bot: объект Bot
    :param id_user: id пользователя
    :return: True если отправлено, False если пропущено
    """
    if id_user in _notified_users:
        return False
    if id_user in _blocked_users:
        return False

    text = 'Действие вашего ключа завершено\nВы можете купить новый,\nчто бы продолжить пользоваться сервисом'
    try:
        await bot.send_message(chat_id=id_user, text=text)
        _notified_users.add(id_user)
        return True
    except Exception as e:
        err_str = str(e).lower()
        if 'blocked' in err_str or 'deactivated' in err_str or 'not found' in err_str:
            _blocked_users.add(id_user)
            logger.log('info', f'User {id_user} blocked bot, added to skip list')
        else:
            logger.log('warning', f'Failed to notify user {id_user}: {e}')
        return False


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
        set_region_server,
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
                    logger.log('error', f'Failed to delete key record {uk.id} from DB: {e}')
                    continue

            # Пересчитать premium-статус на основании оставшихся ключей
            has_active = await sync_premium_status(account=uk.account)
            if not has_active:
                await set_key_to_table_users(account=uk.account, value_key=None)
                await set_date_to_table_users(account=uk.account, value_date=None)
                await set_region_server(account=uk.account, value_region=None)
                await send_notification_to_user(bot=bot, id_user=uk.account)

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
                await set_region_server(account=record.account, value_region=None)

                try:
                    region = record.region_server or 'nederland'
                    olm = OutlineManager(region_server=region)
                    olm.delete_key_from_ol(id_user=str(record.account))
                except KeyError:
                    logger.log('info', f'Server {record.region_server} removed from config, skipping Outline delete for user {record.account}')
                except Exception as e:
                    logger.log('error', f'Failed to delete legacy key for user {record.account}: {e}')

                await send_notification_to_user(bot=bot, id_user=record.account)
    return deleted_count


_traffic_counter = 0


async def main_check_subscribe() -> None:
    """
    Запуск цикла проверки БД на активную подписку
    и отправки напоминаний о продлении
    :return: None
    """
    global _traffic_counter
    from core.handlers.renewal_handler import send_renewal_reminders

    while True:
        try:
            # Блокируем истекшие ключи
            await finish_set_date_and_premium()

            # Отправляем напоминания о скором истечении
            try:
                from core.bot import bot
                await send_renewal_reminders(bot)
            except Exception as e:
                logger.log('warning', f'Failed to send renewal reminders: {e}')

            # Проверка трафика каждые 6 итераций (30 мин)
            _traffic_counter += 1
            if _traffic_counter >= 6:
                _traffic_counter = 0
                try:
                    from core.handlers.traffic_monitor import check_traffic_anomalies
                    from core.bot import bot
                    await check_traffic_anomalies(bot)
                except Exception as e:
                    logger.log('warning', f'Traffic check error: {e}')
        except Exception as e:
            logger.log('error', f'main_check_subscribe error: {e}\n{traceback.format_exc()}')
        await asyncio.sleep(5*60)  # Проверка раз в 5 минут


if __name__ == '__main__':
    asyncio.run(main_check_subscribe())
