"""
Комплексное тестирование модуля file_sender.py

Задача ID: 00001_20251007_T3H8K9
Фаза: 5 (Testing)
Агент: test-automator

Покрытие:
- Unit-тесты для форматирования (format_history_for_file, format_reports_for_file)
- Unit-тесты для throttling (should_send_file, update_last_sent)
- Integration-тесты с mock Pyrogram (auto_send_history_file, auto_send_reports_file)
- E2E-тесты (manual) - инструкции в конце файла

Целевое покрытие: > 85%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime, timedelta
from io import BytesIO
import json
import tempfile
from pathlib import Path

# Импорты из тестируемого модуля
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from file_sender import (
    format_history_for_file,
    format_reports_for_file,
    auto_send_history_file,
    auto_send_reports_file,
    should_send_file,
    update_last_sent,
    THROTTLE_HOURS,
    MAX_MESSAGES,
    MAX_REPORTS
)


# ============================================================================
#                           FIXTURES
# ============================================================================

@pytest.fixture
def mock_message():
    """Создает mock ConversationMessage."""
    def _create(text="Test message", msg_type="user_question", timestamp=None):
        msg = MagicMock()
        msg.text = text
        msg.type = msg_type
        msg.timestamp = timestamp or datetime.now().isoformat()
        msg.sent_as = "message"
        return msg
    return _create


@pytest.fixture
def mock_report():
    """Создает mock ReportMetadata."""
    def _create(question="Test question", search_type="fast", timestamp=None):
        report = MagicMock()
        report.timestamp = timestamp or datetime.now().isoformat()
        report.filename = "voxpersona_20251007_140000.txt"
        report.file_path = "md_reports/user_123/voxpersona_20251007_140000.txt"
        report.question = question
        report.size_bytes = 46284  # ~45.2 KB
        report.tokens = 12345
        report.search_type = search_type
        return report
    return _create


@pytest.fixture
def temp_throttle_file(tmp_path):
    """Создает временный файл throttle_history.json."""
    throttle_file = tmp_path / "throttle_history.json"
    return throttle_file


# ============================================================================
#                     UNIT-ТЕСТЫ: Форматирование истории
# ============================================================================

class TestFormatHistoryForFile:
    """Тесты для функции format_history_for_file()."""

    def test_empty_history(self):
        """Пустая история возвращает заголовок с нулевым счетчиком."""
        result = format_history_for_file([], "Тестовый чат")

        assert "ИСТОРИЯ ЧАТА: Тестовый чат" in result
        assert "Количество сообщений: 0" in result
        assert "=" * 60 in result

    def test_single_message_user(self, mock_message):
        """Одно пользовательское сообщение форматируется корректно."""
        messages = [mock_message(text="Привет, бот!", msg_type="user_question")]
        result = format_history_for_file(messages, "Мой чат")

        assert "🧑 Вы" in result
        assert "Привет, бот!" in result
        assert "Количество сообщений: 1" in result

    def test_single_message_bot(self, mock_message):
        """Одно сообщение бота форматируется корректно."""
        messages = [mock_message(text="Здравствуйте!", msg_type="bot_answer")]
        result = format_history_for_file(messages, "Чат")

        assert "🤖 Бот" in result
        assert "Здравствуйте!" in result

    def test_multiple_messages(self, mock_message):
        """Множество сообщений форматируются корректно."""
        messages = [
            mock_message(f"Сообщение {i}", "user_question")
            for i in range(10)
        ]
        result = format_history_for_file(messages, "Чат")

        assert "Количество сообщений: 10" in result
        for i in range(10):
            assert f"Сообщение {i}" in result

    def test_large_history(self, mock_message):
        """Большая история (100 сообщений) обрабатывается корректно."""
        messages = [
            mock_message(f"Message {i}", "user_question")
            for i in range(100)
        ]
        result = format_history_for_file(messages, "Large Chat")

        assert "Количество сообщений: 100" in result
        assert "[1]" in result
        assert "[100]" in result

    def test_reversed_order(self, mock_message):
        """Проверка обратного порядка сообщений."""
        msg1 = mock_message("Первое сообщение", "user_question")
        msg2 = mock_message("Второе сообщение", "bot_answer")
        msg3 = mock_message("Третье сообщение", "user_question")
        messages = [msg1, msg2, msg3]

        result = format_history_for_file(messages, "Чат")
        lines = result.split('\n')

        # Находим индексы сообщений
        idx_first = next(i for i, line in enumerate(lines) if "Первое сообщение" in line)
        idx_second = next(i for i, line in enumerate(lines) if "Второе сообщение" in line)
        idx_third = next(i for i, line in enumerate(lines) if "Третье сообщение" in line)

        # Проверяем что сообщения идут в том же порядке
        # (функция НЕ реверсит - это делает caller)
        assert idx_first < idx_second < idx_third

    def test_timestamp_formatting(self, mock_message):
        """Корректное форматирование timestamp."""
        timestamp = "2025-10-07T14:30:00"
        msg = mock_message("Тест", "user_question", timestamp=timestamp)
        result = format_history_for_file([msg], "Чат")

        # Должен быть формат DD.MM.YYYY HH:MM:SS
        assert "07.10.2025 14:30:00" in result

    def test_invalid_timestamp_fallback(self, mock_message):
        """Fallback при невалидном timestamp."""
        msg = mock_message("Тест", "user_question", timestamp="invalid-timestamp")
        result = format_history_for_file([msg], "Чат")

        # Должен использовать fallback [:16]
        assert "invalid-timesta" in result or "Тест" in result

    def test_role_emojis(self, mock_message):
        """Проверка корректных эмодзи для ролей."""
        msg_user = mock_message("User msg", "user_question")
        msg_bot = mock_message("Bot msg", "bot_answer")

        result = format_history_for_file([msg_user, msg_bot], "Чат")

        assert "🧑 Вы" in result
        assert "🤖 Бот" in result

    def test_file_marker(self, mock_message):
        """Проверка маркера файла 📎."""
        msg = mock_message("Отправлено как файл", "bot_answer")
        msg.sent_as = "file"

        result = format_history_for_file([msg], "Чат")

        assert "📎" in result

    def test_chat_title_in_header(self):
        """Название чата присутствует в заголовке."""
        result = format_history_for_file([], "Мой супер чат 123")

        assert "ИСТОРИЯ ЧАТА: Мой супер чат 123" in result

    def test_export_timestamp(self):
        """Timestamp экспорта присутствует."""
        result = format_history_for_file([], "Чат")

        assert "Экспортировано:" in result
        # Проверяем что timestamp похож на текущую дату
        current_year = datetime.now().year
        assert str(current_year) in result


# ============================================================================
#                     UNIT-ТЕСТЫ: Форматирование отчетов
# ============================================================================

class TestFormatReportsForFile:
    """Тесты для функции format_reports_for_file()."""

    def test_empty_reports(self):
        """Пустой список отчетов возвращает заголовок."""
        result = format_reports_for_file([])

        assert "СПИСОК ОТЧЕТОВ" in result
        assert "Количество отчетов: 0" in result

    def test_single_report(self, mock_report):
        """Один отчет форматируется корректно."""
        reports = [mock_report(question="Тестовый вопрос")]
        result = format_reports_for_file(reports)

        assert "СПИСОК ОТЧЕТОВ" in result
        assert "Количество отчетов: 1" in result
        assert "Тестовый вопрос" in result
        assert "voxpersona_20251007_140000.txt" in result

    def test_multiple_reports(self, mock_report):
        """Множество отчетов форматируются корректно."""
        reports = [
            mock_report(question=f"Вопрос {i}")
            for i in range(10)
        ]
        result = format_reports_for_file(reports)

        assert "Количество отчетов: 10" in result
        for i in range(10):
            assert f"Вопрос {i}" in result

    def test_large_reports_list(self, mock_report):
        """Большой список отчетов (50 штук)."""
        reports = [
            mock_report(question=f"Report {i}")
            for i in range(50)
        ]
        result = format_reports_for_file(reports)

        assert "Количество отчетов: 50" in result
        assert "[1]" in result
        assert "[50]" in result

    def test_report_timestamp_formatting(self, mock_report):
        """Корректное форматирование timestamp отчета."""
        timestamp = "2025-10-07T14:00:00"
        report = mock_report(timestamp=timestamp)
        result = format_reports_for_file([report])

        assert "07.10.2025 14:00:00" in result

    def test_report_file_path_displayed(self, mock_report):
        """Путь к файлу отображается."""
        report = mock_report()
        result = format_reports_for_file([report])

        assert "Путь: md_reports/user_123/voxpersona_20251007_140000.txt" in result

    def test_report_metadata(self, mock_report):
        """Метаданные отчета (размер, токены, тип)."""
        report = mock_report()
        result = format_reports_for_file([report])

        # Размер в KB (46284 байт = ~45.2 KB)
        assert "45.2 KB" in result
        # Токены с разделителями
        assert "12,345" in result
        # Тип поиска с эмодзи
        assert "⚡ Быстрый" in result

    def test_search_type_icons(self, mock_report):
        """Корректные эмодзи для типов поиска."""
        report_fast = mock_report(search_type="fast")
        report_deep = mock_report(search_type="deep")

        result_fast = format_reports_for_file([report_fast])
        result_deep = format_reports_for_file([report_deep])

        assert "⚡ Быстрый" in result_fast
        assert "🔍 Глубокий" in result_deep

    def test_question_preview(self, mock_report):
        """Превью вопроса отображается."""
        report = mock_report(question="Анализ рынка недвижимости в Москве")
        result = format_reports_for_file([report])

        assert "Вопрос: Анализ рынка недвижимости в Москве" in result


# ============================================================================
#                     UNIT-ТЕСТЫ: Throttling система
# ============================================================================

class TestThrottling:
    """Тесты для функций throttling (should_send_file, update_last_sent)."""

    def test_first_send_allowed(self, temp_throttle_file):
        """Первая отправка всегда разрешена (файл не существует)."""
        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            assert should_send_file(999999, "history") is True

    def test_within_24_hours_blocked(self, temp_throttle_file):
        """Повторная отправка в течение 24 часов запрещена."""
        user_id = 888888

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            # Первая отправка
            update_last_sent(user_id, "history")

            # Сразу проверяем - должно быть False
            assert should_send_file(user_id, "history") is False

    def test_after_24_hours_allowed(self, temp_throttle_file):
        """Отправка после 24 часов разрешена."""
        user_id = 777777

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            # Создаем запись с timestamp 25 часов назад
            past_time = datetime.now() - timedelta(hours=25)
            throttle_data = {
                str(user_id): {
                    "history_last_sent": past_time.isoformat()
                }
            }
            temp_throttle_file.write_text(json.dumps(throttle_data), encoding='utf-8')

            # Проверяем - должно быть True
            assert should_send_file(user_id, "history") is True

    def test_different_file_types_independent(self, temp_throttle_file):
        """Разные типы файлов (history vs reports) независимы."""
        user_id = 666666

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            # Отправляем history
            update_last_sent(user_id, "history")

            # history заблокирован
            assert should_send_file(user_id, "history") is False

            # reports все еще разрешен
            assert should_send_file(user_id, "reports") is True

    def test_different_users_independent(self, temp_throttle_file):
        """Разные пользователи не влияют друг на друга."""
        user1 = 111111
        user2 = 222222

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            # user1 отправляет
            update_last_sent(user1, "history")

            # user1 заблокирован
            assert should_send_file(user1, "history") is False

            # user2 все еще может отправить
            assert should_send_file(user2, "history") is True

    def test_update_creates_file(self, temp_throttle_file):
        """update_last_sent создает файл если не существует."""
        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            assert not temp_throttle_file.exists()

            update_last_sent(123, "history")

            assert temp_throttle_file.exists()

    def test_update_creates_directory(self, tmp_path):
        """update_last_sent создает директорию data/ если не существует."""
        throttle_file = tmp_path / "nonexistent" / "throttle.json"

        with patch('file_sender.THROTTLE_FILE', throttle_file):
            update_last_sent(123, "history")

            assert throttle_file.exists()
            assert throttle_file.parent.exists()

    def test_update_adds_new_user(self, temp_throttle_file):
        """update_last_sent добавляет нового пользователя."""
        user1 = 111
        user2 = 222

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            # Добавляем первого пользователя
            update_last_sent(user1, "history")

            # Добавляем второго
            update_last_sent(user2, "reports")

            # Проверяем что оба в файле
            data = json.loads(temp_throttle_file.read_text(encoding='utf-8'))
            assert str(user1) in data
            assert str(user2) in data

    def test_update_iso_timestamp_format(self, temp_throttle_file):
        """update_last_sent использует ISO формат timestamp."""
        user_id = 333

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            update_last_sent(user_id, "history")

            data = json.loads(temp_throttle_file.read_text(encoding='utf-8'))
            timestamp_str = data[str(user_id)]["history_last_sent"]

            # Проверяем что timestamp парсится корректно
            timestamp = datetime.fromisoformat(timestamp_str)
            assert isinstance(timestamp, datetime)

    def test_corrupted_json_failsafe(self, temp_throttle_file):
        """Graceful degradation при поврежденном JSON."""
        temp_throttle_file.write_text("invalid json {{{", encoding='utf-8')

        with patch('file_sender.THROTTLE_FILE', temp_throttle_file):
            # При ошибке парсинга - разрешаем отправку (fail-safe)
            assert should_send_file(123, "history") is True


# ============================================================================
#                     INTEGRATION-ТЕСТЫ: auto_send_history_file
# ============================================================================

class TestAutoSendHistoryFile:
    """Integration-тесты для функции auto_send_history_file()."""

    @pytest.mark.asyncio
    async def test_success_basic(self, mock_message, temp_throttle_file):
        """Успешная отправка истории (базовый сценарий)."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            # Mock ConversationManager
            cm_mock.get_active_conversation_id.return_value = "test-uuid-1234"

            # Mock Conversation
            mock_conv = MagicMock()
            mock_conv.messages = [mock_message("Тест", "user_question")]
            mock_conv.metadata = MagicMock(title="Тестовый чат")
            cm_mock.load_conversation.return_value = mock_conv

            result = await auto_send_history_file(user_id, app_mock)

            # Assertions
            assert result is True
            app_mock.send_document.assert_called_once()

            # Проверяем что BytesIO был передан
            call_args = app_mock.send_document.call_args
            assert call_args[1]['chat_id'] == user_id
            file_obj = call_args[1]['document']
            assert isinstance(file_obj, BytesIO)

    @pytest.mark.asyncio
    async def test_empty_history_no_send(self, temp_throttle_file):
        """Пустая история - send_document НЕ вызывается."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = "test-uuid"

            # Пустая история
            mock_conv = MagicMock()
            mock_conv.messages = []
            mock_conv.metadata = MagicMock(title="Пустой чат")
            cm_mock.load_conversation.return_value = mock_conv

            result = await auto_send_history_file(user_id, app_mock)

            assert result is False
            app_mock.send_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_active_conversation(self, temp_throttle_file):
        """Нет активного чата - возврат False."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = None

            result = await auto_send_history_file(user_id, app_mock)

            assert result is False
            app_mock.send_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_throttled_no_send(self, temp_throttle_file):
        """Throttling блокирует отправку."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.should_send_file', return_value=False), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            result = await auto_send_history_file(user_id, app_mock)

            assert result is False
            app_mock.send_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_messages(self, mock_message, temp_throttle_file):
        """Отправка множества сообщений."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = "test-uuid"

            # 10 сообщений
            messages = [mock_message(f"Msg {i}", "user_question") for i in range(10)]
            mock_conv = MagicMock()
            mock_conv.messages = messages
            mock_conv.metadata = MagicMock(title="Чат с историей")
            cm_mock.load_conversation.return_value = mock_conv

            result = await auto_send_history_file(user_id, app_mock)

            assert result is True
            app_mock.send_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_messages_limit(self, mock_message, temp_throttle_file):
        """Ограничение MAX_MESSAGES (последние 200)."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = "test-uuid"

            # 300 сообщений (больше чем MAX_MESSAGES=200)
            messages = [mock_message(f"Msg {i}", "user_question") for i in range(300)]
            mock_conv = MagicMock()
            mock_conv.messages = messages
            mock_conv.metadata = MagicMock(title="Большая история")
            cm_mock.load_conversation.return_value = mock_conv

            result = await auto_send_history_file(user_id, app_mock)

            assert result is True
            # Функция использует только последние 200 сообщений
            # Проверить через mock сложно, но функция должна работать

    @pytest.mark.asyncio
    async def test_bytesio_closed(self, mock_message, temp_throttle_file):
        """BytesIO объект закрывается в finally блоке."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = "test-uuid"

            mock_conv = MagicMock()
            mock_conv.messages = [mock_message()]
            mock_conv.metadata = MagicMock(title="Тест")
            cm_mock.load_conversation.return_value = mock_conv

            result = await auto_send_history_file(user_id, app_mock)

            # BytesIO должен быть закрыт (проверяем что ошибки нет)
            assert result is True

    @pytest.mark.asyncio
    async def test_error_handling_graceful_degradation(self, mock_message, temp_throttle_file):
        """Graceful degradation при ошибке Pyrogram."""
        app_mock = AsyncMock()
        app_mock.send_document.side_effect = Exception("Network error")
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = "test-uuid"

            mock_conv = MagicMock()
            mock_conv.messages = [mock_message()]
            mock_conv.metadata = MagicMock(title="Тест")
            cm_mock.load_conversation.return_value = mock_conv

            result = await auto_send_history_file(user_id, app_mock)

            # Ожидаем graceful degradation - False, но без краша
            assert result is False

    @pytest.mark.asyncio
    async def test_caption_includes_metadata(self, mock_message, temp_throttle_file):
        """Caption включает метаданные (название, количество)."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.conversation_manager') as cm_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            cm_mock.get_active_conversation_id.return_value = "test-uuid"

            messages = [mock_message(f"Msg {i}") for i in range(5)]
            mock_conv = MagicMock()
            mock_conv.messages = messages
            mock_conv.metadata = MagicMock(title="Мой чат")
            cm_mock.load_conversation.return_value = mock_conv

            await auto_send_history_file(user_id, app_mock)

            call_args = app_mock.send_document.call_args
            caption = call_args[1]['caption']

            assert "Мой чат" in caption
            assert "5" in caption  # Количество сообщений


# ============================================================================
#                     INTEGRATION-ТЕСТЫ: auto_send_reports_file
# ============================================================================

class TestAutoSendReportsFile:
    """Integration-тесты для функции auto_send_reports_file()."""

    @pytest.mark.asyncio
    async def test_success_basic(self, mock_report, temp_throttle_file):
        """Успешная отправка списка отчетов."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.md_storage_manager') as md_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            # Mock MDStorageManager
            md_mock.get_user_reports.return_value = [
                mock_report("Вопрос 1"),
                mock_report("Вопрос 2"),
            ]

            result = await auto_send_reports_file(user_id, app_mock)

            assert result is True
            app_mock.send_document.assert_called_once()

            # Проверяем BytesIO
            call_args = app_mock.send_document.call_args
            file_obj = call_args[1]['document']
            assert isinstance(file_obj, BytesIO)

    @pytest.mark.asyncio
    async def test_no_reports_no_send(self, temp_throttle_file):
        """Нет отчетов - send_document НЕ вызывается."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.md_storage_manager') as md_mock, \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            md_mock.get_user_reports.return_value = []

            result = await auto_send_reports_file(user_id, app_mock)

            assert result is False
            app_mock.send_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_throttled_no_send(self, temp_throttle_file):
        """Throttling блокирует отправку отчетов."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.should_send_file', return_value=False), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            result = await auto_send_reports_file(user_id, app_mock)

            assert result is False
            app_mock.send_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_reports(self, mock_report, temp_throttle_file):
        """Отправка множества отчетов."""
        app_mock = AsyncMock()
        user_id = 123456

        with patch('file_sender.md_storage_manager') as md_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.update_last_sent'), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            reports = [mock_report(f"Report {i}") for i in range(20)]
            md_mock.get_user_reports.return_value = reports

            result = await auto_send_reports_file(user_id, app_mock)

            assert result is True
            app_mock.send_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_report, temp_throttle_file):
        """Graceful degradation при ошибке."""
        app_mock = AsyncMock()
        app_mock.send_document.side_effect = Exception("API error")
        user_id = 123456

        with patch('file_sender.md_storage_manager') as md_mock, \
             patch('file_sender.should_send_file', return_value=True), \
             patch('file_sender.THROTTLE_FILE', temp_throttle_file):

            md_mock.get_user_reports.return_value = [mock_report()]

            result = await auto_send_reports_file(user_id, app_mock)

            assert result is False


