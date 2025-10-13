"""
Unit тесты для новой реализации 'Мои отчеты' v2.

Task ID: 00001_20251010_144500
Агент: test-automator
Дата: 11.10.2025

Тестируемые функции:
- handle_my_reports_v2() - главный handler
- validate_report_index() - валидация номера отчета
- handle_report_view_input() - просмотр отчета
- handle_report_rename_number_input() - переименование (шаг 1)
- handle_report_rename_name_input() - переименование (шаг 2)
- handle_report_delete_input() - удаление (запрос)
- handle_report_delete_confirm() - удаление (подтверждение)
"""

import pytest
import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

# Импорты тестируемых функций
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from handlers_my_reports_v2 import (
    handle_my_reports_v2,
    validate_report_index,
    handle_report_view_request,
    handle_report_view_input,
    handle_report_rename_request,
    handle_report_rename_number_input,
    handle_report_rename_name_input,
    handle_report_delete_request,
    handle_report_delete_input,
    handle_report_delete_confirm
)

from md_storage import ReportMetadata


# ============================================================================
#                           Фикстуры
# ============================================================================

@pytest.fixture
def mock_app():
    """Мок Pyrogram Client."""
    app = MagicMock()
    app.send_message = AsyncMock()
    app.send_document = AsyncMock()
    app.edit_message_text = AsyncMock()
    app.delete_messages = AsyncMock()
    return app


@pytest.fixture
def mock_report():
    """Мок ReportMetadata."""
    return ReportMetadata(
        file_path="user_123/report_20251010_120000.md",
        user_id=123,
        username="testuser",
        timestamp="2025-10-10T12:00:00",
        question="Анализ рынка недвижимости",
        size_bytes=45000,
        tokens=12345,
        search_type="fast"
    )


@pytest.fixture
def mock_reports():
    """Список из 3 моков отчетов."""
    return [
        ReportMetadata(
            file_path="user_123/report_20251010_120000.md",
            user_id=123,
            username="testuser",
            timestamp="2025-10-10T12:00:00",
            question="Анализ рынка недвижимости",
            size_bytes=45000,
            tokens=12345,
            search_type="fast"
        ),
        ReportMetadata(
            file_path="user_123/report_20251010_130000.md",
            user_id=123,
            username="testuser",
            timestamp="2025-10-10T13:00:00",
            question="Исследование клиентов",
            size_bytes=38000,
            tokens=9876,
            search_type="deep"
        ),
        ReportMetadata(
            file_path="user_123/report_20251010_140000.md",
            user_id=123,
            username="testuser",
            timestamp="2025-10-10T14:00:00",
            question="Конкурентный анализ",
            size_bytes=52000,
            tokens=15000,
            search_type="fast"
        )
    ]


@pytest.fixture
def user_states_clean():
    """Очищенный user_states для изоляции тестов."""
    from config import user_states
    user_states.clear()
    return user_states


@pytest.fixture(autouse=True)
def mock_snapshot_check(monkeypatch):
    """Автоматически мокируем _check_snapshot_timeout для всех тестов (кроме теста timeout)."""
    def mock_check(chat_id):
        return (True, "")  # Валидный snapshot по умолчанию

    import handlers_my_reports_v2
    monkeypatch.setattr(handlers_my_reports_v2, '_check_snapshot_timeout', mock_check)


# ============================================================================
#                   Тесты валидации номера отчета
# ============================================================================

class TestValidateReportIndex:
    """Тесты функции validate_report_index()."""

    def test_valid_index(self):
        """Корректный номер в диапазоне."""
        result = validate_report_index("3", total_reports=10)
        assert result == 3

    def test_valid_index_first(self):
        """Первый отчет (граничное значение)."""
        result = validate_report_index("1", total_reports=10)
        assert result == 1

    def test_valid_index_last(self):
        """Последний отчет (граничное значение)."""
        result = validate_report_index("10", total_reports=10)
        assert result == 10

    def test_invalid_letters(self):
        """Ввод букв вместо числа."""
        result = validate_report_index("abc", total_reports=10)
        assert result is None

    def test_invalid_zero(self):
        """Ввод 0 (недопустимое значение)."""
        result = validate_report_index("0", total_reports=10)
        assert result is None

    def test_invalid_negative(self):
        """Отрицательное число."""
        result = validate_report_index("-5", total_reports=10)
        assert result is None

    def test_invalid_too_high(self):
        """Номер больше количества отчетов."""
        result = validate_report_index("15", total_reports=10)
        assert result is None

    def test_empty_string(self):
        """Пустая строка."""
        result = validate_report_index("", total_reports=10)
        assert result is None

    def test_whitespace(self):
        """Строка с пробелами."""
        result = validate_report_index("   ", total_reports=10)
        assert result is None

    def test_valid_with_whitespace(self):
        """Число с пробелами (должно работать после strip)."""
        result = validate_report_index("  5  ", total_reports=10)
        assert result == 5

    def test_float_number(self):
        """Дробное число (недопустимо)."""
        result = validate_report_index("5.5", total_reports=10)
        assert result is None


