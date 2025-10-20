"""
Скрипт миграции пользователей из config.authorized_users в новую auth систему.

Выполняет перенос существующих пользователей из старой системы авторизации
(config.authorized_users) в новую систему на базе AuthManager.

Логика миграции:
1. Для каждого telegram_id в config.authorized_users:
   - Генерируется случайный пароль (16 символов)
   - Получается username через Telegram API
   - Создается пользователь через auth_storage.create_user()
   - Устанавливается must_change_password=True
   - Устанавливается temp_password_expires_at = datetime.now() + timedelta(days=3)
   - Сохраняется пара (telegram_id, password) для отправки

Результат:
- Создается auth_data/migration_report.json с результатами миграции
- Логируются все успешные и неудачные операции

Автор: backend-developer
Дата: 20 октября 2025
Задача: T18 (#00005_20251014_HRYHG)
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

from pyrogram import Client
from config import API_ID, API_HASH, SESSION_NAME, authorized_users
from auth_manager import AuthManager
from auth_models import User, UserSettings, UserMetadata
from auth_storage import AuthStorageManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class UserMigrator:
    """
    Класс для миграции пользователей из старой системы в новую auth систему.

    Attributes:
        auth_manager: Экземпляр AuthManager для работы с auth системой
        client: Pyrogram Client для получения информации о пользователях
        migrated_users: Список успешно мигрированных пользователей
        failed_users: Список пользователей с ошибками миграции
    """

    def __init__(self, auth_data_path: Path, pyrogram_client: Client):
        """
        Инициализация мигратора.

        Args:
            auth_data_path: Путь к директории auth_data/
            pyrogram_client: Pyrogram Client для Telegram API
        """
        self.auth_manager = AuthManager(base_path=auth_data_path)
        self.client = pyrogram_client
        self.migrated_users = []
        self.failed_users = []

        logger.info(f"UserMigrator инициализирован (auth_data: {auth_data_path})")

    def _generate_temp_password(self) -> str:
        """
        Генерирует случайный временный пароль.

        Использует secrets.token_urlsafe(12) для создания криптографически
        стойкого пароля длиной ~16 символов (base64url encoded).

        Returns:
            str: Временный пароль
        """
        return secrets.token_urlsafe(12)

    def _hash_password(self, password: str) -> str:
        """
        Хеширует пароль через SHA256.

        TEMPORARY: Используется простое хеширование до реализации bcrypt в T09.

        Args:
            password: Открытый пароль

        Returns:
            str: SHA256 хеш пароля
        """
        return hashlib.sha256(password.encode()).hexdigest()

    async def get_telegram_username(self, telegram_id: int) -> str:
        """
        Получает username пользователя через Telegram API.

        Формирует username из first_name и last_name (если доступны).
        Fallback: "User{telegram_id}" если имя не найдено.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            str: Username пользователя
        """
        try:
            # Получить информацию о пользователе через Pyrogram
            user = await self.client.get_users(telegram_id)

            # Сформировать username из first_name и last_name
            username_parts = []
            if user.first_name:
                username_parts.append(user.first_name)
            if user.last_name:
                username_parts.append(user.last_name)

            if username_parts:
                username = " ".join(username_parts)
            else:
                # Fallback: использовать Telegram username или ID
                username = user.username if user.username else f"User{telegram_id}"

            logger.debug(f"Retrieved username for {telegram_id}: {username}")
            return username

        except Exception as e:
            logger.warning(
                f"Failed to retrieve username for {telegram_id}: {e}. "
                f"Using fallback: User{telegram_id}"
            )
            return f"User{telegram_id}"

    async def migrate_user(self, telegram_id: int) -> dict:
        """
        Мигрирует одного пользователя в новую auth систему.

        Процесс миграции:
        1. Генерация временного пароля
        2. Получение username через Telegram API
        3. Создание объекта User
        4. Сохранение через auth_storage.create_user()

        Args:
            telegram_id: Telegram ID пользователя для миграции

        Returns:
            dict: Результат миграции с полями:
                - telegram_id: int
                - username: str
                - temp_password: str (только при успехе)
                - role: str
                - success: bool
                - error: str (только при ошибке)
        """
        try:
            # 1. Проверить, не существует ли уже пользователь
            existing_user = self.auth_manager.storage.get_user_by_telegram_id(telegram_id)
            if existing_user:
                logger.warning(
                    f"User already exists in auth system: telegram_id={telegram_id}, "
                    f"user_id={existing_user.user_id}. Skipping."
                )
                return {
                    "telegram_id": telegram_id,
                    "username": existing_user.username,
                    "role": existing_user.role,
                    "success": False,
                    "error": "User already exists in auth system"
                }

            # 2. Генерация временного пароля
            temp_password = self._generate_temp_password()
            password_hash = self._hash_password(temp_password)

            # 3. Получение username через Telegram API
            username = await self.get_telegram_username(telegram_id)

            # 4. Создание объекта User
            user = User(
                user_id=str(uuid4()),
                telegram_id=telegram_id,
                username=username,
                password_hash=password_hash,
                role="user",  # Все мигрируемые пользователи = обычные пользователи
                must_change_password=True,  # КРИТИЧНО: Требовать смену временного пароля
                temp_password_expires_at=datetime.now() + timedelta(days=3),  # TTL=3 дня
                is_active=True,
                is_blocked=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                created_by_user_id="MIGRATION_SCRIPT",  # Метка миграции
                last_login=None,
                last_login_ip=None,
                login_count=0,
                failed_login_attempts=0,
                last_failed_login=None,
                password_changed_at=datetime.now(),
                settings=UserSettings(),
                metadata=UserMetadata(
                    registration_source="migration",
                    invite_code_used="MIGRATION",
                    notes="Migrated from config.authorized_users"
                )
            )

            # 5. Сохранить пользователя через storage
            if not self.auth_manager.storage.create_user(user):
                logger.error(f"Failed to create user in storage: telegram_id={telegram_id}")
                return {
                    "telegram_id": telegram_id,
                    "username": username,
                    "role": "user",
                    "success": False,
                    "error": "Failed to create user in storage"
                }

            logger.info(
                f"User migrated successfully: telegram_id={telegram_id}, "
                f"user_id={user.user_id}, username={username}"
            )

            return {
                "telegram_id": telegram_id,
                "username": username,
                "temp_password": temp_password,  # КРИТИЧНО: Сохранить для отправки
                "role": "user",
                "user_id": user.user_id,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error migrating user {telegram_id}: {e}", exc_info=True)
            return {
                "telegram_id": telegram_id,
                "username": "UNKNOWN",
                "role": "user",
                "success": False,
                "error": str(e)
            }

    async def migrate_all_users(self) -> dict:
        """
        Мигрирует всех пользователей из config.authorized_users.

        Обрабатывает всех пользователей последовательно, продолжает при ошибках.

        Returns:
            dict: Отчет о миграции с полями:
                - migration_date: str (ISO timestamp)
                - total_users: int (количество пользователей для миграции)
                - migrated: list (успешно мигрированные)
                - failed: list (ошибки миграции)
        """
        logger.info(f"Starting migration of {len(authorized_users)} users from config.authorized_users")

        # Обработать каждого пользователя
        for telegram_id in authorized_users:
            result = await self.migrate_user(telegram_id)

            if result["success"]:
                self.migrated_users.append(result)
            else:
                self.failed_users.append(result)

        # Сформировать отчет о миграции
        report = {
            "migration_date": datetime.now().isoformat(),
            "total_users": len(authorized_users),
            "migrated": self.migrated_users,
            "failed": self.failed_users
        }

        logger.info(
            f"Migration completed: {len(self.migrated_users)} migrated, "
            f"{len(self.failed_users)} failed"
        )

        return report

    def save_migration_report(self, report: dict, output_path: Path) -> None:
        """
        Сохраняет отчет о миграции в JSON файл.

        Args:
            report: Отчет о миграции (результат migrate_all_users)
            output_path: Путь к файлу для сохранения
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Migration report saved to: {output_path}")

        except Exception as e:
            logger.error(f"Failed to save migration report: {e}", exc_info=True)


