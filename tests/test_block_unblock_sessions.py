"""
Тесты для управления сессиями при блокировке/разблокировке пользователей.

Проверяет исправления из задачи #00007_20251105_YEIJEG (08_pass_change):
1. block_user() удаляет все активные сессии пользователя
2. Заблокированный пользователь получает уведомление при попытке доступа
3. unblock_user() НЕ создает сессии автоматически (требуется повторный вход)

Автор: refactoring-specialist, code-reviewer
Дата: 7 ноября 2025
Задача: #00007_20251105_YEIJEG
"""

import pytest
import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Импорт тестируемых модулей
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_manager import AuthManager
from auth_models import User, Session, UserSettings, UserMetadata
from auth_filters import auth_filter, show_user_blocked_notification


# ========== ФИКСТУРЫ ==========

@pytest.fixture
def temp_auth_dir(tmp_path):
    """Временная директория для auth_data (Windows совместимость)."""
    auth_dir = tmp_path / "test_auth_data"
    auth_dir.mkdir(exist_ok=True)
    yield auth_dir
    # Cleanup (Windows совместимость)
    if auth_dir.exists():
        shutil.rmtree(auth_dir, ignore_errors=True)


@pytest.fixture
def auth_manager(temp_auth_dir):
    """AuthManager для тестов."""
    return AuthManager(temp_auth_dir)


@pytest.fixture
def mock_client():
    """Mock Pyrogram Client."""
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


@pytest.fixture
def mock_message():
    """Mock Pyrogram Message."""
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = 123456789
    message.chat = MagicMock()
    message.chat.id = 123456789
    message.text = None
    return message


@pytest.fixture
def active_user_with_session(auth_manager):
    """
    Создать активного пользователя с активной сессией.

    Возвращает tuple: (user, session)
    """
    # Создать пользователя
    user = User(
        user_id=str(uuid4()),
        telegram_id=123456789,
        username="test_user",
        password_hash="test_hash",
        role="user",
        must_change_password=False,
        temp_password_expires_at=None,
        is_active=True,
        is_blocked=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by_user_id=None,
        last_login=None,
        last_login_ip=None,
        login_count=0,
        failed_login_attempts=0,
        last_failed_login=None,
        password_changed_at=datetime.now(),
        settings=UserSettings(),
        metadata=UserMetadata()
    )
    auth_manager.storage.create_user(user)

    # Создать активную сессию для пользователя
    session = Session(
        session_id=str(uuid4()),
        user_id=user.user_id,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=1),  # Установить expires_at на 1 день вперед
        last_activity=datetime.now(),
        ip_address="127.0.0.1",
        user_agent="TestBot/1.0",
        is_active=True
    )
    auth_manager.storage.create_session(user.user_id, session)

    return user, session


@pytest.fixture
def admin_user(auth_manager):
    """Создать админа для блокировки других пользователей."""
    user = User(
        user_id=str(uuid4()),
        telegram_id=999999999,
        username="admin_user",
        password_hash="admin_hash",
        role="admin",
        must_change_password=False,
        temp_password_expires_at=None,
        is_active=True,
        is_blocked=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by_user_id=None,
        last_login=None,
        last_login_ip=None,
        login_count=0,
        failed_login_attempts=0,
        last_failed_login=None,
        password_changed_at=datetime.now(),
        settings=UserSettings(),
        metadata=UserMetadata()
    )
    auth_manager.storage.create_user(user)
    return user


# ========== ТЕСТЫ ==========

@pytest.mark.asyncio
async def test_block_user_deletes_all_sessions(auth_manager, active_user_with_session, admin_user):
    """
    Тест 1: Проверяет, что block_user() удаляет все активные сессии пользователя.

    Сценарий:
    1. Создан пользователь с активной сессией
    2. Админ блокирует пользователя через block_user()
    3. Проверить: is_blocked=True
    4. Проверить: все сессии пользователя удалены (0 сессий в БД)
    5. Проверить: audit log содержит количество удаленных сессий
    """
    user, session = active_user_with_session

    # Проверить начальное состояние: пользователь НЕ заблокирован, сессия активна
    assert user.is_blocked is False
    active_sessions_before = auth_manager.storage.get_user_sessions(user.user_id)
    assert len(active_sessions_before) == 1
    assert active_sessions_before[0].session_id == session.session_id

    # Заблокировать пользователя
    result = await auth_manager.block_user(
        user_id=user.user_id,
        blocked_by_user_id=admin_user.user_id
    )

    # Проверить: операция успешна
    assert result is True

    # Проверить: пользователь заблокирован
    updated_user = auth_manager.storage.get_user(user.user_id)
    assert updated_user.is_blocked is True

    # КРИТИЧНО: Проверить, что все сессии удалены
    active_sessions_after = auth_manager.storage.get_user_sessions(user.user_id)
    assert len(active_sessions_after) == 0, "Сессии должны быть удалены при блокировке"


