"""
Unit тесты для base_storage_manager.py

Покрытие:
- atomic_write() - Two-Phase Commit через .tmp файлы
- atomic_read() - чтение с error handling
- file_exists(), delete_file(), cleanup_temp_files()
- Error handling: IOError, OSError, JSONDecodeError
- Windows 11 совместимость (Path, shutil.rmtree с ignore_errors=True)

Автор: qa-expert
Дата: 17 октября 2025
Задача: T10 (#00005_20251014_HRYHG)
"""

import pytest
import json
import shutil
from pathlib import Path
from managers.base_storage_manager import BaseStorageManager


class TestBaseStorageManager:
    """Тесты для BaseStorageManager."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Создает временную директорию для тестов (Windows 11 совместимость)."""
        test_dir = tmp_path / "test_base_storage"
        test_dir.mkdir(exist_ok=True)
        yield test_dir
        # Cleanup (Windows 11 совместимость)
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.fixture
    def storage_manager(self, temp_dir):
        """Создает BaseStorageManager с временной директорией."""
        return BaseStorageManager(temp_dir)

    # ========== ИНИЦИАЛИЗАЦИЯ ==========

    def test_init_creates_base_directory(self, temp_dir):
        """__init__() создает базовую директорию."""
        test_path = temp_dir / "new_storage"
        manager = BaseStorageManager(test_path)

        assert test_path.exists()
        assert test_path.is_dir()

    def test_init_with_existing_directory(self, temp_dir):
        """__init__() работает с существующей директорией."""
        manager = BaseStorageManager(temp_dir)

        assert temp_dir.exists()

    # ========== ATOMIC_WRITE ==========

    def test_atomic_write_basic(self, storage_manager, temp_dir):
        """atomic_write() успешно записывает JSON."""
        file_path = temp_dir / "test.json"
        data = {"key": "value", "number": 42}

        result = storage_manager.atomic_write(file_path, data)

        assert result is True
        assert file_path.exists()

        # Проверить содержимое
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            assert loaded_data == data

    def test_atomic_write_creates_parent_dirs(self, storage_manager, temp_dir):
        """atomic_write() создает parent директории."""
        file_path = temp_dir / "sub1" / "sub2" / "test.json"
        data = {"nested": "directory"}

        result = storage_manager.atomic_write(file_path, data)

        assert result is True
        assert file_path.exists()

    def test_atomic_write_overwrites_existing_file(self, storage_manager, temp_dir):
        """atomic_write() перезаписывает существующий файл."""
        file_path = temp_dir / "test.json"

        # Первая запись
        data1 = {"version": 1}
        storage_manager.atomic_write(file_path, data1)

        # Вторая запись (перезапись)
        data2 = {"version": 2}
        result = storage_manager.atomic_write(file_path, data2)

        assert result is True

        # Проверить что файл перезаписан
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            assert loaded_data["version"] == 2

    def test_atomic_write_temp_file_cleaned_on_error(self, storage_manager, temp_dir):
        """atomic_write() очищает .tmp файл при ошибке."""
        file_path = temp_dir / "test.json"
        invalid_data = {"key": set()}  # set не JSON-serializable

        result = storage_manager.atomic_write(file_path, invalid_data)

        assert result is False
        # Проверить что .tmp файл удален
        tmp_file = file_path.parent / f"{file_path.name}.tmp"
        assert not tmp_file.exists()

    # ========== ATOMIC_READ ==========

    def test_atomic_read_basic(self, storage_manager, temp_dir):
        """atomic_read() успешно читает JSON."""
        file_path = temp_dir / "test.json"
        data = {"key": "value", "number": 42}

        # Записать файл
        storage_manager.atomic_write(file_path, data)

        # Прочитать файл
        loaded_data = storage_manager.atomic_read(file_path)

        assert loaded_data == data

    def test_atomic_read_nonexistent_file(self, storage_manager, temp_dir):
        """atomic_read() возвращает {} для несуществующего файла."""
        file_path = temp_dir / "nonexistent.json"

        loaded_data = storage_manager.atomic_read(file_path)

        assert loaded_data == {}

    def test_atomic_read_invalid_json(self, storage_manager, temp_dir):
        """atomic_read() возвращает {} для невалидного JSON."""
        file_path = temp_dir / "invalid.json"

        # Записать невалидный JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("NOT_VALID_JSON{{{")

        loaded_data = storage_manager.atomic_read(file_path)

        assert loaded_data == {}

    def test_atomic_read_empty_file(self, storage_manager, temp_dir):
        """atomic_read() возвращает {} для пустого файла."""
        file_path = temp_dir / "empty.json"

        # Создать пустой файл
        file_path.touch()

        loaded_data = storage_manager.atomic_read(file_path)

        assert loaded_data == {}

    # ========== FILE_EXISTS ==========

    def test_file_exists_true(self, storage_manager, temp_dir):
        """file_exists() возвращает True для существующего файла."""
        file_path = temp_dir / "test.json"
        file_path.touch()

        assert storage_manager.file_exists(file_path) is True

    def test_file_exists_false(self, storage_manager, temp_dir):
        """file_exists() возвращает False для несуществующего файла."""
        file_path = temp_dir / "nonexistent.json"

        assert storage_manager.file_exists(file_path) is False

    # ========== DELETE_FILE ==========

    def test_delete_file_existing(self, storage_manager, temp_dir):
        """delete_file() удаляет существующий файл."""
        file_path = temp_dir / "test.json"
        file_path.touch()

        result = storage_manager.delete_file(file_path)

        assert result is True
        assert not file_path.exists()

    def test_delete_file_nonexistent(self, storage_manager, temp_dir):
        """delete_file() возвращает True для несуществующего файла."""
        file_path = temp_dir / "nonexistent.json"

        result = storage_manager.delete_file(file_path)

        assert result is True

    # ========== CLEANUP_TEMP_FILES ==========

    def test_cleanup_temp_files_basic(self, storage_manager, temp_dir):
        """cleanup_temp_files() удаляет .tmp файлы."""
        # Создать несколько .tmp файлов
        (temp_dir / "file1.json.tmp").touch()
        (temp_dir / "file2.json.tmp").touch()
        (temp_dir / "regular.json").touch()

        cleaned_count = storage_manager.cleanup_temp_files(temp_dir)

        assert cleaned_count == 2
        assert not (temp_dir / "file1.json.tmp").exists()
        assert not (temp_dir / "file2.json.tmp").exists()
        assert (temp_dir / "regular.json").exists()  # Обычный файл не удален

    def test_cleanup_temp_files_empty_directory(self, storage_manager, temp_dir):
        """cleanup_temp_files() возвращает 0 для пустой директории."""
        cleaned_count = storage_manager.cleanup_temp_files(temp_dir)

        assert cleaned_count == 0

    def test_cleanup_temp_files_nonexistent_directory(self, storage_manager, temp_dir):
        """cleanup_temp_files() возвращает 0 для несуществующей директории."""
        nonexistent_dir = temp_dir / "nonexistent"

        cleaned_count = storage_manager.cleanup_temp_files(nonexistent_dir)

        assert cleaned_count == 0