async def main():
    """
    Главная функция скрипта миграции.

    Выполняет:
    1. Инициализацию Pyrogram Client
    2. Создание UserMigrator
    3. Миграцию всех пользователей
    4. Сохранение отчета о миграции
    """
    logger.info("=== VoxPersona User Migration Script ===")
    logger.info(f"Authorized users to migrate: {len(authorized_users)}")

    if not authorized_users:
        logger.warning("No users to migrate (config.authorized_users is empty)")
        return

    # Определить пути
    base_dir = Path(__file__).parent.parent
    auth_data_path = base_dir / "src" / "auth_data"
    report_path = auth_data_path / "migration_report.json"

    # Инициализировать Pyrogram Client
    client = Client(
        name=SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=str(base_dir / "src")
    )

    async with client:
        logger.info("Pyrogram Client connected")

        # Создать мигратор
        migrator = UserMigrator(auth_data_path=auth_data_path, pyrogram_client=client)

        # Выполнить миграцию
        report = await migrator.migrate_all_users()

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
                    f"  • ID: {user['telegram_id']} - Error: {user['error']}"
                )

        logger.info(f"\nMigration report saved to: {report_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
    except Exception as e:
        logger.error(f"Migration failed with error: {e}", exc_info=True)
        sys.exit(1)
