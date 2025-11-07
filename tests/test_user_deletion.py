"""
Тесты для функционала полного удаления пользователей.

Проверяет:
- hard_delete_user() в auth_storage.py - физическое удаление директорий
- delete_user() в auth_manager.py - публичный API удаления
- Защита от path traversal
- Проверка требований безопасности (is_active=False)

Задача: 08_del_user (#00007_20251105_YEIJEG)
Дата: 2025-11-07
Автор: python-pro
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime, timedelta

# Импорты должны работать из корня проекта
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_storage import AuthStorageManager
from auth_manager import AuthManager
from auth_models import User, UserSettings, UserMetadata

# ===== FIXTURES =====

@pytest.fixture
def temp_auth_dir():
    """
    Создать временную директорию для auth_data.

    Используется для изоляции тестов - каждый тест работает
    в своей собственной временной директории.

    Yields:
        Path: Путь к временной директории
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="voxpersona_test_"))
    yield temp_dir
    # Cleanup после теста - удалить временную директорию
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def auth_storage(temp_auth_dir):
    """
    Создать AuthStorageManager с временной директорией.

    Args:
        temp_auth_dir: Fixture временной директории

    Returns:
        AuthStorageManager: Инициализированный storage manager
    """
    storage = AuthStorageManager(temp_auth_dir)
    # Инициализировать структуру директорий
    storage.base_path.mkdir(parents=True, exist_ok=True)
    return storage

@pytest.fixture
def auth_manager(temp_auth_dir):
    """
    Создать AuthManager с временной директорией.

    Args:
        temp_auth_dir: Fixture временной директории

    Returns:
        AuthManager: Инициализированный auth manager
    """
    manager = AuthManager(temp_auth_dir)
    return manager

# ===== HELPER FUNCTIONS =====

def create_test_user(storage: AuthStorageManager, user_id: str = "test_user_123",
                     is_active: bool = True, username: str = "testuser") -> Path:
    """
    Создать тестового пользователя с директорией и файлами.

    Создает полную структуру пользователя:
    - user.json с корректными данными
    - sessions.json (пустой)
    - test_data.txt (для проверки полного удаления)

    Args:
        storage: AuthStorageManager для сохранения данных
        user_id: ID пользователя (по умолчанию "test_user_123")
        is_active: Флаг активности пользователя
        username: Имя пользователя

    Returns:
        Path: Путь к созданной директории пользователя
    """
    user_dir = storage.base_path / f"user_{user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)

    # Создать user.json с корректными данными
    user_data = {
        "user_id": user_id,
        "telegram_id": 123456789,
        "username": username,
        "password_hash": "$2b$12$dummy_hash_for_testing",
        "role": "user",
        "is_active": is_active,
        "is_blocked": not is_active,  # Инверсия is_active
        "must_change_password": False,
        "temp_password_expires_at": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "created_by_user_id": None,
        "last_login": None,
        "last_login_ip": None,
        "login_count": 0,
        "failed_login_attempts": 0,
        "last_failed_login": None,
        "password_changed_at": datetime.now().isoformat(),
        "settings": {
            "language": "ru",
            "timezone": "UTC+3",
            "notifications_enabled": True
        },
        "metadata": {
            "registration_source": "invite",
            "invite_code_used": None,
            "notes": ""
        }
    }
    storage.atomic_write(user_dir / "user.json", user_data)

    # Создать sessions.json для реалистичности
    sessions_data = {
        "schema_version": "1.0",
        "sessions": []
    }
    storage.atomic_write(user_dir / "sessions.json", sessions_data)

    # Создать тестовый файл для проверки полного удаления
    test_file = user_dir / "test_data.txt"
    test_file.write_text("test data for deletion verification")

    return user_dir

# ===== ТЕСТЫ УРОВЕНЬ 1: hard_delete_user() =====

def test_hard_delete_user_success(auth_storage):
    """
    Тест 1: Успешное физическое удаление soft-deleted пользователя.

    Проверяет что:
    - Soft-deleted пользователь (is_active=False) может быть удален
    - Директория пользователя полностью удалена
    - Все файлы внутри директории удалены
    - Метод возвращает True
    """
    # Arrange: Создать soft-deleted пользователя (is_active=False)
    user_id = "test_user_001"
    user_dir = create_test_user(auth_storage, user_id, is_active=False)

    # Проверить что директория существует перед удалением
    assert user_dir.exists(), "User directory should exist before deletion"
    assert (user_dir / "user.json").exists(), "user.json should exist"
    assert (user_dir / "sessions.json").exists(), "sessions.json should exist"
    assert (user_dir / "test_data.txt").exists(), "test_data.txt should exist"

    # Act: Удалить пользователя через hard_delete_user()
    result = auth_storage.hard_delete_user(user_id)

    # Assert: Проверить результаты удаления
    assert result is True, "hard_delete_user should return True for successful deletion"
    assert not user_dir.exists(), "User directory should be completely deleted"
    assert not (user_dir / "user.json").exists(), "user.json should be deleted"
    assert not (user_dir / "sessions.json").exists(), "sessions.json should be deleted"
    assert not (user_dir / "test_data.txt").exists(), "test_data.txt should be deleted"

