"""
Тесты для модуля chat_history.py
"""

import pytest
import tempfile
import shutil
from datetime import date, datetime
from pathlib import Path

from src.chat_history import ChatHistoryManager, Message, DayStats, DayHistory


@pytest.fixture
def temp_history_dir():
    """Создает временную директорию для тестов."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def history_manager(temp_history_dir, monkeypatch):
    """Создает менеджер истории с временной директорией."""
    monkeypatch.setattr('src.chat_history.CHAT_HISTORY_DIR', temp_history_dir)
    return ChatHistoryManager()


class TestChatHistoryManager:
    """Тесты для ChatHistoryManager."""

    def test_ensure_history_directory(self, history_manager):
        """Тест создания директории истории."""
        assert history_manager.history_dir.exists()

    def test_ensure_user_directory(self, history_manager):
        """Тест создания директории пользователя."""
        user_id = 123456
        user_dir = history_manager.ensure_user_directory(user_id)
        
        assert user_dir.exists()
        assert user_dir.name == f"user_{user_id}"

    def test_get_filename_methods(self, history_manager):
        """Тест методов генерации имен файлов."""
        today_filename = history_manager.get_today_filename()
        assert today_filename.endswith('.json')
        assert date.today().isoformat() in today_filename
        
        test_date = date(2025, 1, 15)
        date_filename = history_manager.get_date_filename(test_date)
        assert date_filename == "2025-01-15.json"

    def test_save_and_load_day_history(self, history_manager):
        """Тест сохранения и загрузки истории дня."""
        user_id = 123456
        username = "test_user"
        test_date = date(2025, 1, 15)
        
        # Создаем тестовую историю
        messages = [
            Message(
                timestamp=datetime.now().isoformat(),
                message_id=1,
                type="user_question",
                text="Тестовый вопрос",
                tokens=10
            ),
            Message(
                timestamp=datetime.now().isoformat(),
                message_id=2,
                type="bot_answer",
                text="Тестовый ответ",
                tokens=20,
                sent_as="message",
                search_type="fast"
            )
        ]
        
        stats = DayStats(
            total_questions=1,
            total_answers=1,
            fast_searches=1,
            deep_searches=0,
            total_tokens=30,
            files_sent=0
        )
        
        day_history = DayHistory(
            user_id=user_id,
            username=username,
            date=test_date.isoformat(),
            messages=messages,
            stats=stats
        )
        
        # Сохраняем
        success = history_manager.save_day_history(day_history)
        assert success
        
        # Загружаем
        loaded_history = history_manager.load_day_history(user_id, test_date)
        assert loaded_history is not None
        assert loaded_history.user_id == user_id
        assert loaded_history.username == username
        assert len(loaded_history.messages) == 2
        assert loaded_history.stats.total_questions == 1
        assert loaded_history.stats.total_answers == 1

    def test_save_message_to_history(self, history_manager):
        """Тест сохранения сообщения в историю."""
        user_id = 123456
        username = "test_user"
        
        # Сохраняем сообщение пользователя
        success = history_manager.save_message_to_history(
            user_id=user_id,
            username=username,
            message_id=1,
            message_type="user_question",
            text="Тестовый вопрос"
        )
        assert success
        
        # Сохраняем ответ бота
        success = history_manager.save_message_to_history(
            user_id=user_id,
            username=username,
            message_id=2,
            message_type="bot_answer",
            text="Тестовый ответ",
            sent_as="file",
            file_path="/path/to/file.md",
            search_type="deep"
        )
        assert success
        
        # Проверяем что история сохранилась
        today = date.today()
        day_history = history_manager.load_day_history(user_id, today)
        assert day_history is not None
        assert len(day_history.messages) == 2
        assert day_history.stats.total_questions == 1
        assert day_history.stats.total_answers == 1
        assert day_history.stats.deep_searches == 1
        assert day_history.stats.files_sent == 1

    def test_get_user_stats(self, history_manager):
        """Тест получения статистики пользователя."""
        user_id = 123456
        username = "test_user"
        
        # Добавляем несколько сообщений
        for i in range(3):
            history_manager.save_message_to_history(
                user_id=user_id,
                username=username,
                message_id=i * 2 + 1,
                message_type="user_question",
                text=f"Вопрос {i}"
            )
            
            history_manager.save_message_to_history(
                user_id=user_id,
                username=username,
                message_id=i * 2 + 2,
                message_type="bot_answer",
                text=f"Ответ {i}",
                sent_as="message" if i % 2 == 0 else "file",
                search_type="fast" if i % 2 == 0 else "deep"
            )
        
        stats = history_manager.get_user_stats(user_id)
        assert stats["total_questions"] == 3
        assert stats["total_answers"] == 3
        assert stats["fast_searches"] == 2
        assert stats["deep_searches"] == 1
        assert stats["files_sent"] == 1
        assert stats["days_active"] == 1

    def test_format_day_history_for_display(self, history_manager):
        """Тест форматирования истории для отображения."""
        user_id = 123456
        username = "test_user"
        
        # Добавляем сообщение
        history_manager.save_message_to_history(
            user_id=user_id,
            username=username,
            message_id=1,
            message_type="user_question",
            text="Тестовый вопрос"
        )
        
        # Форматируем для отображения
        display_text = history_manager.format_day_history_for_display(user_id)
        
        assert "📊 История за" in display_text
        assert "🤔 Вопросы: 1" in display_text
        assert "Тестовый вопрос" in display_text

    def test_format_user_stats_for_display(self, history_manager):
        """Тест форматирования статистики для отображения."""
        user_id = 123456
        username = "test_user"
        
        # Добавляем сообщения
        history_manager.save_message_to_history(
            user_id=user_id,
            username=username,
            message_id=1,
            message_type="user_question",
            text="Вопрос"
        )
        
        history_manager.save_message_to_history(
            user_id=user_id,
            username=username,
            message_id=2,
            message_type="bot_answer",
            text="Ответ",
            sent_as="message",
            search_type="fast"
        )
        
        # Форматируем для отображения
        display_text = history_manager.format_user_stats_for_display(user_id)
        
        assert "📈 **Ваша статистика" in display_text
        assert "📅 Активных дней: 1" in display_text
        assert "🤔 Всего вопросов: 1" in display_text
        assert "🤖 Всего ответов: 1" in display_text

    def test_empty_history(self, history_manager):
        """Тест обработки пустой истории."""
        user_id = 999999
        
        # Попытка загрузить несуществующую историю
        day_history = history_manager.load_day_history(user_id)
        assert day_history is None
        
        # Статистика для пользователя без истории
        stats = history_manager.get_user_stats(user_id)
        assert stats["total_questions"] == 0
        assert stats["total_answers"] == 0
        assert stats["days_active"] == 0
        
        # Форматирование пустой истории
        display_text = history_manager.format_day_history_for_display(user_id)
        assert "Нет сообщений за этот день" in display_text


class TestMessage:
    """Тесты для модели Message."""

    def test_message_creation(self):
        """Тест создания сообщения."""
        message = Message(
            timestamp="2025-01-15T10:30:00",
            message_id=123,
            type="user_question",
            text="Тестовое сообщение",
            tokens=15,
            sent_as="message",
            file_path=None,
            search_type="fast"
        )
        
        assert message.timestamp == "2025-01-15T10:30:00"
        assert message.message_id == 123
        assert message.type == "user_question"
        assert message.text == "Тестовое сообщение"
        assert message.tokens == 15
        assert message.sent_as == "message"
        assert message.file_path is None
        assert message.search_type == "fast"


class TestDayStats:
    """Тесты для модели DayStats."""

    def test_day_stats_creation(self):
        """Тест создания статистики дня."""
        stats = DayStats(
            total_questions=5,
            total_answers=5,
            fast_searches=3,
            deep_searches=2,
            total_tokens=1000,
            files_sent=2
        )
        
        assert stats.total_questions == 5
        assert stats.total_answers == 5
        assert stats.fast_searches == 3
        assert stats.deep_searches == 2
        assert stats.total_tokens == 1000
        assert stats.files_sent == 2

    def test_day_stats_defaults(self):
        """Тест значений по умолчанию для статистики."""
        stats = DayStats()
        
        assert stats.total_questions == 0
        assert stats.total_answers == 0
        assert stats.fast_searches == 0
        assert stats.deep_searches == 0
        assert stats.total_tokens == 0
        assert stats.files_sent == 0