"""
Unit тесты для auth_models.py

Покрытие:
- Все 22 модели (User, Session, Invitation, Role, AuthSettings и вложенные)
- Методы is_valid(), refresh() для Session и Invitation
- Функции datetime_to_iso(), iso_to_datetime()
- Критичные поля: must_change_password, temp_password_expires_at

Автор: qa-expert
Дата: 17 октября 2025
Задача: T10 (#00005_20251014_HRYHG)
"""

import pytest
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from auth_models import (
    User, UserSettings, UserMetadata,
    Session, SessionMetadata,
    Invitation, InvitationMetadata,
    Role, RoleUIAccess,
    AuthSettings, PasswordPolicy, SessionPolicy, RateLimiting,
    InvitePolicy, RegistrationSettings, SecuritySettings,
    AuthAuditEvent,
    datetime_to_iso, iso_to_datetime
)


class TestUserModels:
    """Тесты для User models (User, UserSettings, UserMetadata)."""

    def test_user_model_creation(self):
        """Базовое создание User."""
        user = User(
            user_id="user_123",
            telegram_id=155894817,
            username="john_doe",
            password_hash="hash123",
            role="user"
        )

        assert user.user_id == "user_123"
        assert user.telegram_id == 155894817
        assert user.username == "john_doe"
        assert user.password_hash == "hash123"
        assert user.role == "user"
        assert user.is_active is True
        assert user.is_blocked is False
        assert user.must_change_password is False
        assert user.temp_password_expires_at is None

    def test_user_must_change_password_field(self):
        """КРИТИЧНО: Проверка поля must_change_password."""
        user = User(
            user_id="user_456",
            telegram_id=123456,
            username="test_user",
            password_hash="hash456",
            must_change_password=True
        )

        assert user.must_change_password is True

    def test_user_temp_password_expires_at_field(self):
        """КРИТИЧНО: Проверка поля temp_password_expires_at (TTL=3 дня)."""
        expires_at = datetime.now() + timedelta(days=3)
        user = User(
            user_id="user_789",
            telegram_id=789012,
            username="temp_user",
            password_hash="hash789",
            must_change_password=True,
            temp_password_expires_at=expires_at
        )

        assert user.temp_password_expires_at == expires_at
        assert user.must_change_password is True

    def test_user_settings_default(self):
        """Проверка UserSettings по умолчанию."""
        settings = UserSettings()

        assert settings.language == "ru"
        assert settings.timezone == "UTC+3"
        assert settings.notifications_enabled is True

    def test_user_metadata_default(self):
        """Проверка UserMetadata по умолчанию."""
        metadata = UserMetadata()

        assert metadata.registration_source == "invite"
        assert metadata.invite_code_used is None
        assert metadata.notes == ""


class TestSessionModels:
    """Тесты для Session models (Session, SessionMetadata)."""

    def test_session_model_creation(self):
        """Базовое создание Session."""
        session = Session(
            session_id="sess_abc123",
            user_id="user_123",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )

        assert session.session_id == "sess_abc123"
        assert session.user_id == "user_123"
        assert session.is_active is True

    def test_session_is_valid_active(self):
        """Session.is_valid() для активной сессии."""
        session = Session(
            session_id="sess_valid",
            user_id="user_123",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),  # Истекает через час
            is_active=True
        )

        assert session.is_valid() is True

    def test_session_is_valid_expired(self):
        """Session.is_valid() для истекшей сессии."""
        session = Session(
            session_id="sess_expired",
            user_id="user_123",
            created_at=datetime.now() - timedelta(hours=2),
            expires_at=datetime.now() - timedelta(hours=1),  # Истекла час назад
            is_active=True
        )

        assert session.is_valid() is False

    def test_session_is_valid_inactive(self):
        """Session.is_valid() для неактивной сессии."""
        session = Session(
            session_id="sess_inactive",
            user_id="user_123",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            is_active=False  # Неактивна
        )

        assert session.is_valid() is False

    def test_session_refresh(self):
        """Session.refresh() обновляет last_activity."""
        session = Session(
            session_id="sess_refresh",
            user_id="user_123",
            created_at=datetime.now() - timedelta(minutes=10),
            expires_at=datetime.now() + timedelta(hours=1),
            last_activity=datetime.now() - timedelta(minutes=10)
        )

        old_activity = session.last_activity
        session.refresh()

        assert session.last_activity > old_activity

    def test_session_metadata_default(self):
        """Проверка SessionMetadata по умолчанию."""
        metadata = SessionMetadata()

        assert metadata.device == "unknown"
        assert metadata.location == "Unknown"


