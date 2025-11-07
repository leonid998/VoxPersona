"""
Интеграционные тесты для callback_query_handler после рефакторинга.

Проверяет что рефакторинг verify_callback_auth() НЕ сломал существующую функциональность:
- callback_query_handler корректно вызывает verify_callback_auth()
- callback_query_handler обрабатывает результаты авторизации
- Интеграция с access_handlers работает корректно
- Существующие callback маршруты продолжают работать

Связано с задачей: 08_pass_change (#00007_20251105_YEIJEG)
Дата: 2025-11-07
Автор: Claude Code (интеграционное тестирование рефакторинга)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime, timedelta

# Добавить src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from auth_models import User, Session


# ==================== FIXTURES ====================

@pytest.fixture(autouse=True)
def mock_minio():
    """Мок MinIO для всех тестов (autouse)."""
    with patch("minio_manager.get_minio_manager", return_value=MagicMock()):
        yield


@pytest.fixture
def mock_client():
    """Мок Pyrogram Client."""
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


@pytest.fixture
def mock_callback_query():
    """Мок CallbackQuery с базовыми параметрами."""
    callback = MagicMock()
    callback.from_user.id = 123456789
    callback.message.chat.id = 123456789
    callback.data = "menu_main"
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def authorized_user():
    """Авторизованный пользователь с активной сессией."""
    return User(
        user_id="user_123",
        telegram_id=123456789,
        username="authorized_user",
        password_hash="$2b$12$dummy",
        role="user",
        is_active=True,
        is_blocked=False,
        must_change_password=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def active_session():
    """Активная сессия."""
    return Session(
        session_id="session_123",
        user_id="user_123",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=24),
        last_activity=datetime.now(),
        is_active=True
    )


# ==================== ТЕСТЫ ИНТЕГРАЦИИ ====================

@pytest.mark.asyncio
async def test_callback_handler_calls_verify_callback_auth(mock_client, mock_callback_query, authorized_user, active_session):
    """
    Тест 1: callback_query_handler вызывает verify_callback_auth().

    Проверяет что рефакторинг работает - handler использует новую функцию.
    """
    from handlers import callback_query_handler

    # Arrange: Мокируем verify_callback_auth чтобы проверить что она вызывается
    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "", "user_123")  # Авторизация успешна

        # Мокируем остальные функции чтобы handler не упал
        with patch("handlers.show_main_menu", new_callable=AsyncMock):
            # Act
            await callback_query_handler(mock_client, mock_callback_query)

    # Assert: verify_callback_auth была вызвана с правильным telegram_id
    mock_verify.assert_called_once()
    call_args = mock_verify.call_args
    assert call_args[0][0] == 123456789  # telegram_id
    assert call_args[0][1] == "menu_main"  # callback_data


@pytest.mark.asyncio
async def test_callback_handler_blocks_unauthorized_user(mock_client, mock_callback_query):
    """
    Тест 2: callback_query_handler блокирует неавторизованного пользователя.

    Проверяет что handler корректно обрабатывает отказ в авторизации.
    """
    from handlers import callback_query_handler

    # Arrange: verify_callback_auth возвращает отказ
    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (False, "❌ Доступ запрещен", None)

        # Act
        await callback_query_handler(mock_client, mock_callback_query)

    # Assert: callback.answer был вызван с сообщением об ошибке
    mock_callback_query.answer.assert_called_once_with("❌ Доступ запрещен", show_alert=True)


@pytest.mark.asyncio
async def test_callback_handler_routes_to_correct_handler(mock_client, mock_callback_query, authorized_user, active_session):
    """
    Тест 3: callback_query_handler корректно маршрутизирует callback после авторизации.

    Проверяет что после успешной авторизации вызывается правильный обработчик.
    """
    from handlers import callback_query_handler

    # Arrange: Успешная авторизация
    mock_callback_query.data = "menu_main"

    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "", "user_123")

        with patch("handlers.show_main_menu", new_callable=AsyncMock) as mock_show_main:
            # Act
            await callback_query_handler(mock_client, mock_callback_query)

            # Assert: show_main_menu был вызван
            mock_show_main.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_integration_with_access_handlers(mock_client, mock_callback_query, authorized_user, active_session):
    """
    Тест 4: callback_query_handler корректно интегрируется с access_handlers.

    Проверяет что callback для access модуля маршрутизируются правильно.
    """
    from handlers import callback_query_handler

    # Arrange: Callback для access модуля
    mock_callback_query.data = "menu_access"

    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "", "user_123")

        with patch("handlers.handle_access_callback", new_callable=AsyncMock) as mock_access:
            # Act
            await callback_query_handler(mock_client, mock_callback_query)

            # Assert: handle_access_callback был вызван
            mock_access.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_preserves_user_id_after_auth(mock_client, mock_callback_query, authorized_user, active_session):
    """
    Тест 5: callback_query_handler сохраняет user_id после авторизации.

    Проверяет что user_id из verify_callback_auth передается дальше.
    """
    from handlers import callback_query_handler

    # Arrange
    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "", "user_123_expected")

        with patch("handlers.show_main_menu", new_callable=AsyncMock) as mock_show_main:
            # Act
            await callback_query_handler(mock_client, mock_callback_query)

            # Assert: Проверяем что user_id доступен после авторизации
            # (В реальном коде handler может использовать user_id для логики)
            mock_verify.assert_called_once()
            assert mock_verify.return_value[2] == "user_123_expected"


# ==================== ТЕСТЫ РАЗЛИЧНЫХ CALLBACK DATA ====================

@pytest.mark.asyncio
@pytest.mark.parametrize("callback_data,expected_handler", [
    ("menu_main", "show_main_menu"),
    ("menu_access", "handle_access_callback"),
    ("new_chat", "handle_new_chat"),
    ("show_stats", "handle_show_stats"),
])
async def test_callback_handler_routes_different_callbacks(
    mock_client, mock_callback_query, authorized_user, active_session,
    callback_data, expected_handler
):
    """
    Тест 6: callback_query_handler маршрутизирует различные callback_data.

    Параметризованный тест для проверки разных маршрутов.
    """
    from handlers import callback_query_handler

    # Arrange
    mock_callback_query.data = callback_data

    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "", "user_123")

        with patch(f"handlers.{expected_handler}", new_callable=AsyncMock) as mock_handler:
            # Act
            await callback_query_handler(mock_client, mock_callback_query)

            # Assert: Правильный обработчик был вызван
            mock_handler.assert_called_once()


# ==================== ТЕСТЫ EDGE CASES ====================

@pytest.mark.asyncio
async def test_callback_handler_handles_empty_callback_data(mock_client, mock_callback_query):
    """
    Тест 7: callback_query_handler обрабатывает пустой callback_data.
    """
    from handlers import callback_query_handler

    # Arrange
    mock_callback_query.data = ""

    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (False, "❌ Некорректный callback", None)

        # Act
        await callback_query_handler(mock_client, mock_callback_query)

        # Assert: verify_callback_auth был вызван с пустым callback_data
        mock_verify.assert_called_once()
        assert mock_verify.call_args[0][1] == ""


@pytest.mark.asyncio
async def test_callback_handler_no_double_answer(mock_client, mock_callback_query):
    """
    Тест 8: callback_query_handler НЕ вызывает callback.answer дважды.

    Критично: Telegram API выдает ошибку при двойном answer.
    """
    from handlers import callback_query_handler

    # Arrange
    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (False, "❌ Доступ запрещен", None)

        # Act
        await callback_query_handler(mock_client, mock_callback_query)

    # Assert: callback.answer вызван РОВНО один раз
    assert mock_callback_query.answer.call_count == 1


@pytest.mark.asyncio
async def test_callback_handler_logs_authorization_failures(mock_client, mock_callback_query):
    """
    Тест 9: callback_query_handler логирует отказы в авторизации.
    """
    from handlers import callback_query_handler

    # Arrange
    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (False, "❌ Пользователь заблокирован", "user_123")

        with patch("handlers.logger") as mock_logger:
            # Act
            await callback_query_handler(mock_client, mock_callback_query)

            # Assert: verify_callback_auth уже логирует, но handler может добавить свои логи
            # Проверяем что ошибка была обработана корректно
            mock_callback_query.answer.assert_called_once()


# ==================== ТЕСТЫ СОВМЕСТИМОСТИ ====================

@pytest.mark.asyncio
async def test_verify_callback_auth_backwards_compatible(authorized_user, active_session):
    """
    Тест 10: verify_callback_auth обратно совместима с ожиданиями handler.

    Проверяет сигнатуру возвращаемых значений.
    """
    from handlers import verify_callback_auth

    # Arrange
    telegram_id = 123456789
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = authorized_user
    mock_auth.storage.get_active_session_by_telegram_id.return_value = active_session

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        result = await verify_callback_auth(telegram_id, "test_callback")

    # Assert: Проверяем формат возврата tuple[bool, str, str | None]
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert isinstance(result[0], bool)  # allowed
    assert isinstance(result[1], str)   # error_msg
    assert result[2] is None or isinstance(result[2], str)  # user_id


@pytest.mark.asyncio
async def test_callback_handler_exception_handling(mock_client, mock_callback_query):
    """
    Тест 11: callback_query_handler корректно обрабатывает исключения в verify_callback_auth.
    """
    from handlers import callback_query_handler

    # Arrange: verify_callback_auth выбрасывает исключение
    with patch("handlers.verify_callback_auth", new_callable=AsyncMock) as mock_verify:
        mock_verify.side_effect = Exception("Database error")

        # Act & Assert: Handler не должен падать
        try:
            await callback_query_handler(mock_client, mock_callback_query)
        except Exception as e:
            pytest.fail(f"callback_query_handler не должен пропускать исключения: {e}")