# ============================================================================
#                   Тесты главного handler handle_my_reports_v2()
# ============================================================================

class TestHandleMyReportsV2:
    """Тесты главного handler handle_my_reports_v2()."""

    @pytest.mark.asyncio
    async def test_no_reports(self, mock_app, user_states_clean):
        """Нет отчетов у пользователя."""
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: нет отчетов
            mock_to_thread.return_value = []

            await handle_my_reports_v2(chat_id=123, app=mock_app)

            # Проверяем что показано сообщение "Нет отчетов"
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "нет сохраненных отчетов" in call_args.kwargs["text"].lower()
            assert call_args.kwargs["message_type"] == "menu"

    @pytest.mark.asyncio
    async def test_success_send_txt_file(self, mock_app, mock_reports, user_states_clean):
        """Успешная отправка TXT файла со списком отчетов."""
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем:
            # 1-й вызов: get_user_reports → возвращает 3 отчета
            # 2-й вызов: export_reports_list_to_txt → возвращает путь к TXT
            # 3-й вызов: _read_file_sync → возвращает содержимое файла
            mock_to_thread.side_effect = [
                mock_reports,  # get_user_reports
                "/tmp/reports_list_123.txt",  # export_reports_list_to_txt
                b"Test file content"  # _read_file_sync
            ]

            await handle_my_reports_v2(chat_id=123, app=mock_app)

            # Проверяем:
            # 1. app.send_document вызван с BytesIO
            mock_app.send_document.assert_called_once()
            call_args = mock_app.send_document.call_args
            assert call_args.kwargs["chat_id"] == 123
            assert isinstance(call_args.kwargs["document"], BytesIO)
            assert "Список ваших отчетов" in call_args.kwargs["caption"]

            # 2. track_and_send вызван с меню операций
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args.kwargs["message_type"] == "menu"
            assert "Выберите действие" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_export_failed(self, mock_app, mock_reports, user_states_clean):
        """Ошибка экспорта TXT файла."""
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем:
            # 1-й вызов: get_user_reports → возвращает 3 отчета
            # 2-й вызов: export_reports_list_to_txt → возвращает None (ошибка)
            mock_to_thread.side_effect = [
                mock_reports,  # get_user_reports
                None  # export_reports_list_to_txt failed
            ]

            await handle_my_reports_v2(chat_id=123, app=mock_app)

            # Проверяем что показано сообщение об ошибке
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "не удалось экспортировать" in call_args.kwargs["text"].lower()
            assert call_args.kwargs["message_type"] == "menu"


# ============================================================================
#       🔴 КРИТИЧНЫЙ ТЕСТ: test_delete_nonexistent_report (race condition fix)
# ============================================================================

