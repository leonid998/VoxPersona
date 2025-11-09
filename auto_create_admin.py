"""
Автоматическое создание тестового super_admin.
Использует предопределённые значения для быстрого запуска.
"""

import sys
import logging
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auth_manager import AuthManager
from auth_models import User
from auth_security import auth_security

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def auto_create_admin():
    """Автоматически создаёт тестового super_admin."""

    # Предопределённые данные из тестов
    telegram_id = 155894817
    username = "test_crawler"
    password = "test1234"

    # Используем ту же директорию, что и main.py
    auth_dir = Path(__file__).parent / "src" / "auth_data"
    auth_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📁 Используется директория: {auth_dir}")
    logger.info(f"👤 Telegram ID: {telegram_id}")
    logger.info(f"👤 Username: {username}")

    try:
        # Инициализируем AuthManager
        auth = AuthManager(auth_dir)

        # Создаём пользователя
        user = User(
            user_id=f"test_{telegram_id}",
            telegram_id=telegram_id,
            username=username,
            password_hash=auth_security.hash_password(password),
            role="super_admin",
            is_active=True,
            is_blocked=False,
            must_change_password=False
        )

        # Сохраняем в storage
        success = auth.storage.create_user(user)

        if success:
            logger.info("✅ Тестовый super_admin создан успешно!")
            logger.info(f"📋 Telegram ID: {telegram_id}")
            logger.info(f"👤 Username: {username}")
            logger.info(f"🔐 Пароль: {password}")
            logger.info(f"👑 Роль: super_admin")
            logger.info(f"📁 Данные: {auth_dir}")
            logger.info("")
            logger.info("🎯 Теперь запустите:")
            logger.info("  1. python src/main.py")
            logger.info("  2. python menu_crawler.py")
            return True
        else:
            logger.error("❌ Пользователь уже существует или ошибка создания")
            logger.info("💡 Если нужно пересоздать, удалите файл:")
            logger.info(f"   {auth_dir / 'users' / f'test_{telegram_id}.json'}")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print(" Автоматическое создание тестового super_admin")
    print("=" * 60)
    print()
    success = auto_create_admin()
    sys.exit(0 if success else 1)
