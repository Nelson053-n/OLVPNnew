"""
Модуль ротационного логгирования с расширенными возможностями.

Features:
- Ротация по времени (ежедневно в полночь UTC)
- Автоматическая очистка старых логов
- Сжатие старых логов (gzip, опционально)
- Мониторинг размера логов
- Глобальный обработчик исключений
"""
import logging
import os
import json
import sys
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import List, Optional


class RotatingFileLogger:
    """
    Расширенный логгер с ротацией, очисткой и сжатием.
    """

    def __init__(self, config_file: str = 'logs/log_settings_base.json'):
        """
        Инициализация логгера.

        :param config_file: Путь к JSON файлу конфигурации
        """
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self.log_dir = Path(config.get('log_dir', 'logs/base'))
        self.log_file_format = config.get('log_file_format', '%Y-%m-%d.log')
        self.max_bytes = config.get('max_bytes', 200000000)
        self.backup_count = config.get('backup_count', 7)
        self.use_compression = config.get('use_compression', False)
        self.log_name = config.get('log_name', None)
        self.log_filename = config.get('log_filename', 'olvpnbot.log')

        self.logger = logging.getLogger(name=self.log_name)
        self.logger.setLevel(logging.INFO)

        self._handler_added = False

        self.setup_logging()

        if self.log_dir.name == 'base':
            sys.excepthook = self.handle_exception

    def setup_logging(self):
        """Настройка хендлеров логгирования"""
        if self._handler_added:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)

        log_file_path = self.log_dir / self.log_filename
        handler = TimedRotatingFileHandler(
            filename=str(log_file_path),
            when='midnight',
            interval=1,
            backupCount=self.backup_count,
            encoding='utf-8',
            delay=False,
            utc=True
        )
        handler.suffix = self.log_file_format
        handler.extMatch = r'^\d{4}-\d{2}-\d{2}.log$'

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        if os.getenv('DEBUG_LOGGING', 'false').lower() == 'true':
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        self._handler_added = True
        self.cleanup_old_logs()

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Глобальный обработчик необработанных исключений"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self.logger.error(
            "Необработанное исключение",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    def log(self, level: str, message: str) -> None:
        """
        Запись сообщения в лог.

        :param level: Уровень (debug, info, warning, error, critical)
        :param message: Сообщение
        """
        level_map = {
            'debug': self.logger.debug,
            'info': self.logger.info,
            'warning': self.logger.warning,
            'error': self.logger.error,
            'critical': self.logger.critical
        }

        if level not in level_map:
            raise ValueError(
                f'Некорректный уровень: {level}. Допустимые: {list(level_map.keys())}'
            )

        level_map[level](message)

    def get_log_files(self) -> List[Path]:
        """Получить список всех файлов логов"""
        if not self.log_dir.exists():
            return []
        return sorted(
            self.log_dir.glob('*.log*'),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

    def cleanup_old_logs(self, force: bool = False) -> int:
        """
        Очистка старых логов.

        :param force: Принудительная очистка
        :return: Количество удаленных файлов
        """
        if not self.log_dir.exists():
            return 0

        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.backup_count)

        for log_file in self.log_dir.glob('*.log*'):
            if self._is_active_log_file(log_file):
                continue

            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if force or file_mtime < cutoff_date:
                try:
                    log_file.unlink()
                    deleted_count += 1
                    self.logger.info(f"Удален старый лог: {log_file}")
                except Exception as e:
                    self.logger.error(f"Ошибка при удалении {log_file}: {e}")

        return deleted_count

    def _is_active_log_file(self, file_path: Path) -> bool:
        """Проверка, является ли файл активным логом"""
        try:
            if file_path.name == self.log_filename:
                return True

            date_str = file_path.name.replace('.log', '').replace('.gz', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            return file_date.date() == datetime.now().date()
        except (ValueError, AttributeError):
            return False

    def compress_old_logs(self, days_old: int = 3) -> int:
        """
        Сжатие старых логов в gzip.

        :param days_old: Сжимать логи старше N дней
        :return: Количество сжатых файлов
        """
        if not self.use_compression:
            return 0

        compressed_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)

        for log_file in self.log_dir.glob('*.log'):
            if self._is_active_log_file(log_file):
                continue

            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                try:
                    gz_path = log_file.with_suffix(log_file.suffix + '.gz')
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()
                    compressed_count += 1
                    self.logger.info(f"Сжат лог: {log_file} -> {gz_path}")
                except Exception as e:
                    self.logger.error(f"Ошибка при сжатии {log_file}: {e}")

        return compressed_count

    def get_logs_size(self) -> int:
        """Общий размер всех логов в байтах"""
        return sum(f.stat().st_size for f in self.get_log_files())

    def get_logs_size_mb(self) -> float:
        """Общий размер всех логов в МБ"""
        return self.get_logs_size() / (1024 * 1024)


def cleanup_logs(config_file: str = 'logs/log_settings_base.json', days_old: int = 30) -> int:
    """
    Функция для очистки логов (для cron).

    :param config_file: Путь к конфигурации
    :param days_old: Удалять логи старше N дней
    :return: Количество удаленных файлов
    """
    logger = RotatingFileLogger(config_file)
    deleted = logger.cleanup_old_logs(force=True)
    logger.log('info', f'Очистка логов: удалено {deleted} файлов')
    return deleted


if __name__ == "__main__":
    logger = RotatingFileLogger()
    logger.log('info', 'Тестовое сообщение')

    print(f"Директория: {logger.log_dir}")
    print(f"Размер: {logger.get_logs_size_mb():.2f} MB")
    print(f"Файлов: {len(logger.get_log_files())}")

    deleted = logger.cleanup_old_logs()
    print(f"Удалено: {deleted}")
