"""
Базовый класс для storage менеджеров с Two-Phase Commit паттерном.

Паттерн извлечен из ConversationManager:
- Atomic write через временные .tmp файлы
- Transaction safety через Path.replace() (атомарная ОС операция)
- Sync методы для консистентности с существующей кодовой базой
- Автоматическое создание parent директорий
- Comprehensive error handling с логированием

Использование:
    class AuthStorageManager(BaseStorageManager):
        def __init__(self, auth_dir: Path):
            super().__init__(auth_dir)
            # Дополнительная инициализация (locks, cache и т.д.)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseStorageManager:
    """
    Базовый класс для storage менеджеров с Two-Phase Commit.

    Реализует атомарные операции чтения/записи JSON файлов через
    паттерн временных файлов (.tmp) с последующим atomic replace.

    Особенности:
    - Sync методы (НЕ async) для консистентности с ConversationManager
    - БЕЗ threading.Lock в базовом классе (будет в наследниках)
    - UTF-8 encoding с поддержкой русских символов
    - Автоматическое создание директорий
    - Транзакционная безопасность через .tmp файлы

    Attributes:
        base_path (Path): Базовая директория для хранилища
    """

    def __init__(self, base_path: Path):
        """
        Инициализация storage менеджера.

        Args:
            base_path: Базовый путь для хранилища данных

        Raises:
            OSError: Если не удалось создать директорию
        """
        self.base_path = Path(base_path)
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"BaseStorageManager initialized with base_path: {self.base_path}")
        except OSError as e:
            logger.error(f"Failed to create base directory {self.base_path}: {e}")
            raise

    def atomic_write(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """
        Two-Phase Commit - безопасная запись через .tmp файлы.

        Алгоритм (паттерн из ConversationManager):
        1. Записать данные в {file_path}.tmp (подготовка)
        2. Atomic replace через Path.replace() (commit)
        3. Автоматическая очистка .tmp при ошибке (rollback)

        Args:
            file_path: Путь к целевому файлу
            data: Данные для записи (должны быть JSON-serializable)

        Returns:
            bool: True если запись успешна, False при ошибке

        Example:
            >>> manager = BaseStorageManager(Path("/data"))
            >>> success = manager.atomic_write(
            ...     Path("/data/users/user_123.json"),
            ...     {"user_id": 123, "tokens": ["abc", "def"]}
            ... )
        """
        # Создаем parent директории если не существуют
        file_path = Path(file_path)
        temp_file = file_path.parent / f"{file_path.name}.tmp"

        try:
            # Убеждаемся что parent директория существует
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Фаза 1: Запись во временный файл (подготовка)
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Фаза 2: Atomic replace (commit)
            temp_file.replace(file_path)

            logger.debug(f"Atomic write successful: {file_path}")
            return True

        except (IOError, OSError, TypeError, ValueError) as e:
            logger.error(f"Atomic write failed for {file_path}: {e}")

            # Rollback: Удаляем временный файл при ошибке
            if temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file}")
                except OSError as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {cleanup_error}")

            return False

    def atomic_read(self, file_path: Path) -> Dict[str, Any]:
        """
        Безопасное чтение JSON файла с обработкой ошибок.

        Args:
            file_path: Путь к файлу для чтения

        Returns:
            dict: Данные из файла или {} при ошибке/отсутствии файла

        Note:
            - Возвращает пустой dict вместо None для упрощения работы
            - Логирует только реальные ошибки (не FileNotFoundError)

        Example:
            >>> manager = BaseStorageManager(Path("/data"))
            >>> data = manager.atomic_read(Path("/data/users/user_123.json"))
            >>> user_id = data.get("user_id")  # Безопасно даже если файла нет
        """
        file_path = Path(file_path)

        # Файл не существует - не ошибка, вернуть пустой dict
        if not file_path.exists():
            logger.debug(f"File not found (returning empty dict): {file_path}")
            return {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Atomic read successful: {file_path}")
                return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {file_path}: {e}")
            return {}

        except (IOError, OSError) as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {}

    def file_exists(self, file_path: Path) -> bool:
        """
        Проверка существования файла.

        Args:
            file_path: Путь к файлу

        Returns:
            bool: True если файл существует
        """
        return Path(file_path).exists()

    def delete_file(self, file_path: Path) -> bool:
        """
        Безопасное удаление файла.

        Args:
            file_path: Путь к файлу для удаления

        Returns:
            bool: True если удаление успешно или файл не существовал
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.debug(f"File already deleted or doesn't exist: {file_path}")
            return True

        try:
            file_path.unlink()
            logger.info(f"File deleted: {file_path}")
            return True

        except OSError as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    def cleanup_temp_files(self, directory: Path) -> int:
        """
        Очистка всех .tmp файлов в директории (recovery после сбоев).

        Args:
            directory: Директория для очистки

        Returns:
            int: Количество удаленных .tmp файлов
        """
        directory = Path(directory)

        if not directory.exists():
            logger.debug(f"Directory doesn't exist: {directory}")
            return 0

        cleaned = 0
        for tmp_file in directory.glob("*.tmp"):
            try:
                tmp_file.unlink()
                cleaned += 1
                logger.debug(f"Cleaned up orphaned temp file: {tmp_file}")
            except OSError as e:
                logger.warning(f"Failed to cleanup temp file {tmp_file}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} temporary files in {directory}")

        return cleaned
