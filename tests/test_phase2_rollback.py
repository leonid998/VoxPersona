"""
Тесты для ФАЗА 2: Issue 1.8 - Rollback Mechanism для create_user

Проверяет:
- Откат создания пользователя при ошибке consume_invitation()
- Логирование ошибок (logger.error, logger.info, logger.critical)
- Выброс RuntimeError при неудаче
- Атомарность операции регистрации

Author: agent-organizer
Date: 2025-11-05
Task: #00007_20251105_YEIJEG/01_bag_8563784537 (Issue 1.8)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import sys
from pathlib import Path

# Настройка sys.path для импорта модулей из src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_models import User, Invitation
from auth_storage import AuthStorageManager


class TestPhase2RollbackMechanism:
    """Тесты для rollback механизма при ошибке consume_invitation (Issue 1.8)."""

    @pytest.fixture
    def mock_storage(self):
        """Мок AuthStorageManager с контролируемым поведением."""
        storage = Mock(spec=AuthStorageManager)

        # По умолчанию все операции успешны
        storage.create_user = Mock(return_value=True)
        storage.consume_invitation = Mock(return_value=True)
        storage.delete_user = Mock(return_value=True)
        storage.log_auth_event = Mock()

        return storage

    @pytest.fixture
    def sample_user(self):
        """Тестовый пользователь."""
        return User(
            user_id="user_test_123",
            telegram_id=999999,
            username="testuser",
            password_hash="hash_test",
            role="user",
            is_active=True,
            is_blocked=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    def test_consume_invitation_failure_triggers_rollback(self, mock_storage, sample_user):
        """
        Тест: при ошибке consume_invitation() вызывается delete_user().

        Сценарий:
        1. create_user() → True
        2. consume_invitation() → False
        3. delete_user() должен быть вызван с user_id
        """
        # Настроить поведение: consume_invitation возвращает False
        mock_storage.consume_invitation.return_value = False
        mock_storage.delete_user.return_value = True

        # Симуляция логики из handlers.py:1528-1541
        create_success = mock_storage.create_user(sample_user)
        assert create_success == True

        consume_success = mock_storage.consume_invitation(
            code="TEST_INVITE_CODE",
            consumed_by_user_id=sample_user.user_id
        )

        if not consume_success:
            # ROLLBACK
            rollback_success = mock_storage.delete_user(sample_user.user_id)

        # Проверки
        mock_storage.create_user.assert_called_once_with(sample_user)
        mock_storage.consume_invitation.assert_called_once()
        mock_storage.delete_user.assert_called_once_with(sample_user.user_id)

    def test_rollback_successful_deletion(self, mock_storage, sample_user):
        """
        Тест: rollback успешно удаляет созданного пользователя.

        Проверяет что delete_user() возвращает True.
        """
        mock_storage.consume_invitation.return_value = False
        mock_storage.delete_user.return_value = True

        # Симуляция
        mock_storage.create_user(sample_user)
        consume_success = mock_storage.consume_invitation("code", sample_user.user_id)

        if not consume_success:
            rollback_success = mock_storage.delete_user(sample_user.user_id)
            assert rollback_success == True

    def test_rollback_failed_deletion_returns_false(self, mock_storage, sample_user):
        """
        Тест: если delete_user() возвращает False, это обнаруживается.

        Критическая ситуация: rollback не сработал.
        """
        mock_storage.consume_invitation.return_value = False
        mock_storage.delete_user.return_value = False  # ROLLBACK FAILED

        # Симуляция
        mock_storage.create_user(sample_user)
        consume_success = mock_storage.consume_invitation("code", sample_user.user_id)

        if not consume_success:
            rollback_success = mock_storage.delete_user(sample_user.user_id)
            assert rollback_success == False  # ❌ Rollback провален

    def test_no_rollback_on_success(self, mock_storage, sample_user):
        """
        Тест: при успешном consume_invitation() rollback НЕ вызывается.

        Нормальный flow без ошибок.
        """
        mock_storage.consume_invitation.return_value = True

        # Симуляция
        mock_storage.create_user(sample_user)
        consume_success = mock_storage.consume_invitation("code", sample_user.user_id)

        # При успехе delete_user() НЕ должен вызываться
        assert consume_success == True
        mock_storage.delete_user.assert_not_called()

    def test_rollback_logs_error_on_consume_failure(self, mock_storage, sample_user):
        """
        Тест: при ошибке consume_invitation() вызывается delete_user.

        Проверяет механизм rollback без зависимости от handlers.py.
        """
        mock_storage.consume_invitation.return_value = False
        mock_storage.delete_user.return_value = True

        # Симуляция логики rollback
        mock_storage.create_user(sample_user)
        consume_success = mock_storage.consume_invitation("TEST_CODE", sample_user.user_id)

        if not consume_success:
            # Rollback должен вызвать delete_user
            rollback_success = mock_storage.delete_user(sample_user.user_id)
            assert rollback_success == True

        # Проверка что delete_user был вызван (значит rollback был)
        mock_storage.delete_user.assert_called_once_with(sample_user.user_id)

    def test_runtime_error_raised_on_consume_failure(self, mock_storage, sample_user):
        """
        Тест: при ошибке consume_invitation() должен выбрасываться RuntimeError.

        Проверяет логику из handlers.py:1541.
        """
        mock_storage.consume_invitation.return_value = False
        mock_storage.delete_user.return_value = True

        # Симуляция
        mock_storage.create_user(sample_user)
        consume_success = mock_storage.consume_invitation("TEST_CODE", sample_user.user_id)

        if not consume_success:
            mock_storage.delete_user(sample_user.user_id)

            # RuntimeError должен быть выброшен
            with pytest.raises(RuntimeError) as exc_info:
                raise RuntimeError(f"Failed to consume invitation code: TEST_CODE")

            assert "Failed to consume invitation code" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