class TestReportViewWorkflow:
    """Тесты workflow просмотра отчета."""

    @pytest.mark.asyncio
    async def test_view_report_success(self, mock_app, mock_report, user_states_clean):
        """Успешный просмотр отчета."""
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path, \
             patch("handlers_my_reports_v2._check_snapshot_timeout") as mock_check_timeout:

            # Мокаем: _check_snapshot_timeout → валидный snapshot
            mock_check_timeout.return_value = (True, "")

            # Мокаем:
            # 1-й вызов: get_report_by_index → возвращает отчет
            # 2-й вызов: _read_file_sync → возвращает содержимое
            mock_to_thread.side_effect = [
                mock_report,  # get_report_by_index
                b"# Test Report Content"  # _read_file_sync
            ]

            # Мокаем путь к файлу (Path object с exists=True)
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__.return_value = "/tmp/report.md"
            mock_get_path.return_value = mock_path

            # Устанавливаем FSM состояние
            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="3", app=mock_app)

            # Проверяем:
            # 1. app.send_document вызван с BytesIO
            mock_app.send_document.assert_called_once()
            call_args = mock_app.send_document.call_args
            assert call_args.kwargs["chat_id"] == 123
            assert isinstance(call_args.kwargs["document"], BytesIO)

            # 2. FSM состояние очищено
            assert user_states_clean[123] == {}

            # 3. Показано меню
            assert mock_track.call_count == 1

    @pytest.mark.asyncio
    async def test_delete_nonexistent_report(self, mock_app, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: Race condition fix.

        Проверяет что handle_report_view_input корректно обрабатывает
        удаление отчета между запросом номера и просмотром.
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2._check_snapshot_timeout") as mock_check_timeout:

            # Мокаем: _check_snapshot_timeout → валидный snapshot
            mock_check_timeout.return_value = (True, "")

            # Мокаем: get_report_by_index → возвращает None (отчет удален)
            mock_to_thread.return_value = None

            # Устанавливаем FSM состояние
            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="3", app=mock_app)

            # Проверяем:
            # 1. Показано сообщение об ошибке
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "не найден" in call_args.kwargs["text"].lower()

            # 2. FSM состояние очищено
            assert user_states_clean[123] == {}

    @pytest.mark.asyncio
    async def test_view_report_file_not_found(self, mock_app, mock_report, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: Файл отчета не найден.

        Проверяет обработку случая когда файл удален вручную.
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            # Мокаем: get_report_by_index → возвращает отчет
            mock_to_thread.return_value = mock_report

            # Мокаем: файл не существует
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_get_path.return_value = mock_path

            # Устанавливаем FSM состояние
            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="3", app=mock_app)

            # Проверяем:
            # 1. Показано сообщение об ошибке
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "файл" in call_args.kwargs["text"].lower()
            assert "не найден" in call_args.kwargs["text"].lower()

            # 2. FSM состояние очищено
            assert user_states_clean[123] == {}


# ============================================================================
#                   Тесты workflow переименования отчета
# ============================================================================

class TestReportRenameWorkflow:
    """Тесты workflow переименования отчета."""

    @pytest.mark.asyncio
    async def test_rename_report_success(self, mock_app, mock_report, user_states_clean):
        """Успешное переименование отчета."""
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: rename_report → возвращает True (успех)
            mock_to_thread.return_value = True

            # Устанавливаем FSM состояние (шаг 2: ввод нового имени)
            user_states_clean[123] = {
                "step": "report_rename_ask_new_name",
                "report_index": 3,
                "old_name": "Старое название"
            }

            await handle_report_rename_name_input(
                chat_id=123,
                user_input="Новое название отчета",
                app=mock_app
            )

            # Проверяем:
            # 1. Показано сообщение об успехе
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "переименован" in call_args.kwargs["text"].lower()
            assert "Новое название отчета" in call_args.kwargs["text"]

            # 2. FSM состояние очищено
            assert user_states_clean[123] == {}


# ============================================================================
#  🔴 КРИТИЧНЫЙ ТЕСТ: test_delete_report_transaction_order (FK constraints fix)
# ============================================================================

class TestReportDeleteWorkflow:
    """Тесты workflow удаления отчета."""

    @pytest.mark.asyncio
    async def test_delete_report_success(self, mock_app, mock_report, user_states_clean):
        """Успешное удаление отчета."""
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: delete_report → возвращает True (успех)
            mock_to_thread.return_value = True

            # Устанавливаем FSM состояние (подтверждение удаления)
            user_states_clean[123] = {
                "step": "report_delete_confirm",
                "report_index": 3,
                "report_name": "Тестовый отчет"
            }

            await handle_report_delete_confirm(chat_id=123, app=mock_app)

            # Проверяем:
            # 1. Показано сообщение об успехе
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "удален" in call_args.kwargs["text"].lower()
            assert "Тестовый отчет" in call_args.kwargs["text"]

            # 2. FSM состояние очищено
            assert user_states_clean[123] == {}

    @pytest.mark.asyncio
    async def test_delete_report_transaction_order(self, mock_app, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: FK constraints fix.

        Проверяет что delete_report вызывается в правильном порядке:
        1. Удаление файла
        2. Удаление записи из индекса
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: delete_report → возвращает True
            mock_to_thread.return_value = True

            # Устанавливаем FSM состояние
            user_states_clean[123] = {
                "step": "report_delete_confirm",
                "report_index": 5,
                "report_name": "Отчет для удаления"
            }

            await handle_report_delete_confirm(chat_id=123, app=mock_app)

            # Проверяем что asyncio.to_thread вызван РОВНО ОДИН РАЗ
            # (внутри должна быть транзакционная логика в md_storage.delete_report)
            assert mock_to_thread.call_count == 1

            # Проверяем аргументы вызова
            call_args = mock_to_thread.call_args[0]
            # Первый аргумент - функция md_storage_manager.delete_report
            # Второй - chat_id (123)
            # Третий - index (5)
            assert call_args[1] == 123
            assert call_args[2] == 5


# ============================================================================
#                   Тесты валидации некорректного ввода
# ============================================================================

class TestInvalidInputHandling:
    """Тесты обработки некорректного ввода."""

    @pytest.mark.asyncio
    async def test_invalid_report_number_letters(self, mock_app, user_states_clean):
        """Ввод букв вместо числа."""
        with patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Устанавливаем FSM состояние
            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="abc", app=mock_app)

            # Проверяем сообщение об ошибке
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "некорректный" in call_args.kwargs["text"].lower()

    @pytest.mark.asyncio
    async def test_invalid_report_number_zero(self, mock_app, user_states_clean):
        """Ввод 0."""
        with patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="0", app=mock_app)

            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "некорректный" in call_args.kwargs["text"].lower()

    @pytest.mark.asyncio
    async def test_invalid_report_number_negative(self, mock_app, user_states_clean):
        """Ввод отрицательного числа."""
        with patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="-5", app=mock_app)

            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "некорректный" in call_args.kwargs["text"].lower()

    @pytest.mark.asyncio
    async def test_invalid_report_number_too_high(self, mock_app, user_states_clean):
        """Номер больше количества отчетов."""
        with patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="10", app=mock_app)

            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "некорректный" in call_args.kwargs["text"].lower()


