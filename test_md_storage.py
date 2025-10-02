"""
Тесты для модуля md_storage.py
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from src.md_storage import MDStorageManager, ReportMetadata


@pytest.fixture
def temp_reports_dir():
    """Создает временную директорию для тестов."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def storage_manager(temp_reports_dir, monkeypatch):
    """Создает менеджер хранения с временной директорией."""
    monkeypatch.setattr('src.md_storage.MD_REPORTS_DIR', temp_reports_dir)
    return MDStorageManager()


class TestMDStorageManager:
    """Тесты для MDStorageManager."""

    def test_ensure_reports_directory(self, storage_manager):
        """Тест создания директории отчетов."""
        assert storage_manager.reports_dir.exists()

    def test_ensure_user_directory(self, storage_manager):
        """Тест создания директории пользователя."""
        user_id = 123456
        user_dir = storage_manager.ensure_user_directory(user_id)
        
        assert user_dir.exists()
        assert user_dir.name == f"user_{user_id}"

    def test_generate_filename(self, storage_manager):
        """Тест генерации имени файла."""
        filename = storage_manager.generate_filename()
        
        assert filename.startswith("voxpersona_")
        assert filename.endswith(".md")
        assert len(filename.split("_")) >= 3  # voxpersona_YYYYMMDD_HHMMSS.md

    def test_create_md_content(self, storage_manager):
        """Тест создания содержимого MD файла."""
        content = "Тестовый отчет"
        username = "test_user"
        user_id = 123456
        question = "Тестовый вопрос"
        search_type = "fast"
        
        md_content = storage_manager.create_md_content(
            content, username, user_id, question, search_type
        )
        
        assert "# Отчет VoxPersona" in md_content
        assert f"@{username}" in md_content
        assert f"ID: {user_id}" in md_content
        assert question in md_content
        assert search_type in md_content
        assert content in md_content

    def test_save_md_report(self, storage_manager):
        """Тест сохранения MD отчета."""
        content = "Тестовый отчет с достаточно длинным содержимым для тестирования"
        user_id = 123456
        username = "test_user"
        question = "Тестовый вопрос"
        search_type = "deep"
        
        file_path = storage_manager.save_md_report(
            content, user_id, username, question, search_type
        )
        
        assert file_path is not None
        
        # Проверяем что файл создался
        full_path = Path(file_path)
        assert full_path.exists()
        
        # Проверяем содержимое файла
        with open(full_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        assert "# Отчет VoxPersona" in file_content
        assert content in file_content
        assert question in file_content

    def test_load_and_save_reports_index(self, storage_manager):
        """Тест загрузки и сохранения индекса отчетов."""
        # Загружаем пустой индекс
        reports = storage_manager.load_reports_index()
        assert isinstance(reports, list)
        assert len(reports) == 0
        
        # Создаем тестовые метаданные
        metadata = ReportMetadata(
            file_path="user_123456/test_report.md",
            user_id=123456,
            username="test_user",
            timestamp=datetime.now().isoformat(),
            question="Тестовый вопрос",
            size_bytes=1024,
            tokens=100,
            search_type="fast"
        )
        
        # Сохраняем индекс
        success = storage_manager.save_reports_index([metadata])
        assert success
        
        # Загружаем и проверяем
        loaded_reports = storage_manager.load_reports_index()
        assert len(loaded_reports) == 1
        assert loaded_reports[0].user_id == 123456
        assert loaded_reports[0].username == "test_user"
        assert loaded_reports[0].question == "Тестовый вопрос"

    def test_update_reports_index(self, storage_manager):
        """Тест обновления индекса отчетов."""
        # Создаем первый отчет
        metadata1 = ReportMetadata(
            file_path="user_123456/report1.md",
            user_id=123456,
            username="test_user",
            timestamp=datetime.now().isoformat(),
            question="Вопрос 1",
            size_bytes=512,
            tokens=50,
            search_type="fast"
        )
        
        success = storage_manager.update_reports_index(metadata1)
        assert success
        
        # Добавляем второй отчет
        metadata2 = ReportMetadata(
            file_path="user_123456/report2.md",
            user_id=123456,
            username="test_user",
            timestamp=datetime.now().isoformat(),
            question="Вопрос 2",
            size_bytes=1024,
            tokens=100,
            search_type="deep"
        )
        
        success = storage_manager.update_reports_index(metadata2)
        assert success
        
        # Проверяем что оба отчета в индексе
        reports = storage_manager.load_reports_index()
        assert len(reports) == 2

    def test_get_user_reports(self, storage_manager):
        """Тест получения отчетов пользователя."""
        user_id = 123456
        
        # Создаем несколько отчетов для пользователя
        for i in range(3):
            metadata = ReportMetadata(
                file_path=f"user_{user_id}/report{i}.md",
                user_id=user_id,
                username="test_user",
                timestamp=datetime.now().isoformat(),
                question=f"Вопрос {i}",
                size_bytes=1024,
                tokens=100,
                search_type="fast" if i % 2 == 0 else "deep"
            )
            storage_manager.update_reports_index(metadata)
        
        # Создаем отчет для другого пользователя
        other_metadata = ReportMetadata(
            file_path="user_999999/other_report.md",
            user_id=999999,
            username="other_user",
            timestamp=datetime.now().isoformat(),
            question="Другой вопрос",
            size_bytes=512,
            tokens=50,
            search_type="fast"
        )
        storage_manager.update_reports_index(other_metadata)
        
        # Получаем отчеты пользователя
        user_reports = storage_manager.get_user_reports(user_id)
        assert len(user_reports) == 3
        assert all(report.user_id == user_id for report in user_reports)
        
        # Тестируем лимит
        limited_reports = storage_manager.get_user_reports(user_id, limit=2)
        assert len(limited_reports) == 2

    def test_get_report_stats(self, storage_manager):
        """Тест получения статистики отчетов."""
        user_id = 123456
        
        # Создаем отчеты
        for i in range(3):
            metadata = ReportMetadata(
                file_path=f"user_{user_id}/report{i}.md",
                user_id=user_id,
                username="test_user",
                timestamp=datetime.now().isoformat(),
                question=f"Вопрос {i}",
                size_bytes=1000 + i * 100,
                tokens=50 + i * 10,
                search_type="fast" if i % 2 == 0 else "deep"
            )
            storage_manager.update_reports_index(metadata)
        
        # Получаем статистику для пользователя
        stats = storage_manager.get_report_stats(user_id)
        assert stats["total_reports"] == 3
        assert stats["total_size_bytes"] == 3300  # 1000 + 1100 + 1200
        assert stats["total_tokens"] == 180  # 50 + 60 + 70
        assert stats["fast_searches"] == 2
        assert stats["deep_searches"] == 1
        assert stats["avg_size_bytes"] == 1100
        assert stats["avg_tokens"] == 60
        
        # Получаем общую статистику
        global_stats = storage_manager.get_report_stats()
        assert global_stats["total_reports"] == 3

    def test_get_report_file_path(self, storage_manager):
        """Тест получения пути к файлу отчета."""
        # Создаем тестовый файл
        user_id = 123456
        user_dir = storage_manager.ensure_user_directory(user_id)
        test_file = user_dir / "test_report.md"
        test_file.write_text("Тестовый отчет", encoding='utf-8')
        
        relative_path = f"user_{user_id}/test_report.md"
        
        # Получаем полный путь
        full_path = storage_manager.get_report_file_path(relative_path)
        assert full_path is not None
        assert full_path.exists()
        assert full_path.name == "test_report.md"
        
        # Тестируем несуществующий файл
        nonexistent_path = storage_manager.get_report_file_path("nonexistent/file.md")
        assert nonexistent_path is None

    def test_format_user_reports_for_display(self, storage_manager):
        """Тест форматирования отчетов для отображения."""
        user_id = 123456
        
        # Создаем отчет
        metadata = ReportMetadata(
            file_path=f"user_{user_id}/report.md",
            user_id=user_id,
            username="test_user",
            timestamp=datetime.now().isoformat(),
            question="Тестовый вопрос для отображения",
            size_bytes=2048,
            tokens=150,
            search_type="deep"
        )
        storage_manager.update_reports_index(metadata)
        
        # Форматируем для отображения
        display_text = storage_manager.format_user_reports_for_display(user_id)
        
        assert "📁 **Ваши отчеты" in display_text
        assert "Тестовый вопрос" in display_text
        assert "🔍" in display_text  # deep search icon
        assert "150" in display_text  # tokens
        assert "2.0 KB" in display_text  # file size
        assert "📈 **Общая статистика:**" in display_text
        assert "📄 Всего отчетов: 1" in display_text

    def test_empty_reports(self, storage_manager):
        """Тест обработки пустых отчетов."""
        user_id = 999999
        
        # Получаем отчеты несуществующего пользователя
        reports = storage_manager.get_user_reports(user_id)
        assert len(reports) == 0
        
        # Статистика для пользователя без отчетов
        stats = storage_manager.get_report_stats(user_id)
        assert stats["total_reports"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["total_tokens"] == 0
        
        # Форматирование пустых отчетов
        display_text = storage_manager.format_user_reports_for_display(user_id)
        assert "У вас пока нет сохраненных отчетов" in display_text

    def test_validate_integrity(self, storage_manager):
        """Тест проверки целостности архива."""
        user_id = 123456
        
        # Создаем реальный файл и добавляем в индекс
        file_path = storage_manager.save_md_report(
            content="Тестовый отчет",
            user_id=user_id,
            username="test_user",
            question="Тестовый вопрос",
            search_type="fast"
        )
        
        # Создаем файл-сирота (не в индексе)
        user_dir = storage_manager.ensure_user_directory(user_id)
        orphan_file = user_dir / "orphan_report.md"
        orphan_file.write_text("Сирота", encoding='utf-8')
        
        # Добавляем в индекс запись о несуществующем файле
        fake_metadata = ReportMetadata(
            file_path=f"user_{user_id}/fake_report.md",
            user_id=user_id,
            username="test_user",
            timestamp=datetime.now().isoformat(),
            question="Поддельный отчет",
            size_bytes=100,
            tokens=10,
            search_type="fast"
        )
        storage_manager.update_reports_index(fake_metadata)
        
        # Проверяем целостность
        integrity = storage_manager.validate_integrity()
        
        assert integrity["total_reports"] == 2  # 1 реальный + 1 поддельный
        assert integrity["existing_files"] == 1
        assert integrity["missing_files"] == 1
        assert integrity["orphaned_files"] == 1
        assert len(integrity["missing_file_paths"]) == 1
        assert len(integrity["orphaned_file_paths"]) == 1


class TestReportMetadata:
    """Тесты для модели ReportMetadata."""

    def test_report_metadata_creation(self):
        """Тест создания метаданных отчета."""
        timestamp = datetime.now().isoformat()
        
        metadata = ReportMetadata(
            file_path="user_123456/test_report.md",
            user_id=123456,
            username="test_user",
            timestamp=timestamp,
            question="Тестовый вопрос",
            size_bytes=2048,
            tokens=150,
            search_type="deep"
        )
        
        assert metadata.file_path == "user_123456/test_report.md"
        assert metadata.user_id == 123456
        assert metadata.username == "test_user"
        assert metadata.timestamp == timestamp
        assert metadata.question == "Тестовый вопрос"
        assert metadata.size_bytes == 2048
        assert metadata.tokens == 150
        assert metadata.search_type == "deep"