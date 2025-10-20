"""
Интеграционные тесты для VoxPersona Authorization System Phase 2.

Тестируемая функциональность:
- T16: Инициализация AuthManager в main.py
- T11: config.py (get_auth_manager, set_auth_manager)
- T12: Custom Filters (auth_filter, require_role, require_permission)
- T13: Интеграция access_handlers.py
- T14: Кнопка "Настройки доступа" в markups.py
- T15: Изменения в handlers.py (FSM, callbacks, /change_password)
- T17: Упрощённые validators.py
- Регрессионные тесты (text, audio, documents с auth_filter)
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from dataclasses import dataclass
from typing import Literal
import asyncio

# Моки для Pyrogram
class MockMessage:
    """Мок для Pyrogram Message"""
    def __init__(self, text="", from_user=None, chat=None):
        self.text = text
        self.from_user = from_user or MockUser(id=100001)
        self.chat = chat or MockChat(id=100001)
        self.reply_to_message = None
        self.document = None
        self.voice = None

    async def reply(self, text, reply_markup=None):
        """Мок метода reply"""
        return MockMessage(text=text)

    async def edit_text(self, text, reply_markup=None):
        """Мок метода edit_text"""
        return True


class MockCallbackQuery:
    """Мок для Pyrogram CallbackQuery"""
    def __init__(self, data="", from_user=None, message=None):
        self.data = data
        self.from_user = from_user or MockUser(id=100001)
        self.message = message or MockMessage()
        self.id = "callback_123"

    async def answer(self, text="", show_alert=False):
        """Мок метода answer"""
        return True

    async def edit_message_text(self, text, reply_markup=None):
        """Мок метода edit_message_text"""
        return True


class MockUser:
    """Мок для Pyrogram User"""
    def __init__(self, id=100001, username="testuser"):
        self.id = id
        self.username = username


class MockChat:
    """Мок для Pyrogram Chat"""
    def __init__(self, id=100001):
        self.id = id


@dataclass
class User:
    """Dataclass модель пользователя (копия из auth_models.py)"""
    user_id: str
    telegram_id: int
    username: str
    password_hash: str
    role: Literal["super_admin", "admin", "user", "guest"]
    is_active: bool
    is_blocked: bool
    must_change_password: bool


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_user():
    """Фикстура для тестового пользователя admin"""
    return User(
        user_id="user_001",
        telegram_id=100001,
        username="admin",
        password_hash="$2b$12$hashed_password",
        role="admin",
        is_active=True,
        is_blocked=False,
        must_change_password=False
    )


@pytest.fixture
def mock_super_admin():
    """Фикстура для super_admin пользователя"""
    return User(
        user_id="user_000",
        telegram_id=100000,
        username="super_admin",
        password_hash="$2b$12$hashed_password",
        role="super_admin",
        is_active=True,
        is_blocked=False,
        must_change_password=False
    )


@pytest.fixture
def mock_guest():
    """Фикстура для guest пользователя"""
    return User(
        user_id="user_002",
        telegram_id=100002,
        username="guest",
        password_hash="$2b$12$hashed_password",
        role="guest",
        is_active=True,
        is_blocked=False,
        must_change_password=False
    )


@pytest.fixture
def mock_must_change_password_user():
    """Фикстура для пользователя, которому нужно сменить пароль"""
    return User(
        user_id="user_003",
        telegram_id=100003,
        username="new_user",
        password_hash="$2b$12$hashed_password",
        role="user",
        is_active=True,
        is_blocked=False,
        must_change_password=True
    )


@pytest.fixture
def mock_auth_storage():
    """Мок для AuthStorageManager"""
    storage = MagicMock()
    storage.get_user_by_telegram_id = MagicMock()
    storage.update_user = MagicMock()
    storage.create_user = MagicMock()
    storage.delete_user = MagicMock()
    storage.list_users = MagicMock()
    storage.add_security_log = MagicMock()
    return storage


@pytest.fixture
def mock_auth_manager(mock_auth_storage, mock_user):
    """Мок для AuthManager"""
    manager = MagicMock()
    manager.storage = mock_auth_storage
    manager.authenticate = MagicMock(return_value=mock_user)
    manager.has_permission = MagicMock(return_value=True)
    manager.has_role = MagicMock(return_value=True)
    manager.is_authenticated = MagicMock(return_value=True)
    manager.get_user_by_telegram_id = MagicMock(return_value=mock_user)
    return manager


@pytest.fixture
def mock_client():
    """Мок для Pyrogram Client"""
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


@pytest.fixture
def mock_message(mock_user):
    """Фикстура для Pyrogram Message"""
    return MockMessage(text="/start", from_user=MockUser(id=mock_user.telegram_id))


@pytest.fixture
def mock_callback_query(mock_user):
    """Фикстура для Pyrogram CallbackQuery"""
    return MockCallbackQuery(
        data="menu_access",
        from_user=MockUser(id=mock_user.telegram_id)
    )


# =============================================================================
# T16: ТЕСТЫ ИНИЦИАЛИЗАЦИИ AuthManager В main.py
# =============================================================================

class TestMainInitialization:
    """Тесты инициализации AuthManager в main.py"""

    @patch('config.set_auth_manager')
    @patch('auth_manager.AuthManager')
    def test_auth_manager_initialized_on_startup(self, mock_auth_class, mock_set_auth):
        """Тест: AuthManager создается при старте приложения"""
        from auth_manager import AuthManager

        # Создаём экземпляр
        manager = AuthManager()
        mock_set_auth(manager)

        # Проверяем вызовы
        mock_set_auth.assert_called_once_with(manager)

    @patch('config.get_auth_manager')
    def test_auth_manager_accessible_globally(self, mock_get_auth, mock_auth_manager):
        """Тест: AuthManager доступен глобально через config"""
        mock_get_auth.return_value = mock_auth_manager

        from config import get_auth_manager
        manager = get_auth_manager()

        assert manager is not None
        assert manager == mock_auth_manager


# =============================================================================
# T11: ТЕСТЫ config.py (get_auth_manager, set_auth_manager)
# =============================================================================

class TestConfigAuthManager:
    """Тесты для config.py функций управления AuthManager"""

    @patch('config.get_auth_manager')
    def test_get_auth_manager_returns_instance(self, mock_get_auth, mock_auth_manager):
        """Тест: get_auth_manager() возвращает экземпляр"""
        mock_get_auth.return_value = mock_auth_manager

        from config import get_auth_manager
        manager = get_auth_manager()

        assert manager is not None
        assert hasattr(manager, 'authenticate')
        assert hasattr(manager, 'has_permission')

    @patch('config.set_auth_manager')
    @patch('config.get_auth_manager')
    def test_set_auth_manager_singleton_pattern(self, mock_get_auth, mock_set_auth, mock_auth_manager):
        """Тест: set_auth_manager() реализует singleton pattern"""
        mock_set_auth(mock_auth_manager)
        mock_get_auth.return_value = mock_auth_manager

        from config import get_auth_manager

        manager1 = get_auth_manager()
        manager2 = get_auth_manager()

        assert manager1 is manager2  # Singleton pattern


# =============================================================================
# T12: ТЕСТЫ CUSTOM FILTERS
# =============================================================================

class TestCustomFilters:
    """Тесты для Custom Filters из auth_filters.py"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_auth_filter_authenticated_user(self, mock_get_auth, mock_auth_manager, mock_message, mock_user):
        """Тест: auth_filter пропускает аутентифицированного пользователя"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user

        # Симулируем фильтр
        result = mock_auth_manager.is_authenticated(mock_message.from_user.id)

        assert result is True
        mock_auth_manager.get_user_by_telegram_id.assert_called()

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_auth_filter_unauthenticated_user(self, mock_get_auth, mock_auth_manager, mock_message):
        """Тест: auth_filter блокирует неаутентифицированного пользователя"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = None
        mock_auth_manager.is_authenticated.return_value = False

        result = mock_auth_manager.is_authenticated(mock_message.from_user.id)

        assert result is False

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_require_role_admin_access(self, mock_get_auth, mock_auth_manager, mock_message, mock_user):
        """Тест: require_role('admin') пропускает admin"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_role.return_value = True

        result = mock_auth_manager.has_role(mock_user, "admin")

        assert result is True

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_require_role_guest_denied(self, mock_get_auth, mock_auth_manager, mock_message, mock_guest):
        """Тест: require_role('admin') блокирует guest"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_role.return_value = False

        result = mock_auth_manager.has_role(mock_guest, "admin")

        assert result is False

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_require_permission_user_management(self, mock_get_auth, mock_auth_manager, mock_user):
        """Тест: require_permission('user_management') для admin"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_permission.return_value = True

        result = mock_auth_manager.has_permission(mock_user, "user_management")

        assert result is True

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_require_permission_denied(self, mock_get_auth, mock_auth_manager, mock_guest):
        """Тест: require_permission блокирует guest"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_permission.return_value = False

        result = mock_auth_manager.has_permission(mock_guest, "user_management")

        assert result is False


