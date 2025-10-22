#!/usr/bin/env python3
"""
Скрипт для установки роли super_admin для TEST_USER
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ['ENV'] = 'production'

from src.auth_storage import AuthStorage


def main():
    """Установить роль super_admin для TEST_USER"""

    TEST_USER_TELEGRAM_ID = 155894817

    print(f"🔍 Поиск TEST_USER (telegram_id: {TEST_USER_TELEGRAM_ID})...")

    # Инициализация AuthStorage
    storage = AuthStorage()

    # Поиск пользователя
    user = storage.get_user_by_telegram_id(TEST_USER_TELEGRAM_ID)

    if not user:
        print(f"❌ TEST_USER не найден (telegram_id: {TEST_USER_TELEGRAM_ID})")
        return 1

    print(f"✅ Найден TEST_USER:")
    print(f"   Username: {user.username}")
    print(f"   User ID: {user.user_id}")
    print(f"   Current role: {user.role}")
    print(f"   Telegram ID: {user.telegram_id}")
    print()

    # Проверка текущей роли
    if user.role == 'super_admin':
        print(f"ℹ️  Роль уже super_admin. Изменений не требуется.")
        return 0

    # Изменение роли
    print(f"🔄 Изменение роли с '{user.role}' на 'super_admin'...")

    user.role = 'super_admin'

    # Сохранение изменений
    success = storage.update_user(user)

    if success:
        print(f"✅ Роль успешно изменена на: super_admin")
        print()
        print(f"🎉 TEST_USER теперь имеет полный доступ к меню 'Настройки доступа'!")
        return 0
    else:
        print(f"❌ Ошибка при сохранении изменений")
        return 1


if __name__ == '__main__':
    sys.exit(main())
