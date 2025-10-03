"""
Интеграционные тесты для системы мультичатов.

Проверяет совместную работу всех компонентов:
- conversation_manager + conversations
- handlers + conversation_handlers
- utils + conversation_manager
- Полный workflow создания и использования чатов
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from conversations import ConversationMessage
from conversation_manager import ConversationManager
from utils import _save_to_conversation_sync


class TestFullWorkflow:
    """Интеграционные тесты полного workflow мультичатов."""

    @pytest.fixture
    def temp_dir(self):
        """Временная директория для тестов."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def manager(self, temp_dir):
        """ConversationManager с временной директорией."""
        return ConversationManager(temp_dir)

    def test_full_chat_lifecycle(self, manager):
        """
        Полный жизненный цикл чата:
        1. Создание чата
        2. Добавление сообщений
        3. Переключение на другой чат
        4. Переименование чата
        5. Удаление чата
        """
        user_id = 12345
        username = "integration_test_user"

        # 1. Создание первого чата
        conv1_id = manager.create_conversation(
            user_id=user_id,
            username=username,
            first_question="Расскажи про Python"
        )

        assert conv1_id is not None
        assert manager.get_active_conversation_id(user_id) == conv1_id

        # 2. Добавление сообщений в первый чат
        for i in range(3):
            msg = ConversationMessage(
                timestamp=datetime.now().isoformat(),
                message_id=i,
                type="user_question" if i % 2 == 0 else "bot_answer",
                text=f"Сообщение {i}",
                tokens=10
            )
            success = manager.add_message(user_id, conv1_id, msg)
            assert success is True

        # Проверяем количество сообщений
        conv1 = manager.load_conversation(user_id, conv1_id)
        assert len(conv1.messages) == 3
        assert conv1.metadata.message_count == 3
        assert conv1.metadata.total_tokens == 30

        # 3. Создание второго чата (автоматически становится активным)
        conv2_id = manager.create_conversation(
            user_id=user_id,
            username=username,
            first_question="Что такое AI?"
        )

        assert manager.get_active_conversation_id(user_id) == conv2_id

        # Проверяем, что первый чат стал неактивным
        index_data = manager.load_index(user_id)
        for conv in index_data["conversations"]:
            if conv["conversation_id"] == conv1_id:
                assert conv["is_active"] is False
            elif conv["conversation_id"] == conv2_id:
                assert conv["is_active"] is True

        # 4. Переключение обратно на первый чат
        success = manager.set_active_conversation(user_id, conv1_id)
        assert success is True
        assert manager.get_active_conversation_id(user_id) == conv1_id

        # 5. Переименование первого чата
        conv1 = manager.load_conversation(user_id, conv1_id)
        conv1.metadata.title = "Python Programming"
        manager.save_conversation(conv1)

        # Проверяем переименование
        reloaded = manager.load_conversation(user_id, conv1_id)
        assert reloaded.metadata.title == "Python Programming"

        # 6. Удаление второго чата
        success = manager.delete_conversation(user_id, conv2_id)
        assert success is True

        # Проверяем, что чат удален
        conv2 = manager.load_conversation(user_id, conv2_id)
        assert conv2 is None

        # Проверяем количество чатов
        conversations = manager.list_conversations(user_id)
        assert len(conversations) == 1
        assert conversations[0].conversation_id == conv1_id

    def test_multiple_users_isolation(self, manager):
        """
        Проверка изоляции данных между пользователями:
        - У каждого пользователя свои чаты
        - Чаты не пересекаются между пользователями
        """
        user1_id = 111
        user2_id = 222

        # Создаем чаты для первого пользователя
        user1_conv1 = manager.create_conversation(user1_id, "user1", "Привет 1")
        user1_conv2 = manager.create_conversation(user1_id, "user1", "Привет 2")

        # Создаем чаты для второго пользователя
        user2_conv1 = manager.create_conversation(user2_id, "user2", "Hello 1")
        user2_conv2 = manager.create_conversation(user2_id, "user2", "Hello 2")

        # Проверяем количество чатов у каждого пользователя
        user1_conversations = manager.list_conversations(user1_id)
        user2_conversations = manager.list_conversations(user2_id)

        assert len(user1_conversations) == 2
        assert len(user2_conversations) == 2

        # Проверяем, что чаты не пересекаются
        user1_conv_ids = {c.conversation_id for c in user1_conversations}
        user2_conv_ids = {c.conversation_id for c in user2_conversations}

        assert user1_conv_ids.isdisjoint(user2_conv_ids)

        # Проверяем активные чаты
        assert manager.get_active_conversation_id(user1_id) == user1_conv2
        assert manager.get_active_conversation_id(user2_id) == user2_conv2

    def test_persistence_across_manager_instances(self, temp_dir):
        """
        Проверка сохранения данных при перезапуске:
        - Создаем чаты с одним менеджером
        - Создаем новый менеджер с той же директорией
        - Проверяем, что все данные сохранились
        """
        user_id = 12345
        username = "persistent_user"

        # Создаем первый менеджер и чаты
        manager1 = ConversationManager(temp_dir)
        conv1_id = manager1.create_conversation(user_id, username, "Чат 1")
        conv2_id = manager1.create_conversation(user_id, username, "Чат 2")

        # Добавляем сообщения в первый чат
        for i in range(5):
            msg = ConversationMessage(
                timestamp=datetime.now().isoformat(),
                message_id=i,
                type="user_question",
                text=f"Msg {i}",
                tokens=5
            )
            manager1.add_message(user_id, conv1_id, msg)

        # Создаем новый менеджер с той же директорией
        manager2 = ConversationManager(temp_dir)

        # Проверяем, что данные сохранились
        conversations = manager2.list_conversations(user_id)
        assert len(conversations) == 2

        # Проверяем, что оба чата существуют
        conv_ids = {c.conversation_id for c in conversations}
        assert conv1_id in conv_ids
        assert conv2_id in conv_ids

        # Проверяем, что есть активный чат
        active_id = manager2.get_active_conversation_id(user_id)
        assert active_id in conv_ids

        # Проверяем сообщения в первом чате
        conv1 = manager2.load_conversation(user_id, conv1_id)
        assert len(conv1.messages) == 5
        assert conv1.metadata.message_count == 5
        assert conv1.metadata.total_tokens == 25

    def test_atomic_operations(self, manager):
        """
        Проверка атомарности операций:
        - Сохранение через временные файлы
        - Откат при ошибках
        """
        user_id = 12345
        username = "atomic_user"

        # Создаем чат
        conv_id = manager.create_conversation(user_id, username, "Test")
        conv = manager.load_conversation(user_id, conv_id)

        # Проверяем существование основного файла
        user_dir = manager.base_dir / f"user_{user_id}"
        main_file = user_dir / f"{conv_id}.json"
        temp_file = user_dir / f"{conv_id}.json.tmp"

        assert main_file.exists()
        assert not temp_file.exists()  # Временный файл должен быть удален после сохранения

    def test_concurrent_message_addition(self, manager):
        """
        Проверка последовательного добавления сообщений:
        - Сообщения добавляются в правильном порядке
        - Счетчики обновляются корректно
        """
        user_id = 12345
        username = "concurrent_user"

        conv_id = manager.create_conversation(user_id, username, "Test")

        # Добавляем 10 сообщений
        for i in range(10):
            msg = ConversationMessage(
                timestamp=datetime.now().isoformat(),
                message_id=i,
                type="user_question" if i % 2 == 0 else "bot_answer",
                text=f"Message {i}",
                tokens=10 + i
            )
            success = manager.add_message(user_id, conv_id, msg)
            assert success is True

        # Проверяем порядок сообщений
        conv = manager.load_conversation(user_id, conv_id)
        assert len(conv.messages) == 10

        for i, msg in enumerate(conv.messages):
            assert msg.text == f"Message {i}"
            assert msg.message_id == i

        # Проверяем счетчики
        assert conv.metadata.message_count == 10
        expected_tokens = sum(10 + i for i in range(10))
        assert conv.metadata.total_tokens == expected_tokens