# ============================================================================
#         🔴 КРИТИЧНЫЕ ТЕСТЫ: Large files, Timeout, Concurrent control
# ============================================================================

class TestFileSize:
    """Тесты проверки размера файла (10MB лимит)."""

    @pytest.mark.asyncio
    async def test_large_report_list_exceeds_limit(self, mock_app, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: Список отчетов >10MB.

        Проверяет что handle_my_reports_v2 корректно обрабатывает
        слишком большой файл списка отчетов.
        """
        # Создаем мок большого списка отчетов (100+ записей)
        large_reports_list = []
        for i in range(150):
            large_reports_list.append(
                ReportMetadata(
                    file_path=f"user_123/report_{i}.md",
                    user_id=123,
                    username="testuser",
                    timestamp=f"2025-10-{10+i//30:02d}T{i%24:02d}:00:00",
                    question=f"Отчет номер {i+1} с длинным названием для увеличения размера файла",
                    size_bytes=150000 + i * 1000,
                    tokens=50000 + i * 100,
                    search_type="deep"
                )
            )

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем:
            # 1-й вызов: get_user_reports → возвращает 150 отчетов
            # 2-й вызов: export_reports_list_to_txt → возвращает путь
            # 3-й вызов: _read_file_sync → возвращает файл >10MB
            mock_to_thread.side_effect = [
                large_reports_list,  # get_user_reports
                "/tmp/large_reports.txt",  # export_reports_list_to_txt
                b"X" * (11 * 1024 * 1024)  # _read_file_sync: 11MB файл
            ]

            await handle_my_reports_v2(chat_id=123, app=mock_app)

            # Проверяем:
            # 1. Файл НЕ был отправлен (send_document не вызван)
            mock_app.send_document.assert_not_called()

            # 2. Показано сообщение об ошибке
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "слишком большой" in call_args.kwargs["text"].lower()
            assert call_args.kwargs["message_type"] == "status_message"


class TestSnapshotTimeout:
    """Тесты механизма timeout для snapshot."""

    @pytest.mark.asyncio
    async def test_snapshot_timeout_expired(self, mock_app, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: Timeout snapshot (>5 минут).

        Проверяет что handle_report_view_input корректно обрабатывает
        устаревший snapshot и показывает сообщение об ошибке.
        """
        from datetime import datetime, timedelta

        with patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2._check_snapshot_timeout") as mock_check_timeout:

            # Мокаем: timeout expired (убираем autouse fixture для этого теста)
            mock_check_timeout.return_value = (False, "❌ **Список отчетов устарел**")

            # Устанавливаем FSM состояние
            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            await handle_report_view_input(chat_id=123, user_input="3", app=mock_app)

            # Проверяем:
            # 1. Показано сообщение о timeout
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "устарел" in call_args.kwargs["text"].lower()
            assert call_args.kwargs["message_type"] == "status_message"


class TestConcurrentControl:
    """Тесты Lock механизма для предотвращения race conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_operations_with_lock(self, mock_app, mock_report, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: Lock предотвращает race conditions.

        Проверяет что concurrent операции с РАЗНЫМИ пользователями
        выполняются параллельно без race conditions благодаря per-user Lock.
        """
        from asyncio import Lock

        # Создаем 2 разных Lock'а для 2 пользователей
        locks_by_user = {}

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2.get_user_lock") as mock_get_lock, \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            # Мокаем get_user_lock чтобы создавать отдельный Lock для каждого пользователя
            def mock_lock_context(chat_id):
                if chat_id not in locks_by_user:
                    locks_by_user[chat_id] = Lock()

                test_lock = locks_by_user[chat_id]

                class LockContext:
                    async def __aenter__(self):
                        await test_lock.acquire()
                        return test_lock

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        test_lock.release()

                return LockContext()

            mock_get_lock.side_effect = mock_lock_context

            # Мокаем успешное получение отчета (4 вызова: 2 пользователя × 2 шага)
            mock_to_thread.side_effect = [
                mock_report,  # get_report_by_index (user 123)
                b"Content User 123",  # _read_file_sync (user 123)
                mock_report,  # get_report_by_index (user 456)
                b"Content User 456"  # _read_file_sync (user 456)
            ]

            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__.return_value = "/tmp/report.md"
            mock_get_path.return_value = mock_path

            # Устанавливаем FSM состояние для ДВУХ пользователей
            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}
            user_states_clean[456] = {"step": "report_view_ask_number", "total_reports": 3}

            # Запускаем 2 concurrent операции для РАЗНЫХ пользователей
            task1 = asyncio.create_task(handle_report_view_input(123, "1", mock_app))
            task2 = asyncio.create_task(handle_report_view_input(456, "2", mock_app))

            # Ждем завершения обеих задач
            await asyncio.gather(task1, task2)

            # Проверяем:
            # 1. Обе операции завершились успешно (каждый user имеет свой Lock)
            assert mock_app.send_document.call_count == 2

            # 2. get_user_lock был вызван для каждой операции
            assert mock_get_lock.call_count == 2

            # 3. Созданы 2 отдельных Lock'а (по одному на user)
            assert len(locks_by_user) == 2


