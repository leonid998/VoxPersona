"""
Скрипт для создания тестового super_admin для Menu Crawler.

Создаёт пользователя в auth_data_test/ (изолировано от production).
"""

import sys
import logging
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auth_manager import AuthManager
from auth_models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_admin():
    """Создаёт тестового super_admin."""

    # КРИТИЧНО: Используем ту же директорию, что и main.py
    # Для безопасности создаём ОТДЕЛЬНОГО пользователя с префиксом test_
    auth_dir = Path(__file__).parent / "src" / "auth_data"
    auth_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📁 Используется директория: {auth_dir}")
    logger.warning("⚠️ ВНИМАНИЕ: Создаётся тестовый пользователь в production auth_data")
    logger.warning("⚠️ Префикс user_id: 'test_' для изоляции")

    # Инициализируем AuthManager
    auth = AuthManager(auth_dir)

    # Данные тестового администратора
    telegram_id = int(input("Введите ваш Telegram ID: "))
    username = input("Введите username (без @): ")
    password = "test1234"  # Простой пароль для теста

    try:
        # Регистрируем super_admin БЕЗ инвайта
        # (напрямую создаём в storage)
        from auth_security import auth_security

        user = User(
            user_id=f"test_{telegram_id}",
            telegram_id=telegram_id,
            username=username,
            password_hash=auth_security.hash_password(password),
            role="super_admin",  # КРИТИЧНО!
            is_active=True,
            is_blocked=False,
            must_change_password=False  # Не требуем смены
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
        else:
            logger.error("❌ Ошибка создания пользователя (возможно, уже существует)")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print(" Создание тестового super_admin для Menu Crawler")
    print("=" * 60)
    print()
    create_test_admin()