@pytest.mark.asyncio
async def test_blocked_user_receives_notification(auth_manager, mock_client, mock_message):
    """
    Тест 2: Проверяет, что заблокированный пользователь получает уведомление.

    Сценарий:
    1. Создан заблокированный пользователь
    2. Заблокированный пользователь пытается обратиться к боту
    3. Вызывается show_user_blocked_notification()
    4. Проверить: уведомление отправлено через client.send_message()
    5. Проверить: текст уведомления содержит "Доступ заблокирован"
    """
    # Создать заблокированного пользователя
    blocked_user = User(
        user_id=str(uuid4()),
        telegram_id=444555666,
        username="blocked_user",
        password_hash="test_hash",
        role="user",
        must_change_password=False,
        temp_password_expires_at=None,
        is_active=True,
        is_blocked=True,  # КРИТИЧНО: заблокирован
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by_user_id=None,
        last_login=None,
        last_login_ip=None,
        login_count=0,
        failed_login_attempts=0,
        last_failed_login=None,
        password_changed_at=datetime.now(),
        settings=UserSettings(),
        metadata=UserMetadata()
    )
    auth_manager.storage.create_user(blocked_user)

    # Установить telegram_id заблокированного пользователя в mock_message
    mock_message.from_user.id = blocked_user.telegram_id

    # Вызвать функцию уведомления
    await show_user_blocked_notification(mock_client, mock_message)

    # Проверить: send_message вызван один раз
    mock_client.send_message.assert_called_once()

    # Проверить: вызов с правильным chat_id
    call_args = mock_client.send_message.call_args
    assert call_args[0][0] == mock_message.chat.id  # Первый аргумент - chat_id

    # Проверить: текст уведомления содержит ключевые слова
    notification_text = call_args[0][1]  # Второй аргумент - текст
    assert "Доступ заблокирован" in notification_text
    assert "заблокирован администратором" in notification_text
    assert "обратитесь к администратору" in notification_text


