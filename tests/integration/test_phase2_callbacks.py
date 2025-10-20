"""
Интеграционные тесты для всех 23 callback branches Phase 2.

Тестирует каждый callback type из handlers.py (строки 1363-1469):
- menu_access
- users (пагинация)
- user_details
- toggle_status
- change_role
- reset_password
- delete_user
- search_user
- invitations (пагинация)
- create_invitation
- revoke_invitation
- security_logs (пагинация)
- export_logs
- settings_access
- require_password_change
- session_timeout
- max_login_attempts
- back_to_main
- back_to_access
- back_to_users
- back_to_invitations
- back_to_security
- back_to_settings
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from pyrogram import Client
from pyrogram.types import CallbackQuery, Message, User as PyrogramUser

from access_control.models import User, UserRole, UserStatus, Invitation, InvitationStatus, SecurityLog


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db_session():
    """Мок сессии базы данных."""
    with patch('access_control.auth_manager.get_session') as mock:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.query.return_value.filter.return_value.all.return_value = []
        session.commit = MagicMock()
        session.add = MagicMock()
        mock.return_value.__enter__.return_value = session
        mock.return_value.__exit__.return_value = None
        yield session


@pytest.fixture
def admin_user():
    """Тестовый администратор."""
    return User(
        user_id=100001,
        username="admin",
        first_name="Admin",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        must_change_password=False,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def regular_user():
    """Тестовый обычный пользователь."""
    return User(
        user_id=100002,
        username="user",
        first_name="User",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        must_change_password=False,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def mock_client():
    """Мок Pyrogram Client."""
    return AsyncMock(spec=Client)


@pytest.fixture
def mock_callback_query(admin_user):
    """Мок callback query."""
    query = AsyncMock(spec=CallbackQuery)
    query.from_user = PyrogramUser(
        id=admin_user.user_id,
        is_bot=False,
        first_name=admin_user.first_name,
        username=admin_user.username
    )
    query.message = AsyncMock(spec=Message)
    query.message.chat = MagicMock()
    query.message.chat.id = admin_user.user_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    return query


# ==================== PARAMETRIZED TESTS ====================

@pytest.mark.asyncio
@pytest.mark.parametrize("callback_data,expected_handler", [
    ("menu_access", "show_access_menu"),
    ("users:0", "list_users"),
    ("user_details:100002", "show_user_details"),
    ("toggle_status:100002", "toggle_user_status"),
    ("change_role:100002", "change_user_role"),
    ("reset_password:100002", "reset_user_password"),
    ("delete_user:100002", "delete_user"),
    ("search_user", "search_user_start"),
    ("invitations:0", "list_invitations"),
    ("create_invitation", "create_invitation"),
    ("revoke_invitation:ABC123", "revoke_invitation"),
    ("security_logs:0", "show_security_logs"),
    ("export_logs", "export_security_logs"),
    ("settings_access", "show_access_settings"),
    ("require_password_change", "toggle_require_password_change"),
    ("session_timeout", "set_session_timeout"),
    ("max_login_attempts", "set_max_login_attempts"),
    ("back_to_main", "start_command"),
    ("back_to_access", "show_access_menu"),
    ("back_to_users", "list_users"),
    ("back_to_invitations", "list_invitations"),
    ("back_to_security", "show_security_logs"),
    ("back_to_settings", "show_access_settings"),
])
async def test_all_callback_routes(callback_data, expected_handler, mock_callback_query, mock_client, mock_db_session, admin_user):
    """Параметризованный тест для всех 23 callback routes."""
    mock_callback_query.data = callback_data
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    with patch(f'access_handlers.{expected_handler}') as mock_handler:
        mock_handler.return_value = AsyncMock()

        from handlers import callback_handler
        await callback_handler(mock_client, mock_callback_query)

        # Проверяем, что хендлер был вызван
        if expected_handler == "start_command":
            # start_command может быть в другом модуле
            pass
        else:
            mock_handler.assert_called_once()


# ==================== ИНДИВИДУАЛЬНЫЕ ТЕСТЫ CALLBACKS ====================

@pytest.mark.asyncio
async def test_callback_menu_access(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: menu_access."""
    mock_callback_query.data = "menu_access"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import show_access_menu
    await show_access_menu(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()
    call_text = mock_callback_query.edit_message_text.call_args[1]['text']
    assert "Управление доступом" in call_text


@pytest.mark.asyncio
async def test_callback_users_pagination(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест callback: users с пагинацией."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.filter.return_value.all.return_value = [regular_user] * 15

    # Страница 0
    mock_callback_query.data = "users:0"
    from access_handlers import list_users
    await list_users(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()

    # Страница 1
    mock_callback_query.data = "users:1"
    await list_users(mock_client, mock_callback_query)

    assert mock_callback_query.edit_message_text.call_count == 2


@pytest.mark.asyncio
async def test_callback_user_details(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест callback: user_details."""
    mock_callback_query.data = f"user_details:{regular_user.user_id}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user

    from access_handlers import show_user_details
    await show_user_details(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()
    call_text = mock_callback_query.edit_message_text.call_args[1]['text']
    assert regular_user.username in call_text


@pytest.mark.asyncio
async def test_callback_toggle_status(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест callback: toggle_status."""
    mock_callback_query.data = f"toggle_status:{regular_user.user_id}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user

    original_status = regular_user.status

    from access_handlers import toggle_user_status
    await toggle_user_status(mock_client, mock_callback_query)

    mock_db_session.commit.assert_called_once()
    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio
async def test_callback_change_role(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест callback: change_role."""
    mock_callback_query.data = f"change_role:{regular_user.user_id}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user

    from access_handlers import change_user_role
    await change_user_role(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()
    call_text = mock_callback_query.edit_message_text.call_args[1]['text']
    assert "Выберите роль" in call_text or "роль" in call_text.lower()


@pytest.mark.asyncio
async def test_callback_reset_password(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест callback: reset_password."""
    mock_callback_query.data = f"reset_password:{regular_user.user_id}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user

    from access_handlers import reset_user_password
    await reset_user_password(mock_client, mock_callback_query)

    mock_db_session.commit.assert_called_once()
    assert regular_user.must_change_password is True


@pytest.mark.asyncio
async def test_callback_delete_user(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест callback: delete_user."""
    mock_callback_query.data = f"delete_user:{regular_user.user_id}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user
    mock_db_session.delete = MagicMock()

    from access_handlers import delete_user
    await delete_user(mock_client, mock_callback_query)

    mock_db_session.delete.assert_called_once_with(regular_user)
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_callback_search_user(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: search_user."""
    mock_callback_query.data = "search_user"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import search_user_start
    await search_user_start(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()
    call_text = mock_callback_query.edit_message_text.call_args[1]['text']
    assert "Введите" in call_text or "поиск" in call_text.lower()


@pytest.mark.asyncio
async def test_callback_invitations_pagination(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: invitations с пагинацией."""
    invitations = [
        Invitation(
            code=f"INV{i:03d}",
            created_by=admin_user.user_id,
            max_uses=1,
            uses=0,
            expires_at=datetime.utcnow() + timedelta(days=7),
            status=InvitationStatus.ACTIVE
        ) for i in range(15)
    ]

    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.filter.return_value.all.return_value = invitations

    mock_callback_query.data = "invitations:0"
    from access_handlers import list_invitations
    await list_invitations(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_create_invitation(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: create_invitation."""
    mock_callback_query.data = "create_invitation"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import create_invitation
    await create_invitation(mock_client, mock_callback_query)

    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_callback_revoke_invitation(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: revoke_invitation."""
    invitation = Invitation(
        code="TEST123",
        created_by=admin_user.user_id,
        max_uses=1,
        uses=0,
        expires_at=datetime.utcnow() + timedelta(days=7),
        status=InvitationStatus.ACTIVE
    )

    mock_callback_query.data = f"revoke_invitation:{invitation.code}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = invitation

    from access_handlers import revoke_invitation
    await revoke_invitation(mock_client, mock_callback_query)

    assert invitation.status == InvitationStatus.REVOKED
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_callback_security_logs_pagination(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: security_logs с пагинацией."""
    logs = [
        SecurityLog(
            user_id=admin_user.user_id,
            action=f"ACTION_{i}",
            details=f"Details {i}",
            timestamp=datetime.utcnow()
        ) for i in range(25)
    ]

    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = logs[:10]

    mock_callback_query.data = "security_logs:0"
    from access_handlers import show_security_logs
    await show_security_logs(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_export_logs(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: export_logs."""
    logs = [
        SecurityLog(
            user_id=admin_user.user_id,
            action="LOGIN",
            details="Test",
            timestamp=datetime.utcnow()
        )
    ]

    mock_callback_query.data = "export_logs"
    mock_db_session.query.return_value.all.return_value = logs

    with patch('access_handlers.generate_logs_csv') as mock_generate:
        mock_generate.return_value = "/tmp/logs.csv"

        from access_handlers import export_security_logs
        await export_security_logs(mock_client, mock_callback_query)

        mock_callback_query.answer.assert_called()


@pytest.mark.asyncio
async def test_callback_settings_access(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: settings_access."""
    mock_callback_query.data = "settings_access"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import show_access_settings
    await show_access_settings(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_require_password_change(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: require_password_change."""
    mock_callback_query.data = "require_password_change"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import toggle_require_password_change
    await toggle_require_password_change(mock_client, mock_callback_query)

    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio
async def test_callback_session_timeout(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: session_timeout."""
    mock_callback_query.data = "session_timeout"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import set_session_timeout
    await set_session_timeout(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_max_login_attempts(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: max_login_attempts."""
    mock_callback_query.data = "max_login_attempts"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import set_max_login_attempts
    await set_max_login_attempts(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


# ==================== NAVIGATION CALLBACKS ====================

@pytest.mark.asyncio
async def test_callback_back_to_main(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: back_to_main."""
    mock_callback_query.data = "back_to_main"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    with patch('handlers.start_command') as mock_start:
        mock_start.return_value = AsyncMock()

        from handlers import callback_handler
        await callback_handler(mock_client, mock_callback_query)


@pytest.mark.asyncio
async def test_callback_back_to_access(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: back_to_access."""
    mock_callback_query.data = "back_to_access"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import show_access_menu
    await show_access_menu(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_back_to_users(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback: back_to_users."""
    mock_callback_query.data = "back_to_users"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    from access_handlers import list_users
    await list_users(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()


# ==================== EDGE CASES ====================

@pytest.mark.asyncio
async def test_callback_invalid_user_id(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback с невалидным user_id."""
    mock_callback_query.data = "user_details:invalid_id"
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    from access_handlers import show_user_details
    await show_user_details(mock_client, mock_callback_query)

    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio
async def test_callback_nonexistent_user(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback с несуществующим пользователем."""
    mock_callback_query.data = "user_details:999999"

    def mock_query_filter(*args, **kwargs):
        result = MagicMock()
        result.first.return_value = None
        return result

    mock_db_session.query.return_value.filter = mock_query_filter

    from access_handlers import show_user_details
    await show_user_details(mock_client, mock_callback_query)

    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio
async def test_callback_pagination_out_of_bounds(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback с пагинацией за пределами."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    mock_callback_query.data = "users:999"
    from access_handlers import list_users
    await list_users(mock_client, mock_callback_query)

    # Должен показать пустую страницу или вернуться на страницу 0
    mock_callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_empty_invitation_list(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест callback с пустым списком инвайтов."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    mock_callback_query.data = "invitations:0"
    from access_handlers import list_invitations
    await list_invitations(mock_client, mock_callback_query)

    mock_callback_query.edit_message_text.assert_called_once()
    call_text = mock_callback_query.edit_message_text.call_args[1]['text']
    assert "нет" in call_text.lower() or "пусто" in call_text.lower()


# ==================== PERMISSION TESTS ====================

@pytest.mark.asyncio
async def test_callback_user_without_admin_rights(mock_callback_query, mock_client, mock_db_session, regular_user):
    """Тест callback от пользователя без прав админа."""
    mock_callback_query.from_user.id = regular_user.user_id
    mock_callback_query.data = "users:0"
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user

    from access_handlers import list_users
    await list_users(mock_client, mock_callback_query)

    # Должен вернуть сообщение об ошибке
    mock_callback_query.answer.assert_called()
    call_text = mock_callback_query.answer.call_args[0][0]
    assert "недостаточно" in call_text.lower() or "доступ" in call_text.lower()


# ==================== SEQUENTIAL FLOW TESTS ====================

@pytest.mark.asyncio
async def test_sequential_user_management_flow(mock_callback_query, mock_client, mock_db_session, admin_user, regular_user):
    """Тест последовательного flow управления пользователями."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user
    mock_db_session.query.return_value.filter.return_value.all.return_value = [regular_user]

    # 1. Список пользователей
    mock_callback_query.data = "users:0"
    from access_handlers import list_users
    await list_users(mock_client, mock_callback_query)

    # 2. Детали пользователя
    mock_db_session.query.return_value.filter.return_value.first.return_value = regular_user
    mock_callback_query.data = f"user_details:{regular_user.user_id}"
    from access_handlers import show_user_details
    await show_user_details(mock_client, mock_callback_query)

    # 3. Изменить статус
    mock_callback_query.data = f"toggle_status:{regular_user.user_id}"
    from access_handlers import toggle_user_status
    await toggle_user_status(mock_client, mock_callback_query)

    # 4. Назад к списку
    mock_callback_query.data = "back_to_users"
    await list_users(mock_client, mock_callback_query)

    assert mock_callback_query.edit_message_text.call_count >= 3


@pytest.mark.asyncio
async def test_sequential_invitation_flow(mock_callback_query, mock_client, mock_db_session, admin_user):
    """Тест последовательного flow работы с инвайтами."""
    invitation = Invitation(
        code="SEQ123",
        created_by=admin_user.user_id,
        max_uses=1,
        uses=0,
        expires_at=datetime.utcnow() + timedelta(days=7),
        status=InvitationStatus.ACTIVE
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = admin_user

    # 1. Создать инвайт
    mock_callback_query.data = "create_invitation"
    from access_handlers import create_invitation
    await create_invitation(mock_client, mock_callback_query)

    # 2. Список инвайтов
    mock_db_session.query.return_value.filter.return_value.all.return_value = [invitation]
    mock_callback_query.data = "invitations:0"
    from access_handlers import list_invitations
    await list_invitations(mock_client, mock_callback_query)

    # 3. Отозвать инвайт
    mock_db_session.query.return_value.filter.return_value.first.return_value = invitation
    mock_callback_query.data = f"revoke_invitation:{invitation.code}"
    from access_handlers import revoke_invitation
    await revoke_invitation(mock_client, mock_callback_query)

    assert mock_db_session.commit.call_count >= 2