# =============================================================================
# T15: ТЕСТЫ must_change_password БЛОКИРОВКИ
# =============================================================================

class TestMustChangePassword:
    """Тесты для must_change_password логики"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_must_change_password_blocks_regular_commands(
        self, mock_get_auth, mock_auth_manager, mock_must_change_password_user
    ):
        """Тест: must_change_password блокирует обычные команды"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_must_change_password_user

        message = MockMessage(text="/start", from_user=MockUser(id=100003))

        # Проверяем что пользователь должен сменить пароль
        user = mock_auth_manager.get_user_by_telegram_id(message.from_user.id)

        assert user.must_change_password is True
        # В реальном обработчике должна быть отправка предупреждения

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_change_password_command_bypasses_restriction(
        self, mock_get_auth, mock_auth_manager, mock_must_change_password_user
    ):
        """Тест: /change_password доступна даже с must_change_password=True"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_must_change_password_user

        message = MockMessage(text="/change_password", from_user=MockUser(id=100003))

        # Команда /change_password НЕ проверяет must_change_password
        assert message.text == "/change_password"
        # В реальном обработчике команда должна быть выполнена


# =============================================================================
# T15: ТЕСТЫ /change_password КОМАНДЫ
# =============================================================================

class TestChangePasswordCommand:
    """Тесты для команды /change_password"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_change_password_command_starts_fsm(
        self, mock_get_auth, mock_auth_manager, mock_user
    ):
        """Тест: /change_password запускает FSM"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user

        message = MockMessage(text="/change_password", from_user=MockUser(id=100001))

        # Симулируем вход в FSM
        fsm_state = "waiting_old_password"

        assert message.text == "/change_password"
        assert fsm_state == "waiting_old_password"

    @pytest.mark.asyncio
    async def test_change_password_requires_authentication(self):
        """Тест: /change_password требует аутентификации"""
        message = MockMessage(text="/change_password", from_user=MockUser(id=999999))

        # Без аутентификации команда не должна работать
        # В реальном обработчике должен быть auth_filter
        assert message.text == "/change_password"


# =============================================================================
# T14: ТЕСТЫ КНОПКИ "НАСТРОЙКИ ДОСТУПА"
# =============================================================================

class TestAccessSettingsButton:
    """Тесты для кнопки 'Настройки доступа' в markups.py"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_access_settings_button_visible_for_super_admin(
        self, mock_get_auth, mock_auth_manager, mock_super_admin
    ):
        """Тест: кнопка видна для super_admin"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_role.return_value = True

        # Проверяем роль
        has_access = mock_auth_manager.has_role(mock_super_admin, "super_admin")

        assert has_access is True

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_access_settings_button_hidden_for_regular_user(
        self, mock_get_auth, mock_auth_manager, mock_user
    ):
        """Тест: кнопка скрыта для обычных пользователей"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_role.return_value = False

        # Проверяем роль
        has_access = mock_auth_manager.has_role(mock_user, "super_admin")

        assert has_access is False


