"""
Юнит-тесты для новой функциональности chat_actions UI.

Тестируются:
- Новая структура кнопок чата (одна кнопка вместо трех)
- Меню действий с чатом (Перейти/Нет/Изменить/Удалить)
- Обработчик handle_chat_actions
- Callback routing для chat_actions||
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from conversations import ConversationMetadata, Conversation
from markups import create_chat_button_row, chat_actions_menu_markup


class TestChatActionsUI:
    """Тесты для новой UI логики с chat_actions меню."""

    @pytest.fixture
    def mock_app(self):
        """Mock объект Pyrogram Client."""
        app = MagicMock()
        app.send_message = MagicMock()
        return app

    def test_create_chat_button_row_single_button(self):
        """Проверка, что create_chat_button_row возвращает ОДНУ кнопку."""
        # Создаем тестовую метадату
        conv = ConversationMetadata(
            conversation_id="test-uuid",
            user_id=12345,
            username="test_user",
            title="Тестовый чат с длинным названием которое должно обрезаться",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=True,
            message_count=5,
            total_tokens=100,
            chat_number=1
        )

        # Получаем кнопку
        button_row = create_chat_button_row(conv, is_active=True, chat_number=1)

        # Проверяем, что это список из одного элемента
        assert isinstance(button_row, list)
        assert len(button_row) == 1

        # Проверяем callback_data
        button = button_row[0]
        assert button.callback_data == f"chat_actions||{conv.conversation_id}"
        assert "📝" in button.text  # Активный чат
        assert "1." in button.text  # Номер чата
        assert "Тестовый чат" in button.text

    def test_create_chat_button_row_inactive(self):
        """Проверка кнопки для неактивного чата."""
        conv = ConversationMetadata(
            conversation_id="test-uuid-2",
            user_id=12345,
            username="test_user",
            title="Неактивный чат",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=False,
            message_count=0,
            total_tokens=0,
            chat_number=2
        )

        button_row = create_chat_button_row(conv, is_active=False, chat_number=2)

        assert len(button_row) == 1
        button = button_row[0]
        assert "💬" in button.text  # Неактивный чат
        assert button.callback_data == f"chat_actions||{conv.conversation_id}"

    def test_create_chat_button_row_no_number(self):
        """Проверка кнопки без номера чата (старые чаты)."""
        conv = ConversationMetadata(
            conversation_id="test-uuid-old",
            user_id=12345,
            username="test_user",
            title="Старый чат",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=False,
            message_count=0,
            total_tokens=0,
            chat_number=0  # Старый чат без номера
        )

        button_row = create_chat_button_row(conv, is_active=False, chat_number=0)

        assert len(button_row) == 1
        button = button_row[0]
        # Проверяем, что номер не добавлен
        assert button.text.startswith("💬 Старый чат")
        assert not any(char.isdigit() for char in button.text.split("💬")[1].split("Старый")[0])

    def test_create_chat_button_row_truncates_long_names(self):
        """Проверка обрезки длинных названий чатов."""
        long_title = "Очень длинное название чата которое точно должно быть обрезано потому что не влезает в кнопку"
        conv = ConversationMetadata(
            conversation_id="test-uuid-long",
            user_id=12345,
            username="test_user",
            title=long_title,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=True,
            message_count=0,
            total_tokens=0,
            chat_number=5
        )

        button_row = create_chat_button_row(conv, is_active=True, chat_number=5)

        button = button_row[0]
        # Проверяем, что название обрезано
        assert "..." in button.text
        # Проверяем максимальную длину (40 символов для текста + эмодзи + номер)
        assert len(button.text) <= 50

    def test_chat_actions_menu_markup_structure(self):
        """Проверка структуры меню chat_actions."""
        markup = chat_actions_menu_markup("test-uuid", "Тестовый чат")

        # Проверяем количество строк - теперь 3 строки
        assert len(markup.inline_keyboard) == 3

        # Строка 1: [Перейти]
        row1 = markup.inline_keyboard[0]
        assert len(row1) == 1
        assert row1[0].callback_data == "confirm_switch||test-uuid"
        assert "Перейти" in row1[0].text

        # Строка 2: [Изменить] [Удалить]
        row2 = markup.inline_keyboard[1]
        assert len(row2) == 2
        assert row2[0].callback_data == "rename_chat||test-uuid"
        assert row2[1].callback_data == "delete_chat||test-uuid"
        assert "Изменить" in row2[0].text
        assert "Удалить" in row2[1].text

        # Строка 3: [Назад]
        row3 = markup.inline_keyboard[2]
        assert len(row3) == 1
        assert row3[0].callback_data == "menu_chats"
        assert "Назад" in row3[0].text

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.send_menu')
    async def test_handle_chat_actions(self, mock_send_menu, mock_manager, mock_app):
        """Тест обработчика handle_chat_actions."""
        from conversation_handlers import handle_chat_actions

        # Создаем mock conversation
        metadata = ConversationMetadata(
            conversation_id="test-uuid",
            user_id=12345,
            username="test_user",
            title="Тестовый чат",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=True,
            message_count=0,
            total_tokens=0,
            chat_number=1
        )
        conversation = Conversation(metadata=metadata, messages=[])
        mock_manager.load_conversation.return_value = conversation

        # Вызываем обработчик
        await handle_chat_actions(12345, "test-uuid", mock_app)

        # Проверяем, что send_menu был вызван
        assert mock_send_menu.called
        call_args = mock_send_menu.call_args

        # Проверяем текст сообщения
        assert "Тестовый чат" in call_args[1]["text"]
        assert "Выберите действие" in call_args[1]["text"]

        # Проверяем, что передана правильная разметка
        assert call_args[1]["reply_markup"] is not None

    @patch('conversation_handlers.conversation_manager')
    async def test_handle_chat_actions_nonexistent_chat(self, mock_manager, mock_app):
        """Тест handle_chat_actions для несуществующего чата."""
        from conversation_handlers import handle_chat_actions

        # Настраиваем mock - чат не найден
        mock_manager.load_conversation.return_value = None

        # Вызываем обработчик
        await handle_chat_actions(12345, "fake-uuid", mock_app)

        # Проверяем, что отправлено сообщение об ошибке
        assert mock_app.send_message.called
        call_args = mock_app.send_message.call_args
        assert "не найден" in call_args[1]["text"].lower()

    def test_chat_actions_callback_data_format(self):
        """Проверка формата callback_data для chat_actions."""
        conv = ConversationMetadata(
            conversation_id="abc-123-def-456",
            user_id=12345,
            username="test_user",
            title="Чат",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=True,
            message_count=0,
            total_tokens=0,
            chat_number=1
        )

        button_row = create_chat_button_row(conv, is_active=True, chat_number=1)
        button = button_row[0]

        # Проверяем формат: "chat_actions||{uuid}"
        assert button.callback_data.startswith("chat_actions||")
        conversation_id = button.callback_data.split("||")[1]
        assert conversation_id == "abc-123-def-456"

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.send_menu')
    async def test_handle_chat_actions_exception_handling(self, mock_send_menu, mock_manager, mock_app):
        """Тест обработки исключений в handle_chat_actions."""
        from conversation_handlers import handle_chat_actions

        # Настраиваем mock для выброса исключения
        mock_manager.load_conversation.side_effect = Exception("Database error")

        # Вызываем обработчик
        await handle_chat_actions(12345, "test-uuid", mock_app)

        # Проверяем, что отправлено сообщение об ошибке
        assert mock_app.send_message.called
        call_args = mock_app.send_message.call_args
        assert "ошибка" in call_args[1]["text"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
