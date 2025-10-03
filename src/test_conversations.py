"""
Юнит-тесты для модулей системы мультичатов.

Тестируемые модули:
- conversations.py: модели данных
- conversation_manager.py: CRUD операции
- conversation_handlers.py: обработчики Telegram
- utils.py: сохранение в conversations
"""

import pytest
import os
import json
import uuid
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, call

# Импорты тестируемых модулей
from conversations import (
    ConversationMessage,
    ConversationMetadata,
    Conversation,
    generate_chat_name
)
from conversation_manager import ConversationManager
from utils import _save_to_conversation_sync


# ============================================================
# ТЕСТЫ ДЛЯ conversations.py
# ============================================================

class TestConversationMessage:
    """Тесты для ConversationMessage dataclass."""

    def test_create_message(self):
        """Создание сообщения с всеми полями."""
        msg = ConversationMessage(
            timestamp="2025-01-01T12:00:00",
            message_id=123,
            type="user_question",
            text="Привет",
            tokens=10,
            sent_as="message",
            file_path=None,
            search_type="fast"
        )

        assert msg.timestamp == "2025-01-01T12:00:00"
        assert msg.message_id == 123
        assert msg.type == "user_question"
        assert msg.text == "Привет"
        assert msg.tokens == 10
        assert msg.sent_as == "message"
        assert msg.file_path is None
        assert msg.search_type == "fast"

    def test_create_message_minimal(self):
        """Создание сообщения с минимальными полями."""
        msg = ConversationMessage(
            timestamp="2025-01-01T12:00:00",
            message_id=123,
            type="bot_answer",
            text="Ответ",
            tokens=15
        )

        assert msg.timestamp == "2025-01-01T12:00:00"
        assert msg.message_id == 123
        assert msg.type == "bot_answer"
        assert msg.text == "Ответ"
        assert msg.tokens == 15
        assert msg.sent_as is None
        assert msg.file_path is None
        assert msg.search_type is None


class TestConversationMetadata:
    """Тесты для ConversationMetadata dataclass."""

    def test_create_metadata(self):
        """Создание метаданных чата."""
        now = datetime.now().isoformat()
        metadata = ConversationMetadata(
            conversation_id="test-uuid-123",
            user_id=12345,
            username="test_user",
            title="Тестовый чат",
            created_at=now,
            updated_at=now,
            is_active=True,
            message_count=0,
            total_tokens=0
        )

        assert metadata.conversation_id == "test-uuid-123"
        assert metadata.user_id == 12345
        assert metadata.username == "test_user"
        assert metadata.title == "Тестовый чат"
        assert metadata.is_active is True
        assert metadata.message_count == 0
        assert metadata.total_tokens == 0


class TestGenerateChatName:
    """Тесты для функции generate_chat_name()."""

    def test_short_text(self):
        """Короткий текст возвращается как есть."""
        result = generate_chat_name("Привет мир", max_length=30)
        assert result == "Привет мир"

    def test_long_text_truncated(self):
        """Длинный текст обрезается с добавлением '...'."""
        long_text = "Проанализируй интервью с клиентом из отеля Москва по факторам качества"
        result = generate_chat_name(long_text, max_length=30)

        assert len(result) <= 33  # 30 + "..."
        assert result.endswith("...")
        assert result.startswith("Проанализируй интервью")

    def test_minimum_three_words(self):
        """Минимум 3 слова даже если превышен лимит."""
        text = "Первое Второе Третье Четвертое"
        result = generate_chat_name(text, max_length=10)

        # Должно быть минимум 3 слова
        words = result.replace("...", "").split()
        assert len(words) >= 3

    def test_removes_extra_spaces(self):
        """Удаляет лишние пробелы."""
        text = "Привет    мир   тест"
        result = generate_chat_name(text)
        assert "  " not in result


# ============================================================
# ТЕСТЫ ДЛЯ conversation_manager.py
# ============================================================