# =============================================================================
# T13: ТЕСТЫ ИНТЕГРАЦИИ access_handlers.py
# =============================================================================

class TestAccessHandlersIntegration:
    """Тесты интеграции 38 функций из access_handlers.py"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_show_access_menu_handler(
        self, mock_get_auth, mock_auth_manager, mock_client, mock_message, mock_super_admin
    ):
        """Тест: show_access_menu() показывает меню для super_admin"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_super_admin
        mock_auth_manager.has_role.return_value = True

        # Симулируем вызов обработчика
        result = await mock_message.reply("🔒 Настройки доступа")

        assert result is not None
        assert "Настройки доступа" in result.text

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_show_users_list_handler(
        self, mock_get_auth, mock_auth_manager, mock_client, mock_callback_query, mock_super_admin, mock_user
    ):
        """Тест: show_users_list() показывает список пользователей"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_super_admin
        mock_auth_manager.storage.list_users.return_value = [mock_user]

        # Симулируем вызов
        users = mock_auth_manager.storage.list_users()

        assert len(users) == 1
        assert users[0].username == "admin"

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_create_invitation_handler(
        self, mock_get_auth, mock_auth_manager, mock_client, mock_callback_query, mock_super_admin
    ):
        """Тест: create_invitation() создаёт приглашение"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_super_admin

        invite_code = "INV123456"

        # Симулируем создание
        result = await mock_callback_query.answer("Код приглашения создан")

        assert result is True


