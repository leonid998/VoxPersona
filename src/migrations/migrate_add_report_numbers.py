#!/usr/bin/env python3
"""
Скрипт миграции для добавления постоянных номеров отчетов (report_number).

Что делает:
1. Создает бэкап всех файлов метаданных
2. Добавляет поле report_number в существующие отчеты
3. Нумерует отчеты по дате создания (от старых к новым)
4. Валидирует результаты (проверка дубликатов)
5. При ошибке выполняет rollback из бэкапа

Использование:
    python migrate_add_report_numbers.py [--dry-run] [--backup-dir PATH]

Опции:
    --dry-run          Режим тестирования (без реальных изменений)
    --backup-dir PATH  Путь для сохранения бэкапов (по умолчанию: ./backups)
"""

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
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


class MigrationError(Exception):
    """Исключение для ошибок миграции."""
    pass


class ReportNumberMigration:
    """Класс для миграции добавления постоянных номеров отчетов."""

    def __init__(self, reports_dir: Path, backup_dir: Optional[Path] = None, dry_run: bool = False):
        """
        Инициализация миграции.

        Args:
            reports_dir: Директория с отчетами
            backup_dir: Директория для бэкапов (по умолчанию: reports_dir/../backups)
            dry_run: Режим тестирования без реальных изменений
        """
        self.reports_dir = reports_dir
        self.backup_dir = backup_dir or reports_dir.parent / "backups"
        self.dry_run = dry_run
        self.backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path: Optional[Path] = None

        logger.info(f"Инициализация миграции:")
        logger.info(f"  - Директория отчетов: {self.reports_dir}")
        logger.info(f"  - Директория бэкапов: {self.backup_dir}")
        logger.info(f"  - Режим dry-run: {self.dry_run}")

    def create_backup(self) -> Path:
        """
        Создает бэкап всех файлов метаданных.

        Returns:
            Путь к директории с бэкапом

        Raises:
            MigrationError: При ошибке создания бэкапа
        """
        logger.info("Создание бэкапа...")

        try:
            # Создаем директорию для бэкапов
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Создаем директорию для конкретного бэкапа
            backup_path = self.backup_dir / f"backup_{self.backup_timestamp}"

            if self.dry_run:
                logger.info(f"[DRY-RUN] Бэкап будет создан в: {backup_path}")
                self.backup_path = backup_path
                return backup_path

            # Копируем всю директорию с отчетами
            shutil.copytree(self.reports_dir, backup_path)
            self.backup_path = backup_path

            logger.info(f"✅ Бэкап создан: {backup_path}")
            return backup_path

        except Exception as e:
            raise MigrationError(f"Ошибка создания бэкапа: {e}")

    def get_user_metadata_files(self) -> List[Path]:
        """
        Находит все файлы метаданных пользователей.

        Returns:
            Список путей к файлам reports_metadata.json
        """
        metadata_files = []

        # Ищем файлы метаданных в поддиректориях пользователей
        for user_dir in self.reports_dir.iterdir():
            if not user_dir.is_dir():
                continue

            metadata_file = user_dir / "reports_metadata.json"
            if metadata_file.exists():
                metadata_files.append(metadata_file)

        logger.info(f"Найдено файлов метаданных: {len(metadata_files)}")
        return metadata_files

    def migrate_user_metadata(self, metadata_file: Path) -> Dict:
        """
        Мигрирует файл метаданных одного пользователя.

        Args:
            metadata_file: Путь к файлу reports_metadata.json

        Returns:
            Словарь с результатами миграции

        Raises:
            MigrationError: При ошибке миграции
        """
        user_id = metadata_file.parent.name
        logger.info(f"Миграция метаданных пользователя {user_id}...")

        try:
            # Читаем файл метаданных
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)

            if not metadata_list:
                logger.info(f"  - Пользователь {user_id}: нет отчетов")
                return {'user_id': user_id, 'reports_count': 0, 'migrated': 0}

            # Сортируем отчеты по дате создания (от старых к новым)
            metadata_list.sort(key=lambda x: x.get('created_at', ''))

            # Добавляем report_number для каждого отчета
            migrated_count = 0
            for idx, report in enumerate(metadata_list, start=1):
                if 'report_number' not in report:
                    report['report_number'] = idx
                    migrated_count += 1

            # Сохраняем обновленные метаданные
            if not self.dry_run:
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata_list, f, ensure_ascii=False, indent=2)

            logger.info(f"  - Пользователь {user_id}: {len(metadata_list)} отчетов, {migrated_count} мигрировано")

            return {
                'user_id': user_id,
                'reports_count': len(metadata_list),
                'migrated': migrated_count
            }

        except Exception as e:
            raise MigrationError(f"Ошибка миграции пользователя {user_id}: {e}")

    def validate_migration(self) -> bool:
        """
        Валидирует результаты миграции.

        Проверяет:
        - Все отчеты имеют поле report_number
        - Нет дубликатов report_number для каждого пользователя
        - Номера начинаются с 1 и идут по порядку

        Returns:
            True если валидация успешна, False иначе
        """
        logger.info("Валидация результатов миграции...")

        metadata_files = self.get_user_metadata_files()
        validation_errors = []

        for metadata_file in metadata_files:
            user_id = metadata_file.parent.name

            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata_list = json.load(f)

                if not metadata_list:
                    continue

                # Проверяем наличие report_number
                missing_number = [i for i, r in enumerate(metadata_list, 1) if 'report_number' not in r]
                if missing_number:
                    validation_errors.append(
                        f"Пользователь {user_id}: отчеты без report_number: {missing_number}"
                    )

                # Проверяем дубликаты
                report_numbers = [r.get('report_number') for r in metadata_list if 'report_number' in r]
                if len(report_numbers) != len(set(report_numbers)):
                    duplicates = [n for n in report_numbers if report_numbers.count(n) > 1]
                    validation_errors.append(
                        f"Пользователь {user_id}: дубликаты report_number: {set(duplicates)}"
                    )

                # Проверяем последовательность (должны идти с 1 по порядку)
                sorted_numbers = sorted(report_numbers)
                expected_numbers = list(range(1, len(report_numbers) + 1))
                if sorted_numbers != expected_numbers:
                    validation_errors.append(
                        f"Пользователь {user_id}: номера не идут по порядку: {sorted_numbers}"
                    )

            except Exception as e:
                validation_errors.append(f"Ошибка валидации пользователя {user_id}: {e}")

        if validation_errors:
            logger.error("❌ Валидация провалилась:")
            for error in validation_errors:
                logger.error(f"  - {error}")
            return False

        logger.info("✅ Валидация успешна")
        return True

    def rollback(self):
        """
        Откатывает изменения из бэкапа.

        Raises:
            MigrationError: При ошибке отката
        """
        if not self.backup_path or not self.backup_path.exists():
            raise MigrationError("Бэкап не найден, откат невозможен")

        logger.info(f"Откат изменений из бэкапа {self.backup_path}...")

        if self.dry_run:
            logger.info("[DRY-RUN] Откат будет выполнен из бэкапа")
            return

        try:
            # Удаляем текущую директорию с отчетами
            if self.reports_dir.exists():
                shutil.rmtree(self.reports_dir)

            # Восстанавливаем из бэкапа
            shutil.copytree(self.backup_path, self.reports_dir)

            logger.info("✅ Откат выполнен успешно")

        except Exception as e:
            raise MigrationError(f"Ошибка отката: {e}")

    def run(self) -> bool:
        """
        Запускает миграцию.

        Returns:
            True если миграция успешна, False иначе
        """
        try:
            # 1. Создаем бэкап
            self.create_backup()

            # 2. Находим все файлы метаданных
            metadata_files = self.get_user_metadata_files()

            if not metadata_files:
                logger.warning("Файлы метаданных не найдены, миграция не требуется")
                return True

            # 3. Мигрируем каждого пользователя
            total_reports = 0
            total_migrated = 0

            for metadata_file in metadata_files:
                result = self.migrate_user_metadata(metadata_file)
                total_reports += result['reports_count']
                total_migrated += result['migrated']

            logger.info(f"Миграция завершена:")
            logger.info(f"  - Всего отчетов: {total_reports}")
            logger.info(f"  - Мигрировано: {total_migrated}")

            # 4. Валидируем результаты
            if not self.validate_migration():
                logger.error("Миграция провалилась на этапе валидации")
                if not self.dry_run:
                    logger.info("Выполняется откат...")
                    self.rollback()
                return False

            logger.info("✅ Миграция выполнена успешно!")
            return True

        except MigrationError as e:
            logger.error(f"❌ Ошибка миграции: {e}")
            if not self.dry_run and self.backup_path:
                logger.info("Выполняется откат...")
                try:
                    self.rollback()
                except MigrationError as rollback_error:
                    logger.error(f"❌ Ошибка отката: {rollback_error}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}")
            if not self.dry_run and self.backup_path:
                logger.info("Выполняется откат...")
                try:
                    self.rollback()
                except MigrationError as rollback_error:
                    logger.error(f"❌ Ошибка отката: {rollback_error}")
            return False


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
        '--backup-dir',
        type=Path,
        help='Путь для сохранения бэкапов (по умолчанию: ./backups)'
    )
    parser.add_argument(
        '--reports-dir',
        type=Path,
        default=Path('reports'),
        help='Путь к директории с отчетами (по умолчанию: ./reports)'
    )

    args = parser.parse_args()

    # Проверяем существование директории с отчетами
    if not args.reports_dir.exists():
        logger.error(f"Директория с отчетами не найдена: {args.reports_dir}")
        sys.exit(1)

    # Запускаем миграцию
    migration = ReportNumberMigration(
        reports_dir=args.reports_dir,
        backup_dir=args.backup_dir,
        dry_run=args.dry_run
    )

    success = migration.run()

    if success:
        logger.info("🎉 Миграция завершена успешно!")
        sys.exit(0)
    else:
        logger.error("💥 Миграция провалилась")
        sys.exit(1)


if __name__ == '__main__':
    main()
