"""
Unit тесты для auth_storage.py

Покрытие:
- ОБЯЗАТЕЛЬНО: 5 тестов из T04_session_cleanup_spec.md для cleanup_expired_sessions()
- Все 20 методов AuthStorageManager (User CRUD, Invitation CRUD, Session CRUD, Audit)
- Threading.Lock корректность (per-user locks)
- Atomic write через BaseStorageManager

Автор: qa-expert
Дата: 17 октября 2025
Задача: T10 (#00005_20251014_HRYHG)
"""

import pytest
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from auth_storage import AuthStorageManager
from auth_models import (
    User, Session, Invitation, AuthAuditEvent,
    UserSettings, UserMetadata, SessionMetadata, InvitationMetadata
)


class TestAuthStorageManager:
    """Тесты для AuthStorageManager."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Создает временную директорию для тестов (Windows 11 совместимость)."""
        test_dir = tmp_path / "test_auth_storage"
        test_dir.mkdir(exist_ok=True)
        yield test_dir
        # Cleanup (Windows 11 совместимость)
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.fixture
    def storage(self, temp_dir):
        """Создает AuthStorageManager с временной директорией."""
        return AuthStorageManager(temp_dir)

    # ========== USER CRUD METHODS (6 методов) ==========

    def test_create_user_basic(self, storage):
        """create_user() создает нового пользователя."""
        user = User(
            user_id="user_123",
            telegram_id=155894817,
            username="john_doe",
            password_hash="hash123",
            role="user"
        )

        result = storage.create_user(user)

        assert result is True

        # Проверить создание директории и файлов
        user_dir = storage.base_path / "user_user_123"
        assert user_dir.exists()
        assert (user_dir / "user.json").exists()
        assert (user_dir / "sessions.json").exists()

    def test_create_user_duplicate(self, storage):
        """create_user() отклоняет дублирующего пользователя."""
        user = User(
            user_id="user_duplicate",
            telegram_id=123456,
            username="duplicate_user",
            password_hash="hash456"
        )

        # Первое создание
        result1 = storage.create_user(user)
        assert result1 is True

        # Второе создание (дубликат)
        result2 = storage.create_user(user)
        assert result2 is False

    def test_get_user_existing(self, storage):
        """get_user() получает существующего пользователя."""
        user = User(
            user_id="user_get",
            telegram_id=789012,
            username="get_user",
            password_hash="hash789"
        )
        storage.create_user(user)

        retrieved_user = storage.get_user("user_get")

        assert retrieved_user is not None
        assert retrieved_user.user_id == "user_get"
        assert retrieved_user.telegram_id == 789012
        assert retrieved_user.username == "get_user"

    def test_get_user_nonexistent(self, storage):
        """get_user() возвращает None для несуществующего пользователя."""
        retrieved_user = storage.get_user("nonexistent_user")

        assert retrieved_user is None

    def test_update_user_existing(self, storage):
        """update_user() обновляет существующего пользователя."""
        user = User(
            user_id="user_update",
            telegram_id=111222,
            username="old_username",
            password_hash="hash111"
        )
        storage.create_user(user)

        # Обновить username
        user.username = "new_username"
        result = storage.update_user(user)

        assert result is True

        # Проверить обновление
        updated_user = storage.get_user("user_update")
        assert updated_user.username == "new_username"

    def test_update_user_nonexistent(self, storage):
        """update_user() отклоняет несуществующего пользователя."""
        user = User(
            user_id="nonexistent_user",
            telegram_id=999999,
            username="fake_user",
            password_hash="hash999"
        )

        result = storage.update_user(user)

        assert result is False

    def test_delete_user_soft_delete(self, storage):
        """delete_user() выполняет soft delete (is_active=False)."""
        user = User(
            user_id="user_delete",
            telegram_id=333444,
            username="delete_user",
            password_hash="hash333"
        )
        storage.create_user(user)

        result = storage.delete_user("user_delete")

        assert result is True

        # Проверить что пользователь не удален физически
        deleted_user = storage.get_user("user_delete")
        assert deleted_user is not None
        assert deleted_user.is_active is False

    def test_get_user_by_telegram_id(self, storage):
        """get_user_by_telegram_id() находит пользователя по telegram_id."""
        user = User(
            user_id="user_tg",
            telegram_id=555666,
            username="tg_user",
            password_hash="hash555"
        )
        storage.create_user(user)

        retrieved_user = storage.get_user_by_telegram_id(555666)

        assert retrieved_user is not None
        assert retrieved_user.telegram_id == 555666
        assert retrieved_user.user_id == "user_tg"

    def test_list_users_default(self, storage):
        """list_users() возвращает всех активных пользователей."""
        user1 = User(user_id="user_1", telegram_id=111, username="user1", password_hash="hash1")
        user2 = User(user_id="user_2", telegram_id=222, username="user2", password_hash="hash2")
        user3 = User(user_id="user_3", telegram_id=333, username="user3", password_hash="hash3", is_active=False)

        storage.create_user(user1)
        storage.create_user(user2)
        storage.create_user(user3)

        users = storage.list_users()

        assert len(users) == 2  # Только активные

    def test_list_users_include_inactive(self, storage):
        """list_users(include_inactive=True) возвращает всех пользователей."""
        user1 = User(user_id="user_1", telegram_id=111, username="user1", password_hash="hash1")
        user2 = User(user_id="user_2", telegram_id=222, username="user2", password_hash="hash2", is_active=False)

        storage.create_user(user1)
        storage.create_user(user2)

        users = storage.list_users(include_inactive=True)

        assert len(users) == 2  # Все пользователи

    # ========== INVITATION CRUD METHODS (4 метода) ==========

    def test_create_invitation_basic(self, storage):
        """create_invitation() создает новое приглашение."""
        invitation = Invitation(
            invite_code="invite_abc123",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )

        result = storage.create_invitation(invitation)

        assert result is True

        # Проверить создание в invitations.json
        invitations_file = storage.base_path / "invitations.json"
        assert invitations_file.exists()

    def test_create_invitation_duplicate(self, storage):
        """create_invitation() отклоняет дублирующий код."""
        invitation = Invitation(
            invite_code="duplicate_code",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )

        # Первое создание
        result1 = storage.create_invitation(invitation)
        assert result1 is True

        # Второе создание (дубликат)
        result2 = storage.create_invitation(invitation)
        assert result2 is False

    def test_get_invitation_existing(self, storage):
        """get_invitation() получает существующее приглашение."""
        invitation = Invitation(
            invite_code="get_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        storage.create_invitation(invitation)

        retrieved = storage.get_invitation("get_invite")

        assert retrieved is not None
        assert retrieved.invite_code == "get_invite"
        assert retrieved.invite_type == "user"

    def test_validate_invitation_valid(self, storage):
        """validate_invitation() возвращает валидное приглашение."""
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
        storage.create_invitation(invitation)

        validated = storage.validate_invitation("valid_invite")

        assert validated is not None
        assert validated.is_valid() is True

    def test_validate_invitation_expired(self, storage):
        """validate_invitation() отклоняет истекшее приглашение."""
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
        storage.create_invitation(invitation)

        validated = storage.validate_invitation("expired_invite")

        assert validated is None

    def test_consume_invitation_success(self, storage):
        """consume_invitation() помечает приглашение как использованное."""
        invitation = Invitation(
            invite_code="consume_invite",
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
        storage.create_invitation(invitation)

        result = storage.consume_invitation("consume_invite", consumed_by_user_id="user_123")

        assert result is True

        # Проверить что приглашение помечено как consumed
        consumed = storage.get_invitation("consume_invite")
        assert consumed.uses_count == 1
        assert consumed.is_consumed is True
        assert consumed.consumed_by_user_id == "user_123"

    # ========== SESSION CRUD METHODS (4 метода) ==========

    def test_create_session_basic(self, storage):
        """create_session() создает новую сессию."""
        # Сначала создать пользователя
        user = User(user_id="user_sess", telegram_id=777888, username="sess_user", password_hash="hash777")
        storage.create_user(user)

        session = Session(
            session_id="sess_abc123",
            user_id="user_sess",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )

        result = storage.create_session("user_sess", session)

        assert result is True

    def test_get_session_existing(self, storage):
        """get_session() получает существующую сессию."""
        # Создать пользователя и сессию
        user = User(user_id="user_get_sess", telegram_id=888999, username="get_sess_user", password_hash="hash888")
        storage.create_user(user)

        session = Session(
            session_id="get_sess_123",
            user_id="user_get_sess",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        storage.create_session("user_get_sess", session)

        retrieved = storage.get_session("get_sess_123")

        assert retrieved is not None
        assert retrieved.session_id == "get_sess_123"
        assert retrieved.user_id == "user_get_sess"

    def test_revoke_session_success(self, storage):
        """revoke_session() удаляет сессию."""
        # Создать пользователя и сессию
        user = User(user_id="user_revoke", telegram_id=999000, username="revoke_user", password_hash="hash999")
        storage.create_user(user)

        session = Session(
            session_id="revoke_sess_123",
            user_id="user_revoke",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        storage.create_session("user_revoke", session)

        result = storage.revoke_session("revoke_sess_123")

        assert result is True

        # Проверить что сессия удалена
        revoked = storage.get_session("revoke_sess_123")
        assert revoked is None

    # ========== T04: CLEANUP_EXPIRED_SESSIONS (5 ОБЯЗАТЕЛЬНЫХ ТЕСТОВ) ==========

    def test_cleanup_expired_sessions_basic(self, storage):
        """
        T04 Test 1: Базовая очистка истекших сессий.

        Удаление истекших сессий, сохранение активных.
        Источник: T04_session_cleanup_spec.md, строки 277-313
        """
        # Создать пользователя
        user = User(user_id="user_cleanup", telegram_id=12345, username="cleanup_user", password_hash="hash_cleanup")
        storage.create_user(user)

        # Создать 2 истекшие + 1 активную сессию
        user_dir = storage.base_path / "user_user_cleanup"
        sessions_file = user_dir / "sessions.json"
        sessions_data = {
            "schema_version": "1.0",
            "sessions": [
                {
                    "session_id": "expired1",
                    "user_id": "user_cleanup",
                    "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                    "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
                    "last_activity": (datetime.now() - timedelta(days=2)).isoformat(),
                    "is_active": True,
                    "ip_address": None,
                    "user_agent": "Telegram Bot",
                    "metadata": {"device": "unknown", "location": "Unknown"}
                },
                {
                    "session_id": "expired2",
                    "user_id": "user_cleanup",
                    "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "last_activity": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "is_active": True,
                    "ip_address": None,
                    "user_agent": "Telegram Bot",
                    "metadata": {"device": "unknown", "location": "Unknown"}
                },
                {
                    "session_id": "active1",
                    "user_id": "user_cleanup",
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=7)).isoformat(),
                    "last_activity": datetime.now().isoformat(),
                    "is_active": True,
                    "ip_address": None,
                    "user_agent": "Telegram Bot",
                    "metadata": {"device": "unknown", "location": "Unknown"}
                }
            ]
        }
        storage.atomic_write(sessions_file, sessions_data)

        # Выполнить очистку
        deleted_count = storage.cleanup_expired_sessions("user_cleanup")

        # Проверки
        assert deleted_count == 2

        remaining = storage.get_user_sessions("user_cleanup")
        assert len(remaining) == 1
        assert remaining[0].session_id == "active1"

    def test_cleanup_expired_sessions_empty_file(self, storage):
        """
        T04 Test 2: Обработка пустого файла сессий.

        Источник: T04_session_cleanup_spec.md, строки 315-324
        """
        # Попытаться очистить для несуществующего пользователя
        deleted_count = storage.cleanup_expired_sessions("nonexistent_user")

        assert deleted_count == 0

    def test_cleanup_expired_sessions_invalid_format(self, storage):
        """
        T04 Test 3: Удаление сессий с некорректным expires_at.

        Источник: T04_session_cleanup_spec.md, строки 326-343
        """
        # Создать пользователя
        user = User(user_id="user_invalid", telegram_id=67890, username="invalid_user", password_hash="hash_invalid")
        storage.create_user(user)

        # Создать сессию с некорректным expires_at
        user_dir = storage.base_path / "user_user_invalid"
        sessions_file = user_dir / "sessions.json"
        sessions_data = {
            "schema_version": "1.0",
            "sessions": [
                {
                    "session_id": "invalid1",
                    "user_id": "user_invalid",
                    "created_at": datetime.now().isoformat(),
                    "expires_at": "NOT_A_DATE",  # Некорректный формат
                    "last_activity": datetime.now().isoformat(),
                    "is_active": True,
                    "ip_address": None,
                    "user_agent": "Telegram Bot",
                    "metadata": {"device": "unknown", "location": "Unknown"}
                }
            ]
        }
        storage.atomic_write(sessions_file, sessions_data)

        # Некорректные сессии должны удаляться
        deleted_count = storage.cleanup_expired_sessions("user_invalid")
        assert deleted_count == 1

        # Проверить что сессия удалена
        remaining = storage.get_user_sessions("user_invalid")
        assert len(remaining) == 0

    def test_cleanup_expired_sessions_thread_safety(self, storage):
        """
        T04 Test 4: Thread-safety при параллельной очистке.

        Источник: T04_session_cleanup_spec.md, строки 345-380
        """
        # Создать пользователя
        user = User(user_id="user_thread", telegram_id=11111, username="thread_user", password_hash="hash_thread")
        storage.create_user(user)

        # Создать 100 истекших сессий
        user_dir = storage.base_path / "user_user_thread"
        sessions_file = user_dir / "sessions.json"
        sessions_list = []
        for i in range(100):
            sessions_list.append({
                "session_id": f"session{i}",
                "user_id": "user_thread",
                "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "last_activity": (datetime.now() - timedelta(days=2)).isoformat(),
                "is_active": True,
                "ip_address": None,
                "user_agent": "Telegram Bot",
                "metadata": {"device": "unknown", "location": "Unknown"}
            })

        sessions_data = {"schema_version": "1.0", "sessions": sessions_list}
        storage.atomic_write(sessions_file, sessions_data)

        # Параллельная очистка из 10 потоков
        results = []

        def cleanup_thread():
            count = storage.cleanup_expired_sessions("user_thread")
            results.append(count)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=cleanup_thread)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Все сессии должны быть удалены (первый поток удалит все)
        remaining = storage.get_user_sessions("user_thread")
        assert len(remaining) == 0

    def test_cleanup_expired_sessions_performance(self, storage):
        """
        T04 Test 5: Производительность на 1000 сессий.

        Источник: T04_session_cleanup_spec.md, строки 382-409
        """
        # Создать пользователя
        user = User(user_id="user_perf", telegram_id=22222, username="perf_user", password_hash="hash_perf")
        storage.create_user(user)

        # Создать 1000 сессий (500 истекших + 500 активных)
        user_dir = storage.base_path / "user_user_perf"
        sessions_file = user_dir / "sessions.json"
        sessions_list = []

        for i in range(500):
            sessions_list.append({
                "session_id": f"expired{i}",
                "user_id": "user_perf",
                "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "last_activity": (datetime.now() - timedelta(days=2)).isoformat(),
                "is_active": True,
                "ip_address": None,
                "user_agent": "Telegram Bot",
                "metadata": {"device": "unknown", "location": "Unknown"}
            })

        for i in range(500):
            sessions_list.append({
                "session_id": f"active{i}",
                "user_id": "user_perf",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=7)).isoformat(),
                "last_activity": datetime.now().isoformat(),
                "is_active": True,
                "ip_address": None,
                "user_agent": "Telegram Bot",
                "metadata": {"device": "unknown", "location": "Unknown"}
            })

        sessions_data = {"schema_version": "1.0", "sessions": sessions_list}
        storage.atomic_write(sessions_file, sessions_data)

        # Замерить время очистки
        start_time = time.time()
        deleted_count = storage.cleanup_expired_sessions("user_perf")
        elapsed_time = time.time() - start_time

        assert deleted_count == 500
        assert elapsed_time < 1.0  # Должно выполниться < 1 секунды

    # ========== AUDIT LOG METHOD (1 метод) ==========

    def test_log_auth_event_basic(self, storage):
        """log_auth_event() записывает событие в audit log."""
        event = AuthAuditEvent(
            event_id="evt_123",
            event_type="LOGIN_SUCCESS",
            user_id="user_123",
            timestamp=datetime.now(),
            ip_address="192.168.1.1",
            details={"session_id": "sess_abc"}
        )

        result = storage.log_auth_event(event)

        assert result is True

        # Проверить создание audit log файла
        audit_file = storage.base_path / "auth_audit.log"
        assert audit_file.exists()

    # ========== ДОПОЛНИТЕЛЬНЫЕ ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    def test_get_user_sessions(self, storage):
        """get_user_sessions() возвращает список сессий пользователя."""
        # Создать пользователя
        user = User(user_id="user_getsess", telegram_id=33333, username="getsess_user", password_hash="hash_getsess")
        storage.create_user(user)

        # Создать 2 активные сессии
        session1 = Session(
            session_id="sess1",
            user_id="user_getsess",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        session2 = Session(
            session_id="sess2",
            user_id="user_getsess",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        storage.create_session("user_getsess", session1)
        storage.create_session("user_getsess", session2)

        sessions = storage.get_user_sessions("user_getsess")

        assert len(sessions) >= 2  # Минимум 2 активные

    def test_list_invitations(self, storage):
        """list_invitations() возвращает список всех приглашений."""
        invitation1 = Invitation(
            invite_code="list_invite_1",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        invitation2 = Invitation(
            invite_code="list_invite_2",
            invite_type="admin",
            created_by_user_id="admin_1",
            target_role="admin",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )

        storage.create_invitation(invitation1)
        storage.create_invitation(invitation2)

        invitations = storage.list_invitations()

        assert len(invitations) >= 2

    def test_update_invitation(self, storage):
        """update_invitation() обновляет приглашение."""
        invitation = Invitation(
            invite_code="update_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        storage.create_invitation(invitation)

        # Обновить is_active
        invitation.is_active = False
        result = storage.update_invitation(invitation)

        assert result is True

        # Проверить обновление
        updated = storage.get_invitation("update_invite")
        assert updated.is_active is False

    def test_get_auth_settings(self, storage):
        """get_auth_settings() возвращает настройки авторизации."""
        settings = storage.get_auth_settings()

        assert settings is not None
        assert settings.password_policy.min_length == 5
        assert settings.password_policy.max_length == 8

    def test_update_auth_settings(self, storage):
        """update_auth_settings() обновляет настройки авторизации."""
        settings = storage.get_auth_settings()
        settings.password_policy.min_length = 6

        result = storage.update_auth_settings(settings)

        assert result is True

        # Проверить обновление
        updated_settings = storage.get_auth_settings()
        assert updated_settings.password_policy.min_length == 6