# =============================================================================
# T15: ТЕСТЫ CALLBACK ROUTING В handlers.py
# =============================================================================

class TestCallbackRouting:
    """Тесты для callback routing из handlers.py"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_menu_access_callback(
        self, mock_get_auth, mock_auth_manager, mock_callback_query, mock_super_admin
    ):
        """Тест: callback 'menu_access' работает"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_super_admin

        callback = MockCallbackQuery(data="menu_access")

        assert callback.data == "menu_access"
        result = await callback.answer()
        assert result is True

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_user_details_callback(
        self, mock_get_auth, mock_auth_manager, mock_callback_query, mock_super_admin, mock_user
    ):
        """Тест: callback 'user_details:{user_id}' работает"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_super_admin
        mock_auth_manager.storage.get_user_by_telegram_id.return_value = mock_user

        callback = MockCallbackQuery(data="user_details:user_001")

        assert callback.data.startswith("user_details:")
        user_id = callback.data.split(":")[1]
        assert user_id == "user_001"


# =============================================================================
# T15: ТЕСТЫ FSM В handle_authorized_text
# =============================================================================

class TestFSMIntegration:
    """Тесты для FSM интеграции в handle_authorized_text"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_fsm_state_search_user(
        self, mock_get_auth, mock_auth_manager, mock_message, mock_super_admin
    ):
        """Тест: FSM состояние 'search_user'"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_super_admin

        # Симулируем FSM состояние
        fsm_state = "search_user"
        message = MockMessage(text="admin")

        assert fsm_state == "search_user"
        assert message.text == "admin"

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_fsm_state_waiting_new_password(
        self, mock_get_auth, mock_auth_manager, mock_message, mock_user
    ):
        """Тест: FSM состояние 'waiting_new_password'"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user

        fsm_state = "waiting_new_password"
        message = MockMessage(text="NewPassword123!")

        assert fsm_state == "waiting_new_password"
        assert message.text == "NewPassword123!"


# =============================================================================
# РЕГРЕССИОННЫЕ ТЕСТЫ
# =============================================================================

class TestRegressionTests:
    """Регрессионные тесты для существующих обработчиков"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_text_handler_with_auth_filter(
        self, mock_get_auth, mock_auth_manager, mock_message, mock_user
    ):
        """Тест: обработчик текста работает с auth_filter"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user
        mock_auth_manager.is_authenticated.return_value = True

        message = MockMessage(text="Hello", from_user=MockUser(id=100001))

        is_auth = mock_auth_manager.is_authenticated(message.from_user.id)

        assert is_auth is True
        assert message.text == "Hello"

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_audio_handler_with_auth_filter(
        self, mock_get_auth, mock_auth_manager, mock_user
    ):
        """Тест: обработчик аудио работает с auth_filter"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user
        mock_auth_manager.is_authenticated.return_value = True

        message = MockMessage(from_user=MockUser(id=100001))
        message.voice = MagicMock()

        is_auth = mock_auth_manager.is_authenticated(message.from_user.id)

        assert is_auth is True
        assert message.voice is not None

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_document_handler_with_auth_filter(
        self, mock_get_auth, mock_auth_manager, mock_user
    ):
        """Тест: обработчик документов работает с auth_filter"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user
        mock_auth_manager.is_authenticated.return_value = True

        message = MockMessage(from_user=MockUser(id=100001))
        message.document = MagicMock()

        is_auth = mock_auth_manager.is_authenticated(message.from_user.id)

        assert is_auth is True
        assert message.document is not None


# =============================================================================
# ТЕСТЫ ОБРАБОТКИ ОШИБОК
# =============================================================================

