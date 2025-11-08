"""
Тесты для проверки RBAC (Role-Based Access Control) в access_handlers.py.

Проверяет что:
- super_admin имеет доступ ко всем функциям
- admin имеет доступ ТОЛЬКО к функциям приглашений
- admin НЕ имеет доступа к настройкам доступа, управлению пользователями и безопасности
- user НЕ имеет доступа ни к чему в access_handlers

Автор: Claude Code
Дата: 2025-11-08
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock


# Тесты для функции check_role_access

@pytest.mark.asyncio
async def test_check_role_access_super_admin_allowed():
    """Суперадмин должен пройти проверку для роли super_admin"""
    from src.access_handlers import check_role_access

    chat_id = 123456
    app = AsyncMock()

    # Мок пользователя с ролью super_admin
    mock_user = Mock()
    mock_user.role = "super_admin"
    mock_user.username = "superadmin"

    with patch('src.access_handlers.get_auth_manager') as mock_auth:
        mock_auth.return_value.storage.get_user_by_telegram_id.return_value = mock_user

        has_access, user = await check_role_access(chat_id, ["super_admin"], app)

        assert has_access == True
        assert user == mock_user
        assert user.role == "super_admin"


@pytest.mark.asyncio
async def test_check_role_access_admin_denied_for_super_admin_only():
    """Админ НЕ должен пройти проверку для роли super_admin"""
    from src.access_handlers import check_role_access

    chat_id = 123456
    app = AsyncMock()

    # Мок пользователя с ролью admin
    mock_user = Mock()
    mock_user.role = "admin"
    mock_user.username = "admin"

    with patch('src.access_handlers.get_auth_manager') as mock_auth, \
         patch('src.access_handlers.track_and_send', new_callable=AsyncMock) as mock_send:
        mock_auth.return_value.storage.get_user_by_telegram_id.return_value = mock_user

        has_access, user = await check_role_access(chat_id, ["super_admin"], app)

        assert has_access == False
        assert user is None
        # Проверяем что отправлено сообщение об ошибке
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert "Доступ запрещен" in call_kwargs['text']


@pytest.mark.asyncio
async def test_check_role_access_admin_allowed_for_admin_role():
    """Админ должен пройти проверку для ролей admin ИЛИ super_admin"""
    from src.access_handlers import check_role_access

    chat_id = 123456
    app = AsyncMock()

    # Мок пользователя с ролью admin
    mock_user = Mock()
    mock_user.role = "admin"
    mock_user.username = "admin"

    with patch('src.access_handlers.get_auth_manager') as mock_auth:
        mock_auth.return_value.storage.get_user_by_telegram_id.return_value = mock_user

        has_access, user = await check_role_access(chat_id, ["admin", "super_admin"], app)

        assert has_access == True
        assert user == mock_user
        assert user.role == "admin"


@pytest.mark.asyncio
async def test_check_role_access_user_denied():
    """Обычный пользователь НЕ должен пройти проверку ни для какой роли"""
    from src.access_handlers import check_role_access

    chat_id = 123456
    app = AsyncMock()

    # Мок пользователя с ролью user
    mock_user = Mock()
    mock_user.role = "user"
    mock_user.username = "regular_user"

    with patch('src.access_handlers.get_auth_manager') as mock_auth, \
         patch('src.access_handlers.track_and_send', new_callable=AsyncMock) as mock_send:
        mock_auth.return_value.storage.get_user_by_telegram_id.return_value = mock_user

        has_access, user = await check_role_access(chat_id, ["admin", "super_admin"], app)

        assert has_access == False
        assert user is None
        mock_send.assert_called_once()


# Тесты для функций ТОЛЬКО super_admin

@pytest.mark.asyncio
async def test_handle_access_menu_requires_super_admin():
    """handle_access_menu должна требовать роль super_admin"""
    from src.access_handlers import handle_access_menu

    chat_id = 123456
    app = AsyncMock()

    # Мок пользователя с ролью admin (НЕ super_admin)
    mock_user = Mock()
    mock_user.role = "admin"

    with patch('src.access_handlers.check_role_access', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = (False, None)  # Отказано в доступе

        result = await handle_access_menu(chat_id, app)

        # Функция должна вызвать check_role_access с ["super_admin"]
        mock_check.assert_called_once_with(chat_id, ["super_admin"], app)
        # Функция должна вернуть None (ранний выход)
        assert result is None


@pytest.mark.asyncio
async def test_handle_users_menu_requires_super_admin():
    """handle_users_menu должна требовать роль super_admin"""
    from src.access_handlers import handle_users_menu

    chat_id = 123456
    app = AsyncMock()

    with patch('src.access_handlers.check_role_access', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = (False, None)

        result = await handle_users_menu(chat_id, app)

        mock_check.assert_called_once_with(chat_id, ["super_admin"], app)
        assert result is None


@pytest.mark.asyncio
async def test_handle_audit_log_requires_super_admin():
    """handle_audit_log должна требовать роль super_admin (КРИТИЧНО)"""
    from src.access_handlers import handle_audit_log

    chat_id = 123456
    app = AsyncMock()

    with patch('src.access_handlers.check_role_access', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = (False, None)

        result = await handle_audit_log(chat_id, 1, app)

        mock_check.assert_called_once_with(chat_id, ["super_admin"], app)
        assert result is None


# Тесты для функций admin ИЛИ super_admin

@pytest.mark.asyncio
async def test_handle_invitations_menu_allows_admin():
    """handle_invitations_menu должна разрешать доступ admin"""
    from src.access_handlers import handle_invitations_menu

    chat_id = 123456
    app = AsyncMock()

    # Мок пользователя с ролью admin
    mock_user = Mock()
    mock_user.role = "admin"
    mock_user.username = "admin"

    with patch('src.access_handlers.check_role_access', new_callable=AsyncMock) as mock_check, \
         patch('src.access_handlers.track_and_send', new_callable=AsyncMock):
        mock_check.return_value = (True, mock_user)  # Доступ разрешен

        # Функция должна НЕ вернуть None (т.е. продолжить выполнение)
        await handle_invitations_menu(chat_id, app)

        # Проверяем что check_role_access вызван с admin И super_admin
        mock_check.assert_called_once()
        call_args = mock_check.call_args[0]
        assert call_args[0] == chat_id
        assert "admin" in call_args[1]
        assert "super_admin" in call_args[1]


@pytest.mark.asyncio
async def test_handle_invitations_menu_denies_regular_user():
    """handle_invitations_menu должна отказывать обычному пользователю"""
    from src.access_handlers import handle_invitations_menu

    chat_id = 123456
    app = AsyncMock()

    with patch('src.access_handlers.check_role_access', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = (False, None)  # Отказано

        result = await handle_invitations_menu(chat_id, app)

        mock_check.assert_called_once()
        assert result is None


# Тест проверки всех критических функций

@pytest.mark.asyncio
async def test_all_critical_functions_have_role_checks():
    """
    Проверка что все критические функции имеют проверку роли.

    Этот тест читает исходный код и проверяет наличие вызова check_role_access
    в критических функциях.
    """
    import re

    # Критические функции которые ОБЯЗАТЕЛЬНО должны иметь проверку
    critical_functions = [
        "handle_access_menu",
        "handle_users_menu",
        "handle_audit_log",
        "handle_set_cleanup_hours",
        "handle_cleanup_per_user",
        "handle_view_cleanup_schedule",
    ]

    with open("C:/Users/l0934/Projects/VoxPersona/src/access_handlers.py", "r", encoding="utf-8") as f:
        content = f.read()

    for func_name in critical_functions:
        # Ищем функцию в коде
        pattern = rf"async def {func_name}\([^)]+\):.*?(?=async def|\Z)"
        match = re.search(pattern, content, re.DOTALL)

        assert match is not None, f"Функция {func_name} не найдена в файле"

        func_body = match.group(0)

        # Проверяем что есть вызов check_role_access
        assert "check_role_access" in func_body, \
            f"Функция {func_name} не имеет проверки роли через check_role_access!"

        # Проверяем что проверка происходит в начале функции (до основной логики)
        first_check_pos = func_body.find("check_role_access")
        first_logic_pos = func_body.find("auth = get_auth_manager()")

        if first_logic_pos > 0:  # Если есть основная логика
            assert first_check_pos < first_logic_pos, \
                f"В функции {func_name} проверка роли должна быть ДО основной логики!"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
