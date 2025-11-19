"""
Тесты для модуля index_selector.py

Тестируется:
1. Базовый выбор индекса с разными релевантностями
2. Обработка равных оценок (детерминированность)
3. Обработка отсутствующих отчетов
4. Обработка пустого словаря релевантностей
5. Валидация маппинга индексов
6. Структура INDEX_MAPPING (покрытие всех 22 отчетов)
7. Статистика индексов
8. Граничные случаи

Запуск:
    pytest tests/test_index_selector.py -v
    pytest tests/test_index_selector.py -v --cov=src.index_selector
"""

import pytest
import logging
from typing import Dict, List

from src.index_selector import (
    select_most_relevant_index,
    validate_index_mapping,
    get_index_statistics,
    load_index_mapping_from_file,
    INDEX_MAPPING,
    DEFAULT_INDEX
)


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def sample_report_relevance() -> Dict[str, float]:
    """Пример релевантностей отчетов для тестов."""
    return {
        "Дизайн и архитектура": 0.95,
        "Сильные стороны": 0.90,
        "Недостатки": 0.85,
        "Обследование": 0.30,
        "Общие_факторы": 0.25
    }


@pytest.fixture
def valid_custom_mapping() -> Dict[str, List[str]]:
    """Валидный кастомный маппинг для тестов."""
    return {
        "Index1": ["Report1", "Report2", "Report3"],
        "Index2": ["Report4", "Report5"],
        "Index3": ["Report6"]
    }


@pytest.fixture
def invalid_mapping_empty_reports() -> Dict[str, List[str]]:
    """Невалидный маппинг с пустым списком отчетов."""
    return {
        "Index1": ["Report1"],
        "Index2": []  # Пустой список
    }


@pytest.fixture
def invalid_mapping_duplicates() -> Dict[str, List[str]]:
    """Невалидный маппинг с дублирующимися отчетами."""
    return {
        "Index1": ["Report1", "Report2"],
        "Index2": ["Report2", "Report3"]  # Report2 дублируется
    }


# ============================================================================
# Тесты select_most_relevant_index
# ============================================================================