class TestConversationManager:
    """Тесты для ConversationManager."""

    @pytest.fixture
    def temp_dir(self):
        """Создает временную директорию для тестов."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def manager(self, temp_dir):
        """Создает ConversationManager с временной директорией."""
        return ConversationManager(temp_dir)

    def test_init_manager(self, temp_dir):
        """Инициализация ConversationManager создает базовую директорию."""
        manager = ConversationManager(temp_dir)
        assert manager.base_dir.exists()
        assert manager.base_dir.is_dir()

    def test_ensure_user_directory(self, manager):
        """Создание директории пользователя."""
        user_dir = manager.ensure_user_directory(12345)

        assert user_dir.exists()
        assert user_dir.is_dir()
        assert user_dir.name == "user_12345"

    def test_create_conversation(self, manager):
        """Создание нового чата."""
        conversation_id = manager.create_conversation(
            user_id=12345,
            username="test_user",
            first_question="Привет, как дела?"
        )

        # Проверяем UUID формат
        assert isinstance(conversation_id, str)
        assert len(conversation_id) == 36

        # Проверяем существование файла
        user_dir = manager.base_dir / "user_12345"
        conversation_file = user_dir / f"{conversation_id}.json"
        assert conversation_file.exists()

        # Проверяем index.json
        index_file = user_dir / "index.json"
        assert index_file.exists()

        with open(index_file, 'r', encoding='utf-8') as f:
            index_data = json.load(f)

        assert index_data["user_id"] == 12345
        assert index_data["username"] == "test_user"
        assert index_data["last_active_conversation_id"] == conversation_id
        assert len(index_data["conversations"]) == 1

    def test_load_conversation(self, manager):
        """Загрузка существующего чата."""
        # Создаем чат
        conversation_id = manager.create_conversation(
            user_id=12345,
            username="test_user",
            first_question="Тест"
        )

        # Загружаем чат
        conversation = manager.load_conversation(12345, conversation_id)

        assert conversation is not None
        assert conversation.metadata.conversation_id == conversation_id
        assert conversation.metadata.user_id == 12345
        assert conversation.metadata.username == "test_user"
        assert len(conversation.messages) == 0

    def test_load_nonexistent_conversation(self, manager):
        """Загрузка несуществующего чата возвращает None."""
        conversation = manager.load_conversation(12345, "fake-uuid")
        assert conversation is None

    def test_save_conversation(self, manager):
        """Сохранение изменений в чате."""
        # Создаем чат
        conversation_id = manager.create_conversation(
            user_id=12345,
            username="test_user"
        )

        # Загружаем и изменяем
        conversation = manager.load_conversation(12345, conversation_id)
        conversation.metadata.title = "Новое название"

        # Сохраняем
        result = manager.save_conversation(conversation)
        assert result is True

        # Перезагружаем и проверяем
        reloaded = manager.load_conversation(12345, conversation_id)
        assert reloaded.metadata.title == "Новое название"

    def test_delete_conversation(self, manager):
        """Удаление чата."""
        # Создаем 2 чата
        conv1 = manager.create_conversation(12345, "test_user", "Чат 1")
        conv2 = manager.create_conversation(12345, "test_user", "Чат 2")

        # Удаляем первый чат
        result = manager.delete_conversation(12345, conv1)
        assert result is True

        # Проверяем, что файл удален
        user_dir = manager.base_dir / "user_12345"
        conv1_file = user_dir / f"{conv1}.json"
        assert not conv1_file.exists()

        # Проверяем index.json
        index_data = manager.load_index(12345)
        assert len(index_data["conversations"]) == 1
        assert index_data["conversations"][0]["conversation_id"] == conv2

    def test_get_active_conversation_id(self, manager):
        """Получение ID активного чата."""
        conversation_id = manager.create_conversation(12345, "test_user")
        active_id = manager.get_active_conversation_id(12345)

        assert active_id == conversation_id

    def test_set_active_conversation(self, manager):
        """Переключение активного чата."""
        # Создаем 2 чата
        conv1 = manager.create_conversation(12345, "test_user", "Чат 1")
        conv2 = manager.create_conversation(12345, "test_user", "Чат 2")

        # conv2 активен по умолчанию, переключаем на conv1
        result = manager.set_active_conversation(12345, conv1)
        assert result is True

        # Проверяем
        active_id = manager.get_active_conversation_id(12345)
        assert active_id == conv1

    def test_add_message(self, manager):
        """Добавление сообщения в чат."""
        conversation_id = manager.create_conversation(12345, "test_user")

        # Создаем сообщение
        message = ConversationMessage(
            timestamp=datetime.now().isoformat(),
            message_id=999,
            type="user_question",
            text="Привет",
            tokens=5
        )

        # Добавляем сообщение
        result = manager.add_message(12345, conversation_id, message)
        assert result is True

        # Проверяем
        conversation = manager.load_conversation(12345, conversation_id)
        assert len(conversation.messages) == 1
        assert conversation.messages[0].text == "Привет"
        assert conversation.metadata.message_count == 1
        assert conversation.metadata.total_tokens == 5

    def test_get_messages(self, manager):
        """Получение последних N сообщений."""
        conversation_id = manager.create_conversation(12345, "test_user")

        # Добавляем 5 сообщений
        for i in range(5):
            message = ConversationMessage(
                timestamp=datetime.now().isoformat(),
                message_id=i,
                type="user_question",
                text=f"Сообщение {i}",
                tokens=5
            )
            manager.add_message(12345, conversation_id, message)

        # Получаем последние 3
        messages = manager.get_messages(12345, conversation_id, limit=3)
        assert len(messages) == 3
        assert messages[0].text == "Сообщение 2"
        assert messages[2].text == "Сообщение 4"

    def test_list_conversations(self, manager):
        """Получение списка всех чатов пользователя."""
        # Создаем 3 чата
        conv1 = manager.create_conversation(12345, "test_user", "Чат 1")
        conv2 = manager.create_conversation(12345, "test_user", "Чат 2")
        conv3 = manager.create_conversation(12345, "test_user", "Чат 3")

        # Получаем список
        conversations = manager.list_conversations(12345)
        assert len(conversations) == 3

        # Проверяем типы
        for conv in conversations:
            assert isinstance(conv, ConversationMetadata)


# ============================================================
# ТЕСТЫ ДЛЯ utils.py
# ============================================================

class TestSaveToConversationSync:
    """Тесты для _save_to_conversation_sync."""

    @patch('conversation_manager.conversation_manager')
    @patch('utils.count_tokens')
    def test_save_message_to_conversation(self, mock_count_tokens, mock_conv_manager):
        """Сохранение сообщения в conversations."""
        mock_count_tokens.return_value = 100
        mock_conv_manager.add_message.return_value = True

        _save_to_conversation_sync(
            user_id=12345,
            conversation_id="test-uuid",
            message_id=999,
            message_type="bot_answer",
            text="Тестовый ответ",
            sent_as="message",
            search_type="fast"
        )

        # Проверяем вызов add_message
        assert mock_conv_manager.add_message.called
        call_args = mock_conv_manager.add_message.call_args
        assert call_args[1]["user_id"] == 12345
        assert call_args[1]["conversation_id"] == "test-uuid"

        # Проверяем message object
        message = call_args[1]["message"]
        assert message.message_id == 999
        assert message.type == "bot_answer"
        assert message.text == "Тестовый ответ"
        assert message.tokens == 100

    @patch('conversation_manager.conversation_manager')
    def test_save_handles_exception(self, mock_conv_manager):
        """Обработка исключений при сохранении."""
        mock_conv_manager.add_message.side_effect = Exception("Test error")

        # Не должно падать
        _save_to_conversation_sync(
            user_id=12345,
            conversation_id="test-uuid",
            message_id=999,
            message_type="bot_answer",
            text="Тест"
        )


# ============================================================
# ТЕСТЫ ДЛЯ conversation_handlers.py
# ============================================================

class TestConversationHandlers:
    """Тесты для обработчиков мультичатов."""

    @pytest.fixture
    def mock_app(self):
        """Mock объект Pyrogram Client."""
        app = MagicMock()
        app.send_message = MagicMock()
        app.get_chat = MagicMock()
        return app

    @patch('conversation_handlers.conversation_manager')
    def test_ensure_active_conversation_existing(self, mock_manager, mock_app):
        """ensure_active_conversation с существующим чатом."""
        from conversation_handlers import ensure_active_conversation

        # Настраиваем mock
        mock_manager.get_active_conversation_id.return_value = "existing-uuid"
        mock_manager.load_conversation.return_value = MagicMock()

        # Вызываем
        result = ensure_active_conversation(12345, "test_user", "Привет")

        assert result == "existing-uuid"
        mock_manager.create_conversation.assert_not_called()

    @patch('conversation_handlers.conversation_manager')
    def test_ensure_active_conversation_create_new(self, mock_manager, mock_app):
        """ensure_active_conversation создает новый чат."""
        from conversation_handlers import ensure_active_conversation

        # Настраиваем mock
        mock_manager.get_active_conversation_id.return_value = None
        mock_manager.create_conversation.return_value = "new-uuid"

        # Вызываем
        result = ensure_active_conversation(12345, "test_user", "Привет")

        assert result == "new-uuid"
        mock_manager.create_conversation.assert_called_once()

    @patch('conversation_handlers.conversation_manager')
    @patch('conversation_handlers.get_username_from_chat')
    def test_handle_new_chat(self, mock_get_username, mock_manager, mock_app):
        """handle_new_chat создает новый чат."""
        from conversation_handlers import handle_new_chat
        from config import user_states

        mock_get_username.return_value = "test_user"
        mock_manager.create_conversation.return_value = "new-uuid"

        # Вызываем
        handle_new_chat(12345, mock_app)

        # Проверяем
        mock_manager.create_conversation.assert_called_once_with(
            user_id=12345,
            username="test_user",
            first_question="Новый чат"
        )
        assert mock_app.send_message.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
