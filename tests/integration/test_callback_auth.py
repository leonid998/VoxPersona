"""
Интеграционные тесты для авторизации callback_query.

Проверяет функцию verify_callback_auth() в handlers.py, которая:
- Блокирует удаленных пользователей (не найден в БД)
- Блокирует неактивных пользователей (is_active=False)
- Блокирует заблокированных пользователей (is_blocked=True)
- Блокирует пользователей без активной сессии
- Пропускает авторизованных пользователей с активной сессией

Связано с задачей: 08_pass_change (#00007_20251105_YEIJEG)
Дата: 2025-11-07
Автор: Claude Code (test-automator role)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Добавить src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# ⚠️ ВАЖНО: НЕ импортировать handlers на уровне модуля!
# handlers.py при импорте инициализирует MinIO, который недоступен в тестах.
# Импорт handlers будет внутри каждого теста ПОСЛЕ установки моков.

from auth_models import User, Session


# ==================== FIXTURES ====================

@pytest.fixture(autouse=True)
def mock_minio():
    """
    Мок MinIO для всех тестов (autouse).

    Патчит get_minio_manager чтобы избежать MinIOConnectionError при импорте handlers.
    """
    with patch("minio_manager.get_minio_manager", return_value=MagicMock()):
        yield


@pytest.fixture
def active_user():
    """
    Создать активного пользователя с сессией.

    Returns:
        User: Активный пользователь
    """
    return User(
        user_id="active_user_123",
        telegram_id=123456789,
        username="active_user",
        password_hash="$2b$12$dummy_hash",
        role="user",
        is_active=True,
        is_blocked=False,
        must_change_password=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def inactive_user():
    """
    Создать неактивного пользователя.

    Returns:
        User: Неактивный пользователь (is_active=False)
    """
    return User(
        user_id="inactive_user_456",
        telegram_id=987654321,
        username="inactive_user",
        password_hash="$2b$12$dummy_hash",
        role="user",
        is_active=False,  # ← Неактивен
        is_blocked=True,
        must_change_password=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def blocked_user():
    """
    Создать заблокированного пользователя.

    Returns:
        User: Заблокированный пользователь (is_blocked=True)
    """
    return User(
        user_id="blocked_user_789",
        telegram_id=111222333,
        username="blocked_user",
        password_hash="$2b$12$dummy_hash",
        role="user",
        is_active=True,  # ← Активен, но заблокирован (is_blocked=True проверяется после is_active)
        is_blocked=True,  # ← Заблокирован
        must_change_password=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def active_session():
    """
    Создать активную сессию.

    Returns:
        Session: Активная сессия
    """
    return Session(
        session_id="session_123",
        user_id="active_user_123",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=24),
        last_activity=datetime.now(),
        is_active=True
    )


# ==================== ТЕСТЫ ====================

@pytest.mark.asyncio
async def test_callback_blocked_user_not_found():
    """
    Тест 1: Callback заблокирован для несуществующего пользователя.

    Проверяет, что пользователь, не найденный в БД, получает отказ.
    """
    from handlers import verify_callback_auth

    # Arrange: Несуществующий telegram_id
    telegram_id = 999999999
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = None

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(telegram_id, "menu_access")

    # Assert
    assert allowed is False
    assert user_id is None
    assert "❌" in error_msg
    assert "не найден" in error_msg.lower()


@pytest.mark.asyncio
async def test_callback_blocked_inactive_user(inactive_user):
    """
    Тест 2: Callback заблокирован для неактивного пользователя.
    """
    from handlers import verify_callback_auth

    # Arrange
    telegram_id = inactive_user.telegram_id
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = inactive_user

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(telegram_id)

    # Assert
    assert allowed is False
    assert user_id == inactive_user.user_id
    assert "❌" in error_msg
    assert "деактивирован" in error_msg.lower()


@pytest.mark.asyncio
async def test_callback_blocked_blocked_user(blocked_user):
    """
    Тест 3: Callback заблокирован для заблокированного пользователя.
    """
    from handlers import verify_callback_auth

    # Arrange
    telegram_id = blocked_user.telegram_id
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = blocked_user

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(telegram_id)

    # Assert
    assert allowed is False
    assert user_id == blocked_user.user_id
    assert "🚫" in error_msg
    assert "заблокирован" in error_msg.lower()


@pytest.mark.asyncio
async def test_callback_blocked_no_session(active_user):
    """
    Тест 4: Callback заблокирован для пользователя без активной сессии.
    """
    from handlers import verify_callback_auth

    # Arrange
    telegram_id = active_user.telegram_id
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = active_user
    mock_auth.storage.get_active_session_by_telegram_id.return_value = None  # ← Нет сессии

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(telegram_id)

    # Assert
    assert allowed is False
    assert user_id == active_user.user_id
    assert "❌" in error_msg
    assert "сессия" in error_msg.lower()
    assert "/login" in error_msg.lower()


@pytest.mark.asyncio
async def test_callback_allowed_authorized_user(active_user, active_session):
    """
    Тест 5: Callback разрешен для авторизованного пользователя.
    """
    from handlers import verify_callback_auth

    # Arrange
    telegram_id = active_user.telegram_id
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = active_user
    mock_auth.storage.get_active_session_by_telegram_id.return_value = active_session

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(telegram_id, "menu_access")

    # Assert
    assert allowed is True
    assert error_msg == ""
    assert user_id == active_user.user_id


# ==================== ПАРАМЕТРИЗОВАННЫЙ ТЕСТ ====================

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,expected_error_substring", [
    ("user_not_found", "не найден"),
    ("inactive_user", "деактивирован"),
    ("blocked_user", "заблокирован"),
    ("no_session", "сессия"),
])
async def test_callback_auth_all_rejection_scenarios(
    scenario, expected_error_substring,
    active_user, inactive_user, blocked_user, active_session
):
    """
    Параметризованный тест для всех сценариев отказа.
    """
    from handlers import verify_callback_auth

    # Arrange
    if scenario == "user_not_found":
        telegram_id = 999999999
        user_to_return = None
        session_to_return = None
    elif scenario == "inactive_user":
        telegram_id = inactive_user.telegram_id
        user_to_return = inactive_user
        session_to_return = active_session
    elif scenario == "blocked_user":
        telegram_id = blocked_user.telegram_id
        user_to_return = blocked_user
        session_to_return = active_session
    else:  # no_session
        telegram_id = active_user.telegram_id
        user_to_return = active_user
        session_to_return = None

    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = user_to_return
    mock_auth.storage.get_active_session_by_telegram_id.return_value = session_to_return

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(telegram_id)

    # Assert
    assert allowed is False
    assert expected_error_substring.lower() in error_msg.lower()


# ==================== ТЕСТ ЛОГИРОВАНИЯ ====================

@pytest.mark.asyncio
async def test_callback_auth_logging(inactive_user):
    """
    Тест 6: Проверка логирования блокировок callback.
    """
    from handlers import verify_callback_auth

    # Arrange
    telegram_id = inactive_user.telegram_id
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = inactive_user

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        with patch("handlers.logger") as mock_logger:
            # Act
            await verify_callback_auth(telegram_id)

    # Assert: Проверить логирование
    mock_logger.warning.assert_called_once()
    log_message = mock_logger.warning.call_args[0][0]
    assert "Callback blocked" in log_message
    assert "user inactive" in log_message.lower()
    assert str(inactive_user.telegram_id) in log_message
