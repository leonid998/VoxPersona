# -*- coding: utf-8 -*-
"""
Unit-тесты для модуля json_size_estimator.

Тестирует функции оценки размера JSON-контейнера с описаниями отчетов.
"""

import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils_pkg.json_size_estimator import (
    CHARS_PER_TOKEN_RU,
    SAFE_DATA_LIMIT_TOKENS,
    FileStats,
    JSONSizeEstimator,
    SizeEstimation,
    calculate_file_stats,
    estimate_json_size,
    get_truncation_strategy,
)


class TestFileStats:
    """Тесты для dataclass FileStats."""

    def test_file_stats_creation(self) -> None:
        """Тест создания объекта FileStats."""
        stats = FileStats(
            filename='test_report.md',
            filepath='/path/to/test_report.md',
            char_count=1000,
            estimated_tokens=333,
        )
        assert stats.filename == 'test_report.md'
        assert stats.char_count == 1000
        assert stats.estimated_tokens == 333

    def test_short_name_property(self) -> None:
        """Тест свойства short_name."""
        stats = FileStats(
            filename='Содержание_отчетов_Дизайн.md',
            filepath='',
            char_count=500,
            estimated_tokens=167,
        )
        assert stats.short_name == 'Содержание_отчетов_Дизайн'


class TestSizeEstimation:
    """Тесты для dataclass SizeEstimation."""

    def test_to_dict(self) -> None:
        """Тест конвертации в словарь."""
        estimation = SizeEstimation(
            total_chars=10000,
            estimated_tokens=3333,
            within_limit=True,
            strategy='full_descriptions',
            file_stats=[],
            min_chars=100,
            max_chars=500,
            avg_chars=300.0,
            recommended_truncation=None,
        )
        result = estimation.to_dict()

        assert result['total_chars'] == 10000
        assert result['estimated_tokens'] == 3333
        assert result['within_limit'] is True
        assert result['strategy'] == 'full_descriptions'
        assert result['file_count'] == 0
        assert result['recommended_truncation'] is None


