"""
Тесты для функций умной отправки в utils.py
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pyrogram.enums import ParseMode

from src.utils import (
    smart_send_text,
    smart_send_text_sync,
    create_preview_text,
    get_username_from_chat
)


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


class TestSmartSendText:
    """Тесты для функции smart_send_text."""

    @pytest.mark.asyncio
    async def test_send_short_message(self, mock_app, mock_message):
        """Тест отправки короткого сообщения."""
        text = "Короткое сообщение"
        chat_id = 123456
        username = "test_user"
        
        mock_app.send_message.return_value = mock_message
        
        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils.asyncio.create_task') as mock_create_task:
            
            result = await smart_send_text(
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
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_long_message_as_file(self, mock_app, mock_message):
        """Тест отправки длинного сообщения как файла."""
        text = "X" * 1500  # Длинный текст
        chat_id = 123456
        username = "test_user"
        question = "Тестовый вопрос"
        
        mock_app.send_message.return_value = mock_message
        mock_app.send_document.return_value = mock_message
        
        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils.md_storage_manager') as mock_storage, \
             patch('src.utils.asyncio.create_task') as mock_create_task:
            
            mock_storage.save_md_report.return_value = "/path/to/report.md"
            
            result = await smart_send_text(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=username,
                question=question,
                search_type="deep"
            )
        
        assert result is True
        
        # Проверяем что отправлено превью
        assert mock_app.send_message.called
        preview_call = mock_app.send_message.call_args
        preview_text = preview_call[0][1]
        assert "📄 **Ваш отчет готов!**" in preview_text
        
        # Проверяем что сохранен MD файл
        mock_storage.save_md_report.assert_called_once_with(
            content=text,
            user_id=chat_id,
            username=username,
            question=question,
            search_type="deep"
        )
        
        # Проверяем что отправлен файл
        mock_app.send_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_file_fallback_to_split(self, mock_app, mock_message):
        """Тест fallback к разделению текста при ошибке отправки файла."""
        text = "X" * 1500
        chat_id = 123456
        username = "test_user"
        
        mock_app.send_message.return_value = mock_message
        mock_app.send_document.side_effect = Exception("Send file error")
        
        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils.md_storage_manager') as mock_storage, \
             patch('src.utils.split_and_send_long_text') as mock_split:
            
            mock_storage.save_md_report.return_value = "/path/to/report.md"
            
            result = await smart_send_text(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=username,
                question="Тест",
                search_type="fast"
            )
        
        assert result is True
        mock_split.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_username_detection(self, mock_app, mock_message):
        """Тест автоматического определения username."""
        text = "Тест"
        chat_id = 123456
        
        mock_app.send_message.return_value = mock_message
        
        with patch('src.utils.get_username_from_chat') as mock_get_username, \
             patch('src.utils.asyncio.create_task'):
            
            mock_get_username.return_value = "auto_user"
            
            await smart_send_text(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=None,  # Не передаем username
                question="Тест",
                search_type="fast"
            )
        
        mock_get_username.assert_called_once_with(chat_id, mock_app)


class TestSmartSendTextSync:
    """Тесты для синхронной обертки smart_send_text_sync."""

    def test_sync_wrapper_with_new_loop(self, mock_app):
        """Тест синхронной обертки с новым event loop."""
        text = "Тест"
        chat_id = 123456
        
        with patch('src.utils.asyncio.get_event_loop') as mock_get_loop, \
             patch('src.utils.asyncio.run') as mock_run, \
             patch('src.utils.smart_send_text') as mock_smart_send:
            
            # Симулируем отсутствие event loop
            mock_get_loop.side_effect = RuntimeError("No event loop")
            mock_run.return_value = True
            mock_smart_send.return_value = True
            
            result = smart_send_text_sync(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username="test_user",
                question="Тест",
                search_type="fast"
            )
        
        assert result is True
        mock_run.assert_called_once()

    def test_sync_wrapper_with_existing_loop(self, mock_app):
        """Тест синхронной обертки с существующим event loop."""
        text = "Тест"
        chat_id = 123456
        
        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.return_value = True
        
        with patch('src.utils.asyncio.get_event_loop', return_value=mock_loop), \
             patch('src.utils.smart_send_text') as mock_smart_send:
            
            mock_smart_send.return_value = True
            
            result = smart_send_text_sync(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username="test_user",
                question="Тест",
                search_type="fast"
            )
        
        assert result is True
        mock_loop.run_until_complete.assert_called_once()

    def test_sync_wrapper_fallback_to_split(self, mock_app):
        """Тест fallback к split_and_send_long_text при ошибке."""
        text = "Тест"
        chat_id = 123456
        
        with patch('src.utils.asyncio.get_event_loop') as mock_get_loop, \
             patch('src.utils.split_and_send_long_text') as mock_split:
            
            mock_get_loop.side_effect = Exception("General error")
            
            result = smart_send_text_sync(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username="test_user",
                question="Тест",
                search_type="fast"
            )
        
        assert result is True
        mock_split.assert_called_once_with(
            text, chat_id, mock_app, parse_mode=None
        )


class TestIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio
    async def test_full_workflow_short_message(self, mock_app, mock_message):
        """Тест полного workflow для короткого сообщения."""
        text = "Короткий ответ на вопрос пользователя"
        chat_id = 123456
        username = "test_user"
        question = "Какой-то вопрос"
        
        mock_app.send_message.return_value = mock_message
        
        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils.chat_history_manager') as mock_history:
            
            result = await smart_send_text(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=username,
                question=question,
                search_type="fast",
                parse_mode=ParseMode.MARKDOWN
            )
        
        assert result is True
        mock_app.send_message.assert_called_once()
        
        # Проверяем параметры вызова
        call_args = mock_app.send_message.call_args
        assert call_args[0][0] == chat_id  # chat_id
        assert call_args[0][1] == text     # text
        assert call_args[1]['parse_mode'] == ParseMode.MARKDOWN

    @pytest.mark.asyncio
    async def test_full_workflow_long_message(self, mock_app, mock_message):
        """Тест полного workflow для длинного сообщения."""
        text = "X" * 2000  # Очень длинный текст
        chat_id = 123456
        username = "test_user"
        question = "Сложный вопрос"
        
        mock_app.send_message.return_value = mock_message
        mock_app.send_document.return_value = mock_message
        
        with patch('src.utils.TELEGRAM_MESSAGE_THRESHOLD', 1200), \
             patch('src.utils.md_storage_manager') as mock_storage, \
             patch('src.utils.chat_history_manager') as mock_history:
            
            mock_storage.save_md_report.return_value = "/tmp/test_report.md"
            
            result = await smart_send_text(
                text=text,
                chat_id=chat_id,
                app=mock_app,
                username=username,
                question=question,
                search_type="deep"
            )
        
        assert result is True
        
        # Проверяем что отправлено превью сообщение
        preview_calls = [call for call in mock_app.send_message.call_args_list 
                        if "📄 **Ваш отчет готов!**" in call[0][1]]
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
        doc_call = mock_app.send_document.call_args
        assert doc_call[0][0] == chat_id
        assert doc_call[0][1] == "/tmp/test_report.md"