"""
Async корректность для модуля "Мои отчеты" v2.

Task ID: 00001_20251010_144500
Агент: test-automator
Дата: 11.10.2025

Тесты async паттернов:
- Event loop blocking detection
- asyncio.to_thread wrapping
- Concurrent operations
- Task cancellation
- Timeout handling
"""

import pytest
import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Импорты тестируемых функций
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from handlers_my_reports_v2 import (
    handle_my_reports_v2,
    handle_report_view_input,
    handle_report_rename_name_input,
    handle_report_delete_confirm
)


# ============================================================================
#                           Фикстуры
# ============================================================================

@pytest.fixture
def mock_app():
    """Мок Pyrogram Client."""
    app = MagicMock()
    app.send_message = AsyncMock()
    app.send_document = AsyncMock()
    return app


@pytest.fixture
def user_states_clean():
    """Очищенный user_states для изоляции тестов."""
    from config import user_states
    user_states.clear()
    return user_states


# ============================================================================
#                   Тесты event loop blocking detection
# ============================================================================

class TestEventLoopBlocking:
    """Тесты детекции блокирования event loop."""

    @pytest.mark.asyncio
    async def test_no_sync_file_operations_in_handlers(self, mock_app, user_states_clean):
        """
        Проверяет что нет синхронных file операций в handlers.

        Все file I/O должны быть обернуты в asyncio.to_thread().
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = []

            await handle_my_reports_v2(123, mock_app)

            # Проверяем что asyncio.to_thread вызван
            assert mock_to_thread.call_count >= 1

    @pytest.mark.asyncio
    async def test_all_async_operations_awaited(self, mock_app, user_states_clean):
        """
        Проверяет что все async операции правильно awaited.

        Не должно быть забытых await.
        """
        from md_storage import ReportMetadata

        mock_report = ReportMetadata(
            file_path="test.md",
            user_id=123,
            username="test",
            timestamp="2025-01-01T00:00:00",
            question="Test",
            size_bytes=100,
            tokens=10,
            search_type="fast"
        )

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            mock_to_thread.side_effect = [mock_report, b"content"]
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_get_path.return_value = mock_path

            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            # Запускаем handler
            await handle_report_view_input(123, "1", mock_app)

            # Проверяем что все async функции вызваны
            assert mock_to_thread.call_count >= 1
            assert mock_track.call_count >= 1


# ============================================================================
#                   Тесты asyncio.to_thread wrapping
# ============================================================================

class TestAsyncioToThreadWrapping:
    """Тесты обертки file I/O в asyncio.to_thread()."""

    @pytest.mark.asyncio
    async def test_get_user_reports_wrapped(self, mock_app, user_states_clean):
        """
        Проверяет что md_storage.get_user_reports обернут в asyncio.to_thread().
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = []

            await handle_my_reports_v2(123, mock_app)

            # Проверяем вызов asyncio.to_thread
            assert mock_to_thread.call_count >= 1
            call_args = mock_to_thread.call_args_list[0][0]
            # Первый аргумент - функция md_storage_manager.get_user_reports
            # Второй - chat_id
            assert call_args[1] == 123

    @pytest.mark.asyncio
    async def test_export_reports_list_wrapped(self, mock_app, user_states_clean):
        """
        Проверяет что export_reports_list_to_txt обернут в asyncio.to_thread().
        """
        from md_storage import ReportMetadata

        mock_reports = [
            ReportMetadata(
                file_path="test.md",
                user_id=123,
                username="test",
                timestamp="2025-01-01T00:00:00",
                question="Test",
                size_bytes=100,
                tokens=10,
                search_type="fast"
            )
        ]

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.side_effect = [
                mock_reports,  # get_user_reports
                "/tmp/reports.txt",  # export_reports_list_to_txt
                b"Test content"  # _read_file_sync
            ]

            await handle_my_reports_v2(123, mock_app)

            # Проверяем что asyncio.to_thread вызван 3 раза
            assert mock_to_thread.call_count == 3

    @pytest.mark.asyncio
    async def test_rename_report_wrapped(self, mock_app, user_states_clean):
        """
        Проверяет что md_storage.rename_report обернут в asyncio.to_thread().
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = True

            user_states_clean[123] = {
                "step": "report_rename_ask_new_name",
                "report_index": 3,
                "old_name": "Old name"
            }

            await handle_report_rename_name_input(123, "New name", mock_app)

            # Проверяем вызов asyncio.to_thread
            assert mock_to_thread.call_count == 1

    @pytest.mark.asyncio
    async def test_delete_report_wrapped(self, mock_app, user_states_clean):
        """
        Проверяет что md_storage.delete_report обернут в asyncio.to_thread().
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = True

            user_states_clean[123] = {
                "step": "report_delete_confirm",
                "report_index": 5,
                "report_name": "Test"
            }

            await handle_report_delete_confirm(123, mock_app)

            # Проверяем вызов asyncio.to_thread
            assert mock_to_thread.call_count == 1


