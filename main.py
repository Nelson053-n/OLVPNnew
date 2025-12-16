import asyncio
import multiprocessing
import sys
import signal
import time
import traceback

from core import bot, check_time_subscribe
from logs.log_main import RotatingFileLogger

logger = RotatingFileLogger()
logger_payments = RotatingFileLogger(config_file='logs/log_settings_payments.json')


def run_bot() -> None:
    """
    Для запуска процесса бота
    :return: None
    """
    try:
        logger.log('info', 'run_bot: starting bot loop')
        asyncio.run(bot.start_bot())
    except Exception as e:
        tb = traceback.format_exc()
        logger_payments.log('error', f'run_bot exception: {e}\n{tb}')
        logger.log('error', f'run_bot exception: {e}')
        raise


def run_checker() -> None:
    """
    Для запуска процесса проверки подписки
    :return: None
    """
    try:
        logger.log('info', 'run_checker: starting checker loop')
        asyncio.run(check_time_subscribe.main_check_subscribe())
    except Exception as e:
        tb = traceback.format_exc()
        logger_payments.log('error', f'run_checker exception: {e}\n{tb}')
        logger.log('error', f'run_checker exception: {e}')
        raise


def stop_application(signum: int, frame: int) -> None:
    """
    Обработчик сигнала остановки приложения
    :param signum: Номер сигнала
    :param frame: Текущий фрейм стека
    :return: None
    """
    logger_payments.log('warning', 'Логгер остановлен')
    logger.log('info', 'Приложение остановлено')
    sys.exit(0)


if __name__ == "__main__":
    """
    Запуск модулей через multiprocessing
    """
    signal.signal(signal.SIGINT, stop_application)

    logger.log('info', 'Запуск приложения')
    logger_payments.log('warning', 'Запуск логгера payments')
    bot_th = multiprocessing.Process(target=run_bot)
    plan_th = multiprocessing.Process(target=run_checker)
    bot_th.start()
    plan_th.start()
    try:
        # Monitor child processes and log if they exit unexpectedly
        while True:
            if not bot_th.is_alive():
                logger.log('warning', f'Bot process exited with code {bot_th.exitcode}')
                logger_payments.log('warning', f'Bot process exited with code {bot_th.exitcode}')
                break
            if not plan_th.is_alive():
                logger.log('warning', f'Checker process exited with code {plan_th.exitcode}')
                logger_payments.log('warning', f'Checker process exited with code {plan_th.exitcode}')
                break
            time.sleep(1)
    finally:
        bot_th.join()
        plan_th.join()


# Добавить получение ссылки (или файл) сразу на приложение по запросу платформы
# Проверить работу выбора региона, добавить возможность добавления регионов из бота
# Добавить проработку в случае отсутвия региона. Убрать его из env