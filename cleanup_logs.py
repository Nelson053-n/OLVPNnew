#!/usr/bin/env python3
"""
Утилита для очистки и сжатия старых логов.

Использование:
    python cleanup_logs.py [--days DAYS] [--config CONFIG] [--compress] [--dry-run] [--all]

Примеры:
    python cleanup_logs.py --days 30 --all           # Удалить логи старше 30 дней
    python cleanup_logs.py --days 7 --compress       # Сжать логи старше 7 дней
    python cleanup_logs.py --days 30 --dry-run       # Проверка без удаления
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from logs.log_main import RotatingFileLogger


def main():
    parser = argparse.ArgumentParser(
        description='Очистка и сжатие старых логов',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=30,
        help='Удалять логи старше N дней (по умолчанию: 30)'
    )
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='logs/log_settings_base.json',
        help='Путь к конфигу (по умолчанию: logs/log_settings_base.json)'
    )
    parser.add_argument(
        '--config-payments',
        type=str,
        default='logs/log_settings_payments.json',
        help='Путь к конфигу платежей'
    )
    parser.add_argument(
        '--compress',
        action='store_true',
        help='Сжать старые логи вместо удаления'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Проверка без фактического удаления/сжатия'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Обработать все логи (основные + платежи)'
    )

    args = parser.parse_args()

    configs = []
    if args.all:
        configs.extend([
            ('base', args.config),
            ('payments', args.config_payments)
        ])
    else:
        configs.append(('base', args.config))

    total_deleted = 0
    total_compressed = 0

    for log_type, config_path in configs:
        print(f"\n{'='*50}")
        print(f"Обработка логов: {log_type}")
        print(f"{'='*50}")

        if not Path(config_path).exists():
            print(f"⚠️  Конфигурация не найдена: {config_path}")
            continue

        try:
            logger = RotatingFileLogger(config_file=config_path)

            log_files = logger.get_log_files()
            total_size_mb = logger.get_logs_size_mb()

            print(f"\nСтатистика:")
            print(f"  Файлов: {len(log_files)}")
            print(f"  Размер: {total_size_mb:.2f} MB")
            print(f"  Директория: {logger.log_dir}")

            if args.dry_run:
                print(f"\nDRY-RUN (файлы не будут удалены/сжаты)")
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=args.days)

                for log_file in log_files:
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        status = "Удаление" if not args.compress else "Сжатие"
                        print(f"  {status}: {log_file.name}")
            else:
                if args.compress:
                    compressed = logger.compress_old_logs(days_old=args.days)
                    total_compressed += compressed
                    print(f"\nСжато логов: {compressed}")
                else:
                    deleted = logger.cleanup_old_logs(force=True)
                    total_deleted += deleted
                    print(f"\nУдалено логов: {deleted}")

                remaining_files = logger.get_log_files()
                remaining_size_mb = logger.get_logs_size_mb()
                print(f"\nПосле очистки:")
                print(f"  Файлов: {len(remaining_files)}")
                print(f"  Размер: {remaining_size_mb:.2f} MB")
                print(f"  Освобождено: {total_size_mb - remaining_size_mb:.2f} MB")

        except Exception as e:
            print(f"Ошибка при обработке {log_type}: {e}")
            if not args.dry_run:
                return 1

    print(f"\n{'='*50}")
    print("Завершено!")
    if not args.dry_run:
        print(f"  Всего удалено: {total_deleted}")
        print(f"  Всего сжато: {total_compressed}")
    print(f"{'='*50}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
