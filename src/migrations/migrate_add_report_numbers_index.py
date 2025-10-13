#!/usr/bin/env python3
"""
Скрипт миграции для добавления постоянных номеров отчетов (report_number).
Версия для единого index.json файла.

Что делает:
1. Создает бэкап index.json
2. Добавляет поле report_number в существующие отчеты
3. Нумерует отчеты по дате создания (от старых к новым) для каждого пользователя
4. Валидирует результаты (проверка дубликатов)
5. При ошибке выполняет rollback из бэкапа

Использование:
    python migrate_add_report_numbers_index.py [--dry-run] [--reports-dir PATH]
"""

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import argparse

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Главная функция скрипта."""
    parser = argparse.ArgumentParser(
        description='Миграция для добавления постоянных номеров отчетов (report_number)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Режим тестирования без реальных изменений'
    )
    parser.add_argument(
        '--reports-dir',
        type=str,
        default='md_reports',
        help='Путь к директории с отчетами (по умолчанию: md_reports)'
    )

    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    index_file = reports_dir / "index.json"

    if not index_file.exists():
        logger.error(f"Файл index.json не найден: {index_file}")
        sys.exit(1)

    logger.info(f"Инициализация миграции:")
    logger.info(f"  - Директория отчетов: {reports_dir}")
    logger.info(f"  - Файл index.json: {index_file}")
    logger.info(f"  - Режим dry-run: {args.dry_run}")

    try:
        # 1. Создаем бэкап
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = reports_dir / f"index.json.backup_{timestamp}"

        if args.dry_run:
            logger.info(f"[DRY-RUN] Бэкап будет создан: {backup_file}")
        else:
            shutil.copy2(index_file, backup_file)
            logger.info(f"✅ Бэкап создан: {backup_file}")

        # 2. Читаем index.json
        with open(index_file, 'r', encoding='utf-8') as f:
            reports = json.load(f)

        logger.info(f"Найдено отчетов: {len(reports)}")

        # 3. Группируем по пользователям
        users_reports: Dict[int, List[dict]] = {}
        for report in reports:
            user_id = report.get('user_id')
            if user_id not in users_reports:
                users_reports[user_id] = []
            users_reports[user_id].append(report)

        logger.info(f"Найдено пользователей: {len(users_reports)}")

        # 4. Добавляем report_number для каждого пользователя
        total_migrated = 0

        for user_id, user_reports in users_reports.items():
            # Сортируем по timestamp (старые первые)
            user_reports.sort(key=lambda x: x.get('timestamp', ''))

            # Присваиваем номера
            migrated_count = 0
            for idx, report in enumerate(user_reports, start=1):
                if 'report_number' not in report:
                    report['report_number'] = idx
                    migrated_count += 1

            logger.info(f"  - Пользователь {user_id}: {len(user_reports)} отчетов, {migrated_count} мигрировано")
            total_migrated += migrated_count

        logger.info(f"Всего мигрировано отчетов: {total_migrated}")

        # 5. Валидация
        logger.info("Валидация результатов...")
        validation_errors = []

        for user_id, user_reports in users_reports.items():
            # Проверяем наличие report_number
            missing = [i for i, r in enumerate(user_reports, 1) if 'report_number' not in r]
            if missing:
                validation_errors.append(f"Пользователь {user_id}: отчеты без report_number: {missing}")

            # Проверяем дубликаты
            numbers = [r.get('report_number') for r in user_reports if 'report_number' in r]
            if len(numbers) != len(set(numbers)):
                duplicates = [n for n in numbers if numbers.count(n) > 1]
                validation_errors.append(f"Пользователь {user_id}: дубликаты: {set(duplicates)}")

            # Проверяем последовательность
            sorted_numbers = sorted(numbers)
            expected = list(range(1, len(numbers) + 1))
            if sorted_numbers != expected:
                validation_errors.append(f"Пользователь {user_id}: не последовательные номера: {sorted_numbers}")

        if validation_errors:
            logger.error("❌ Валидация провалилась:")
            for error in validation_errors:
                logger.error(f"  - {error}")

            if not args.dry_run:
                logger.info("Откат из бэкапа...")
                shutil.copy2(backup_file, index_file)
                logger.info("✅ Откат выполнен")

            sys.exit(1)

        logger.info("✅ Валидация успешна")

        # 6. Сохраняем обновленный index.json
        if args.dry_run:
            logger.info("[DRY-RUN] Изменения НЕ сохранены")
        else:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(reports, f, ensure_ascii=False, indent=2)
            logger.info("✅ Обновленный index.json сохранен")

        logger.info("🎉 Миграция завершена успешно!")

        # Показываем примеры обновленных записей
        if users_reports:
            user_id = list(users_reports.keys())[0]
            sample_reports = users_reports[user_id][:3]
            logger.info(f"\nПример обновленных записей (пользователь {user_id}):")
            for report in sample_reports:
                logger.info(f"  - [{report.get('report_number')}] {report.get('timestamp')} - {report.get('file_path')}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
