"""
Тестовая версия скрипта миграции пользователей.

Создает тестовых пользователей в auth системе для проверки логики миграции.
Использует mock данные вместо реального Telegram API.

Автор: backend-developer
Дата: 20 октября 2025
"""

import asyncio
import hashlib
import json
import logging
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Добавить путь к src для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_manager import AuthManager
from auth_models import User, UserSettings, UserMetadata

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Mock данные для тестирования
TEST_USERS = [
    {"telegram_id": 111111111, "username": "Тестовый Пользователь 1"},
    {"telegram_id": 222222222, "username": "Тестовый Пользователь 2"},
    {"telegram_id": 333333333, "username": "Test User 3"},
]


class MockUserMigrator:
    """
    Mock версия UserMigrator для тестирования.
    """

    def __init__(self, auth_data_path: Path):
        """Инициализация мигратора."""
        self.auth_manager = AuthManager(base_path=auth_data_path)
        self.migrated_users = []
        self.failed_users = []
        logger.info(f"MockUserMigrator инициализирован (auth_data: {auth_data_path})")

    def _generate_temp_password(self) -> str:
        """Генерирует случайный временный пароль."""
        return secrets.token_urlsafe(12)

    def _hash_password(self, password: str) -> str:
        """Хеширует пароль через SHA256."""
        return hashlib.sha256(password.encode()).hexdigest()

    async def migrate_user(self, telegram_id: int, username: str) -> dict:
        """
        Мигрирует одного пользователя (mock версия).

        Args:
            telegram_id: Telegram ID пользователя
            username: Username для пользователя (mock данные)

        Returns:
            dict: Результат миграции
        """
        try:
            # 1. Проверить, не существует ли уже пользователь
            existing_user = self.auth_manager.storage.get_user_by_telegram_id(telegram_id)
            if existing_user:
                logger.warning(
                    f"User already exists: telegram_id={telegram_id}, "
                    f"user_id={existing_user.user_id}. Skipping."
                )
                return {
                    "telegram_id": telegram_id,
                    "username": existing_user.username,
                    "role": existing_user.role,
                    "success": False,
                    "error": "User already exists"
                }

            # 2. Генерация временного пароля
            temp_password = self._generate_temp_password()
            password_hash = self._hash_password(temp_password)

            # 3. Создание объекта User
            user = User(
                user_id=str(uuid4()),
                telegram_id=telegram_id,
                username=username,
                password_hash=password_hash,
                role="user",
                must_change_password=True,
                temp_password_expires_at=datetime.now() + timedelta(days=3),
                is_active=True,
                is_blocked=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by_user_id="TEST_MIGRATION_SCRIPT",
                last_login=None,
                last_login_ip=None,
                login_count=0,
                failed_login_attempts=0,
                last_failed_login=None,
                password_changed_at=datetime.now(),
                settings=UserSettings(),
                metadata=UserMetadata(
                    registration_source="test_migration",
                    invite_code_used="TEST_MIGRATION",
                    notes="Test migration from mock data"
                )
            )

            # 4. Сохранить пользователя
            if not self.auth_manager.storage.create_user(user):
                logger.error(f"Failed to create user: telegram_id={telegram_id}")
                return {
                    "telegram_id": telegram_id,
                    "username": username,
                    "role": "user",
                    "success": False,
                    "error": "Failed to create user in storage"
                }

            logger.info(
                f"User migrated successfully: telegram_id={telegram_id}, "
                f"user_id={user.user_id}, username={username}, "
                f"temp_password={temp_password}"
            )

            return {
                "telegram_id": telegram_id,
                "username": username,
                "temp_password": temp_password,
                "role": "user",
                "user_id": user.user_id,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error migrating user {telegram_id}: {e}", exc_info=True)
            return {
                "telegram_id": telegram_id,
                "username": username,
                "role": "user",
                "success": False,
                "error": str(e)
            }

    async def migrate_all_users(self, test_users: list) -> dict:
        """
        Мигрирует всех тестовых пользователей.

        Args:
            test_users: Список словарей с telegram_id и username

        Returns:
            dict: Отчет о миграции
        """
        logger.info(f"Starting test migration of {len(test_users)} users")

        for user_data in test_users:
            result = await self.migrate_user(
                telegram_id=user_data["telegram_id"],
                username=user_data["username"]
            )

            if result["success"]:
                self.migrated_users.append(result)
            else:
                self.failed_users.append(result)

        report = {
            "migration_date": datetime.now().isoformat(),
            "total_users": len(test_users),
            "migrated": self.migrated_users,
            "failed": self.failed_users
        }

        logger.info(
            f"Migration completed: {len(self.migrated_users)} migrated, "
            f"{len(self.failed_users)} failed"
        )

        return report

    def save_migration_report(self, report: dict, output_path: Path) -> None:
        """Сохраняет отчет о миграции."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Migration report saved to: {output_path}")

        except Exception as e:
            logger.error(f"Failed to save migration report: {e}", exc_info=True)


async def main():
    """Главная функция тестового скрипта."""
    logger.info("=== VoxPersona Test User Migration ===")
    logger.info(f"Test users to migrate: {len(TEST_USERS)}")

    # Определить пути
    base_dir = Path(__file__).parent.parent
    auth_data_path = base_dir / "src" / "auth_data"
    report_path = auth_data_path / "test_migration_report.json"

    # Создать мигратор
    migrator = MockUserMigrator(auth_data_path=auth_data_path)

    # Выполнить миграцию
    report = await migrator.migrate_all_users(TEST_USERS)

    # Сохранить отчет
    migrator.save_migration_report(report, report_path)

    # Вывести итоговую статистику
    logger.info("=== Migration Summary ===")
    logger.info(f"Total users: {report['total_users']}")
    logger.info(f"Successfully migrated: {len(report['migrated'])}")
    logger.info(f"Failed: {len(report['failed'])}")

    if report['migrated']:
        logger.info("\n--- Migrated Users ---")
        for user in report['migrated']:
            logger.info(
                f"  • {user['username']} (ID: {user['telegram_id']}) - "
                f"Password: {user['temp_password']}"
            )

    if report['failed']:
        logger.warning("\n--- Failed Users ---")
        for user in report['failed']:
            logger.warning(
                f"  • {user['username']} (ID: {user['telegram_id']}) - "
                f"Error: {user['error']}"
            )

    logger.info(f"\nTest migration report saved to: {report_path}")

    # Проверить созданных пользователей
    logger.info("\n=== Verification ===")
    for migrated_user in report['migrated']:
        user = migrator.auth_manager.storage.get_user_by_telegram_id(
            migrated_user['telegram_id']
        )
        if user:
            logger.info(
                f"✓ User verified: {user.username} (user_id={user.user_id}, "
                f"must_change_password={user.must_change_password}, "
                f"temp_password_expires_at={user.temp_password_expires_at})"
            )
        else:
            logger.error(f"✗ User NOT found: telegram_id={migrated_user['telegram_id']}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test migration interrupted by user")
    except Exception as e:
        logger.error(f"Test migration failed: {e}", exc_info=True)
        sys.exit(1)
