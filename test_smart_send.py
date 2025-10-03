"""
Тесты для функций умной отправки в utils.py

ПРИМЕЧАНИЕ: Тесты для старых async функций (smart_send_text, smart_send_text_sync)
являются DEPRECATED так как эти функции были заменены на smart_send_text_unified.
Новые тесты находятся в классе TestSmartSendTextUnified в конце файла.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pyrogram.enums import ParseMode

from src.utils import (
    smart_send_text_unified,
    create_preview_text,
    get_username_from_chat
)

# DEPRECATED: Старые функции удалены, импорты ниже не работают
# from src.utils import smart_send_text, smart_send_text_sync


@pytest.fixture
def mock_app():
    """Создает мок Pyrogram клиента."""
    app = Mock()
    app.send_message = Mock()
    app.send_document = Mock()
    app.get_chat = Mock()
    return app


@pytest.fixture
def mock_message():
    """Создает мок сообщения."""
    message = Mock()
    message.id = 123
    return message


class TestCreatePreviewText:
    """Тесты для функции create_preview_text."""

    def test_short_text(self):
        """Тест с коротким текстом."""
        text = "Короткий текст"
        preview = create_preview_text(text, length=100)
        assert preview == text

    def test_long_text_with_space(self):
        """Тест с длинным текстом, содержащим пробелы."""
        text = "Это очень длинный текст который должен быть обрезан по ближайшему пробелу"
        preview = create_preview_text(text, length=50)
        
        assert len(preview) <= 53  # 50 + "..."
        assert preview.endswith("...")
        assert " " in preview[:-3]  # Должен быть пробел до "..."

    def test_long_text_without_spaces(self):
        """Тест с длинным текстом без пробелов."""
        text = "Очень_длинный_текст_без_пробелов_который_нужно_обрезать"
        preview = create_preview_text(text, length=30)
        
        assert len(preview) == 33  # 30 + "..."
        assert preview.endswith("...")
        assert preview[:-3] == text[:30]

    def test_exactly_max_length(self):
        """Тест с текстом точно равным максимальной длине."""
        text = "X" * 100
        preview = create_preview_text(text, length=100)
        assert preview == text


class TestGetUsernameFromChat:
    """Тесты для функции get_username_from_chat."""

    def test_get_username_with_app(self, mock_app):
        """Тест получения username с клиентом."""
        mock_chat = Mock()
        mock_chat.username = "test_user"
        mock_app.get_chat.return_value = mock_chat
        
        username = get_username_from_chat(123456, mock_app)
        assert username == "test_user"
        mock_app.get_chat.assert_called_once_with(123456)

    def test_get_username_no_username(self, mock_app):
        """Тест получения username когда у чата нет username."""
        mock_chat = Mock()
        mock_chat.username = None
        mock_app.get_chat.return_value = mock_chat
        
        username = get_username_from_chat(123456, mock_app)
        assert username == "user_123456"

    def test_get_username_without_app(self):
        """Тест получения username без клиента."""
        username = get_username_from_chat(123456)
        assert username == "user_123456"

    def test_get_username_exception(self, mock_app):
        """Тест обработки исключения при получении username."""
        mock_app.get_chat.side_effect = Exception("Test error")
        
        username = get_username_from_chat(123456, mock_app)
        assert username == "user_123456"


# ============================================================================
# DEPRECATED TESTS - Старые тесты удалены, так как функции были заменены
# ============================================================================
# class TestSmartSendText - УДАЛЕНО (smart_send_text удалена)
# class TestSmartSendTextSync - УДАЛЕНО (smart_send_text_sync удалена)
# class TestIntegration - УДАЛЕНО (использовала удаленные функции)
# ============================================================================


class TestSmartSendTextUnified:
    """Тесты для новой unified синхронной функции smart_send_text_unified."""

    def test_send_short_message(self, mock_app, mock_message):
        """Тест отправки короткого сообщения через unified функцию."""
        text = "Короткое сообщение"
        chat_id = 123456
        username = "test_user"

        mock_app.send_message.return_value = mock_message

        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils._save_to_history_sync') as mock_save:

            result = smart_send_text_unified(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=username,
                question="Тестовый вопрос",
                search_type="fast",
                parse_mode=ParseMode.MARKDOWN
            )

        assert result is True
        mock_app.send_message.assert_called_once_with(
            chat_id, text, parse_mode=ParseMode.MARKDOWN
        )
        mock_save.assert_called_once()

    def test_send_long_message_as_file(self, mock_app, mock_message):
        """Тест отправки длинного сообщения как MD файла через unified функцию."""
        text = "X" * 1500  # Длинный текст
        chat_id = 123456
        username = "test_user"
        question = "Тестовый вопрос"

        mock_app.send_message.return_value = mock_message
        mock_app.send_document.return_value = mock_message

        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils.md_storage_manager') as mock_storage, \
             patch('src.utils._save_to_history_sync') as mock_save:

            mock_storage.save_md_report.return_value = "/path/to/report.md"

            result = smart_send_text_unified(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=username,
                question=question,
                search_type="deep"
            )

        assert result is True

        # Проверяем что отправлено превью
        preview_calls = [call for call in mock_app.send_message.call_args_list
                        if len(call[0]) > 1 and "📄 **Ваш отчет готов!**" in call[0][1]]
        assert len(preview_calls) == 1

        # Проверяем что сохранен MD файл
        mock_storage.save_md_report.assert_called_once_with(
            content=text,
            user_id=chat_id,
            username=username,
            question=question,
            search_type="deep"
        )

        # Проверяем что отправлен документ
        mock_app.send_document.assert_called_once()

    def test_auto_username_detection(self, mock_app, mock_message):
        """Тест автоматического определения username в unified функции."""
        text = "Тест"
        chat_id = 123456

        mock_app.send_message.return_value = mock_message

        with patch('src.utils.get_username_from_chat') as mock_get_username, \
             patch('src.utils._save_to_history_sync'):

            mock_get_username.return_value = "auto_user"

            smart_send_text_unified(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=None,  # Не передаем username
                question="Тест",
                search_type="fast"
            )

        mock_get_username.assert_called_once_with(chat_id, mock_app)