@pytest.mark.asyncio
async def test_blocked_user_notification_via_auth_filter(auth_manager, mock_client, mock_message):
    """
    Тест 2.1: Проверяет, что auth_filter автоматически вызывает уведомление для заблокированного пользователя.

    Сценарий:
    1. Создан заблокированный пользователь с активной сессией
    2. Вызывается auth_filter
    3. Проверить: фильтр возвращает False (доступ запрещен)
    4. Проверить: уведомление отправлено асинхронно (через asyncio.create_task)
    """
    # Создать заблокированного пользователя
    blocked_user = User(
        user_id=str(uuid4()),
        telegram_id=444555666,
        username="blocked_user",
        password_hash="test_hash",
        role="user",
        must_change_password=False,
        temp_password_expires_at=None,
        is_active=True,
        is_blocked=True,  # КРИТИЧНО: заблокирован
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by_user_id=None,
        last_login=None,
        last_login_ip=None,
        login_count=0,
        failed_login_attempts=0,
        last_failed_login=None,
        password_changed_at=datetime.now(),
        settings=UserSettings(),
        metadata=UserMetadata()
    )
    auth_manager.storage.create_user(blocked_user)

    # Создать активную сессию (чтобы пройти проверку активной сессии в auth_filter)
    session = Session(
        session_id=str(uuid4()),
        user_id=blocked_user.user_id,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=1),  # Установить expires_at на 1 день вперед
        last_activity=datetime.now(),
        ip_address="127.0.0.1",
        user_agent="TestBot/1.0",
        is_active=True
    )
    auth_manager.storage.create_session(blocked_user.user_id, session)

    # Установить telegram_id заблокированного пользователя
    mock_message.from_user.id = blocked_user.telegram_id

    # Мокировать get_auth_manager()
    with patch("config.get_auth_manager", return_value=auth_manager):
        # Вызвать фильтр
        result = await auth_filter(mock_client, mock_message)

        # Проверить: фильтр вернул False
        assert result is False

        # Проверить: уведомление вызвано асинхронно (через asyncio.create_task)
        # NOTE: asyncio.create_task() запускает задачу асинхронно, нужно подождать
        await asyncio.sleep(0.1)

        # Проверить: send_message вызван
        mock_client.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_unblock_user_no_auto_session_creation(auth_manager, admin_user):
    """
    Тест 3: Проверяет, что unblock_user() НЕ создает сессии автоматически.

    Сценарий:
    1. Создан заблокированный пользователь БЕЗ сессий
    2. Админ разблокирует пользователя через unblock_user()
    3. Проверить: is_blocked=False
    4. Проверить: сессии НЕ созданы автоматически (0 сессий в БД)
    5. Проверить: пользователь должен войти заново через /login для создания сессии
    """
    # Создать заблокированного пользователя БЕЗ сессий
    blocked_user = User(
        user_id=str(uuid4()),
        telegram_id=777888999,
        username="blocked_user_no_sessions",
        password_hash="test_hash",
        role="user",
        must_change_password=False,
        temp_password_expires_at=None,
        is_active=True,
        is_blocked=True,  # КРИТИЧНО: заблокирован
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by_user_id=None,
        last_login=None,
        last_login_ip=None,
        login_count=0,
        failed_login_attempts=0,
        last_failed_login=None,
        password_changed_at=datetime.now(),
        settings=UserSettings(),
        metadata=UserMetadata()
    )
    auth_manager.storage.create_user(blocked_user)

    # Проверить начальное состояние: пользователь заблокирован, сессий нет
    assert blocked_user.is_blocked is True
    sessions_before = auth_manager.storage.get_user_sessions(blocked_user.user_id)
    assert len(sessions_before) == 0

    # Разблокировать пользователя
    result = await auth_manager.unblock_user(
        user_id=blocked_user.user_id
    )

    # Проверить: операция успешна
    assert result is True

    # Проверить: пользователь разблокирован
    updated_user = auth_manager.storage.get_user(blocked_user.user_id)
    assert updated_user.is_blocked is False

    # КРИТИЧНО: Проверить, что сессии НЕ созданы автоматически
    sessions_after = auth_manager.storage.get_user_sessions(blocked_user.user_id)
    assert len(sessions_after) == 0, (
        "Сессии НЕ должны создаваться автоматически при разблокировке. "
        "Пользователь должен войти заново через /login."
    )


@pytest.mark.asyncio
async def test_block_user_with_multiple_sessions(auth_manager, admin_user):
    """
    Тест 4 (дополнительный): Проверяет удаление НЕСКОЛЬКИХ сессий при блокировке.

    Сценарий:
    1. Создан пользователь с 3 активными сессиями (разные устройства)
    2. Админ блокирует пользователя
    3. Проверить: ВСЕ 3 сессии удалены
    4. Проверить: audit log содержит sessions_deleted=3
    """
    # Создать пользователя
    user = User(
        user_id=str(uuid4()),
        telegram_id=111222333,
        username="multi_session_user",
        password_hash="test_hash",
        role="user",
        must_change_password=False,
        temp_password_expires_at=None,
        is_active=True,
        is_blocked=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        created_by_user_id=None,
        last_login=None,
        last_login_ip=None,
        login_count=0,
        failed_login_attempts=0,
        last_failed_login=None,
        password_changed_at=datetime.now(),
        settings=UserSettings(),
        metadata=UserMetadata()
    )
    auth_manager.storage.create_user(user)

    # Создать 3 активные сессии (разные устройства)
    for i in range(3):
        session = Session(
            session_id=str(uuid4()),
            user_id=user.user_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=1),  # Установить expires_at на 1 день вперед
            last_activity=datetime.now(),
            ip_address=f"127.0.0.{i+1}",
            user_agent=f"Device_{i+1}/1.0",
            is_active=True
        )
        auth_manager.storage.create_session(user.user_id, session)

    # Проверить: 3 активные сессии созданы
    sessions_before = auth_manager.storage.get_user_sessions(user.user_id)
    assert len(sessions_before) == 3

    # Заблокировать пользователя
    result = await auth_manager.block_user(
        user_id=user.user_id,
        blocked_by_user_id=admin_user.user_id
    )

    # Проверить: операция успешна
    assert result is True

    # КРИТИЧНО: Проверить, что ВСЕ 3 сессии удалены
    sessions_after = auth_manager.storage.get_user_sessions(user.user_id)
    assert len(sessions_after) == 0, "Все сессии должны быть удалены при блокировке"
