# -*- coding: utf-8 -*-
"""
Утилита для оценки размера JSON-контейнера с описаниями отчетов.

Этот модуль предоставляет функции для:
- Подсчета размера текстовых данных в символах и токенах
- Оценки соответствия лимитам контекстного окна LLM
- Определения стратегии обрезки текстов при превышении лимитов
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Константы для расчетов
# Для русского текста соотношение символы/токены примерно 2.5-3.5
# Используем консервативную оценку 3 символа на токен для русского текста
CHARS_PER_TOKEN_RU: float = 3.0
CHARS_PER_TOKEN_EN: float = 4.0

# Лимиты для Claude Haiku (входные токены)
CLAUDE_HAIKU_INPUT_LIMIT: int = 200_000
# Резерв для системного промпта и запроса пользователя
PROMPT_RESERVE_TOKENS: int = 2_000
# Безопасный лимит для данных
SAFE_DATA_LIMIT_TOKENS: int = CLAUDE_HAIKU_INPUT_LIMIT - PROMPT_RESERVE_TOKENS


@dataclass
class FileStats:
    """Статистика по одному файлу описания отчета."""

    filename: str
    filepath: str
    char_count: int
    estimated_tokens: int

    @property
    def short_name(self) -> str:
        """Возвращает короткое имя файла без расширения."""
        return Path(self.filename).stem


@dataclass
class SizeEstimation:
    """Результат оценки размера JSON-контейнера с описаниями."""

    total_chars: int
    estimated_tokens: int
    within_limit: bool
    strategy: str
    file_stats: list[FileStats] = field(default_factory=list)
    min_chars: int = 0
    max_chars: int = 0
    avg_chars: float = 0.0
    recommended_truncation: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Конвертирует результат в словарь для сериализации."""
        return {
            'total_chars': self.total_chars,
            'estimated_tokens': self.estimated_tokens,
            'within_limit': self.within_limit,
            'strategy': self.strategy,
            'min_chars': self.min_chars,
            'max_chars': self.max_chars,
            'avg_chars': self.avg_chars,
            'file_count': len(self.file_stats),
            'recommended_truncation': self.recommended_truncation,
        }