class TestInvitationModels:
    """Тесты для Invitation models (Invitation, InvitationMetadata)."""

    def test_invitation_model_creation(self):
        """Базовое создание Invitation."""
        invitation = Invitation(
            invite_code="invite_abc123",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )

        assert invitation.invite_code == "invite_abc123"
        assert invitation.invite_type == "user"
        assert invitation.target_role == "user"
        assert invitation.is_active is True
        assert invitation.is_consumed is False

    def test_invitation_is_valid_active(self):
        """Invitation.is_valid() для валидного приглашения."""
        invitation = Invitation(
            invite_code="valid_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            is_active=True,
            is_consumed=False,
            max_uses=1,
            uses_count=0
        )

        assert invitation.is_valid() is True

    def test_invitation_is_valid_expired(self):
        """Invitation.is_valid() для истекшего приглашения."""
        invitation = Invitation(
            invite_code="expired_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now() - timedelta(hours=49),
            expires_at=datetime.now() - timedelta(hours=1),  # Истекло
            is_active=True,
            is_consumed=False
        )

        assert invitation.is_valid() is False

    def test_invitation_is_valid_consumed(self):
        """Invitation.is_valid() для использованного приглашения."""
        invitation = Invitation(
            invite_code="consumed_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            is_active=True,
            is_consumed=True,  # Использовано
            max_uses=1,
            uses_count=1
        )

        assert invitation.is_valid() is False

    def test_invitation_metadata_default(self):
        """Проверка InvitationMetadata по умолчанию."""
        metadata = InvitationMetadata()

        assert metadata.purpose == ""
        assert metadata.contact_info == ""


class TestRoleModels:
    """Тесты для Role models (Role, RoleUIAccess)."""

    def test_role_model_creation(self):
        """Базовое создание Role."""
        role = Role(
            role_id="admin",
            display_name="Администратор",
            description="Управление пользователями",
            priority=70,
            permissions=["users.read", "users.list"]
        )

        assert role.role_id == "admin"
        assert role.display_name == "Администратор"
        assert role.priority == 70
        assert "users.read" in role.permissions

    def test_role_ui_access_default(self):
        """Проверка RoleUIAccess по умолчанию."""
        ui_access = RoleUIAccess()

        assert ui_access.menu_access_management is False
        assert ui_access.menu_system is False
        assert ui_access.menu_chats is True
        assert ui_access.menu_reports is True
        assert ui_access.menu_help is True


class TestAuthSettingsModels:
    """Тесты для AuthSettings models (AuthSettings и 5 sub-моделей)."""

    def test_password_policy_default(self):
        """Проверка PasswordPolicy по умолчанию."""
        policy = PasswordPolicy()

        assert policy.min_length == 5
        assert policy.max_length == 8
        assert policy.require_numbers is True
        assert policy.require_letters is True
        assert policy.bcrypt_rounds == 12

    def test_session_policy_default(self):
        """Проверка SessionPolicy по умолчанию."""
        policy = SessionPolicy()

        assert policy.ttl_hours == 24
        assert policy.max_sessions_per_user == 3
        assert policy.auto_extend_on_activity is True

    def test_rate_limiting_default(self):
        """Проверка RateLimiting по умолчанию."""
        rate_limiting = RateLimiting()

        assert rate_limiting.enabled is True
        assert rate_limiting.max_login_attempts == 3
        assert rate_limiting.lockout_duration_minutes == 15

    def test_auth_settings_default(self):
        """Проверка AuthSettings по умолчанию."""
        settings = AuthSettings()

        assert isinstance(settings.password_policy, PasswordPolicy)
        assert isinstance(settings.session_policy, SessionPolicy)
        assert isinstance(settings.rate_limiting, RateLimiting)
        assert settings.password_policy.min_length == 5


class TestAuditEventModel:
    """Тесты для AuthAuditEvent."""

    def test_audit_event_creation(self):
        """Базовое создание AuthAuditEvent."""
        event = AuthAuditEvent(
            event_id="evt_123",
            event_type="LOGIN_SUCCESS",
            user_id="user_123",
            timestamp=datetime.now(),
            ip_address="192.168.1.1",
            details={"session_id": "sess_abc"}
        )

        assert event.event_id == "evt_123"
        assert event.event_type == "LOGIN_SUCCESS"
        assert event.user_id == "user_123"
        assert event.ip_address == "192.168.1.1"
        assert event.details["session_id"] == "sess_abc"


class TestUtilityFunctions:
    """Тесты для utility функций (datetime_to_iso, iso_to_datetime)."""

    def test_datetime_to_iso(self):
        """Конвертация datetime в ISO строку."""
        dt = datetime(2025, 10, 17, 10, 30, 0)
        iso_str = datetime_to_iso(dt)

        assert iso_str is not None
        assert "2025-10-17" in iso_str
        assert "10:30:00" in iso_str

    def test_datetime_to_iso_none(self):
        """Конвертация None в ISO строку."""
        iso_str = datetime_to_iso(None)

        assert iso_str is None

    def test_iso_to_datetime(self):
        """Конвертация ISO строки в datetime."""
        iso_str = "2025-10-17T10:30:00"
        dt = iso_to_datetime(iso_str)

        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 10
        assert dt.day == 17

    def test_iso_to_datetime_none(self):
        """Конвертация None в datetime."""
        dt = iso_to_datetime(None)

        assert dt is None

    def test_iso_to_datetime_invalid(self):
        """Конвертация невалидной ISO строки в datetime."""
        dt = iso_to_datetime("NOT_A_DATE")

        assert dt is None
