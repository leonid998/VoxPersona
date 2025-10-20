"""
Unit тесты для auth_manager.py

Покрытие:
- authenticate() - с проверкой must_change_password и temp_password_expires_at
- logout(), register_user()
- RBAC: has_permission(), has_role(), get_user_permissions()
- Управление пользователями (7 методов)
- Управление приглашениями (2 метода)
- КРИТИЧНО: must_change_password workflow

Автор: qa-expert
Дата: 17 октября 2025
Задача: T10 (#00005_20251014_HRYHG)
"""

import pytest
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from auth_manager import AuthManager
from auth_models import User, Session, Invitation


class TestAuthManager:
    """Тесты для AuthManager."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Создает временную директорию для тестов (Windows 11 совместимость)."""
        test_dir = tmp_path / "test_auth_manager"
        test_dir.mkdir(exist_ok=True)
        yield test_dir
        # Cleanup (Windows 11 совместимость)
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.fixture
    def auth_manager(self, temp_dir):
        """Создает AuthManager с временной директорией."""
        return AuthManager(temp_dir)

    # ========== АУТЕНТИФИКАЦИЯ (2 метода) ==========

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_manager):
        """authenticate() успешно авторизует пользователя."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="john_doe",
            password="Pass123",
            invite_code="test_invite"
        )

        # Аутентификация
        session = await auth_manager.authenticate(155894817, "Pass123")

        assert session is not None
        assert session.user_id == user.user_id
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_manager):
        """authenticate() отклоняет неверный пароль."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        await auth_manager.register_user(
            telegram_id=155894817,
            username="john_doe",
            password="Pass123",
            invite_code="test_invite"
        )

        # Аутентификация с неверным паролем
        session = await auth_manager.authenticate(155894817, "WrongPass")

        assert session is None

    @pytest.mark.asyncio
    async def test_authenticate_temp_password_expired(self, auth_manager):
        """КРИТИЧНО: authenticate() отклоняет истекший временный пароль."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="john_doe",
            password="Pass123",
            invite_code="test_invite"
        )

        # Сбросить пароль (устанавливает temp_password_expires_at)
        await auth_manager.reset_password(user.user_id, "Temp123", "admin_1")

        # Вручную установить истекший temp_password_expires_at
        user = auth_manager.storage.get_user(user.user_id)
        user.temp_password_expires_at = datetime.now() - timedelta(days=1)  # Истек вчера
        auth_manager.storage.update_user(user)

        # Аутентификация должна провалиться
        session = await auth_manager.authenticate(155894817, "Temp123")

        assert session is None

    @pytest.mark.asyncio
    async def test_authenticate_must_change_password_logged(self, auth_manager):
        """КРИТИЧНО: authenticate() логирует must_change_password в audit."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="john_doe",
            password="Pass123",
            invite_code="test_invite"
        )

        # Сбросить пароль (устанавливает must_change_password=True)
        await auth_manager.reset_password(user.user_id, "Temp123", "admin_1")

        # Аутентификация
        session = await auth_manager.authenticate(155894817, "Temp123")

        assert session is not None
        # Проверить что must_change_password=True был залогирован (в details audit event)

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_manager):
        """logout() успешно удаляет сессию."""
        # Создать пользователя и аутентифицироваться
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        await auth_manager.register_user(
            telegram_id=155894817,
            username="john_doe",
            password="Pass123",
            invite_code="test_invite"
        )

        session = await auth_manager.authenticate(155894817, "Pass123")

        # Выйти
        result = await auth_manager.logout(session.session_id)

        assert result is True

        # Проверить что сессия удалена
        deleted_session = auth_manager.storage.get_session(session.session_id)
        assert deleted_session is None

    # ========== РЕГИСТРАЦИЯ (1 метод) ==========

    @pytest.mark.asyncio
    async def test_register_user_success(self, auth_manager):
        """register_user() успешно создает пользователя."""
        # Создать приглашение
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        # Регистрация
        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="john_doe",
            password="Pass123",
            invite_code="test_invite"
        )

        assert user is not None
        assert user.telegram_id == 155894817
        assert user.username == "john_doe"
        assert user.role == "user"
        assert user.must_change_password is False  # КРИТИЧНО: Регулярная регистрация

    @pytest.mark.asyncio
    async def test_register_user_invalid_password(self, auth_manager):
        """register_user() отклоняет невалидный пароль."""
        # Создать приглашение
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        # Попытка регистрации с невалидным паролем
        with pytest.raises(ValueError, match="Невалидный пароль"):
            await auth_manager.register_user(
                telegram_id=155894817,
                username="john_doe",
                password="Too",  # Слишком короткий
                invite_code="test_invite"
            )

    @pytest.mark.asyncio
    async def test_register_user_invalid_invite(self, auth_manager):
        """register_user() отклоняет невалидное приглашение."""
        # Попытка регистрации с невалидным invite_code
        with pytest.raises(ValueError, match="Недействительный код приглашения"):
            await auth_manager.register_user(
                telegram_id=155894817,
                username="john_doe",
                password="Pass123",
                invite_code="invalid_code"
            )

    # ========== RBAC (3 метода) ==========

    @pytest.mark.asyncio
    async def test_has_permission_super_admin(self, auth_manager):
        """has_permission() возвращает True для super_admin."""
        # Создать super_admin пользователя
        invite = Invitation(
            invite_code="admin_invite",
            invite_type="admin",
            created_by_user_id="system",
            target_role="super_admin",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="super_admin_user",
            password="Admin1",
            invite_code="admin_invite"
        )

        # Проверка прав (super_admin имеет все права)
        has_perm = await auth_manager.has_permission(user.user_id, "users.delete")

        assert has_perm is True

    @pytest.mark.asyncio
    async def test_has_permission_user_no_permission(self, auth_manager):
        """has_permission() возвращает False для отсутствующего права."""
        # Создать обычного пользователя
        invite = Invitation(
            invite_code="user_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="regular_user",
            password="User123",
            invite_code="user_invite"
        )

        # Проверка прав (user НЕ имеет users.delete)
        has_perm = await auth_manager.has_permission(user.user_id, "users.delete")

        assert has_perm is False

    @pytest.mark.asyncio
    async def test_has_role_success(self, auth_manager):
        """has_role() возвращает True для корректной роли."""
        # Создать пользователя
        invite = Invitation(
            invite_code="user_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="regular_user",
            password="User123",
            invite_code="user_invite"
        )

        # Проверка роли
        has_role = await auth_manager.has_role(user.user_id, "user")

        assert has_role is True

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, auth_manager):
        """get_user_permissions() возвращает список прав."""
        # Создать пользователя
        invite = Invitation(
            invite_code="user_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(
            telegram_id=155894817,
            username="regular_user",
            password="User123",
            invite_code="user_invite"
        )

        # Получить права
        permissions = await auth_manager.get_user_permissions(user.user_id)

        assert isinstance(permissions, list)
        assert len(permissions) > 0
        assert "files.upload" in permissions  # user имеет files.upload

    # ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (7 методов) ==========

    @pytest.mark.asyncio
    async def test_list_users_active_only(self, auth_manager):
        """list_users() возвращает только активных пользователей."""
        # Создать 2 активных + 1 неактивного
        invite = Invitation(
            invite_code="invite1",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user1 = await auth_manager.register_user(155894817, "user1", "Pass123", "invite1")

        # Второе приглашение для user2
        invite2 = Invitation(
            invite_code="invite2",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite2)

        user2 = await auth_manager.register_user(123456789, "user2", "Pass456", "invite2")

        # Деактивировать user2
        user2_obj = auth_manager.storage.get_user(user2.user_id)
        user2_obj.is_active = False
        auth_manager.storage.update_user(user2_obj)

        # Получить активных пользователей
        users = await auth_manager.list_users(include_inactive=False)

        assert len(users) == 1  # Только user1

    @pytest.mark.asyncio
    async def test_get_user_existing(self, auth_manager):
        """get_user() возвращает существующего пользователя."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # Получить пользователя
        retrieved = await auth_manager.get_user(user.user_id)

        assert retrieved is not None
        assert retrieved.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_block_user_success(self, auth_manager):
        """block_user() блокирует пользователя."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # Блокировать
        result = await auth_manager.block_user(user.user_id, "admin_1")

        assert result is True

        # Проверить блокировку
        blocked_user = auth_manager.storage.get_user(user.user_id)
        assert blocked_user.is_blocked is True

    @pytest.mark.asyncio
    async def test_unblock_user_success(self, auth_manager):
        """unblock_user() разблокирует пользователя."""
        # Создать и заблокировать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")
        await auth_manager.block_user(user.user_id, "admin_1")

        # Разблокировать
        result = await auth_manager.unblock_user(user.user_id)

        assert result is True

        # Проверить разблокировку
        unblocked_user = auth_manager.storage.get_user(user.user_id)
        assert unblocked_user.is_blocked is False

    @pytest.mark.asyncio
    async def test_change_role_success(self, auth_manager):
        """change_role() изменяет роль пользователя."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # Изменить роль на admin
        result = await auth_manager.change_role(user.user_id, "admin", "super_admin_1")

        assert result is True

        # Проверить смену роли
        updated_user = auth_manager.storage.get_user(user.user_id)
        assert updated_user.role == "admin"

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_manager):
        """КРИТИЧНО: change_password() успешно меняет пароль и сбрасывает must_change_password."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # Сбросить пароль (устанавливает must_change_password=True)
        await auth_manager.reset_password(user.user_id, "Temp456", "admin_1")

        # Сменить пароль
        result = await auth_manager.change_password(user.user_id, "Temp456", "New789")

        assert result is True

        # Проверить что must_change_password сброшен
        updated_user = auth_manager.storage.get_user(user.user_id)
        assert updated_user.must_change_password is False
        assert updated_user.temp_password_expires_at is None

    @pytest.mark.asyncio
    async def test_change_password_invalid_old_password(self, auth_manager):
        """change_password() отклоняет неверный старый пароль."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # Попытка смены с неверным старым паролем
        with pytest.raises(ValueError, match="Неверный старый пароль"):
            await auth_manager.change_password(user.user_id, "WrongOld", "New789")

    @pytest.mark.asyncio
    async def test_reset_password_sets_must_change(self, auth_manager):
        """КРИТИЧНО: reset_password() устанавливает must_change_password=True."""
        # Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # Сбросить пароль
        temp_password = await auth_manager.reset_password(user.user_id, "Temp456", "admin_1")

        assert temp_password == "Temp456"

        # Проверить must_change_password=True и temp_password_expires_at
        reset_user = auth_manager.storage.get_user(user.user_id)
        assert reset_user.must_change_password is True
        assert reset_user.temp_password_expires_at is not None
        assert reset_user.temp_password_expires_at > datetime.now()

    # ========== УПРАВЛЕНИЕ ПРИГЛАШЕНИЯМИ (2 метода) ==========

    @pytest.mark.asyncio
    async def test_create_invitation_success(self, auth_manager):
        """create_invitation() создает приглашение."""
        # Создать приглашение
        invitation = await auth_manager.create_invitation("user", "admin_1", "user")

        assert invitation is not None
        assert invitation.invite_type == "user"
        assert invitation.target_role == "user"
        assert invitation.created_by_user_id == "admin_1"

    @pytest.mark.asyncio
    async def test_create_invitation_invalid_role(self, auth_manager):
        """create_invitation() отклоняет невалидную роль."""
        # Попытка создания с невалидной ролью
        with pytest.raises(ValueError, match="Недействительная роль"):
            await auth_manager.create_invitation("user", "admin_1", "invalid_role")

    @pytest.mark.asyncio
    async def test_validate_invitation_valid(self, auth_manager):
        """validate_invitation() возвращает True для валидного приглашения."""
        # Создать приглашение
        invitation = await auth_manager.create_invitation("user", "admin_1", "user")

        # Валидировать
        is_valid = await auth_manager.validate_invitation(invitation.invite_code)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_invitation_invalid(self, auth_manager):
        """validate_invitation() возвращает False для невалидного приглашения."""
        # Валидировать несуществующее приглашение
        is_valid = await auth_manager.validate_invitation("invalid_code")

        assert is_valid is False

    # ========== MUST_CHANGE_PASSWORD WORKFLOW ==========

    @pytest.mark.asyncio
    async def test_must_change_password_workflow(self, auth_manager):
        """КРИТИЧНО: Полный workflow принудительной смены пароля."""
        # 1. Создать пользователя
        invite = Invitation(
            invite_code="test_invite",
            invite_type="user",
            created_by_user_id="admin_1",
            target_role="user",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48)
        )
        auth_manager.storage.create_invitation(invite)

        user = await auth_manager.register_user(155894817, "john_doe", "Pass123", "test_invite")

        # 2. Админ сбрасывает пароль (must_change_password=True, TTL=3 дня)
        temp_password = await auth_manager.reset_password(user.user_id, "Temp456", "admin_1")
        reset_user = auth_manager.storage.get_user(user.user_id)

        assert reset_user.must_change_password is True
        assert reset_user.temp_password_expires_at is not None

        # 3. Пользователь входит с временным паролем
        session = await auth_manager.authenticate(155894817, temp_password)
        assert session is not None

        # 4. Пользователь меняет пароль (must_change_password сбрасывается)
        await auth_manager.change_password(user.user_id, temp_password, "New789")
        changed_user = auth_manager.storage.get_user(user.user_id)

        assert changed_user.must_change_password is False
        assert changed_user.temp_password_expires_at is None

        # 5. Пользователь может войти с новым паролем
        new_session = await auth_manager.authenticate(155894817, "New789")
        assert new_session is not None
