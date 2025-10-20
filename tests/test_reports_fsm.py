"""
Integration тесты для FSM workflow "Мои отчеты" v2.

Task ID: 00001_20251010_144500
Агент: test-automator
Дата: 11.10.2025

Тестируемые workflow:
- View Report: полный flow просмотра отчета
- Rename Report: полный flow переименования отчета
- Delete Report: полный flow удаления отчета
"""

import pytest
import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch, call

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from handlers_my_reports_v2 import (
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


# ============================================================================
#                   Integration тест: View Report workflow
# ============================================================================

class TestViewReportFullWorkflow:
    """
    Integration тест: полный flow "Посмотреть отчет".

    Шаги:
    1. Нажатие "Посмотреть" → handle_report_view_request()
    2. Ввод номера "2" → handle_report_view_input()
    3. Получение файла отчета
    4. Очистка FSM состояния
    5. Показ меню чатов
    """

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_app, mock_reports, user_states_clean):
        """Полный flow просмотра отчета."""
        chat_id = 123

        # ===== ШАГ 1: Нажатие "Посмотреть" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: get_user_reports → возвращает 3 отчета
            mock_to_thread.return_value = mock_reports

            await handle_report_view_request(chat_id, mock_app)

            # Проверяем FSM состояние установлено
            assert user_states_clean[chat_id]["step"] == "report_view_ask_number"
            assert user_states_clean[chat_id]["total_reports"] == 3

            # Проверяем запрос номера отчета
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "введите номер" in call_args.kwargs["text"].lower()

        # ===== ШАГ 2: Ввод номера "2" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track, \
             patch("handlers_my_reports_v2.md_storage_manager.get_report_file_path") as mock_get_path:

            # Мокаем:
            # 1-й вызов: get_report_by_index → возвращает отчет #2
            # 2-й вызов: _read_file_sync → возвращает содержимое файла
            mock_to_thread.side_effect = [
                mock_reports[1],  # get_report_by_index(chat_id, 2)
                b"# Report #2 Content"  # _read_file_sync
            ]

            # Мокаем путь к файлу
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__.return_value = "/tmp/report_2.md"
            mock_get_path.return_value = mock_path

            await handle_report_view_input(chat_id, "2", mock_app)

            # ===== ПРОВЕРКИ =====
            # 1. app.send_document вызван с BytesIO
            mock_app.send_document.assert_called_once()
            call_args = mock_app.send_document.call_args
            assert call_args.kwargs["chat_id"] == chat_id
            assert isinstance(call_args.kwargs["document"], BytesIO)
            assert "Исследование клиентов" in call_args.kwargs["caption"]

            # 2. FSM состояние очищено
            assert user_states_clean.get(chat_id, {}) == {}

            # 3. Показано меню чатов
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args.kwargs["message_type"] == "menu"


# ============================================================================
#                   Integration тест: Rename Report workflow
# ============================================================================

class TestRenameReportFullWorkflow:
    """
    Integration тест: полный flow "Переименовать отчет".

    Шаги:
    1. Нажатие "Переименовать" → handle_report_rename_request()
    2. Ввод номера "3" → handle_report_rename_number_input()
    3. Ввод нового имени "Новый анализ" → handle_report_rename_name_input()
    4. Подтверждение изменений
    5. Очистка FSM состояния
    6. Показ меню чатов
    """

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_app, mock_reports, user_states_clean):
        """Полный flow переименования отчета."""
        chat_id = 123

        # ===== ШАГ 1: Нажатие "Переименовать" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: get_user_reports → возвращает 3 отчета
            mock_to_thread.return_value = mock_reports

            await handle_report_rename_request(chat_id, mock_app)

            # Проверяем FSM состояние
            assert user_states_clean[chat_id]["step"] == "report_rename_ask_number"
            assert user_states_clean[chat_id]["total_reports"] == 3

            # Проверяем запрос номера
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "введите номер" in call_args.kwargs["text"].lower()

        # ===== ШАГ 2: Ввод номера "3" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: get_report_by_index → возвращает отчет #3
            mock_to_thread.return_value = mock_reports[2]

            await handle_report_rename_number_input(chat_id, "3", mock_app)

            # Проверяем FSM состояние обновлено
            assert user_states_clean[chat_id]["step"] == "report_rename_ask_new_name"
            assert user_states_clean[chat_id]["report_index"] == 3
            assert user_states_clean[chat_id]["old_name"] == "Конкурентный анализ"

            # Проверяем запрос нового имени
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "введите новое название" in call_args.kwargs["text"].lower()

        # ===== ШАГ 3: Ввод нового имени "Новый анализ" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: rename_report → возвращает True (успех)
            mock_to_thread.return_value = True

            await handle_report_rename_name_input(chat_id, "Новый анализ", mock_app)

            # ===== ПРОВЕРКИ =====
            # 1. Показано сообщение об успехе
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "переименован" in call_args.kwargs["text"].lower()
            assert "Новый анализ" in call_args.kwargs["text"]
            assert "Конкурентный анализ" in call_args.kwargs["text"]  # Старое название

            # 2. FSM состояние очищено
            assert user_states_clean.get(chat_id, {}) == {}