def test_hard_delete_user_active_user(auth_storage):
    """
    Тест 2: Нельзя удалить активного пользователя (is_active=True).

    Проверяет защиту от случайного удаления:
    - Активный пользователь НЕ может быть удален
    - Директория остается нетронутой
    - Метод возвращает False
    """
    # Arrange: Создать АКТИВНОГО пользователя (is_active=True)
    user_id = "test_user_002"
    user_dir = create_test_user(auth_storage, user_id, is_active=True)

    assert user_dir.exists(), "User directory should exist"

    # Act: Попытаться удалить активного пользователя
    result = auth_storage.hard_delete_user(user_id)

    # Assert: Операция должна провалиться (защита от случайного удаления)
    assert result is False, "Cannot delete active user (is_active=True)"
    assert user_dir.exists(), "Active user directory should NOT be deleted"
    assert (user_dir / "user.json").exists(), "user.json should still exist for active user"

def test_hard_delete_user_path_traversal(auth_storage):
    """
    Тест 3: Защита от path traversal атаки.

    Проверяет что злоумышленник не может удалить файлы
    вне директории auth_data используя path traversal:
    - "../../../etc/passwd" - попытка выйти за пределы директории
    - "../../important_data" - относительные пути
    - Все попытки должны быть заблокированы
    """
    # Arrange: Создать вредоносные user_id с path traversal
    malicious_ids = [
        "../../../etc/passwd",      # Попытка выйти на 3 уровня вверх
        "../../important_data",      # Выход на 2 уровня
        "../outside_dir",            # Выход на 1 уровень
        "user/../../secret",         # Обход через подпапку
        "..\\..\\windows\\system32"  # Windows path traversal
    ]

    for malicious_id in malicious_ids:
        # Act: Попытаться удалить с вредоносным путем
        result = auth_storage.hard_delete_user(malicious_id)

        # Assert: Все попытки должны провалиться (защита от path traversal)
        assert result is False, f"Path traversal should be blocked for: {malicious_id}"

def test_hard_delete_user_nonexistent(auth_storage):
    """
    Тест 4: Удаление несуществующего пользователя.

    Проверяет что попытка удалить несуществующего пользователя:
    - Не приводит к ошибке
    - Возвращает False (операция не выполнена)
    - Не создает побочных эффектов
    """
    # Arrange: user_id который НЕ существует в системе
    nonexistent_id = "user_does_not_exist_999"
    user_dir = auth_storage.base_path / f"user_{nonexistent_id}"

    assert not user_dir.exists(), "User should not exist before test"

    # Act: Попытаться удалить несуществующего пользователя
    result = auth_storage.hard_delete_user(nonexistent_id)

    # Assert: Должен вернуть False (директория не существует)
    assert result is False, "Should return False for nonexistent user"

# ===== ТЕСТЫ УРОВЕНЬ 2: auth_manager.delete_user() =====