class TestJSONSizeEstimator:
    """Тесты для класса JSONSizeEstimator."""

    def test_estimate_tokens(self) -> None:
        """Тест оценки токенов в тексте."""
        estimator = JSONSizeEstimator(chars_per_token=3.0)

        # 300 символов при 3 символа/токен = 100 токенов
        text = 'а' * 300
        tokens = estimator.estimate_tokens(text)
        assert tokens == 100

    def test_estimate_tokens_english(self) -> None:
        """Тест оценки токенов для английского текста."""
        estimator = JSONSizeEstimator(chars_per_token=4.0)

        text = 'a' * 400
        tokens = estimator.estimate_tokens(text)
        assert tokens == 100

    def test_estimate_from_empty_descriptions(self) -> None:
        """Тест пустого словаря описаний."""
        estimator = JSONSizeEstimator()
        result = estimator.estimate_from_descriptions({})

        assert result.total_chars == 0
        assert result.estimated_tokens == 0
        assert result.within_limit is True
        assert result.strategy == 'empty'

    def test_estimate_from_descriptions_small(self) -> None:
        """Тест маленького объема данных."""
        estimator = JSONSizeEstimator(
            chars_per_token=3.0,
            token_limit=100000,  # 100K токенов
        )

        # Создаем данные ~10K символов (~3.3K токенов) - менее 5% лимита
        descriptions = {
            'report_1': 'Текст ' * 500,  # ~3000 символов
            'report_2': 'Описание ' * 500,  # ~4500 символов
        }

        result = estimator.estimate_from_descriptions(descriptions)

        assert result.within_limit is True
        assert result.strategy == 'full_descriptions'
        assert len(result.file_stats) == 2

    def test_estimate_from_descriptions_large(self) -> None:
        """Тест большого объема данных, превышающего лимит."""
        estimator = JSONSizeEstimator(
            chars_per_token=3.0,
            token_limit=1000,  # Маленький лимит для теста
        )

        # Создаем данные ~6000 символов (~2000 токенов) - превышает лимит
        descriptions = {
            'report_1': 'Текст ' * 500,
            'report_2': 'Описание ' * 500,
        }

        result = estimator.estimate_from_descriptions(descriptions)

        assert result.within_limit is False
        assert 'truncate' in result.strategy
        assert result.recommended_truncation is not None

    def test_estimate_from_directory(self, tmp_path: Path) -> None:
        """Тест чтения файлов из директории."""
        # Создаем тестовые файлы
        (tmp_path / 'report1.md').write_text('Содержание первого отчета.', encoding='utf-8')
        (tmp_path / 'report2.md').write_text('Содержание второго отчета.', encoding='utf-8')
        (tmp_path / 'other.txt').write_text('Не должен учитываться.', encoding='utf-8')

        estimator = JSONSizeEstimator()
        result = estimator.estimate_from_directory(tmp_path, '*.md')

        assert len(result.file_stats) == 2
        assert result.total_chars > 0
        assert all(stat.filename.endswith('.md') for stat in result.file_stats)

    def test_estimate_from_nonexistent_directory(self, tmp_path: Path) -> None:
        """Тест обработки несуществующей директории."""
        estimator = JSONSizeEstimator()

        # Используем путь который точно не существует внутри tmp_path
        nonexistent_path = tmp_path / 'this_directory_does_not_exist_12345'

        with pytest.raises(FileNotFoundError):
            estimator.estimate_from_directory(nonexistent_path)

    def test_strategy_full_descriptions(self) -> None:
        """Тест стратегии полных описаний (< 50% лимита)."""
        estimator = JSONSizeEstimator(
            chars_per_token=3.0,
            token_limit=10000,
        )

        # 3000 символов = 1000 токенов = 10% лимита
        strategy, truncation = estimator._determine_strategy(
            total_chars=3000,
            estimated_tokens=1000,
            file_count=3,
        )

        assert strategy == 'full_descriptions'
        assert truncation is None

    def test_strategy_full_with_caution(self) -> None:
        """Тест стратегии с осторожностью (50-90% лимита)."""
        estimator = JSONSizeEstimator(
            chars_per_token=3.0,
            token_limit=10000,
        )

        # 21000 символов = 7000 токенов = 70% лимита
        strategy, truncation = estimator._determine_strategy(
            total_chars=21000,
            estimated_tokens=7000,
            file_count=5,
        )

        assert strategy == 'full_with_caution'
        assert truncation is None

    def test_strategy_truncate(self) -> None:
        """Тест стратегии обрезки (> 100% лимита)."""
        estimator = JSONSizeEstimator(
            chars_per_token=3.0,
            token_limit=1000,
        )

        # 6000 символов = 2000 токенов = 200% лимита
        strategy, truncation = estimator._determine_strategy(
            total_chars=6000,
            estimated_tokens=2000,
            file_count=3,
        )

        assert 'truncate' in strategy
        assert truncation is not None


class TestEstimateJsonSize:
    """Тесты для функции estimate_json_size."""

    def test_basic_usage(self) -> None:
        """Тест базового использования функции."""
        descriptions = {
            'report_1': 'Текст описания первого отчета.' * 10,
            'report_2': 'Текст описания второго отчета.' * 20,
        }

        result = estimate_json_size(descriptions)

        assert 'total_chars' in result
        assert 'estimated_tokens' in result
        assert 'within_limit' in result
        assert 'strategy' in result
        assert 'file_count' in result
        assert result['file_count'] == 2

    def test_empty_descriptions(self) -> None:
        """Тест пустого словаря."""
        result = estimate_json_size({})

        assert result['total_chars'] == 0
        assert result['estimated_tokens'] == 0
        assert result['within_limit'] is True

    def test_custom_parameters(self) -> None:
        """Тест с кастомными параметрами."""
        descriptions = {'report': 'a' * 1000}

        result = estimate_json_size(
            descriptions,
            chars_per_token=4.0,
            token_limit=100,
        )

        # 1000 символов / 4 = 250 токенов > 100 лимит
        assert result['estimated_tokens'] == 250
        assert result['within_limit'] is False