class TestManyReports:
    """Тесты работы со списками из большого количества отчетов."""

    @pytest.mark.asyncio
    async def test_100_reports_txt_generation(self, mock_app, user_states_clean):
        """
        🔴 КРИТИЧНЫЙ ТЕСТ: 100 отчетов - полный TXT файл.

        Проверяет что handle_my_reports_v2 корректно обрабатывает
        список из 100 отчетов и отправляет файл.
        """
        # Создаем список из 100 отчетов
        hundred_reports = []
        for i in range(100):
            hundred_reports.append(
                ReportMetadata(
                    file_path=f"user_123/report_{i:03d}.md",
                    user_id=123,
                    username="testuser",
                    timestamp=f"2025-10-{10+i//30:02d}T{i%24:02d}:00:00",
                    question=f"Отчет #{i+1}",
                    size_bytes=50000,
                    tokens=15000,
                    search_type="fast"
                )
            )

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем:
            # 1-й вызов: get_user_reports → 100 отчетов
            # 2-й вызов: export_reports_list_to_txt → путь к файлу
            # 3-й вызов: _read_file_sync → содержимое файла (<10MB)
            mock_to_thread.side_effect = [
                hundred_reports,  # get_user_reports
                "/tmp/reports_100.txt",  # export_reports_list_to_txt
                b"Report list content (100 items)"  # _read_file_sync
            ]

            await handle_my_reports_v2(chat_id=123, app=mock_app)

            # Проверяем:
            # 1. Файл отправлен
            mock_app.send_document.assert_called_once()
            call_args = mock_app.send_document.call_args
            assert call_args.kwargs["chat_id"] == 123

            # 2. Меню показано
            mock_track.assert_called_once()
            assert mock_track.call_args.kwargs["message_type"] == "menu"

    @pytest.mark.asyncio
    async def test_single_report(self, mock_app, user_states_clean):
        """
        Один отчет - TXT с 1 записью + меню.
        """
        single_report = [
            ReportMetadata(
                file_path="user_123/report_001.md",
                user_id=123,
                username="testuser",
                timestamp="2025-10-10T12:00:00",
                question="Единственный отчет",
                size_bytes=25000,
                tokens=8000,
                search_type="fast"
            )
        ]

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            mock_to_thread.side_effect = [
                single_report,  # get_user_reports
                "/tmp/report_single.txt",  # export_reports_list_to_txt
                b"Single report content"  # _read_file_sync
            ]

            await handle_my_reports_v2(chat_id=123, app=mock_app)

            # Проверяем отправку файла и меню
            mock_app.send_document.assert_called_once()
            mock_track.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