def test_auth_manager_delete_user_success(auth_manager):
    """
    Тест 5: Успешное удаление пользователя через AuthManager API.

    Проверяет полный workflow удаления:
    - Пользователь soft-deleted (is_active=False)
    - Вызов delete_user() через public API
    - Физическое удаление директории
    - Audit event записан в лог
    """
    # Arrange: Создать soft-deleted пользователя (is_active=False)
    user_id = "test_user_003"
    admin_id = "admin_001"

    # Создать пользователя вручную через storage
    user_dir = create_test_user(auth_manager.storage, user_id, is_active=False)

    assert user_dir.exists(), "User directory should exist before deletion"

    # Act: Удалить через публичный API AuthManager
    # ВАЖНО: метод async, используем asyncio
    import asyncio
    asyncio.run(auth_manager.delete_user(user_id, admin_id))

    # Assert: Пользователь полностью удален
    assert not user_dir.exists(), "User directory should be deleted"

    # Проверить что audit event создан (читаем последнюю строку auth_audit.log)
    audit_file = auth_manager.storage.base_path / "auth_audit.log"
    if audit_file.exists():
        with open(audit_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                import json
                last_event = json.loads(lines[-1])
                assert last_event['event_type'] == "USER_DELETED", "Audit event should be USER_DELETED"
                assert last_event['user_id'] == user_id, "Audit event should reference deleted user"

def test_auth_manager_delete_user_active_raises(auth_manager):
    """
    Тест 6: ValueError при попытке удалить активного пользователя.

    Проверяет защиту на уровне API:
    - Активный пользователь НЕ может быть удален через API
    - Выбрасывается ValueError с понятным сообщением
    - Пользователь остается нетронутым после ошибки
    """
    # Arrange: Создать АКТИВНОГО пользователя (is_active=True)
    user_id = "test_user_004"
    admin_id = "admin_001"

    user_dir = create_test_user(auth_manager.storage, user_id, is_active=True)
    assert user_dir.exists(), "User directory should exist"

    # Act & Assert: Должен выбросить ValueError
    import asyncio
    with pytest.raises(ValueError, match="Нельзя удалить активного пользователя"):
        asyncio.run(auth_manager.delete_user(user_id, admin_id))

    # Пользователь не должен быть удален после ошибки
    assert user_dir.exists(), "Active user should not be deleted on error"

def test_auth_manager_delete_user_nonexistent_raises(auth_manager):
    """
    Тест 7: ValueError при попытке удалить несуществующего пользователя.

    Проверяет валидацию на уровне API:
    - Несуществующий пользователь вызывает ValueError
    - Сообщение об ошибке информативное
    - Не происходит побочных эффектов
    """
    # Arrange: user_id который не существует в системе
    nonexistent_id = "user_nonexistent_999"
    admin_id = "admin_001"

    user_dir = auth_manager.storage.base_path / f"user_{nonexistent_id}"
    assert not user_dir.exists(), "User should not exist"

    # Act & Assert: Должен выбросить ValueError
    import asyncio
    with pytest.raises(ValueError, match="Пользователь не найден"):
        asyncio.run(auth_manager.delete_user(nonexistent_id, admin_id))


# ===== ДОПОЛНИТЕЛЬНЫЕ EDGE CASE ТЕСТЫ =====

def test_hard_delete_user_removes_lock_from_memory(auth_storage):
    """
    Тест 8: Проверка очистки per-user lock из памяти после удаления.

    КРИТИЧНО: Предотвращает memory leak при множественных удалениях.
    Проверяет что:
    - Lock создается при работе с пользователем
    - Lock удаляется из _user_locks после hard_delete_user()
    """
    # Arrange: Создать soft-deleted пользователя
    user_id = "test_user_005"
    user_dir = create_test_user(auth_storage, user_id, is_active=False)

    # Создать lock для пользователя (через вызов любого метода)
    _ = auth_storage.get_user(user_id)

    # Проверить что lock создан
    assert user_id in auth_storage._user_locks, "Lock should exist after user access"

    # Act: Удалить пользователя
    result = auth_storage.hard_delete_user(user_id)

    # Assert: Lock должен быть удален из памяти
    assert result is True, "Deletion should succeed"
    assert user_id not in auth_storage._user_locks, "Lock should be removed from memory"

def test_hard_delete_user_with_multiple_files(auth_storage):
    """
    Тест 9: Удаление пользователя с несколькими файлами в директории.

    Проверяет что рекурсивное удаление работает корректно:
    - Удаляются все файлы в директории
    - Удаляются вложенные поддиректории (если есть)
    - Сама директория пользователя удаляется
    """
    # Arrange: Создать пользователя с множеством файлов
    user_id = "test_user_006"
    user_dir = create_test_user(auth_storage, user_id, is_active=False)

    # Добавить дополнительные файлы и директории
    (user_dir / "extra_file1.txt").write_text("extra data 1")
    (user_dir / "extra_file2.json").write_text('{"key": "value"}')

    # Создать вложенную директорию с файлом
    subdir = user_dir / "subdirectory"
    subdir.mkdir()
    (subdir / "nested_file.txt").write_text("nested data")

    # Проверить что все создано
    assert (user_dir / "extra_file1.txt").exists()
    assert (user_dir / "extra_file2.json").exists()
    assert (subdir / "nested_file.txt").exists()

    # Act: Удалить пользователя
    result = auth_storage.hard_delete_user(user_id)

    # Assert: Все файлы и директории удалены
    assert result is True, "Deletion should succeed"
    assert not user_dir.exists(), "User directory should be completely deleted"
    assert not (user_dir / "extra_file1.txt").exists()
    assert not (user_dir / "extra_file2.json").exists()
    assert not subdir.exists(), "Nested subdirectory should be deleted"


# ===== INTEGRATION TESTS =====

def test_full_user_lifecycle_with_deletion(auth_manager):
    """
    Интеграционный тест: Полный жизненный цикл пользователя с удалением.

    Проверяет последовательность:
    1. Создание пользователя
    2. Блокировка пользователя (soft delete)
    3. Физическое удаление через API
    4. Проверка что все данные удалены
    """
    import asyncio

    # 1. Создать пользователя через storage (имитация регистрации)
    user_id = "test_user_007"
    user_dir = create_test_user(auth_manager.storage, user_id, is_active=True)

    assert user_dir.exists(), "User should be created"

    # 2. Блокировать пользователя (soft delete)
    asyncio.run(auth_manager.block_user(user_id, "admin_001"))

    # Проверить что пользователь заблокирован
    user = auth_manager.storage.get_user(user_id)
    assert user is not None
    assert user.is_blocked is True
    assert user.is_active is False

    # 3. Физически удалить пользователя
    asyncio.run(auth_manager.delete_user(user_id, "admin_001"))

    # 4. Проверить что все данные удалены
    assert not user_dir.exists(), "User directory should be deleted"
    deleted_user = auth_manager.storage.get_user(user_id)
    assert deleted_user is None, "User should not exist in storage"