class TestCalculateFileStats:
    """Тесты для функции calculate_file_stats."""

    def test_calculate_from_directory(self, tmp_path: Path) -> None:
        """Тест расчета статистики из директории."""
        # Создаем тестовые файлы
        content1 = 'Первый файл. ' * 10
        content2 = 'Второй файл. ' * 20

        (tmp_path / 'file1.md').write_text(content1, encoding='utf-8')
        (tmp_path / 'file2.md').write_text(content2, encoding='utf-8')

        stats = calculate_file_stats(tmp_path)

        assert len(stats) == 2

        for stat in stats:
            assert 'filename' in stat
            assert 'filepath' in stat
            assert 'char_count' in stat
            assert 'estimated_tokens' in stat
            assert stat['char_count'] > 0

    def test_nested_directories(self, tmp_path: Path) -> None:
        """Тест поиска в поддиректориях."""
        # Создаем вложенную структуру
        subdir = tmp_path / 'subdir'
        subdir.mkdir()

        (tmp_path / 'root.md').write_text('Корневой файл.', encoding='utf-8')
        (subdir / 'nested.md').write_text('Вложенный файл.', encoding='utf-8')

        stats = calculate_file_stats(tmp_path, '**/*.md')

        assert len(stats) == 2


class TestGetTruncationStrategy:
    """Тесты для функции get_truncation_strategy."""

    def test_no_truncation_needed(self) -> None:
        """Тест когда обрезка не нужна."""
        result = get_truncation_strategy(
            total_chars=10000,
            file_count=5,
            token_limit=100000,
        )

        assert result['within_limit'] is True
        assert result['truncation_length'] is None
        assert result['usage_percent'] < 50

    def test_truncation_needed(self) -> None:
        """Тест когда обрезка нужна."""
        result = get_truncation_strategy(
            total_chars=100000,
            file_count=10,
            token_limit=10000,
        )

        assert result['within_limit'] is False
        assert result['truncation_length'] is not None
        assert 'truncate' in result['strategy']

    def test_usage_percent_calculation(self) -> None:
        """Тест расчета процента использования."""
        result = get_truncation_strategy(
            total_chars=30000,  # 10000 токенов при 3 символа/токен
            file_count=5,
            chars_per_token=3.0,
            token_limit=20000,
        )

        # 10000 / 20000 = 50%
        assert result['usage_percent'] == 50.0


class TestRealWorldScenario:
    """Интеграционные тесты для реальных сценариев."""

    def test_voxpersona_scenario(self) -> None:
        """
        Тест сценария VoxPersona: 22 файла общим объемом ~164K символов.

        Проверяем, что такой объем данных помещается в лимит Claude Haiku.
        """
        # Эмулируем реальные данные проекта
        file_sizes = [
            7687, 10117, 6542, 6413, 6098, 6030, 5957, 5791, 6990,
            15784, 18926, 6330, 5633, 6564, 6758, 5990, 5660, 6445,
            5661, 6290, 6196, 6460
        ]

        # Создаем тестовые описания с соответствующими размерами
        descriptions = {}
        for i, size in enumerate(file_sizes):
            descriptions[f'report_{i+1}'] = 'а' * size

        result = estimate_json_size(descriptions)

        # Проверяем общие характеристики
        assert result['total_chars'] == sum(file_sizes)
        assert result['file_count'] == 22

        # При 3 символа/токен: 164322 / 3 = ~54774 токенов
        # Лимит 198000 токенов - должно помещаться с запасом
        assert result['within_limit'] is True
        assert result['strategy'] == 'full_descriptions'

    def test_edge_case_exactly_at_limit(self) -> None:
        """Тест граничного случая: ровно на лимите."""
        # Создаем данные ровно на 90% лимита
        # 198000 * 0.9 = 178200 токенов = 534600 символов
        descriptions = {'report': 'а' * 534600}

        result = estimate_json_size(
            descriptions,
            chars_per_token=3.0,
            token_limit=198000,
        )

        assert result['within_limit'] is True
        assert result['strategy'] == 'full_at_limit'

    def test_multiple_small_files(self) -> None:
        """Тест множества маленьких файлов."""
        # 100 файлов по 500 символов = 50000 символов
        descriptions = {f'report_{i}': 'а' * 500 for i in range(100)}

        result = estimate_json_size(descriptions)

        assert result['file_count'] == 100
        assert result['total_chars'] == 50000
        assert result['avg_chars'] == 500.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