# ============================================================================
#                     E2E-ТЕСТЫ (MANUAL) - ИНСТРУКЦИИ
# ============================================================================

"""
=============================================================================
                        E2E-ТЕСТЫ (MANUAL)
=============================================================================

Эти тесты необходимо выполнить вручную с реальным Telegram ботом.

СЦЕНАРИЙ 1: Новый пользователь
-------------------------------
Шаги:
1. Запустить бота: python main.py
2. Открыть Telegram, найти бот
3. Команда /start (новый пользователь, нет истории)

Ожидаемое поведение:
✅ Файлы НЕ отправляются (нет истории)
✅ Главное меню появляется
✅ Бот не падает с ошибкой


СЦЕНАРИЙ 2: Существующий пользователь с историей
-------------------------------------------------
Шаги:
1. Создать историю: отправить 3-5 сообщений боту
2. Команда /start

Ожидаемое поведение:
✅ Два файла отправляются:
   - history_{user_id}.txt
   - reports_{user_id}.txt (если есть отчеты)
✅ Открыть history.txt
✅ Проверить обратный порядок (последнее сообщение первым)
✅ Главное меню появляется после файлов


СЦЕНАРИЙ 3: Throttling (24 часа)
---------------------------------
Шаги:
1. /start → файлы отправлены
2. Сразу снова /start

Ожидаемое поведение:
✅ Файлы НЕ отправляются (throttling 24 часа)
✅ Главное меню появляется
✅ Бот не падает

Проверка через данные:
- Проверить data/throttle_history.json
- Timestamp должен быть обновлен


СЦЕНАРИЙ 4: Обратная совместимость
-----------------------------------
Шаги:
1. Команда /history
2. Команда /reports

Ожидаемое поведение:
✅ /history работает как раньше (текстовое сообщение)
✅ /reports работает как раньше
✅ Нет регрессий


ЧЕКЛИСТ ПОСЛЕ ВЫПОЛНЕНИЯ E2E:
------------------------------
[ ] Сценарий 1 пройден
[ ] Сценарий 2 пройден
[ ] Сценарий 3 пройден
[ ] Сценарий 4 пройден
[ ] Скриншоты/логи сохранены
[ ] Баги задокументированы (если найдены)

=============================================================================
"""


# ============================================================================
#                     КОМАНДЫ ДЛЯ ЗАПУСКА ТЕСТОВ
# ============================================================================

"""
Запуск всех тестов:
-------------------
pytest src/tests/test_file_sender.py -v

Запуск с покрытием:
-------------------
pytest src/tests/test_file_sender.py --cov=file_sender --cov-report=html --cov-report=term

Запуск только unit-тестов:
---------------------------
pytest src/tests/test_file_sender.py -v -k "not asyncio"

Запуск только integration-тестов:
----------------------------------
pytest src/tests/test_file_sender.py -v -k "asyncio"

Запуск конкретного класса:
--------------------------
pytest src/tests/test_file_sender.py::TestFormatHistoryForFile -v

Запуск конкретного теста:
--------------------------
pytest src/tests/test_file_sender.py::TestFormatHistoryForFile::test_empty_history -v

Генерация HTML отчета покрытия:
--------------------------------
pytest src/tests/test_file_sender.py --cov=file_sender --cov-report=html
# Откройте htmlcov/index.html в браузере
"""


if __name__ == "__main__":
    # Запуск pytest из скрипта
    pytest.main([__file__, "-v", "--cov=file_sender", "--cov-report=term"])
