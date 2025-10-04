"""
Smoke-тесты после удаления компонента визуальной минимизации.

Проверяет что все основные функции работают без VisualContextManager:
1. Импорты всех модулей без ошибок
2. MenuManager работает корректно
3. send_menu работает без context параметра
4. ConversationHandlers работают без минимизации
5. utils.py работает без трекинга сообщений
"""

import pytest
import sys
import importlib


class TestImports:
    """Проверка что все модули импортируются без ошибок."""

    def test_import_menu_manager(self):
        """MenuManager импортируется без VisualContextManager."""
        from menu_manager import MenuManager, send_menu, clear_menus
        assert MenuManager is not None
        assert send_menu is not None
        assert clear_menus is not None

    def test_import_conversation_handlers(self):
        """ConversationHandlers импортируется без VisualContextManager."""
        from conversation_handlers import (
            ensure_active_conversation,
            handle_new_chat,
            handle_switch_chat_confirm,
            handle_rename_chat_input,
            handle_delete_chat_confirm
        )
        assert ensure_active_conversation is not None
        assert handle_new_chat is not None
        assert handle_switch_chat_confirm is not None
        assert handle_rename_chat_input is not None
        assert handle_delete_chat_confirm is not None

    def test_import_utils(self):
        """Utils импортируется без VisualContextManager."""
        from utils import smart_send_text_unified
        assert smart_send_text_unified is not None

    def test_import_handlers(self):
        """Handlers импортируется без VisualContextManager."""
        # Пропускаем этот тест если MinIO недоступен
        pytest.skip("handlers.py требует подключение к MinIO")

    def test_import_menus(self):
        """Menus импортируется без send_menu_and_remove_old."""
        from menus import send_main_menu, show_confirmation_menu, show_edit_menu
        assert send_main_menu is not None
        assert show_confirmation_menu is not None
        assert show_edit_menu is not None

    def test_import_run_analysis(self):
        """RunAnalysis импортируется без send_menu_and_remove_old."""
        import run_analysis
        assert run_analysis is not None

    def test_visual_context_manager_deleted(self):
        """Проверка что visual_context_manager.py удален."""
        with pytest.raises(ModuleNotFoundError):
            import visual_context_manager


class TestNoVisualContextManagerReferences:
    """Проверка что нет ссылок на VisualContextManager в коде."""

    def test_menu_manager_no_visual_refs(self):
        """menu_manager.py не содержит ссылок на VisualContextManager."""
        import inspect
        from menu_manager import MenuManager, send_menu

        # Проверяем что параметр context отсутствует
        sig = inspect.signature(send_menu)
        assert 'context' not in sig.parameters

        # Проверяем сигнатуру MenuManager.send_menu_with_cleanup
        sig2 = inspect.signature(MenuManager.send_menu_with_cleanup)
        assert 'context' not in sig2.parameters

    def test_utils_no_visual_refs(self):
        """utils.py не содержит импортов VisualContextManager."""
        import utils

        # Проверяем что VisualContextManager не импортирован
        assert not hasattr(utils, 'VisualContextManager')

    def test_conversation_handlers_no_visual_refs(self):
        """conversation_handlers.py не содержит импортов VisualContextManager."""
        import conversation_handlers

        # Проверяем что VisualContextManager не импортирован
        assert not hasattr(conversation_handlers, 'VisualContextManager')

    def test_handlers_no_visual_refs(self):
        """handlers.py не содержит импортов VisualContextManager."""
        # Пропускаем этот тест если MinIO недоступен
        pytest.skip("handlers.py требует подключение к MinIO")


class TestFunctionSignatures:
    """Проверка что сигнатуры функций обновлены корректно."""

    def test_send_menu_signature(self):
        """send_menu имеет правильную сигнатуру без context."""
        import inspect
        from menu_manager import send_menu

        sig = inspect.signature(send_menu)
        params = list(sig.parameters.keys())

        assert params == ['chat_id', 'app', 'text', 'reply_markup']
        assert 'context' not in params

    def test_menu_manager_send_menu_with_cleanup_signature(self):
        """MenuManager.send_menu_with_cleanup имеет правильную сигнатуру без context."""
        import inspect
        from menu_manager import MenuManager

        sig = inspect.signature(MenuManager.send_menu_with_cleanup)
        params = list(sig.parameters.keys())

        # Для classmethod первый параметр 'cls' не включается в signature
        assert params == ['chat_id', 'app', 'text', 'reply_markup']
        assert 'context' not in params


class TestNoArtifacts:
    """Проверка что нет артефактов old/new в названиях функций."""

    def test_no_old_new_in_function_names(self):
        """Проверка что send_menu_and_remove_old переименовано."""
        from menu_manager import send_menu

        # Проверяем что функция называется send_menu а не send_menu_and_remove_old
        assert send_menu.__name__ == 'send_menu'

        # Проверяем что send_menu_and_remove_old не существует
        import menu_manager
        assert not hasattr(menu_manager, 'send_menu_and_remove_old')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
