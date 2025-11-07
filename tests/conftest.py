"""
Pytest фикстуры и конфигурация для тестов VoxPersona.

Предоставляет:
- Фикстуры для AuthManager с временным хранилищем
- Тестовых пользователей (активные, заблокированные)
- Утилиты для очистки данных между тестами
- Моки для внешних зависимостей

Автор: test-automator
Дата: 7 ноября 2025
Проект: VoxPersona User Management Tests
"""

import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Generator
import pytest

# Добавить src в PYTHONPATH для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_manager import AuthManager
from auth_security import AuthSecurityManager
from auth_models import User, Session, Role


@pytest.fixture(scope="function")
def temp_storage() -> Generator[Path, None, None]:
    """
    Временная директория для auth_data (изолированное хранилище).

    Создается перед каждым тестом и удаляется после.
    Гарантирует независимость тестов друг от друга.

    Yields:
        Path: Путь к временной директории

    Example:
        >>> def test_something(temp_storage):
        ...     auth_manager = AuthManager(base_path=temp_storage)
        ...     # тест использует изолированное хранилище
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="voxpersona_test_"))

    try:
        yield temp_dir
    finally:
        # Очистка после теста
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def auth_manager(temp_storage: Path) -> AuthManager:
    """
    Экземпляр AuthManager с временным хранилищем.

    Используется для всех тестов управления пользователями.
    Каждый тест получает чистый AuthManager без данных.

    Args:
        temp_storage: Фикстура временной директории

    Returns:
        AuthManager: Готовый к использованию auth manager

    Example:
        >>> def test_block_user(auth_manager):
        ...     user = await auth_manager.create_user(...)
        ...     result = await auth_manager.block_user(user.user_id, "admin123")
        ...     assert result is True
    """
    return AuthManager(base_path=temp_storage)


@pytest.fixture(scope="function")
def auth_security() -> AuthSecurityManager:
    """
    Экземпляр AuthSecurityManager для тестов паролей и токенов.

    Returns:
        AuthSecurityManager: Security manager с дефолтными настройками

    Example:
        >>> def test_validate_password(auth_security):
        ...     is_valid, msg = auth_security.validate_password("test123")
        ...     assert is_valid is True
    """
    return AuthSecurityManager()


@pytest.fixture
async def test_user_active(auth_manager: AuthManager) -> User:
    """
    Тестовый активный пользователь.

    Создает пользователя с:
    - is_active = True
    - is_blocked = False
    - role = "user"
    - Валидным паролем "test123"

    Args:
        auth_manager: Фикстура auth manager

    Returns:
        User: Созданный активный пользователь

    Example:
        >>> async def test_active_user(test_user_active):
        ...     assert test_user_active.is_active is True
        ...     assert test_user_active.is_blocked is False
    """
    # Создать приглашение для регистрации
    invitation = await auth_manager.create_invitation(
        created_by_user_id="system",
        target_role="user",
        expires_at=datetime.now() + timedelta(days=1)
    )

    # Зарегистрировать пользователя
    user = await auth_manager.register_user(
        telegram_id=123456789,
        username="test_active_user",
        password="test123",
        invite_code=invitation.invite_code
    )

    return user


@pytest.fixture
async def test_user_blocked(auth_manager: AuthManager) -> User:
    """
    Тестовый заблокированный пользователь.

    Создает пользователя с:
    - is_active = False
    - is_blocked = True
    - role = "user"
    - Валидным паролем "test456"

    Args:
        auth_manager: Фикстура auth manager

    Returns:
        User: Созданный заблокированный пользователь

    Example:
        >>> async def test_blocked_user(test_user_blocked):
        ...     assert test_user_blocked.is_active is False
        ...     assert test_user_blocked.is_blocked is True
    """
    # Создать приглашение
    invitation = await auth_manager.create_invitation(
        created_by_user_id="system",
        target_role="user",
        expires_at=datetime.now() + timedelta(days=1)
    )

    # Зарегистрировать пользователя
    user = await auth_manager.register_user(
        telegram_id=987654321,
        username="test_blocked_user",
        password="test456",
        invite_code=invitation.invite_code
    )

    # Заблокировать пользователя
    await auth_manager.block_user(user.user_id, "admin_test")

    # Получить обновленного пользователя
    blocked_user = await auth_manager.get_user(user.user_id)

    return blocked_user


@pytest.fixture
async def test_admin_user(auth_manager: AuthManager) -> User:
    """
    Тестовый пользователь с ролью admin.

    Используется для тестов прав доступа и административных действий.

    Args:
        auth_manager: Фикстура auth manager

    Returns:
        User: Созданный администратор

    Example:
        >>> async def test_admin_actions(test_admin_user, auth_manager):
        ...     can_block = await auth_manager.has_permission(
        ...         test_admin_user.user_id, "users.block"
        ...     )
        ...     assert can_block is True
    """
    # Создать приглашение для admin
    invitation = await auth_manager.create_invitation(
        created_by_user_id="system",
        target_role="admin",
        expires_at=datetime.now() + timedelta(days=1)
    )

    # Зарегистрировать admin
    admin = await auth_manager.register_user(
        telegram_id=111222333,
        username="test_admin",
        password="admin1",
        invite_code=invitation.invite_code
    )

    return admin


@pytest.fixture
def password_samples() -> dict:
    """
    Примеры паролей для тестирования валидации.

    Returns:
        dict: Словарь с категориями паролей
            - valid: Валидные пароли (5-8 символов, буквы + цифры)
            - invalid_length: Невалидная длина (< 5 или > 8)
            - invalid_no_letters: Только цифры
            - invalid_no_digits: Только буквы

    Example:
        >>> def test_validation(password_samples):
        ...     for pwd in password_samples['valid']:
        ...         is_valid, _ = validate_password(pwd)
        ...         assert is_valid is True
    """
    return {
        "valid": [
            "abc123",      # 6 символов, латиница + цифры
            "test1",       # 5 символов (минимум)
            "pass1234",    # 8 символов (максимум)
            "тест123",     # Кириллица + цифры
            "Qq1ww",       # Mixed case
            "a1b2c3",      # Чередование букв и цифр
        ],
        "invalid_length": [
            "abc1",        # 4 символа (< 5)
            "test12345",   # 9 символов (> 8)
            "ab12",        # 4 символа
            "verylongpassword123",  # Слишком длинный
        ],
        "invalid_no_letters": [
            "123456",      # Только цифры
            "999999",
            "12345",       # 5 цифр
        ],
        "invalid_no_digits": [
            "abcdef",      # Только буквы
            "password",
            "тестпароль",  # Только кириллица
        ],
    }


@pytest.fixture
def mock_user_dict():
    """
    Фабрика для создания моковых пользователей (dict формат).

    Используется для тестов отображения статуса без полной инициализации AuthManager.

    Returns:
        callable: Функция для создания моковых пользователей

    Example:
        >>> def test_status_display(mock_user_dict):
        ...     user = mock_user_dict(is_active=True)
        ...     status = "✅" if user["is_active"] else "🚫"
        ...     assert status == "✅"
    """
    def _create_mock_user(
        user_id: str = "test_user_123",
        username: str = "test_user",
        is_active: bool = True,
        role: str = "user"
    ) -> dict:
        """
        Создать мокового пользователя.

        Args:
            user_id: ID пользователя
            username: Имя пользователя
            is_active: Статус активности
            role: Роль пользователя

        Returns:
            dict: Словарь с данными пользователя
        """
        # Вычислить is_blocked на основе is_active (источник истины)
        is_blocked = not is_active

        return {
            "user_id": user_id,
            "username": username,
            "is_active": is_active,
            "is_blocked": is_blocked,  # Синхронизирован с is_active
            "role": role,
            "telegram_id": 123456789,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    return _create_mock_user


# Pytest хуки для настройки тестовой среды

def pytest_configure(config):
    """
    Конфигурация pytest перед запуском тестов.

    Регистрирует маркеры и настраивает окружение.
    """
    config.addinivalue_line(
        "markers", "auth: Тесты системы авторизации"
    )
    config.addinivalue_line(
        "markers", "user_management: Тесты управления пользователями"
    )
    config.addinivalue_line(
        "markers", "password: Тесты паролей"
    )
    config.addinivalue_line(
        "markers", "blocking: Тесты блокировки пользователей"
    )


def pytest_collection_modifyitems(config, items):
    """
    Модификация собранных тестов перед выполнением.

    Добавляет маркеры автоматически на основе имени теста.
    """
    for item in items:
        # Автоматически добавить маркер @pytest.mark.auth ко всем тестам auth модуля
        if "test_user_management" in item.nodeid:
            item.add_marker(pytest.mark.auth)
            item.add_marker(pytest.mark.user_management)

        # Добавить маркер slow для тестов с "slow" в имени
        if "slow" in item.name:
            item.add_marker(pytest.mark.slow)
