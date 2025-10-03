"""
Юнит-тесты для MenuManager и отрефакторенных функций обработчиков меню.

Проверяет:
1. MenuManager корректно удаляет старые меню и отправляет новые
2. Отрефакторенные функции работают правильно с MenuManager
3. Не возникает дублирования меню
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified, MessageIdInvalid

from menu_manager import MenuManager, send_menu_and_remove_old, clear_menus
from conversation_handlers import (
    handle_new_chat,
    handle_switch_chat_confirm,
    handle_rename_chat_input,
    handle_delete_chat_confirm
)


class TestMenuManager:
    """Тесты для MenuManager класса."""

    def setup_method(self):
        """Очистка состояния перед каждым тестом."""
        MenuManager._last_menu_ids.clear()

    def test_first_menu_no_old_menu_to_remove(self):
        """Первое меню - нет старого меню для удаления."""
        chat_id = 12345
        app = MagicMock(spec=Client)
        text = "Выберите действие:"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Тест", callback_data="test")]])

        # Симулируем отправку сообщения
        mock_message = MagicMock(spec=Message)
        mock_message.id = 100
        app.send_message.return_value = mock_message

        # Вызываем метод
        import asyncio
        result = asyncio.run(send_menu_and_remove_old(chat_id, app, text, markup))

        # Проверяем
        assert result.id == 100
        app.send_message.assert_called_once_with(
            chat_id=chat_id,
            text=text,
            reply_markup=markup
        )
        # edit_message_reply_markup НЕ должен вызываться (нет старого меню)
        app.edit_message_reply_markup.assert_not_called()

        # Проверяем, что ID сохранен
        assert MenuManager._last_menu_ids[chat_id] == 100

    def test_second_menu_removes_old_menu(self):
        """Второе меню - старое меню должно быть удалено."""
        chat_id = 12345
        app = MagicMock(spec=Client)
        text = "Новое меню"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новое", callback_data="new")]])

        # Устанавливаем старое меню
        MenuManager._last_menu_ids[chat_id] = 100

        # Симулируем отправку нового сообщения
        mock_message = MagicMock(spec=Message)
        mock_message.id = 200
        app.send_message.return_value = mock_message

        # Вызываем метод
        import asyncio
        asyncio.run(send_menu_and_remove_old(chat_id, app, text, markup))

        # Проверяем, что старое меню было обновлено (кнопки удалены)
        app.edit_message_reply_markup.assert_called_once_with(
            chat_id=chat_id,
            message_id=100,
            reply_markup=None
        )

        # Проверяем, что новое меню отправлено
        app.send_message.assert_called_once()

        # Проверяем, что новый ID сохранен
        assert MenuManager._last_menu_ids[chat_id] == 200

    def test_clear_menus_clears_history(self):
        """clear_menus() очищает историю меню."""
        chat_id = 12345
        MenuManager._last_menu_ids[chat_id] = 100

        clear_menus(chat_id)

        assert chat_id not in MenuManager._last_menu_ids

    def test_message_not_modified_error_handled(self):
        """MessageNotModified ошибка обрабатывается корректно."""
        chat_id = 12345
        app = MagicMock(spec=Client)

        # Старое меню уже без кнопок
        MenuManager._last_menu_ids[chat_id] = 100
        app.edit_message_reply_markup.side_effect = MessageNotModified()

        # Новое сообщение
        mock_message = MagicMock(spec=Message)
        mock_message.id = 200
        app.send_message.return_value = mock_message

        text = "Меню"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Кнопка", callback_data="btn")]])

        # Не должно вызвать исключение
        import asyncio
        asyncio.run(send_menu_and_remove_old(chat_id, app, text, markup))

        # Новое меню все равно отправлено
        app.send_message.assert_called_once()
        assert MenuManager._last_menu_ids[chat_id] == 200

    def test_message_id_invalid_error_handled(self):
        """MessageIdInvalid ошибка обрабатывается корректно."""
        chat_id = 12345
        app = MagicMock(spec=Client)

        # Старое меню было удалено
        MenuManager._last_menu_ids[chat_id] = 100
        app.edit_message_reply_markup.side_effect = MessageIdInvalid()

        # Новое сообщение
        mock_message = MagicMock(spec=Message)
        mock_message.id = 200
        app.send_message.return_value = mock_message

        text = "Меню"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("Кнопка", callback_data="btn")]])

        # Не должно вызвать исключение
        import asyncio
        asyncio.run(send_menu_and_remove_old(chat_id, app, text, markup))

        # Новое меню все равно отправлено
        app.send_message.assert_called_once()
        assert MenuManager._last_menu_ids[chat_id] == 200


class TestConversationHandlers:
    """Тесты для отрефакторенных функций conversation_handlers."""

    def setup_method(self):
        """Очистка состояния перед каждым тестом."""
        MenuManager._last_menu_ids.clear()

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.get_username_from_chat')
    @patch('conversation_handlers.send_menu_and_remove_old', new_callable=AsyncMock)
    @patch('conversation_handlers.clear_menus')
    def test_handle_new_chat(self, mock_clear_menus, mock_send_menu, mock_get_username, mock_manager):
        """handle_new_chat использует MenuManager корректно."""
        chat_id = 12345
        app = MagicMock(spec=Client)

        mock_get_username.return_value = "test_user"
        mock_manager.create_conversation.return_value = "new-uuid"

        import asyncio
        asyncio.run(handle_new_chat(chat_id, app))

        # Проверяем, что clear_menus вызван
        mock_clear_menus.assert_called_once_with(chat_id)

        # Проверяем, что send_menu_and_remove_old вызван с правильными параметрами
        mock_send_menu.assert_called_once()
        call_kwargs = mock_send_menu.call_args.kwargs
        assert call_kwargs['chat_id'] == chat_id
        assert call_kwargs['app'] == app
        assert "Новый чат создан" in call_kwargs['text']
        assert call_kwargs['reply_markup'] is not None

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.send_menu_and_remove_old', new_callable=AsyncMock)
    def test_handle_switch_chat_confirm(self, mock_send_menu, mock_manager):
        """handle_switch_chat_confirm объединяет сообщения и использует MenuManager."""
        chat_id = 12345
        conversation_id = "test-uuid"
        app = MagicMock(spec=Client)

        # Мокируем conversation
        mock_conversation = MagicMock()
        mock_conversation.metadata.title = "Тестовый чат"
        mock_manager.load_conversation.return_value = mock_conversation
        mock_manager.get_messages.return_value = []

        import asyncio
        asyncio.run(handle_switch_chat_confirm(chat_id, conversation_id, app))

        # Проверяем, что send_menu_and_remove_old вызван
        mock_send_menu.assert_called_once()
        call_kwargs = mock_send_menu.call_args.kwargs
        assert "Переключено на чат" in call_kwargs['text']
        assert "Выберите действие" in call_kwargs['text']

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.send_menu_and_remove_old', new_callable=AsyncMock)
    @patch('conversation_handlers.user_states', {})
    def test_handle_rename_chat_input(self, mock_send_menu, mock_manager):
        """handle_rename_chat_input объединяет результат и меню."""
        chat_id = 12345
        new_name = "Новое название"
        app = MagicMock(spec=Client)

        # Устанавливаем состояние
        from conversation_handlers import user_states
        user_states[chat_id] = {"conversation_id": "test-uuid"}

        # Мокируем conversation
        mock_conversation = MagicMock()
        mock_manager.load_conversation.return_value = mock_conversation

        import asyncio
        asyncio.run(handle_rename_chat_input(chat_id, new_name, app))

        # Проверяем, что send_menu_and_remove_old вызван
        mock_send_menu.assert_called_once()
        call_kwargs = mock_send_menu.call_args.kwargs
        assert "переименован" in call_kwargs['text']
        assert "Ваши чаты" in call_kwargs['text']

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.send_menu_and_remove_old', new_callable=AsyncMock)
    @patch('conversation_handlers.clear_menus')
    def test_handle_delete_chat_confirm_last_chat(self, mock_clear_menus, mock_send_menu, mock_manager):
        """handle_delete_chat_confirm очищает меню при создании нового чата."""
        chat_id = 12345
        conversation_id = "test-uuid"
        username = "test_user"
        app = MagicMock(spec=Client)

        # Мокируем что это последний чат
        mock_manager.list_conversations.return_value = []
        mock_manager.create_conversation.return_value = "new-uuid"

        import asyncio
        asyncio.run(handle_delete_chat_confirm(chat_id, conversation_id, username, app))

        # Проверяем, что clear_menus вызван
        mock_clear_menus.assert_called_once_with(chat_id)

        # Проверяем, что send_menu_and_remove_old вызван
        mock_send_menu.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
