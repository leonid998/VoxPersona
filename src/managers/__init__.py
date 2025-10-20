"""
Менеджеры для работы с хранилищем данных VoxPersona.

Модули:
- base_storage_manager: Базовый класс с Two-Phase Commit паттерном
"""

from .base_storage_manager import BaseStorageManager

__all__ = [
    "BaseStorageManager",
]
