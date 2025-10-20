"""
Базовый класс для всех форматтеров VoxPersona
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseFormatter(ABC):
    """Базовый абстрактный класс для форматирования данных"""

    def __init__(self):
        """Инициализация форматтера"""
        self.line_separator = "─" * 40
        self.heavy_separator = "━" * 40

    @abstractmethod
    def format(self, data: Any) -> str:
        """
        Основной метод форматирования данных.

        Args:
            data: Данные для форматирования

        Returns:
            Отформатированная строка
        """
        pass

    def format_timestamp(self, timestamp: str, format_type: str = "full") -> str:
        """
        Форматирование временных меток.

        Args:
            timestamp: ISO формат timestamp (например, "2025-10-09T14:30:00")
            format_type: Тип форматирования:
                - "full": "DD.MM.YYYY в HH:MM"
                - "short": "DD.MM HH:MM"
                - "date": "DD.MM.YYYY"
                - "time": "HH:MM"

        Returns:
            Форматированная строка времени
        """
        try:
            dt = datetime.fromisoformat(timestamp)
        except (ValueError, TypeError):
            return timestamp  # Возврат как есть при ошибке

        if format_type == "full":
            return dt.strftime("%d.%m.%Y в %H:%M")
        elif format_type == "short":
            return dt.strftime("%d.%m %H:%M")
        elif format_type == "date":
            return dt.strftime("%d.%m.%Y")
        elif format_type == "time":
            return dt.strftime("%H:%M")
        else:
            return dt.strftime("%d.%m.%Y в %H:%M")

    def truncate_text(self, text: str, max_length: int = 100) -> str:
        """
        Умная обрезка текста по словам.

        Args:
            text: Исходный текст
            max_length: Максимальная длина (default: 100)

        Returns:
            Обрезанный текст с "..." или полный текст
        """
        if not text:
            return ""

        if len(text) <= max_length:
            return text

        truncated = text[:max_length]
        last_space = truncated.rfind(' ')

        # Если последний пробел близко к концу (>80% длины), обрезаем по нему
        if last_space > max_length * 0.8:
            truncated = truncated[:last_space]

        return truncated + "..."

    def escape_markdown(self, text: str) -> str:
        """
        Экранирование спецсимволов Markdown.

        Args:
            text: Исходный текст

        Returns:
            Текст с экранированными спецсимволами
        """
        if not text:
            return ""

        escape_chars = ['\\', '`', '*', '_', '[', ']', '(', ')', '#', '+', '-', '.', '!', '|', '{', '}']

        for char in escape_chars:
            text = text.replace(char, f'\\{char}')

        return text