class TestSelectMostRelevantIndex:
    """Тесты основной функции выбора индекса."""

    def test_select_most_relevant_index_basic(self, sample_report_relevance):
        """
        Тест базового выбора индекса.

        Ожидается:
        - Выбран индекс "Otchety_po_dizaynu" (3 отчета с высокими оценками: 0.95, 0.90, 0.85)
        """
        result = select_most_relevant_index(sample_report_relevance)

        assert result == "Otchety_po_dizaynu"

    def test_select_most_relevant_index_equal_scores(self):
        """
        Тест выбора при равных оценках индексов.

        Ожидается:
        - При равных оценках выбирается первый по алфавиту
        - В данном случае "Dizayn" < "Intervyu" по алфавиту
        """
        report_rel = {
            "Структурированный_отчет_аудита": 0.5,  # Dizayn: 0.5
            "Общие_факторы": 0.5,  # Intervyu: (0.5 + ?) / 2 или только 0.5 если других нет
            "Отчет_о_связках": 0.5,  # Intervyu
            "Факторы_в_этом_заведении": 0.5  # Intervyu: (0.5 + 0.5 + 0.5) / 3 = 0.5
        }

        result = select_most_relevant_index(report_rel)

        # Оба индекса имеют среднюю релевантность 0.5
        # Dizayn: 1 отчет с 0.5 = 0.5
        # Intervyu: 3 отчета с 0.5 = 0.5
        # Должен выбраться первый по алфавиту
        assert result == "Dizayn"

    def test_select_most_relevant_index_missing_reports(self):
        """
        Тест обработки отсутствующих отчетов в report_relevance.

        Ожидается:
        - Индексы без отчетов в report_relevance получают релевантность 0.0
        - Выбирается индекс с хотя бы одним найденным отчетом
        """
        report_rel = {
            "Обследование": 0.8  # Только этот отчет есть (Iskhodniki_obsledovanie)
        }

        result = select_most_relevant_index(report_rel)

        assert result == "Iskhodniki_obsledovanie"

    def test_select_most_relevant_index_empty_relevance(self):
        """
        Тест обработки пустого словаря релевантностей.

        Ожидается:
        - Поднимается ValueError
        """
        with pytest.raises(ValueError, match="report_relevance не может быть пустым"):
            select_most_relevant_index({})

    def test_select_most_relevant_index_all_zero_relevance(self):
        """
        Тест когда все отчеты имеют релевантность 0.0.

        Ожидается:
        - Возвращается DEFAULT_INDEX
        """
        report_rel = {
            "Неизвестный отчет 1": 0.5,
            "Неизвестный отчет 2": 0.8
        }

        result = select_most_relevant_index(report_rel)

        # Ни один отчет не совпадает с известными => все индексы получат 0.0
        assert result == DEFAULT_INDEX

    def test_select_most_relevant_index_custom_mapping(self, valid_custom_mapping):
        """
        Тест с кастомным маппингом индексов.

        Ожидается:
        - Выбор индекса на основе переданного маппинга
        """
        report_rel = {
            "Report1": 0.9,
            "Report2": 0.8,
            "Report3": 0.7,
            "Report4": 0.3,
            "Report5": 0.2
        }

        result = select_most_relevant_index(report_rel, index_mapping=valid_custom_mapping)

        # Index1: (0.9 + 0.8 + 0.7) / 3 = 0.8
        # Index2: (0.3 + 0.2) / 2 = 0.25
        assert result == "Index1"

    def test_select_most_relevant_index_single_report_per_index(self):
        """
        Тест когда каждый индекс имеет только один отчет с оценкой.

        Ожидается:
        - Выбор индекса с максимальной оценкой единственного отчета
        """
        report_rel = {
            "Структурированный_отчет_аудита": 0.6,  # Dizayn
            "Аудит_Дизайна": 0.9,  # Iskhodniki_dizayn
            "Обследование": 0.4  # Iskhodniki_obsledovanie
        }

        result = select_most_relevant_index(report_rel)

        assert result == "Iskhodniki_dizayn"

    def test_select_most_relevant_index_partial_coverage(self):
        """
        Тест когда для индекса присутствуют не все отчеты.

        Ожидается:
        - Среднее вычисляется только по присутствующим отчетам
        """
        report_rel = {
            "Краткое резюме": 1.0,  # Itogovye_otchety
            "Ощущения": 0.9,  # Itogovye_otchety
            # Остальные 4 отчета из Itogovye_otchety отсутствуют
            "Обследование": 0.5  # Iskhodniki_obsledovanie
        }

        result = select_most_relevant_index(report_rel)

        # Itogovye_otchety: (1.0 + 0.9) / 2 = 0.95
        # Iskhodniki_obsledovanie: 0.5 / 1 = 0.5
        assert result == "Itogovye_otchety"


# ============================================================================
# Тесты validate_index_mapping
# ============================================================================

class TestValidateIndexMapping:
    """Тесты валидации маппинга индексов."""

    def test_validate_index_mapping_valid(self, valid_custom_mapping):
        """
        Тест валидации корректного маппинга.

        Ожидается:
        - Возвращается True
        """
        result = validate_index_mapping(valid_custom_mapping)

        assert result is True

    def test_validate_index_mapping_empty(self):
        """
        Тест валидации пустого маппинга.

        Ожидается:
        - Возвращается False
        """
        result = validate_index_mapping({})

        assert result is False

    def test_validate_index_mapping_empty_report_list(self, invalid_mapping_empty_reports):
        """
        Тест валидации маппинга с пустым списком отчетов.

        Ожидается:
        - Возвращается False
        """
        result = validate_index_mapping(invalid_mapping_empty_reports)

        assert result is False

    def test_validate_index_mapping_duplicates(self, invalid_mapping_duplicates):
        """
        Тест валидации маппинга с дублирующимися отчетами.

        Ожидается:
        - Возвращается False
        """
        result = validate_index_mapping(invalid_mapping_duplicates)

        assert result is False

    def test_validate_index_mapping_with_available_rags(self, valid_custom_mapping):
        """
        Тест валидации с проверкой существования индексов в available_rags.

        Ожидается:
        - True если все индексы есть в available_rags
        - False если хотя бы один индекс отсутствует
        """
        available_rags = ["Index1", "Index2", "Index3"]
        result = validate_index_mapping(valid_custom_mapping, available_rags=available_rags)
        assert result is True

        # Тест с отсутствующим индексом
        available_rags_incomplete = ["Index1", "Index2"]  # Index3 отсутствует
        result = validate_index_mapping(valid_custom_mapping, available_rags=available_rags_incomplete)
        assert result is False

    def test_validate_index_mapping_default(self):
        """
        Тест валидации дефолтного INDEX_MAPPING.

        Ожидается:
        - INDEX_MAPPING должен быть валидным
        """
        result = validate_index_mapping(INDEX_MAPPING)

        assert result is True