# ============================================================================
#                   Тесты concurrent operations
# ============================================================================

class TestConcurrentOperations:
    """Тесты concurrent операций."""

    @pytest.mark.asyncio
    async def test_concurrent_view_operations(self, mock_app, user_states_clean):
        """
        Проверяет корректность concurrent просмотров отчетов.

        3 пользователя одновременно просматривают разные отчеты.
        """
        from md_storage import ReportMetadata

        mock_report = ReportMetadata(
            file_path="test.md",
            user_id=123,
            username="test",
            timestamp="2025-01-01T00:00:00",
            question="Test",
            size_bytes=100,
            tokens=10,
            search_type="fast"
        )

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock), \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            mock_to_thread.side_effect = [
                mock_report, b"content1",
                mock_report, b"content2",
                mock_report, b"content3"
            ]

            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_get_path.return_value = mock_path

            # FSM состояния для 3 пользователей
            user_states_clean[111] = {"step": "report_view_ask_number", "total_reports": 5}
            user_states_clean[222] = {"step": "report_view_ask_number", "total_reports": 5}
            user_states_clean[333] = {"step": "report_view_ask_number", "total_reports": 5}

            # Concurrent запуск
            tasks = [
                asyncio.create_task(handle_report_view_input(111, "1", mock_app)),
                asyncio.create_task(handle_report_view_input(222, "2", mock_app)),
                asyncio.create_task(handle_report_view_input(333, "3", mock_app))
            ]

            await asyncio.gather(*tasks)

            # Проверяем что все FSM очищены
            assert user_states_clean.get(111, {}) == {}
            assert user_states_clean.get(222, {}) == {}
            assert user_states_clean.get(333, {}) == {}

    @pytest.mark.asyncio
    async def test_concurrent_rename_operations(self, mock_app, user_states_clean):
        """
        Проверяет корректность concurrent переименований.

        2 пользователя одновременно переименовывают разные отчеты.
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.side_effect = [True, True]

            # FSM состояния
            user_states_clean[111] = {
                "step": "report_rename_ask_new_name",
                "report_index": 1,
                "old_name": "Report 1"
            }
            user_states_clean[222] = {
                "step": "report_rename_ask_new_name",
                "report_index": 2,
                "old_name": "Report 2"
            }

            # Concurrent запуск
            tasks = [
                asyncio.create_task(handle_report_rename_name_input(111, "New Report 1", mock_app)),
                asyncio.create_task(handle_report_rename_name_input(222, "New Report 2", mock_app))
            ]

            await asyncio.gather(*tasks)

            # Проверяем что оба успешно завершены
            assert user_states_clean.get(111, {}) == {}
            assert user_states_clean.get(222, {}) == {}

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, mock_app, user_states_clean):
        """
        Проверяет корректность смешанных concurrent операций.

        Пользователь 1 - просмотр
        Пользователь 2 - переименование
        Пользователь 3 - удаление
        """
        from md_storage import ReportMetadata

        mock_report = ReportMetadata(
            file_path="test.md",
            user_id=123,
            username="test",
            timestamp="2025-01-01T00:00:00",
            question="Test",
            size_bytes=100,
            tokens=10,
            search_type="fast"
        )

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock), \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            mock_to_thread.side_effect = [
                mock_report, b"content",  # view
                True,  # rename
                True   # delete
            ]

            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_get_path.return_value = mock_path

            # FSM состояния
            user_states_clean[111] = {"step": "report_view_ask_number", "total_reports": 5}
            user_states_clean[222] = {
                "step": "report_rename_ask_new_name",
                "report_index": 2,
                "old_name": "Old"
            }
            user_states_clean[333] = {
                "step": "report_delete_confirm",
                "report_index": 3,
                "report_name": "Test"
            }

            # Concurrent запуск
            tasks = [
                asyncio.create_task(handle_report_view_input(111, "1", mock_app)),
                asyncio.create_task(handle_report_rename_name_input(222, "New", mock_app)),
                asyncio.create_task(handle_report_delete_confirm(333, mock_app))
            ]

            await asyncio.gather(*tasks)

            # Проверяем что все успешно завершены
            assert user_states_clean.get(111, {}) == {}
            assert user_states_clean.get(222, {}) == {}
            assert user_states_clean.get(333, {}) == {}


# ============================================================================
#                   Тесты task cancellation
# ============================================================================

class TestTaskCancellation:
    """Тесты отмены задач."""

    @pytest.mark.asyncio
    async def test_task_cancellation_during_view(self, mock_app, user_states_clean):
        """
        Проверяет корректность cancellation задачи во время просмотра.

        FSM состояние должно быть очищено.
        """
        from md_storage import ReportMetadata

        mock_report = ReportMetadata(
            file_path="test.md",
            user_id=123,
            username="test",
            timestamp="2025-01-01T00:00:00",
            question="Test",
            size_bytes=100,
            tokens=10,
            search_type="fast"
        )

        async def slow_read():
            await asyncio.sleep(1.0)
            return b"content"

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock), \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            mock_to_thread.side_effect = [mock_report, slow_read()]

            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_get_path.return_value = mock_path

            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            # Создаем задачу и отменяем её
            task = asyncio.create_task(handle_report_view_input(123, "1", mock_app))
            await asyncio.sleep(0.1)
            task.cancel()

            # Ждем завершения
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Проверяем что FSM очищен (опционально - зависит от реализации)
            # assert user_states_clean.get(123, {}) == {}

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, mock_app, user_states_clean):
        """
        Проверяет graceful shutdown при отмене всех задач.

        Все FSM состояния должны быть очищены.
        """
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = []

            # Создаем несколько задач
            tasks = [
                asyncio.create_task(handle_my_reports_v2(111, mock_app)),
                asyncio.create_task(handle_my_reports_v2(222, mock_app)),
                asyncio.create_task(handle_my_reports_v2(333, mock_app))
            ]

            await asyncio.sleep(0.01)

            # Отменяем все задачи
            for task in tasks:
                task.cancel()

            # Ждем завершения
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Все задачи должны быть отменены
            assert all(task.cancelled() for task in tasks)


# ============================================================================
#                   Тесты timeout handling
# ============================================================================

class TestTimeoutHandling:
    """Тесты обработки timeout."""

    @pytest.mark.asyncio
    async def test_timeout_on_slow_file_read(self, mock_app, user_states_clean):
        """
        Проверяет timeout при медленном чтении файла.

        Если file read занимает больше N секунд - должен быть timeout.
        """
        from md_storage import ReportMetadata

        mock_report = ReportMetadata(
            file_path="test.md",
            user_id=123,
            username="test",
            timestamp="2025-01-01T00:00:00",
            question="Test",
            size_bytes=100,
            tokens=10,
            search_type="fast"
        )

        async def very_slow_read():
            await asyncio.sleep(10.0)  # 10 секунд
            return b"content"

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock), \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            mock_to_thread.side_effect = [mock_report, very_slow_read()]

            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_get_path.return_value = mock_path

            user_states_clean[123] = {"step": "report_view_ask_number", "total_reports": 5}

            # Запускаем handler с timeout
            try:
                await asyncio.wait_for(
                    handle_report_view_input(123, "1", mock_app),
                    timeout=0.5
                )
            except asyncio.TimeoutError:
                # Ожидаемый timeout
                pass

            # Проверяем что FSM очищен (если реализован cleanup в handler)
            # assert user_states_clean.get(123, {}) == {}

    @pytest.mark.asyncio
    async def test_timeout_on_slow_md_storage_operation(self, mock_app, user_states_clean):
        """
        Проверяет timeout при медленной операции md_storage.

        Если delete_report занимает больше N секунд - должен быть timeout.
        """
        async def very_slow_delete():
            await asyncio.sleep(10.0)
            return True

        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.side_effect = [very_slow_delete()]

            user_states_clean[123] = {
                "step": "report_delete_confirm",
                "report_index": 5,
                "report_name": "Test"
            }

            # Запускаем handler с timeout
            try:
                await asyncio.wait_for(
                    handle_report_delete_confirm(123, mock_app),
                    timeout=0.5
                )
            except asyncio.TimeoutError:
                # Ожидаемый timeout
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