class JSONSizeEstimator:
    """
    Класс для оценки размера JSON-контейнера с описаниями отчетов.

    Основная задача - определить, помещаются ли все описания в контекстное
    окно LLM и какую стратегию использовать для работы с ними.
    """

    def __init__(
        self,
        chars_per_token: float = CHARS_PER_TOKEN_RU,
        token_limit: int = SAFE_DATA_LIMIT_TOKENS,
    ) -> None:
        """
        Инициализация эстиматора.

        Args:
            chars_per_token: Количество символов на один токен.
                            Для русского текста рекомендуется 3.0.
            token_limit: Максимальное количество токенов для данных.
        """
        self.chars_per_token = chars_per_token
        self.token_limit = token_limit

    def estimate_tokens(self, text: str) -> int:
        """
        Оценивает количество токенов в тексте.

        Args:
            text: Текст для оценки.

        Returns:
            Примерное количество токенов.
        """
        return int(len(text) / self.chars_per_token)

    def estimate_tokens_from_chars(self, char_count: int) -> int:
        """
        Оценивает количество токенов по количеству символов.

        Args:
            char_count: Количество символов.

        Returns:
            Примерное количество токенов.
        """
        return int(char_count / self.chars_per_token)

    def estimate_from_descriptions(
        self,
        descriptions: dict[str, str],
    ) -> SizeEstimation:
        """
        Оценивает размер JSON-контейнера с описаниями отчетов.

        Args:
            descriptions: Словарь {имя_отчета: текст_описания}.

        Returns:
            Объект SizeEstimation с результатами оценки.
        """
        if not descriptions:
            return SizeEstimation(
                total_chars=0,
                estimated_tokens=0,
                within_limit=True,
                strategy='empty',
            )

        # Подсчитываем статистику по каждому файлу
        file_stats: list[FileStats] = []
        char_counts: list[int] = []

        for name, content in descriptions.items():
            char_count = len(content)
            char_counts.append(char_count)

            file_stats.append(FileStats(
                filename=name,
                filepath='',  # Путь неизвестен при работе со словарем
                char_count=char_count,
                estimated_tokens=self.estimate_tokens(content),
            ))

        # Общая статистика
        total_chars = sum(char_counts)
        estimated_tokens = self.estimate_tokens_from_chars(total_chars)
        within_limit = estimated_tokens <= self.token_limit

        # Определяем стратегию
        strategy, recommended_truncation = self._determine_strategy(
            total_chars,
            estimated_tokens,
            len(descriptions),
        )

        return SizeEstimation(
            total_chars=total_chars,
            estimated_tokens=estimated_tokens,
            within_limit=within_limit,
            strategy=strategy,
            file_stats=file_stats,
            min_chars=min(char_counts),
            max_chars=max(char_counts),
            avg_chars=total_chars / len(char_counts),
            recommended_truncation=recommended_truncation,
        )

    def estimate_from_directory(
        self,
        directory: str | Path,
        pattern: str = '**/*.md',
    ) -> SizeEstimation:
        """
        Оценивает размер всех файлов в директории.

        Args:
            directory: Путь к директории с файлами описаний.
            pattern: Glob-паттерн для поиска файлов.

        Returns:
            Объект SizeEstimation с результатами оценки.
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Директория не найдена: {directory}")

        # Собираем все файлы по паттерну
        descriptions: dict[str, str] = {}
        file_paths: dict[str, str] = {}

        for filepath in directory.glob(pattern):
            if filepath.is_file():
                try:
                    content = filepath.read_text(encoding='utf-8')
                    descriptions[filepath.name] = content
                    file_paths[filepath.name] = str(filepath)
                except UnicodeDecodeError:
                    # Пробуем альтернативную кодировку
                    try:
                        content = filepath.read_text(encoding='cp1251')
                        descriptions[filepath.name] = content
                        file_paths[filepath.name] = str(filepath)
                    except Exception:
                        # Пропускаем файл, который не удалось прочитать
                        pass

        # Получаем оценку
        estimation = self.estimate_from_descriptions(descriptions)

        # Дополняем пути к файлам
        for stat in estimation.file_stats:
            if stat.filename in file_paths:
                stat.filepath = file_paths[stat.filename]

        return estimation

    def _determine_strategy(
        self,
        total_chars: int,  # noqa: ARG002 - сохранен для API совместимости
        estimated_tokens: int,
        file_count: int,
    ) -> tuple[str, int | None]:
        """
        Определяет оптимальную стратегию работы с описаниями.

        Args:
            total_chars: Общее количество символов (сохранен для API совместимости).
            estimated_tokens: Оценочное количество токенов.
            file_count: Количество файлов.

        Returns:
            Кортеж (стратегия, рекомендуемая_длина_обрезки).

        Note:
            Параметр total_chars сохранен для обратной совместимости API,
            так как используется в тестах и внешних вызовах.
        """
        # Если все помещается с запасом (менее 50% лимита)
        if estimated_tokens < self.token_limit * 0.5:
            return ('full_descriptions', None)

        # Если помещается, но близко к лимиту (50-90% лимита)
        if estimated_tokens < self.token_limit * 0.9:
            return ('full_with_caution', None)

        # Если помещается, но на пределе (90-100% лимита)
        if estimated_tokens <= self.token_limit:
            return ('full_at_limit', None)

        # Если не помещается - нужна обрезка
        # Рассчитываем максимальную длину на один отчет
        available_chars = int(self.token_limit * self.chars_per_token)
        # Оставляем 10% запаса на JSON-обертку и служебные символы
        available_chars = int(available_chars * 0.9)
        max_chars_per_file = available_chars // file_count

        if max_chars_per_file >= 1000:
            return ('truncate_1000', 1000)
        elif max_chars_per_file >= 500:
            return ('truncate_500', 500)
        elif max_chars_per_file >= 300:
            return ('truncate_300', 300)
        else:
            # Критическая ситуация - слишком много файлов или слишком малый лимит
            return ('truncate_minimal', max(100, max_chars_per_file))


def estimate_json_size(
    descriptions: dict[str, str],
    chars_per_token: float = CHARS_PER_TOKEN_RU,
    token_limit: int = SAFE_DATA_LIMIT_TOKENS,
) -> dict[str, Any]:
    """
    Оценивает размер JSON-контейнера с описаниями отчетов.

    Основная функция для быстрой оценки. Возвращает словарь с результатами.

    Args:
        descriptions: Словарь {имя_отчета: текст_описания}.
        chars_per_token: Количество символов на один токен (по умолчанию 3.0).
        token_limit: Максимальное количество токенов для данных.

    Returns:
        Словарь с полями:
        - total_chars: Общее количество символов
        - estimated_tokens: Оценочное количество токенов
        - within_limit: Помещается ли в лимит (bool)
        - strategy: Рекомендуемая стратегия работы
        - min_chars: Минимальный размер файла
        - max_chars: Максимальный размер файла
        - avg_chars: Средний размер файла
        - file_count: Количество файлов
        - recommended_truncation: Рекомендуемая длина обрезки (если нужна)

    Example:
        >>> descriptions = {'report1': 'Текст описания...', 'report2': '...'}
        >>> result = estimate_json_size(descriptions)
        >>> print(f"Токенов: {result['estimated_tokens']}")
        >>> print(f"Стратегия: {result['strategy']}")
    """
    estimator = JSONSizeEstimator(
        chars_per_token=chars_per_token,
        token_limit=token_limit,
    )
    estimation = estimator.estimate_from_descriptions(descriptions)
    return estimation.to_dict()


def calculate_file_stats(
    directory: str | Path,
    pattern: str = '**/*.md',
) -> list[dict[str, Any]]:
    """
    Подсчитывает статистику по файлам в директории.

    Args:
        directory: Путь к директории.
        pattern: Glob-паттерн для поиска файлов.

    Returns:
        Список словарей со статистикой по каждому файлу.

    Example:
        >>> stats = calculate_file_stats('/path/to/descriptions')
        >>> for s in stats:
        ...     print(f"{s['filename']}: {s['char_count']} символов")
    """
    estimator = JSONSizeEstimator()
    estimation = estimator.estimate_from_directory(directory, pattern)

    return [
        {
            'filename': stat.filename,
            'filepath': stat.filepath,
            'char_count': stat.char_count,
            'estimated_tokens': stat.estimated_tokens,
        }
        for stat in estimation.file_stats
    ]


def get_truncation_strategy(
    total_chars: int,
    file_count: int,
    chars_per_token: float = CHARS_PER_TOKEN_RU,
    token_limit: int = SAFE_DATA_LIMIT_TOKENS,
) -> dict[str, Any]:
    """
    Определяет стратегию обрезки для заданных параметров.

    Args:
        total_chars: Общее количество символов.
        file_count: Количество файлов.
        chars_per_token: Символов на токен.
        token_limit: Лимит токенов.

    Returns:
        Словарь с рекомендуемой стратегией и параметрами.

    Example:
        >>> result = get_truncation_strategy(200000, 22)
        >>> print(f"Стратегия: {result['strategy']}")
        >>> if result['truncation_length']:
        ...     print(f"Обрезать до: {result['truncation_length']} символов")
    """
    estimated_tokens = int(total_chars / chars_per_token)
    within_limit = estimated_tokens <= token_limit

    estimator = JSONSizeEstimator(chars_per_token, token_limit)
    strategy, truncation_length = estimator._determine_strategy(
        total_chars,
        estimated_tokens,
        file_count,
    )

    return {
        'strategy': strategy,
        'within_limit': within_limit,
        'truncation_length': truncation_length,
        'estimated_tokens': estimated_tokens,
        'token_limit': token_limit,
        'usage_percent': round(estimated_tokens / token_limit * 100, 1),
    }


if __name__ == '__main__':
    # Демонстрация работы утилиты
    # Создаем тестовые данные
    test_descriptions = {
        'report_1': 'Описание первого отчета. ' * 100,
        'report_2': 'Описание второго отчета. ' * 200,
        'report_3': 'Описание третьего отчета. ' * 150,
    }

    result = estimate_json_size(test_descriptions)

    print('=' * 50)
    print('Результат оценки JSON-контейнера:')
    print('=' * 50)
    print(f"Всего символов: {result['total_chars']:,}")
    print(f"Оценка токенов: {result['estimated_tokens']:,}")
    print(f"Помещается в лимит: {'Да' if result['within_limit'] else 'Нет'}")
    print(f"Рекомендуемая стратегия: {result['strategy']}")
    print(f"Минимум символов: {result['min_chars']:,}")
    print(f"Максимум символов: {result['max_chars']:,}")
    print(f"В среднем: {result['avg_chars']:,.0f}")
    print(f"Количество файлов: {result['file_count']}")

    if result['recommended_truncation']:
        print(f"Рекомендуемая обрезка: {result['recommended_truncation']} символов")

    print('=' * 50)