# ============================================================================
# Тесты INDEX_MAPPING
# ============================================================================

class TestIndexMappingStructure:
    """Тесты структуры и покрытия INDEX_MAPPING."""

    def test_index_mapping_has_7_indices(self):
        """
        Тест наличия всех 7 индексов в INDEX_MAPPING.

        Ожидается:
        - INDEX_MAPPING содержит ровно 7 индексов
        """
        assert len(INDEX_MAPPING) == 7

    def test_index_mapping_indices_names(self):
        """
        Тест правильности названий индексов.

        Ожидается:
        - Все 7 ожидаемых индексов присутствуют
        """
        expected_indices = {
            "Dizayn",
            "Intervyu",
            "Iskhodniki_dizayn",
            "Iskhodniki_obsledovanie",
            "Itogovye_otchety",
            "Otchety_po_dizaynu",
            "Otchety_po_obsledovaniyu"
        }

        assert set(INDEX_MAPPING.keys()) == expected_indices

    def test_index_mapping_total_22_reports(self):
        """
        Тест покрытия всех 22 отчетов.

        Ожидается:
        - В INDEX_MAPPING содержится ровно 22 уникальных отчета
        """
        all_reports = []
        for reports in INDEX_MAPPING.values():
            all_reports.extend(reports)

        # Проверка количества
        assert len(all_reports) == 22

        # Проверка уникальности (нет дублей)
        assert len(set(all_reports)) == 22

    def test_index_mapping_report_distribution(self):
        """
        Тест распределения отчетов по индексам.

        Ожидается:
        - Dizayn: 1 отчет
        - Intervyu: 3 отчета
        - Iskhodniki_dizayn: 1 отчет
        - Iskhodniki_obsledovanie: 1 отчет
        - Itogovye_otchety: 6 отчетов
        - Otchety_po_dizaynu: 5 отчетов
        - Otchety_po_obsledovaniyu: 5 отчетов
        """
        expected_distribution = {
            "Dizayn": 1,
            "Intervyu": 3,
            "Iskhodniki_dizayn": 1,
            "Iskhodniki_obsledovanie": 1,
            "Itogovye_otchety": 6,
            "Otchety_po_dizaynu": 5,
            "Otchety_po_obsledovaniyu": 5
        }

        actual_distribution = {
            index: len(reports)
            for index, reports in INDEX_MAPPING.items()
        }

        assert actual_distribution == expected_distribution

    def test_index_mapping_no_empty_lists(self):
        """
        Тест отсутствия пустых списков отчетов.

        Ожидается:
        - Ни один индекс не имеет пустого списка отчетов
        """
        for index_name, reports in INDEX_MAPPING.items():
            assert len(reports) > 0, f"Индекс '{index_name}' имеет пустой список отчетов"

    def test_index_mapping_report_names_not_empty(self):
        """
        Тест что все названия отчетов не пустые строки.

        Ожидается:
        - Все названия отчетов являются непустыми строками
        """
        for index_name, reports in INDEX_MAPPING.items():
            for report_name in reports:
                assert isinstance(report_name, str), \
                    f"Отчет в индексе '{index_name}' не является строкой: {report_name}"
                assert report_name.strip(), \
                    f"Отчет в индексе '{index_name}' является пустой строкой"


# ============================================================================
# Тесты get_index_statistics
# ============================================================================

class TestGetIndexStatistics:
    """Тесты функции получения статистики индексов."""

    def test_get_index_statistics_default(self):
        """
        Тест получения статистики для дефолтного INDEX_MAPPING.

        Ожидается:
        - Возвращается словарь с количеством отчетов для каждого индекса
        - Сумма всех отчетов равна 22
        """
        stats = get_index_statistics()

        assert len(stats) == 7
        assert sum(stats.values()) == 22

    def test_get_index_statistics_custom_mapping(self, valid_custom_mapping):
        """
        Тест получения статистики для кастомного маппинга.

        Ожидается:
        - Статистика соответствует переданному маппингу
        """
        stats = get_index_statistics(index_mapping=valid_custom_mapping)

        expected_stats = {
            "Index1": 3,
            "Index2": 2,
            "Index3": 1
        }

        assert stats == expected_stats

    def test_get_index_statistics_structure(self):
        """
        Тест структуры возвращаемой статистики.

        Ожидается:
        - Ключи - названия индексов (строки)
        - Значения - количество отчетов (целые числа > 0)
        """
        stats = get_index_statistics()

        for index_name, count in stats.items():
            assert isinstance(index_name, str)
            assert isinstance(count, int)
            assert count > 0