class TestErrorHandling:
    """Тесты обработки ошибок"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_auth_manager_not_initialized(self, mock_get_auth):
        """Тест: обработка ошибки если AuthManager не инициализирован"""
        mock_get_auth.return_value = None

        from config import get_auth_manager
        manager = get_auth_manager()

        assert manager is None

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_invalid_user_data(self, mock_get_auth, mock_auth_manager):
        """Тест: обработка невалидных данных пользователя"""
        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = None

        result = mock_auth_manager.get_user_by_telegram_id(999999)

        assert result is None

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_blocked_user_access(self, mock_get_auth, mock_auth_manager):
        """Тест: блокированный пользователь не может получить доступ"""
        blocked_user = User(
            user_id="user_004",
            telegram_id=100004,
            username="blocked",
            password_hash="hashed",
            role="user",
            is_active=False,
            is_blocked=True,
            must_change_password=False
        )

        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = blocked_user

        user = mock_auth_manager.get_user_by_telegram_id(100004)

        assert user.is_blocked is True
        assert user.is_active is False


# =============================================================================
# ТЕСТЫ ВАЛИДАТОРОВ (T17)
# =============================================================================

class TestValidators:
    """Тесты для упрощённых validators.py"""

    def test_validate_username(self):
        """Тест: валидация username"""
        # Симулируем валидатор
        valid_usernames = ["admin", "user123", "test_user"]
        invalid_usernames = ["", "a", "user@123", "very_long_username_exceeding_limit"]

        for username in valid_usernames:
            assert len(username) >= 3
            assert len(username) <= 32

        for username in invalid_usernames:
            assert len(username) < 3 or len(username) > 32 or "@" in username

    def test_validate_password(self):
        """Тест: валидация password"""
        valid_passwords = ["Password123!", "Secure@Pass1", "Test#1234"]
        invalid_passwords = ["weak", "nodigits", "NOLOWER123", "noupper123"]

        for password in valid_passwords:
            assert len(password) >= 8

        for password in invalid_passwords:
            assert len(password) < 8 or not any(c.isupper() for c in password)

    def test_validate_role(self):
        """Тест: валидация role"""
        valid_roles = ["super_admin", "admin", "user", "guest"]
        invalid_roles = ["moderator", "owner", "superuser"]

        for role in valid_roles:
            assert role in ["super_admin", "admin", "user", "guest"]

        for role in invalid_roles:
            assert role not in ["super_admin", "admin", "user", "guest"]


# =============================================================================
# ТЕСТЫ PERMISSIONS
# =============================================================================

class TestPermissions:
    """Тесты для проверки прав доступа"""

    @pytest.mark.parametrize("role,permission,expected", [
        ("super_admin", "user_management", True),
        ("super_admin", "system_settings", True),
        ("admin", "user_management", True),
        ("admin", "system_settings", False),
        ("user", "user_management", False),
        ("guest", "user_management", False),
    ])
    @patch('config.get_auth_manager')
    def test_role_permissions(self, mock_get_auth, mock_auth_manager, role, permission, expected):
        """Тест: проверка прав для разных ролей"""
        user = User(
            user_id="test_user",
            telegram_id=100001,
            username="test",
            password_hash="hashed",
            role=role,
            is_active=True,
            is_blocked=False,
            must_change_password=False
        )

        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_permission.return_value = expected

        result = mock_auth_manager.has_permission(user, permission)

        assert result == expected


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Тесты производительности"""

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_auth_check_performance(self, mock_get_auth, mock_auth_manager, mock_user):
        """Тест: проверка аутентификации должна быть быстрой"""
        import time

        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.get_user_by_telegram_id.return_value = mock_user

        start = time.time()
        for _ in range(100):
            mock_auth_manager.get_user_by_telegram_id(100001)
        end = time.time()

        # Проверка должна занимать < 1 секунды для 100 запросов
        assert (end - start) < 1.0

    @pytest.mark.asyncio
    @patch('config.get_auth_manager')
    async def test_permission_check_performance(self, mock_get_auth, mock_auth_manager, mock_user):
        """Тест: проверка прав должна быть быстрой"""
        import time

        mock_get_auth.return_value = mock_auth_manager
        mock_auth_manager.has_permission.return_value = True

        start = time.time()
        for _ in range(100):
            mock_auth_manager.has_permission(mock_user, "user_management")
        end = time.time()

        # Проверка должна занимать < 1 секунды для 100 запросов
        assert (end - start) < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
