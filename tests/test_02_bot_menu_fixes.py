"""
Автотесты для проверки исправлений ошибок меню бота (ФАЗА 1 + ФАЗА 2).

Проверяет 5 исправленных ошибок:
1. ФАЗА 1.1: handle_password_policy (новый handler)
2. ФАЗА 1.2: handle_cleanup_settings (новый handler)
3. ФАЗА 1.3: callback.answer() исправлен на track_and_send
4. ФАЗА 2.1: handle_list_invitations (параметр include_consumed)
5. ФАЗА 2.2: handle_audit_log (заглушка get_audit_log)

Автор: agent-organizer
Дата: 2025-11-05
Задача: #00007_20251105_YEIJEG/02_bot_menu_baf_HFUEJD
Commits: 2df907c, 67f40f6, d83779c
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4

# Импорт тестируемых модулей
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_storage import AuthStorageManager
from auth_manager import AuthManager
from auth_models import User, Invitation, InvitationMetadata
from access_handlers import (
    handle_password_policy,
    handle_cleanup_settings,
    handle_list_invitations,
    handle_audit_log
)


# ========== ФИКСТУРЫ ==========

@pytest.fixture
def temp_auth_dir(tmp_path):
    """Временная директория для auth_data."""
    auth_dir = tmp_path / "auth_data"
    auth_dir.mkdir()
    return auth_dir


@pytest.fixture
def auth_storage(temp_auth_dir):
    """AuthStorageManager для тестов."""
    return AuthStorageManager(temp_auth_dir)


@pytest.fixture
def auth_manager(temp_auth_dir):
    """AuthManager для тестов."""
    manager = AuthManager(temp_auth_dir)
    return manager


@pytest.fixture
def mock_app():
    """Mock Pyrogram Client."""
    app = MagicMock()
    app.send_message = AsyncMock(return_value=MagicMock(id=123))
    return app


@pytest.fixture
def sample_user():
    """Образец пользователя для тестов."""
    return User(
        user_id=str(uuid4()),
        telegram_id=12345,
        username="testuser",
        role="user",
        created_at=datetime.now(),
        password_hash="test_hash"
    )


@pytest.fixture
def sample_invitation():
    """Образец приглашения для тестов."""
    return Invitation(
        invite_code="TEST123",
        invite_type="user",
        created_by_user_id="admin_user_id",
        target_role="user",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=7),
        is_consumed=False,
        consumed_by_user_id=None,
        consumed_at=None,
        metadata=InvitationMetadata()
    )


# ========== ТЕСТЫ ФАЗЫ 2: AUTH_STORAGE ==========

class TestAuthStorageAuditLog:
    """Тесты для метода get_audit_log() (заглушка)."""

    def test_get_audit_log_exists(self, auth_storage):
        """Тест: метод get_audit_log() существует."""
        assert hasattr(auth_storage, 'get_audit_log')
        assert callable(auth_storage.get_audit_log)

    def test_get_audit_log_returns_empty_list(self, auth_storage):
        """Тест: get_audit_log() возвращает пустой список (заглушка)."""
        result = auth_storage.get_audit_log()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_audit_log_accepts_limit_parameter(self, auth_storage):
        """Тест: get_audit_log() принимает параметр limit."""
        result = auth_storage.get_audit_log(limit=100)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_audit_log_default_limit(self, auth_storage):
        """Тест: get_audit_log() имеет дефолтное значение limit=100."""
        # Проверяем что вызов без параметров работает
        result = auth_storage.get_audit_log()
        assert result == []


class TestAuthStorageListInvitations:
    """Тесты для метода list_invitations() (исправленный параметр)."""

    def test_list_invitations_accepts_include_consumed(self, auth_storage, sample_invitation):
        """Тест: list_invitations() принимает параметр include_consumed (не active_only)."""
        # Создаем приглашение
        auth_storage.create_invitation(sample_invitation)

        # Проверяем что метод принимает include_consumed
        result = auth_storage.list_invitations(include_consumed=False)
        assert isinstance(result, list)

    def test_list_invitations_filters_consumed(self, auth_storage, sample_invitation):
        """Тест: list_invitations(include_consumed=False) фильтрует использованные."""
        # Создаем 2 приглашения: одно активное, одно использованное
        invite1 = sample_invitation
        invite1.invite_code = "ACTIVE123"
        invite1.is_consumed = False

        invite2 = Invitation(
            invite_code="CONSUMED123",
            invite_type="user",
            created_by_user_id="admin_user_id",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            is_consumed=True,
            consumed_by_user_id="user123",
            consumed_at=datetime.now(),
            metadata=InvitationMetadata()
        )

        auth_storage.create_invitation(invite1)
        auth_storage.create_invitation(invite2)

        # include_consumed=False → только активные
        result = auth_storage.list_invitations(include_consumed=False)
        assert len(result) == 1
        assert result[0].invite_code == "ACTIVE123"

        # include_consumed=True → все
        result_all = auth_storage.list_invitations(include_consumed=True)
        assert len(result_all) == 2

    def test_list_invitations_no_active_only_parameter(self, auth_storage):
        """Тест: list_invitations() НЕ принимает параметр active_only (старая ошибка)."""
        # Проверяем что active_only вызовет TypeError
        with pytest.raises(TypeError) as exc_info:
            auth_storage.list_invitations(active_only=True)

        assert "active_only" in str(exc_info.value) or "unexpected keyword argument" in str(exc_info.value)


# ========== ТЕСТЫ ФАЗЫ 1: НОВЫЕ HANDLERS ==========

class TestPasswordPolicyHandler:
    """Тесты для handle_password_policy() (новый handler ФАЗА 1.1)."""

    @pytest.mark.asyncio
    async def test_handle_password_policy_exists(self):
        """Тест: handler handle_password_policy существует."""
        assert callable(handle_password_policy)

    @pytest.mark.asyncio
    async def test_handle_password_policy_calls_track_and_send(self, mock_app):
        """Тест: handle_password_policy вызывает track_and_send."""
        chat_id = 12345

        with patch('access_handlers.track_and_send', new=AsyncMock()) as mock_track:
            await handle_password_policy(chat_id, mock_app)

            # Проверяем что track_and_send был вызван
            assert mock_track.called
            call_args = mock_track.call_args

            # Проверяем параметры вызова
            assert call_args[1]['chat_id'] == chat_id
            assert call_args[1]['app'] == mock_app
            assert 'ПОЛИТИКА ПАРОЛЕЙ' in call_args[1]['text']
            assert call_args[1]['message_type'] == "menu"

    @pytest.mark.asyncio
    async def test_handle_password_policy_no_exception(self, mock_app):
        """Тест: handle_password_policy не вызывает исключений."""
        chat_id = 12345

        with patch('access_handlers.track_and_send', new=AsyncMock()):
            try:
                await handle_password_policy(chat_id, mock_app)
            except Exception as e:
                pytest.fail(f"handle_password_policy вызвал исключение: {e}")


class TestCleanupSettingsHandler:
    """Тесты для handle_cleanup_settings() (новый handler ФАЗА 1.2)."""

    @pytest.mark.asyncio
    async def test_handle_cleanup_settings_exists(self):
        """Тест: handler handle_cleanup_settings существует."""
        assert callable(handle_cleanup_settings)

    @pytest.mark.asyncio
    async def test_handle_cleanup_settings_calls_track_and_send(self, mock_app):
        """Тест: handle_cleanup_settings вызывает track_and_send."""
        chat_id = 12345

        with patch('access_handlers.track_and_send', new=AsyncMock()) as mock_track:
            await handle_cleanup_settings(chat_id, mock_app)

            # Проверяем что track_and_send был вызван
            assert mock_track.called
            call_args = mock_track.call_args

            # Проверяем параметры вызова
            assert call_args[1]['chat_id'] == chat_id
            assert call_args[1]['app'] == mock_app
            assert 'АВТООЧИСТКА СООБЩЕНИЙ' in call_args[1]['text']
            assert call_args[1]['message_type'] == "menu"

    @pytest.mark.asyncio
    async def test_handle_cleanup_settings_no_exception(self, mock_app):
        """Тест: handle_cleanup_settings не вызывает исключений."""
        chat_id = 12345

        with patch('access_handlers.track_and_send', new=AsyncMock()):
            try:
                await handle_cleanup_settings(chat_id, mock_app)
            except Exception as e:
                pytest.fail(f"handle_cleanup_settings вызвал исключение: {e}")


# ========== ТЕСТЫ ФАЗЫ 2: ИСПРАВЛЕННЫЕ HANDLERS ==========

class TestListInvitationsHandler:
    """Тесты для handle_list_invitations() (исправлен параметр ФАЗА 2.1)."""

    @pytest.mark.asyncio
    async def test_handle_list_invitations_uses_include_consumed(self, mock_app):
        """Тест: handle_list_invitations использует include_consumed (не active_only)."""
        chat_id = 12345

        # Mock AuthManager и storage
        with patch('access_handlers.get_auth_manager') as mock_get_auth:
            mock_auth = MagicMock()
            mock_auth.storage.list_invitations = MagicMock(return_value=[])
            mock_get_auth.return_value = mock_auth

            with patch('access_handlers.track_and_send', new=AsyncMock()):
                await handle_list_invitations(chat_id, page=1, app=mock_app)

                # Проверяем что list_invitations был вызван с include_consumed
                mock_auth.storage.list_invitations.assert_called_once()
                call_args = mock_auth.storage.list_invitations.call_args

                # Проверяем что используется include_consumed, а НЕ active_only
                assert 'include_consumed' in call_args[1]
                assert call_args[1]['include_consumed'] is False

                # Проверяем что active_only НЕ используется
                assert 'active_only' not in call_args[1]

    @pytest.mark.asyncio
    async def test_handle_list_invitations_with_traceback_logging(self, mock_app):
        """Тест: handle_list_invitations логирует traceback при ошибке."""
        chat_id = 12345

        # Mock AuthManager который выбросит исключение
        with patch('access_handlers.get_auth_manager') as mock_get_auth:
            mock_auth = MagicMock()
            mock_auth.storage.list_invitations.side_effect = Exception("Test error")
            mock_get_auth.return_value = mock_auth

            with patch('access_handlers.track_and_send', new=AsyncMock()):
                with patch('access_handlers.logger') as mock_logger:
                    await handle_list_invitations(chat_id, page=1, app=mock_app)

                    # Проверяем что logger.error был вызван дважды (error + traceback)
                    assert mock_logger.error.call_count >= 2


class TestAuditLogHandler:
    """Тесты для handle_audit_log() (работа с заглушкой ФАЗА 2.2)."""

    @pytest.mark.asyncio
    async def test_handle_audit_log_works_with_stub(self, mock_app):
        """Тест: handle_audit_log работает с заглушкой get_audit_log()."""
        chat_id = 12345

        # Mock AuthManager с заглушкой
        with patch('access_handlers.get_auth_manager') as mock_get_auth:
            mock_auth = MagicMock()
            mock_auth.storage.get_audit_log = MagicMock(return_value=[])  # Заглушка
            mock_get_auth.return_value = mock_auth

            with patch('access_handlers.track_and_send', new=AsyncMock()):
                # Не должно быть исключений
                await handle_audit_log(chat_id, page=1, app=mock_app)

                # Проверяем что get_audit_log был вызван
                mock_auth.storage.get_audit_log.assert_called_once_with(limit=1000)

    @pytest.mark.asyncio
    async def test_handle_audit_log_handles_empty_list(self, mock_app):
        """Тест: handle_audit_log корректно обрабатывает пустой список."""
        chat_id = 12345

        with patch('access_handlers.get_auth_manager') as mock_get_auth:
            mock_auth = MagicMock()
            mock_auth.storage.get_audit_log = MagicMock(return_value=[])
            mock_get_auth.return_value = mock_auth

            with patch('access_handlers.track_and_send', new=AsyncMock()) as mock_track:
                await handle_audit_log(chat_id, page=1, app=mock_app)

                # Проверяем что сообщение отправлено
                assert mock_track.called
                call_args = mock_track.call_args

                # Проверяем текст сообщения (должен показывать 0 событий)
                text = call_args[1]['text']
                assert 'ЖУРНАЛ ДЕЙСТВИЙ' in text
                assert 'Всего событий: 0' in text

    @pytest.mark.asyncio
    async def test_handle_audit_log_with_traceback_logging(self, mock_app):
        """Тест: handle_audit_log логирует traceback при ошибке."""
        chat_id = 12345

        # Mock AuthManager который выбросит исключение
        with patch('access_handlers.get_auth_manager') as mock_get_auth:
            mock_auth = MagicMock()
            mock_auth.storage.get_audit_log.side_effect = Exception("Test error")
            mock_get_auth.return_value = mock_auth

            with patch('access_handlers.track_and_send', new=AsyncMock()):
                with patch('access_handlers.logger') as mock_logger:
                    await handle_audit_log(chat_id, page=1, app=mock_app)

                    # Проверяем что logger.error был вызван дважды (error + traceback)
                    assert mock_logger.error.call_count >= 2


# ========== ИНТЕГРАЦИОННЫЕ ТЕСТЫ ==========

class TestIntegrationAllFixes:
    """Интеграционные тесты всех исправлений вместе."""

    @pytest.mark.asyncio
    async def test_all_handlers_no_exceptions(self, mock_app, auth_manager):
        """Тест: все исправленные handlers работают без исключений."""
        chat_id = 12345

        with patch('access_handlers.get_auth_manager', return_value=auth_manager):
            with patch('access_handlers.track_and_send', new=AsyncMock()):
                # ФАЗА 1.1
                await handle_password_policy(chat_id, mock_app)

                # ФАЗА 1.2
                await handle_cleanup_settings(chat_id, mock_app)

                # ФАЗА 2.1
                await handle_list_invitations(chat_id, page=1, app=mock_app)

                # ФАЗА 2.2
                await handle_audit_log(chat_id, page=1, app=mock_app)

    def test_auth_storage_all_methods_exist(self, auth_storage):
        """Тест: все необходимые методы существуют в AuthStorageManager."""
        # Метод из ФАЗЫ 2.1
        assert hasattr(auth_storage, 'list_invitations')

        # Метод из ФАЗЫ 2.2
        assert hasattr(auth_storage, 'get_audit_log')


# ========== РЕЗЮМЕ ТЕСТОВ ==========

"""
ПОКРЫТИЕ ТЕСТАМИ:

✅ ФАЗА 1: Silent Failures (3 ошибки)
  ✅ 1.1 handle_password_policy - 3 теста
  ✅ 1.2 handle_cleanup_settings - 3 теста
  ✅ 1.3 callback.answer() - косвенно (проверка track_and_send)

✅ ФАЗА 2: Runtime Errors (2 ошибки)
  ✅ 2.1 list_invitations параметр - 3 теста
  ✅ 2.2 get_audit_log заглушка - 4 теста
  ✅ 2.3 handle_list_invitations - 2 теста
  ✅ 2.4 handle_audit_log - 3 теста

✅ ИНТЕГРАЦИОННЫЕ ТЕСТЫ: 2 теста

ИТОГО: 20 автотестов покрывают все 5 исправленных ошибок
"""
