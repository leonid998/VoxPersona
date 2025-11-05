"""
Тесты для K-04: UI доступ для admin к управлению приглашениями

Проверяет:
1. Кнопка "Управление приглашениями" видна для admin в system_menu_markup
2. Кнопка НЕ видна для user/guest
3. Улучшенная клавиатура после создания invite
"""

import pytest
import sys
from pathlib import Path

# Добавить src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markups import system_menu_markup
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class TestSystemMenuMarkup:
    """Тесты для system_menu_markup - проверка видимости кнопок по ролям."""

    def test_admin_sees_invitations_button(self):
        """K-04: Admin должен видеть кнопку 'Управление приглашениями'."""
        markup = system_menu_markup(user_role="admin")

        assert isinstance(markup, InlineKeyboardMarkup), "Должен вернуть InlineKeyboardMarkup"

        # Получить все кнопки
        all_buttons = []
        for row in markup.inline_keyboard:
            for button in row:
                all_buttons.append(button)

        # Проверить что есть кнопка с callback "access_invitations_menu"
        invitation_buttons = [
            btn for btn in all_buttons
            if btn.callback_data == "access_invitations_menu"
        ]

        assert len(invitation_buttons) == 1, (
            "Admin должен видеть РОВНО ОДНУ кнопку 'Управление приглашениями'"
        )

        # Проверить текст кнопки
        button = invitation_buttons[0]
        assert "приглашениями" in button.text.lower() or "приглашения" in button.text.lower(), (
            f"Текст кнопки должен содержать 'приглашения', получено: {button.text}"
        )

    def test_user_does_not_see_invitations_button(self):
        """K-04: User НЕ должен видеть кнопку 'Управление приглашениями'."""
        markup = system_menu_markup(user_role="user")

        assert isinstance(markup, InlineKeyboardMarkup)

        # Получить все callback_data
        all_callbacks = []
        for row in markup.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)

        assert "access_invitations_menu" not in all_callbacks, (
            "User НЕ должен видеть кнопку 'Управление приглашениями'"
        )

    def test_guest_does_not_see_invitations_button(self):
        """K-04: Guest НЕ должен видеть кнопку 'Управление приглашениями'."""
        markup = system_menu_markup(user_role="guest")

        assert isinstance(markup, InlineKeyboardMarkup)

        all_callbacks = []
        for row in markup.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)

        assert "access_invitations_menu" not in all_callbacks, (
            "Guest НЕ должен видеть кнопку 'Управление приглашениями'"
        )

    def test_super_admin_sees_access_settings(self):
        """Super_admin должен видеть 'Настройки доступа' (не затронуто K-04)."""
        markup = system_menu_markup(user_role="super_admin")

        assert isinstance(markup, InlineKeyboardMarkup)

        all_callbacks = []
        for row in markup.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)

        assert "menu_access" in all_callbacks, (
            "Super_admin должен видеть кнопку 'Настройки доступа'"
        )

    def test_admin_does_not_see_access_settings(self):
        """K-04: Admin НЕ должен видеть 'Настройки доступа' (только для super_admin)."""
        markup = system_menu_markup(user_role="admin")

        assert isinstance(markup, InlineKeyboardMarkup)

        all_callbacks = []
        for row in markup.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)

        assert "menu_access" not in all_callbacks, (
            "Admin НЕ должен видеть 'Настройки доступа' (только для super_admin)"
        )

    def test_all_roles_see_storage_button(self):
        """Все роли должны видеть кнопку 'Хранилище'."""
        roles = ["user", "admin", "super_admin", "guest"]

        for role in roles:
            markup = system_menu_markup(user_role=role)

            all_callbacks = []
            for row in markup.inline_keyboard:
                for button in row:
                    all_callbacks.append(button.callback_data)

            assert "menu_storage" in all_callbacks, (
                f"Роль '{role}' должна видеть кнопку 'Хранилище'"
            )

    def test_all_roles_see_back_button(self):
        """Все роли должны видеть кнопку 'Назад'."""
        roles = ["user", "admin", "super_admin", "guest"]

        for role in roles:
            markup = system_menu_markup(user_role=role)

            all_callbacks = []
            for row in markup.inline_keyboard:
                for button in row:
                    all_callbacks.append(button.callback_data)

            assert "menu_main" in all_callbacks, (
                f"Роль '{role}' должна видеть кнопку 'Назад'"
            )


class TestInviteCreationKeyboard:
    """Тесты для клавиатуры после создания приглашения."""

    def test_improved_keyboard_structure(self):
        """
        K-04: После создания invite должна быть улучшенная клавиатура
        с кнопками 'Создать еще', 'Список приглашений', 'Главное меню'.

        ПРИМЕЧАНИЕ: Этот тест проверяет структуру через код access_handlers.py
        """
        # Читаем код access_handlers.py для проверки улучшенной клавиатуры
        access_handlers_path = Path(__file__).parent.parent / "src" / "access_handlers.py"

        with open(access_handlers_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Проверяем что есть комментарий K-04
        assert "K-04: Улучшенная клавиатура после создания приглашения" in content, (
            "Должен быть комментарий K-04 в handle_confirm_create_invite"
        )

        # Проверяем наличие всех трёх кнопок
        assert 'callback_data="access_invitations_menu"' in content, (
            "Должна быть кнопка 'Создать еще' (callback: access_invitations_menu)"
        )

        assert 'callback_data="access_list_invites"' in content, (
            "Должна быть кнопка 'Список приглашений' (callback: access_list_invites)"
        )

        assert 'callback_data="menu_main"' in content, (
            "Должна быть кнопка 'Главное меню' (callback: menu_main)"
        )

    def test_no_old_access_back_markup(self):
        """
        K-04: Старый access_back_markup должен быть заменён на улучшенную клавиатуру.

        Проверяем что в handle_confirm_create_invite НЕТ старого кода:
        reply_markup=access_back_markup("access_invitations_menu")
        """
        access_handlers_path = Path(__file__).parent.parent / "src" / "access_handlers.py"

        with open(access_handlers_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Найти функцию handle_confirm_create_invite
        func_start = content.find("async def handle_confirm_create_invite")
        func_end = content.find("async def", func_start + 10)

        if func_end == -1:
            func_end = len(content)

        func_content = content[func_start:func_end]

        # Проверить что НЕТ старого кода
        assert 'access_back_markup("access_invitations_menu")' not in func_content, (
            "Старый access_back_markup должен быть заменён на улучшенную клавиатуру"
        )


class TestK04Integration:
    """Интеграционные тесты для K-04."""

    def test_callback_routing_exists(self):
        """
        K-04: Callback роутинг для 'access_invitations_menu' должен существовать.

        Проверяем handlers.py на наличие роутинга.
        """
        handlers_path = Path(__file__).parent.parent / "src" / "handlers.py"

        with open(handlers_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert 'elif data == "access_invitations_menu":' in content, (
            "Должен быть callback роутинг для 'access_invitations_menu' в handlers.py"
        )

        assert "await handle_invitations_menu(c_id, app)" in content, (
            "Callback должен вызывать handle_invitations_menu"
        )

    def test_handle_invitations_menu_exists(self):
        """
        K-04: Функция handle_invitations_menu должна существовать.
        """
        access_handlers_path = Path(__file__).parent.parent / "src" / "access_handlers.py"

        with open(access_handlers_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "async def handle_invitations_menu" in content, (
            "Функция handle_invitations_menu должна существовать в access_handlers.py"
        )


if __name__ == "__main__":
    # Запуск тестов с подробным выводом
    pytest.main([__file__, "-v", "-s", "--tb=short"])
