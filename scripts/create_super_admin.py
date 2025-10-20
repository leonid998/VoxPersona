"""
Скрипт для создания super_admin пользователя в production auth системе.

Использование:
    python scripts/create_super_admin.py <telegram_id> <username> <password>

Пример:
    python scripts/create_super_admin.py 155894817 admin Admin1!

Автор: backend-developer
Дата: 20 октября 2025
Задача: Исправление миграции (#00005_20251014_HRYHG)
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_manager import AuthManager
from auth_models import User
from auth_security import auth_security

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_super_admin(telegram_id: int, username: str, password: str) -> bool:
    """
    Создаёт super_admin пользователя в production auth системе.

    Args:
        telegram_id: Telegram ID пользователя
        username: Username пользователя (без @)
        password: Пароль для пользователя

    Returns:
        bool: True если успешно, False иначе
    """

    # Путь к auth_data (production)
    auth_dir = Path(__file__).parent.parent / "src" / "auth_data"
    auth_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📁 Auth data directory: {auth_dir}")
    logger.info(f"👤 Creating super_admin user:")
    logger.info(f"   - Telegram ID: {telegram_id}")
    logger.info(f"   - Username: {username}")
    logger.info(f"   - Role: super_admin")

    try:
        # Инициализируем AuthManager
        auth = AuthManager(auth_dir)

        # Проверяем существует ли пользователь
        existing_user = auth.storage.get_user_by_telegram_id(telegram_id)
        if existing_user:
            logger.error(f"❌ User with telegram_id={telegram_id} already exists!")
            logger.info(f"   - User ID: {existing_user.user_id}")
            logger.info(f"   - Username: {existing_user.username}")
            logger.info(f"   - Role: {existing_user.role}")
            return False

        # Валидация пароля (5-8 символов, буквы и цифры)
        is_valid, error_msg = auth_security.validate_password(password)
        if not is_valid:
            logger.error(f"❌ Password validation failed: {error_msg}")
            return False

        # Создаём пользователя напрямую через storage (bypass invitation system)
        # Это допустимо только для первого super_admin
        import uuid
        from datetime import datetime, timedelta

        user_data = User(
            user_id=str(uuid.uuid4()),
            telegram_id=telegram_id,
            username=username,
            password_hash=auth_security.hash_password(password),
            role="super_admin",
            is_active=True,
            is_blocked=False,
            must_change_password=False,  # Не требуем смены для первого admin
            failed_login_attempts=0,
            last_failed_login=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        success = auth.storage.create_user(user_data)

        if not success:
            logger.error("❌ Failed to create user in storage")
            return False

        user = user_data

        if user:
            logger.info("✅ Super_admin created successfully!")
            logger.info(f"📋 User details:")
            logger.info(f"   - User ID: {user.user_id}")
            logger.info(f"   - Telegram ID: {user.telegram_id}")
            logger.info(f"   - Username: {user.username}")
            logger.info(f"   - Role: {user.role}")
            logger.info(f"   - Active: {user.is_active}")
            logger.info(f"   - Blocked: {user.is_blocked}")
            logger.info(f"   - Must change password: {user.must_change_password}")
            logger.info("")
            logger.info("🎯 Next steps:")
            logger.info("  1. Test authentication in Telegram bot")
            logger.info("  2. Send /start to the bot")
            logger.info(f"  3. Enter password: {password}")
            logger.info("  4. Access admin menu via Системная → Настройки доступа")
            return True
        else:
            logger.error("❌ Failed to create user (unknown error)")
            return False

    except Exception as e:
        logger.error(f"❌ Error creating super_admin: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("=" * 70)
    print(" 🔐 VoxPersona Super Admin Creation Script")
    print("=" * 70)
    print()

    # Проверка аргументов
    if len(sys.argv) != 4:
        print("❌ Usage: python scripts/create_super_admin.py <telegram_id> <username> <password>")
        print()
        print("Example:")
        print("  python scripts/create_super_admin.py 155894817 admin Admin1!")
        print()
        print("Password requirements:")
        print("  - 5-8 characters")
        print("  - Must contain letters and digits")
        sys.exit(1)

    try:
        telegram_id = int(sys.argv[1])
        username = sys.argv[2]
        password = sys.argv[3]

        success = create_super_admin(telegram_id, username, password)

        if success:
            print()
            print("=" * 70)
            print("✅ SUCCESS: Super admin created!")
            print("=" * 70)
            sys.exit(0)
        else:
            print()
            print("=" * 70)
            print("❌ FAILED: Could not create super admin")
            print("=" * 70)
            sys.exit(1)

    except ValueError:
        logger.error("❌ Invalid telegram_id: must be a number")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
