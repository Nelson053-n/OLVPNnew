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

MAX_RESTART_ATTEMPTS = 5
RESTART_BASE_DELAY = 2  # секунды, экспоненциально растёт


def run_bot() -> None:
    """
    Для запуска процесса бота
    :return: None
    """
    try:
        logger.log('info', 'run_bot: starting bot loop')
        print('[main] run_bot: starting bot loop')
        asyncio.run(bot.start_bot())
    except Exception as e:
        tb = traceback.format_exc()
        logger_payments.log('error', f'run_bot exception: {e}\n{tb}')
        logger.log('error', f'run_bot exception: {e}')
        print('[main] run_bot exception:', e)
        print(tb)
        raise


def run_checker() -> None:
    """
    Для запуска процесса проверки подписки
    :return: None
    """
    try:
        logger.log('info', 'run_checker: starting checker loop')
        print('[main] run_checker: starting checker loop')
        asyncio.run(check_time_subscribe.main_check_subscribe())
    except Exception as e:
        tb = traceback.format_exc()
        logger_payments.log('error', f'run_checker exception: {e}\n{tb}')
        logger.log('error', f'run_checker exception: {e}')
        print('[main] run_checker exception:', e)
        print(tb)
        raise


# Глобальные ссылки на процессы для graceful shutdown
_processes: list[multiprocessing.Process] = []
_shutting_down = False


def _graceful_shutdown(signum: int, frame) -> None:
    """
    Обработчик SIGINT/SIGTERM: корректно завершает дочерние процессы.
    terminate → join(10s) → kill
    """
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True

    sig_name = signal.Signals(signum).name
    logger.log('info', f'Получен {sig_name}, завершаю процессы...')
    logger_payments.log('warning', 'Логгер остановлен')
    print(f'[main] Получен {sig_name}, завершаю процессы...')

    for proc in _processes:
        if proc.is_alive():
            proc.terminate()

    for proc in _processes:
        proc.join(timeout=10)
        if proc.is_alive():
            logger.log('warning', f'Процесс {proc.name} не завершился за 10с, SIGKILL')
            proc.kill()
            proc.join(timeout=5)

    logger.log('info', 'Приложение остановлено')
    sys.exit(0)


def _start_process(target, name: str) -> multiprocessing.Process:
    proc = multiprocessing.Process(target=target, name=name, daemon=True)
    proc.start()
    return proc


if __name__ == "__main__":
    """
    Запуск модулей через multiprocessing с автоперезапуском
    """
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    logger.log('info', 'Запуск приложения')
    logger_payments.log('warning', 'Запуск логгера payments')

    # Автоочистка старых логов при старте
    logger.cleanup_old_logs()
    logger_payments.cleanup_old_logs()

    print('[main] Запуск приложения')

    bot_restart_count = 0
    checker_restart_count = 0

    bot_proc = _start_process(run_bot, 'bot')
    checker_proc = _start_process(run_checker, 'checker')
    _processes = [bot_proc, checker_proc]

    try:
        while not _shutting_down:
            if not bot_proc.is_alive():
                bot_restart_count += 1
                if bot_restart_count > MAX_RESTART_ATTEMPTS:
                    logger.log('error', f'Bot процесс упал {bot_restart_count} раз, останавливаю приложение')
                    break
                delay = min(RESTART_BASE_DELAY ** bot_restart_count, 60)
                logger.log('warning', f'Bot процесс упал (код {bot_proc.exitcode}), перезапуск #{bot_restart_count} через {delay}с')
                print(f'[main] Bot процесс упал (код {bot_proc.exitcode}), перезапуск #{bot_restart_count} через {delay}с')
                time.sleep(delay)
                bot_proc = _start_process(run_bot, 'bot')
                _processes[0] = bot_proc

            if not checker_proc.is_alive():
                checker_restart_count += 1
                if checker_restart_count > MAX_RESTART_ATTEMPTS:
                    logger.log('error', f'Checker процесс упал {checker_restart_count} раз, останавливаю приложение')
                    break
                delay = min(RESTART_BASE_DELAY ** checker_restart_count, 60)
                logger.log('warning', f'Checker процесс упал (код {checker_proc.exitcode}), перезапуск #{checker_restart_count} через {delay}с')
                print(f'[main] Checker процесс упал (код {checker_proc.exitcode}), перезапуск #{checker_restart_count} через {delay}с')
                time.sleep(delay)
                checker_proc = _start_process(run_checker, 'checker')
                _processes[1] = checker_proc

            time.sleep(1)
    finally:
        if not _shutting_down:
            _graceful_shutdown(signal.SIGTERM, None)


# Добавить получение ссылки (или файл) сразу на приложение по запросу платформы
# Проверить работу выбора региона, добавить возможность добавления регионов из бота
# Добавить проработку в случае отсутвия региона. Убрать его из env