# ============================================================================
# Тесты load_index_mapping_from_file
# ============================================================================

class TestLoadIndexMappingFromFile:
    """Тесты функции загрузки маппинга из файла."""

    def test_load_index_mapping_from_file_not_implemented(self):
        """
        Тест что функция пока не реализована.

        Ожидается:
        - Поднимается NotImplementedError
        """
        with pytest.raises(NotImplementedError):
            load_index_mapping_from_file()


# ============================================================================
# Интеграционные тесты
# ============================================================================

class TestIntegration:
    """Интеграционные тесты полного workflow."""

    def test_full_workflow_realistic_scenario(self):
        """
        Тест полного workflow с реалистичными данными.

        Сценарий:
        - Пользователь спросил про дизайн отеля
        - Получены высокие оценки для отчетов по дизайну
        - Должен выбраться индекс Otchety_po_dizaynu
        """
        # Симуляция выхода из relevance_evaluator
        report_relevance = {
            "Дизайн и архитектура": 0.95,
            "Сильные стороны": 0.92,
            "Недостатки": 0.88,
            "Ожидания": 0.85,
            "Противоречия": 0.83,
            "Структурированный_отчет_аудита": 0.70,
            "Обследование": 0.25,
            "Краткое резюме": 0.20
        }

        # Выбор индекса
        selected_index = select_most_relevant_index(report_relevance)

        # Проверка результата
        assert selected_index == "Otchety_po_dizaynu"

    def test_full_workflow_itogi_scenario(self):
        """
        Тест полного workflow для итоговых отчетов.

        Сценарий:
        - Пользователь спросил про общие рекомендации и резюме
        - Должен выбраться индекс Itogovye_otchety
        """
        report_relevance = {
            "Краткое резюме": 0.98,
            "Итоговый": 0.95,
            "Рекомендации": 0.93,
            "Ощущения": 0.85,
            "Отдых": 0.75,
            "Заполняемость": 0.70,
            "Дизайн и архитектура": 0.40
        }

        selected_index = select_most_relevant_index(report_relevance)

        assert selected_index == "Itogovye_otchety"

    def test_validation_and_selection_together(self):
        """
        Тест совместной работы валидации и выбора индекса.

        Ожидается:
        - Валидация проходит успешно
        - Выбор индекса работает корректно
        """
        # Проверяем дефолтный маппинг
        assert validate_index_mapping(INDEX_MAPPING)

        # Используем его для выбора
        report_rel = {
            "Обследование": 0.9,
            "Аудит_Дизайна": 0.5
        }

        result = select_most_relevant_index(report_rel)

        assert result in INDEX_MAPPING.keys()


# ============================================================================
# Тесты логирования
# ============================================================================

class TestLogging:
    """Тесты логирования модуля."""

    def test_logging_info_messages(self, caplog, sample_report_relevance):
        """
        Тест что важные сообщения логируются на уровне INFO.

        Ожидается:
        - Логируется начало выбора
        - Логируется топ-3 индексов
        - Логируется выбранный индекс
        """
        with caplog.at_level(logging.INFO):
            select_most_relevant_index(sample_report_relevance)

        # Проверяем наличие ключевых сообщений
        assert any("Начинаем выбор индекса" in record.message for record in caplog.records)
        assert any("Топ-3 индекса" in record.message for record in caplog.records)
        assert any("Выбран индекс" in record.message for record in caplog.records)

    def test_logging_warning_on_missing_reports(self, caplog):
        """
        Тест что логируется предупреждение при отсутствии отчетов индекса.

        Ожидается:
        - Логируется WARNING если ни один отчет индекса не найден
        """
        report_rel = {
            "Неизвестный отчет": 0.5
        }

        with caplog.at_level(logging.WARNING):
            select_most_relevant_index(report_rel)

        # Должны быть предупреждения о том, что отчеты не найдены
        warnings = [record for record in caplog.records if record.levelname == "WARNING"]
        assert len(warnings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.index_selector", "--cov-report=term-missing"])