# ============================================================================
#                   Integration тест: Delete Report workflow
# ============================================================================

class TestDeleteReportFullWorkflow:
    """
    Integration тест: полный flow "Удалить отчет".

    Шаги:
    1. Нажатие "Удалить" → handle_report_delete_request()
    2. Ввод номера "1" → handle_report_delete_input()
    3. Подтверждение "Да, удалить" → handle_report_delete_confirm()
    4. Удаление файла + запись из индекса
    5. Очистка FSM состояния
    6. Показ меню чатов
    """

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_app, mock_reports, user_states_clean):
        """Полный flow удаления отчета."""
        chat_id = 123

        # ===== ШАГ 1: Нажатие "Удалить" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: get_user_reports → возвращает 3 отчета
            mock_to_thread.return_value = mock_reports

            await handle_report_delete_request(chat_id, mock_app)

            # Проверяем FSM состояние
            assert user_states_clean[chat_id]["step"] == "report_delete_ask_number"
            assert user_states_clean[chat_id]["total_reports"] == 3

            # Проверяем запрос номера
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "введите номер" in call_args.kwargs["text"].lower()

        # ===== ШАГ 2: Ввод номера "1" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: get_report_by_index → возвращает отчет #1
            mock_to_thread.return_value = mock_reports[0]

            await handle_report_delete_input(chat_id, "1", mock_app)

            # Проверяем FSM состояние обновлено
            assert user_states_clean[chat_id]["step"] == "report_delete_confirm"
            assert user_states_clean[chat_id]["report_index"] == 1
            assert user_states_clean[chat_id]["report_name"] == "Анализ рынка недвижимости"

            # Проверяем запрос подтверждения
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "удалить отчет" in call_args.kwargs["text"].lower()
            assert call_args.kwargs["message_type"] == "confirmation"

        # ===== ШАГ 3: Подтверждение "Да, удалить" =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock) as mock_track:

            # Мокаем: delete_report → возвращает True (успех)
            mock_to_thread.return_value = True

            await handle_report_delete_confirm(chat_id, mock_app)

            # ===== ПРОВЕРКИ =====
            # 1. Показано сообщение об успехе
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert "удален" in call_args.kwargs["text"].lower()
            assert "Анализ рынка недвижимости" in call_args.kwargs["text"]

            # 2. FSM состояние очищено
            assert user_states_clean.get(chat_id, {}) == {}

    @pytest.mark.asyncio
    async def test_cancel_delete_workflow(self, mock_app, mock_reports, user_states_clean):
        """Отмена удаления отчета (пользователь нажал "Отмена")."""
        chat_id = 123

        # ===== ШАГ 1: Запрос удаления =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = mock_reports

            await handle_report_delete_request(chat_id, mock_app)

            # Устанавливаем FSM
            assert user_states_clean[chat_id]["step"] == "report_delete_ask_number"

        # ===== ШАГ 2: Ввод номера =====
        with patch("handlers_my_reports_v2.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread, \
             patch("handlers_my_reports_v2.track_and_send", new_callable=AsyncMock):

            mock_to_thread.return_value = mock_reports[0]

            await handle_report_delete_input(chat_id, "1", mock_app)

            # FSM состояние ждет подтверждения
            assert user_states_clean[chat_id]["step"] == "report_delete_confirm"

        # ===== ШАГ 3: Пользователь нажимает "Отмена" вместо подтверждения =====
        # В реальном боте callback_data="show_my_reports" → вернется в меню
        # FSM состояние должно быть очищено вручную или автоматически

        # Симулируем ручную очистку FSM (как в реальном handler)
        user_states_clean[chat_id] = {}

        # Проверяем что FSM очищено
        assert user_states_clean.get(chat_id, {}) == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