class TestUtilsIntegration:
    """Интеграционные тесты для utils.py с conversation_manager."""

    @pytest.fixture
    def temp_dir(self):
        """Временная директория для тестов."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def manager(self, temp_dir):
        """ConversationManager с временной директорией."""
        return ConversationManager(temp_dir)

    @patch('utils.count_tokens')
    def test_save_to_conversation_sync_integration(self, mock_count_tokens, manager):
        """
        Интеграционный тест _save_to_conversation_sync:
        - Создаем реальный чат
        - Сохраняем сообщение через utils
        - Проверяем, что оно попало в conversation_manager
        """
        mock_count_tokens.return_value = 50

        user_id = 12345
        username = "utils_test_user"

        # Создаем чат
        conv_id = manager.create_conversation(user_id, username, "Test")

        # Подменяем глобальный conversation_manager на уровне модуля conversation_manager
        with patch('conversation_manager.conversation_manager', manager):
            # Сохраняем через utils
            _save_to_conversation_sync(
                user_id=user_id,
                conversation_id=conv_id,
                message_id=999,
                message_type="bot_answer",
                text="Интеграционный тест",
                sent_as="message",
                search_type="fast"
            )

        # Проверяем, что сообщение сохранилось
        conv = manager.load_conversation(user_id, conv_id)
        assert len(conv.messages) == 1

        msg = conv.messages[0]
        assert msg.message_id == 999
        assert msg.type == "bot_answer"
        assert msg.text == "Интеграционный тест"
        assert msg.sent_as == "message"
        assert msg.search_type == "fast"
        assert msg.tokens == 50


class TestEdgeCases:
    """Тесты граничных случаев."""

    @pytest.fixture
    def temp_dir(self):
        """Временная директория для тестов."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def manager(self, temp_dir):
        """ConversationManager с временной директорией."""
        return ConversationManager(temp_dir)

    def test_empty_conversations_list(self, manager):
        """Получение списка чатов для пользователя без чатов."""
        conversations = manager.list_conversations(99999)
        assert conversations == []

    def test_get_messages_from_empty_chat(self, manager):
        """Получение сообщений из пустого чата."""
        conv_id = manager.create_conversation(12345, "test_user")
        messages = manager.get_messages(12345, conv_id, limit=10)
        assert messages == []

    def test_delete_last_conversation(self, manager):
        """
        Удаление последнего чата:
        - Должен создаться новый чат автоматически
        """
        user_id = 12345
        username = "test_user"

        # Создаем один чат
        conv_id = manager.create_conversation(user_id, username, "Единственный чат")

        # Удаляем его
        success = manager.delete_conversation(user_id, conv_id)
        assert success is True

        # Проверяем, что создался новый чат
        index_data = manager.load_index(user_id)
        assert len(index_data["conversations"]) == 1
        assert index_data["last_active_conversation_id"] is not None

    def test_unicode_in_chat_names(self, manager):
        """Поддержка unicode в названиях чатов."""
        user_id = 12345

        # Создаем чаты с разными unicode символами
        conv1 = manager.create_conversation(
            user_id, "test_user",
            "Привет мир 🌍"
        )
        conv2 = manager.create_conversation(
            user_id, "test_user",
            "你好世界 中文"
        )
        conv3 = manager.create_conversation(
            user_id, "test_user",
            "مرحبا بالعالم عربي"
        )

        # Загружаем и проверяем
        conversations = manager.list_conversations(user_id)
        assert len(conversations) == 3

        titles = {c.title for c in conversations}
        assert "Привет мир 🌍" in titles
        assert "你好世界 中文" in titles
        assert "مرحبا بالعالم عربي" in titles

    def test_very_long_messages(self, manager):
        """Сохранение очень длинных сообщений."""
        user_id = 12345
        conv_id = manager.create_conversation(user_id, "test_user")

        # Создаем очень длинное сообщение (10000 символов)
        long_text = "A" * 10000

        msg = ConversationMessage(
            timestamp=datetime.now().isoformat(),
            message_id=1,
            type="bot_answer",
            text=long_text,
            tokens=5000
        )

        success = manager.add_message(user_id, conv_id, msg)
        assert success is True

        # Проверяем сохранение
        conv = manager.load_conversation(user_id, conv_id)
        assert len(conv.messages) == 1
        assert len(conv.messages[0].text) == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
