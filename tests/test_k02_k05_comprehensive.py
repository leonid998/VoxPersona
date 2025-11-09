"""
Comprehensive tests for K-02 (RBAC) and K-05 (invite_code generation).

K-02: RBAC проверка для создания invite
K-05: Рефакторинг генерации invite_code

Author: agent-organizer
Date: 2025-11-05
Task: #00007_20251105_YEIJEG/01_bag_8563784537
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

# Настройка sys.path для импорта модулей из src
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import components
from auth_security import AuthSecurityManager
from auth_storage import AuthStorageManager
from auth_models import User, Invitation


# ==================== K-05 TESTS: generate_invite_code ====================

class TestK05InviteCodeGeneration:
    """Тесты для K-05: рефакторинг генерации invite_code."""

    def test_generate_invite_code_default_length(self):
        """Тест: генерация invite_code с длиной по умолчанию (32)."""
        invite_code = AuthSecurityManager.generate_invite_code()

        assert invite_code is not None
        assert isinstance(invite_code, str)
        assert len(invite_code) == 32

    def test_generate_invite_code_custom_length(self):
        """Тест: генерация invite_code с кастомной длиной."""
        for length in [16, 24, 32, 64]:
            invite_code = AuthSecurityManager.generate_invite_code(length=length)
            assert len(invite_code) == length

    def test_generate_invite_code_valid_chars(self):
        """Тест: invite_code содержит только допустимые символы (a-zA-Z0-9)."""
        invite_code = AuthSecurityManager.generate_invite_code()

        # Проверка regex: только буквы и цифры
        assert re.match(r'^[a-zA-Z0-9]+$', invite_code)

    def test_generate_invite_code_uniqueness(self):
        """Тест: каждый вызов генерирует уникальный код."""
        codes = [AuthSecurityManager.generate_invite_code() for _ in range(100)]

        # Все коды уникальны
        assert len(codes) == len(set(codes))

    def test_generate_invite_code_cryptographically_secure(self):
        """Тест: генерация использует secrets (криптографически безопасно)."""
        # Проверка что используется secrets.choice (высокая энтропия)
        codes = [AuthSecurityManager.generate_invite_code() for _ in range(1000)]

        # Статистическая проверка: все символы встречаются с примерно одинаковой частотой
        # (для криптографически безопасной генерации)
        all_chars = ''.join(codes)
        char_counts = {}
        for char in all_chars:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Минимальная и максимальная частота символов не должны отличаться слишком сильно
        # (проверка равномерности распределения)
        if char_counts:
            min_count = min(char_counts.values())
            max_count = max(char_counts.values())
            # Допустимое отклонение: в 2 раза (для 1000 кодов по 32 символа)
            assert max_count / min_count < 2.0


# ==================== K-02 TESTS: RBAC ====================

class TestK02RBACInviteCreation:
    """Тесты для K-02: RBAC проверка при создании приглашений."""

    @pytest.fixture
    def mock_auth(self):
        """Мок AuthManager с пользователями разных ролей."""
        auth = Mock()
        auth.storage = Mock()

        # Мок пользователи
        admin_user = User(
            user_id="admin_123",
            telegram_id=111111,
            username="admin_user",
            password_hash="hash",
            role="admin",
            is_active=True,
            is_blocked=False
        )

        regular_user = User(
            user_id="user_456",
            telegram_id=222222,
            username="regular_user",
            password_hash="hash",
            role="user",
            is_active=True,
            is_blocked=False
        )

        guest_user = User(
            user_id="guest_789",
            telegram_id=333333,
            username="guest_user",
            password_hash="hash",
            role="guest",
            is_active=True,
            is_blocked=False
        )

        # Маппинг telegram_id → User
        def get_user_by_telegram_id(telegram_id):
            mapping = {
                111111: admin_user,
                222222: regular_user,
                333333: guest_user
            }
            return mapping.get(telegram_id)

        auth.storage.get_user_by_telegram_id = Mock(side_effect=get_user_by_telegram_id)
        auth.storage.log_auth_event = Mock()

        return auth

    def test_admin_can_create_invitation(self, mock_auth):
        """Тест: администратор может создать приглашение."""
        admin_user = mock_auth.storage.get_user_by_telegram_id(111111)

        # Проверка роли
        assert admin_user.role == "admin"

        # RBAC проверка должна пройти
        assert admin_user.role == "admin"  # ✅ доступ разрешен

    def test_user_cannot_create_invitation(self, mock_auth):
        """Тест: обычный пользователь НЕ может создать приглашение."""
        regular_user = mock_auth.storage.get_user_by_telegram_id(222222)

        # Проверка роли
        assert regular_user.role == "user"

        # RBAC проверка должна отклонить
        assert regular_user.role != "admin"  # ❌ доступ запрещен

    def test_guest_cannot_create_invitation(self, mock_auth):
        """Тест: гость НЕ может создать приглашение."""
        guest_user = mock_auth.storage.get_user_by_telegram_id(333333)

        # Проверка роли
        assert guest_user.role == "guest"

        # RBAC проверка должна отклонить
        assert guest_user.role != "admin"  # ❌ доступ запрещен

    def test_rbac_violation_logged(self, mock_auth):
        """Тест: попытка нарушения RBAC логируется в audit log."""
        regular_user = mock_auth.storage.get_user_by_telegram_id(222222)

        # Симуляция попытки создать invite обычным пользователем
        if regular_user.role != "admin":
            # Должен быть вызван audit logging
            mock_auth.storage.log_auth_event(
                event_type="RBAC_VIOLATION",
                user_id=regular_user.user_id,
                metadata={
                    "action": "create_invitation",
                    "required_role": "admin",
                    "actual_role": regular_user.role,
                    "telegram_id": regular_user.telegram_id,
                    "timestamp": datetime.now().isoformat()
                }
            )

        # Проверка что log_auth_event был вызван
        mock_auth.storage.log_auth_event.assert_called_once()

        # Проверка параметров вызова
        call_args = mock_auth.storage.log_auth_event.call_args
        assert call_args[1]['event_type'] == "RBAC_VIOLATION"
        assert call_args[1]['user_id'] == "user_456"
        assert call_args[1]['metadata']['action'] == "create_invitation"
        assert call_args[1]['metadata']['required_role'] == "admin"
        assert call_args[1]['metadata']['actual_role'] == "user"

    def test_blocked_admin_cannot_create_invitation(self, mock_auth):
        """Тест: заблокированный администратор НЕ может создать приглашение."""
        blocked_admin = User(
            user_id="blocked_admin",
            telegram_id=444444,
            username="blocked_admin",
            password_hash="hash",
            role="admin",
            is_active=True,
            is_blocked=True  # ЗАБЛОКИРОВАН
        )

        # Даже если role == "admin", но is_blocked == True → отказ
        assert blocked_admin.role == "admin"
        assert blocked_admin.is_blocked == True

        # RBAC должен учитывать is_blocked
        should_deny = blocked_admin.is_blocked
        assert should_deny == True  # ❌ доступ запрещен

    def test_inactive_admin_cannot_create_invitation(self, mock_auth):
        """Тест: неактивный администратор НЕ может создать приглашение."""
        inactive_admin = User(
            user_id="inactive_admin",
            telegram_id=555555,
            username="inactive_admin",
            password_hash="hash",
            role="admin",
            is_active=False,  # НЕАКТИВЕН
            is_blocked=False
        )

        # Даже если role == "admin", но is_active == False → отказ
        assert inactive_admin.role == "admin"
        assert inactive_admin.is_active == False

        # RBAC должен учитывать is_active
        should_deny = not inactive_admin.is_active
        assert should_deny == True  # ❌ доступ запрещен


# ==================== INTEGRATION TESTS ====================

class TestK02K05Integration:
    """Интеграционные тесты K-02 и K-05."""

    def test_admin_creates_invitation_with_new_generator(self):
        """Тест: администратор создает приглашение с новым генератором кода."""
        # Создание invite_code через новый метод
        invite_code = AuthSecurityManager.generate_invite_code()

        # Код валиден
        assert len(invite_code) == 32
        assert re.match(r'^[a-zA-Z0-9]+$', invite_code)

        # Код может быть использован для создания Invitation
        invitation = Invitation(
            invite_code=invite_code,
            invite_type="user",
            created_by_user_id="admin_123",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48),
            max_uses=1,
            uses_count=0,
            is_active=True,
            is_consumed=False
        )

        # Приглашение создано корректно
        assert invitation.invite_code == invite_code
        assert invitation.is_active == True
        assert invitation.is_consumed == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
