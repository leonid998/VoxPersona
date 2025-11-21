"""
Тесты для функции build_json_container() из модуля relevance_evaluator.

Проверяют:
- Корректность структуры JSON-контейнера
- Наличие всех 22 отчетов
- Правильность маппинга на 7 индексов
- Валидность JSON на выходе

Запуск тестов:
    pytest src/tests/test_json_container.py -v

Запуск с покрытием:
    pytest src/tests/test_json_container.py -v --cov=src.relevance_evaluator
"""

import json
import sys
from pathlib import Path

import pytest

# Добавить путь к src для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from relevance_evaluator import (
    REPORT_TO_INDEX_MAPPING,
    INDEX_DISPLAY_NAMES,
    build_json_container,
    get_json_container_stats,
    load_report_descriptions,
)


# === FIXTURES ===

@pytest.fixture
def sample_descriptions():
    """
    Минимальный набор описаний отчетов для тестирования.
    Включает по одному отчету из нескольких индексов.
    """
    return {
        "Структурированный_отчет_аудита": "Описание отчета о дизайне интерьера...",
        "Общие_факторы": "Описание факторов принятия решений потребителями...",
        "Аудит_Дизайна": "Описание аудита дизайна...",
    }


@pytest.fixture
def sample_mapping():
    """
    Маппинг для тестового набора описаний.
    """
    return {
        "Структурированный_отчет_аудита": "Dizayn",
        "Общие_факторы": "Intervyu",
        "Аудит_Дизайна": "Iskhodniki_dizayn",
    }


@pytest.fixture
def full_descriptions():
    """
    Полный набор описаний отчетов из файловой системы.
    Загружается один раз для всех тестов.
    """
    return load_report_descriptions()


# === ТЕСТЫ СТРУКТУРЫ JSON ===

class TestBuildJsonContainerStructure:
    """Тесты структуры JSON-контейнера."""

    def test_build_json_container_structure(self, sample_descriptions, sample_mapping):
        """
        Проверяет что JSON имеет правильную структуру с обязательными полями.

        Ожидаемые поля:
        - reports: список отчетов
        - indices: список индексов
        - total_reports: количество отчетов
        - total_indices: количество индексов
        """
        json_string = build_json_container(
            sample_descriptions,
            report_to_index=sample_mapping
        )

        # Парсим JSON
        data = json.loads(json_string)

        # Проверяем обязательные поля верхнего уровня
        assert "reports" in data, "Отсутствует поле 'reports'"
        assert "indices" in data, "Отсутствует поле 'indices'"
        assert "total_reports" in data, "Отсутствует поле 'total_reports'"
        assert "total_indices" in data, "Отсутствует поле 'total_indices'"

        # Проверяем типы
        assert isinstance(data["reports"], list), "reports должен быть списком"
        assert isinstance(data["indices"], list), "indices должен быть списком"
        assert isinstance(data["total_reports"], int), "total_reports должен быть int"
        assert isinstance(data["total_indices"], int), "total_indices должен быть int"

    def test_report_entry_structure(self, sample_descriptions, sample_mapping):
        """
        Проверяет структуру каждой записи отчета.

        Каждый отчет должен содержать:
        - id: уникальный числовой идентификатор
        - name: имя отчета
        - index: название индекса
        - description: полное описание
        """
        json_string = build_json_container(
            sample_descriptions,
            report_to_index=sample_mapping
        )
        data = json.loads(json_string)

        for report in data["reports"]:
            assert "id" in report, "Отчет должен содержать 'id'"
            assert "name" in report, "Отчет должен содержать 'name'"
            assert "index" in report, "Отчет должен содержать 'index'"
            assert "description" in report, "Отчет должен содержать 'description'"

            # Проверяем типы полей
            assert isinstance(report["id"], int), "id должен быть int"
            assert isinstance(report["name"], str), "name должен быть str"
            assert isinstance(report["index"], str), "index должен быть str"
            assert isinstance(report["description"], str), "description должен быть str"

    def test_index_entry_structure(self, sample_descriptions, sample_mapping):
        """
        Проверяет структуру каждой записи индекса.

        Каждый индекс должен содержать:
        - name: транслитерированное имя
        - display_name: человекочитаемое название
        - report_ids: список ID отчетов
        """
        json_string = build_json_container(
            sample_descriptions,
            report_to_index=sample_mapping
        )
        data = json.loads(json_string)

        for index in data["indices"]:
            assert "name" in index, "Индекс должен содержать 'name'"
            assert "display_name" in index, "Индекс должен содержать 'display_name'"
            assert "report_ids" in index, "Индекс должен содержать 'report_ids'"

            # Проверяем типы
            assert isinstance(index["name"], str), "name должен быть str"
            assert isinstance(index["display_name"], str), "display_name должен быть str"
            assert isinstance(index["report_ids"], list), "report_ids должен быть list"

            # Все ID должны быть числами
            for report_id in index["report_ids"]:
                assert isinstance(report_id, int), f"report_id должен быть int, получено {type(report_id)}"

    def test_report_ids_start_from_one(self, sample_descriptions, sample_mapping):
        """
        Проверяет что ID отчетов начинаются с 1.
        """
        json_string = build_json_container(
            sample_descriptions,
            report_to_index=sample_mapping
        )
        data = json.loads(json_string)

        # Собираем все ID
        ids = [report["id"] for report in data["reports"]]

        assert min(ids) == 1, "Минимальный ID должен быть 1"

        # ID должны быть последовательными
        expected_ids = list(range(1, len(sample_descriptions) + 1))
        assert sorted(ids) == expected_ids, "ID должны быть последовательными"


# === ТЕСТЫ ПОЛНОТЫ ДАННЫХ ===

class TestAllReportsIncluded:
    """Тесты полноты включения всех отчетов."""

    def test_all_reports_included_with_full_data(self, full_descriptions):
        """
        Проверяет что все 22 отчета включены в JSON-контейнер.

        Это ключевой тест - должно быть ровно 22 отчета.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        assert data["total_reports"] == 22, f"Должно быть 22 отчета, получено {data['total_reports']}"
        assert len(data["reports"]) == 22, "В списке reports должно быть 22 элемента"  # SonarCloud fix: removed empty f-string prefix

    def test_all_report_names_present(self, full_descriptions):
        """
        Проверяет что все имена отчетов из descriptions присутствуют в JSON.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        # Собираем имена из JSON
        json_report_names = {report["name"] for report in data["reports"]}

        # Все имена из входных данных должны быть в JSON
        for name in full_descriptions.keys():
            assert name in json_report_names, f"Отчет '{name}' отсутствует в JSON"

    def test_descriptions_not_truncated(self, full_descriptions):
        """
        Проверяет что описания не обрезаются.

        Каждое описание в JSON должно совпадать с оригиналом.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        for report in data["reports"]:
            original_desc = full_descriptions.get(report["name"])
            if original_desc:
                assert report["description"] == original_desc, (
                    f"Описание отчета '{report['name']}' было изменено"
                )


# === ТЕСТЫ МАППИНГА ИНДЕКСОВ ===

class TestIndicesMappingCorrect:
    """Тесты корректности маппинга отчетов на индексы."""

    def test_all_seven_indices_present(self, full_descriptions):
        """
        Проверяет что все 7 индексов представлены в JSON.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        assert data["total_indices"] == 7, f"Должно быть 7 индексов, получено {data['total_indices']}"
        assert len(data["indices"]) == 7, "В списке indices должно быть 7 элементов"

    def test_expected_indices_present(self, full_descriptions):
        """
        Проверяет наличие конкретных ожидаемых индексов.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        # Ожидаемые индексы
        expected_indices = {
            "Dizayn",
            "Intervyu",
            "Iskhodniki_dizayn",
            "Iskhodniki_obsledovanie",
            "Itogovye_otchety",
            "Otchety_po_dizaynu",
            "Otchety_po_obsledovaniyu"
        }

        json_indices = {idx["name"] for idx in data["indices"]}

        assert json_indices == expected_indices, (
            f"Несоответствие индексов.\n"
            f"Ожидалось: {expected_indices}\n"
            f"Получено: {json_indices}"
        )

    def test_reports_correctly_mapped_to_indices(self, full_descriptions):
        """
        Проверяет что каждый отчет привязан к правильному индексу
        согласно REPORT_TO_INDEX_MAPPING.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        for report in data["reports"]:
            report_name = report["name"]
            json_index = report["index"]

            # Получаем ожидаемый индекс из маппинга
            expected_index = REPORT_TO_INDEX_MAPPING.get(report_name)

            if expected_index:
                assert json_index == expected_index, (
                    f"Отчет '{report_name}' привязан к индексу '{json_index}', "
                    f"но должен быть привязан к '{expected_index}'"
                )

    def test_report_ids_match_index_references(self, full_descriptions):
        """
        Проверяет что report_ids в индексах ссылаются на существующие отчеты.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        # Собираем все ID отчетов
        all_report_ids = {report["id"] for report in data["reports"]}

        # Проверяем что все ссылки из indices валидны
        for index in data["indices"]:
            for report_id in index["report_ids"]:
                assert report_id in all_report_ids, (
                    f"Индекс '{index['name']}' ссылается на несуществующий "
                    f"report_id={report_id}"
                )

    def test_no_duplicate_report_ids_in_indices(self, full_descriptions):
        """
        Проверяет что каждый отчет привязан только к одному индексу.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        # Собираем все report_ids из всех индексов
        all_ids = []
        for index in data["indices"]:
            all_ids.extend(index["report_ids"])

        # Не должно быть дубликатов
        assert len(all_ids) == len(set(all_ids)), (
            "Найдены дублирующиеся report_ids в разных индексах"
        )

    def test_index_display_names_correct(self, full_descriptions):
        """
        Проверяет корректность человекочитаемых названий индексов.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        for index in data["indices"]:
            index_name = index["name"]
            display_name = index["display_name"]

            expected_display = INDEX_DISPLAY_NAMES.get(index_name)
            if expected_display:
                assert display_name == expected_display, (
                    f"display_name для '{index_name}' = '{display_name}', "
                    f"ожидалось '{expected_display}'"
                )


# === ТЕСТЫ ВАЛИДНОСТИ JSON ===

class TestJsonIsValid:
    """Тесты валидности JSON на выходе."""

    def test_json_is_valid(self, sample_descriptions, sample_mapping):
        """
        Проверяет что результат является валидным JSON.
        """
        json_string = build_json_container(
            sample_descriptions,
            report_to_index=sample_mapping
        )

        # Попытка парсинга не должна вызывать исключение
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            pytest.fail(f"Невалидный JSON: {e}")

    def test_json_is_valid_with_full_data(self, full_descriptions):
        """
        Проверяет валидность JSON с полными данными (22 отчета).
        """
        json_string = build_json_container(full_descriptions)

        try:
            _ = json.loads(json_string)  # SonarCloud fix: unused variable data replaced with _
        except json.JSONDecodeError as e:
            pytest.fail(f"Невалидный JSON с полными данными: {e}")

    def test_russian_characters_preserved(self, full_descriptions):
        """
        Проверяет что русские символы сохраняются без экранирования.
        """
        json_string = build_json_container(full_descriptions)

        # Проверяем что русские буквы не экранированы как \uXXXX
        assert "\\u" not in json_string[:1000], (
            "Русские символы не должны быть экранированы"
        )

        # Проверяем наличие кириллицы
        assert any(ord(c) > 1024 for c in json_string), (
            "В JSON должны быть русские символы"
        )


# === ТЕСТЫ ВАЛИДАЦИИ И EDGE CASES ===

class TestValidationAndEdgeCases:
    """Тесты валидации входных данных и граничных случаев."""

    def test_empty_descriptions_raises_error(self):
        """
        Проверяет что пустой словарь описаний вызывает ValueError.
        """
        with pytest.raises(ValueError, match="не может быть пустым"):
            build_json_container({})

    def test_none_descriptions_raises_error(self):
        """
        Проверяет что None вызывает TypeError.
        """
        with pytest.raises((ValueError, TypeError)):
            build_json_container(None)

    def test_custom_mapping(self):
        """
        Проверяет работу с кастомным маппингом.
        """
        descriptions = {
            "Report1": "Description 1",
            "Report2": "Description 2",
        }
        custom_mapping = {
            "Report1": "Index_A",
            "Report2": "Index_B",
        }

        json_string = build_json_container(descriptions, report_to_index=custom_mapping)
        data = json.loads(json_string)

        # Проверяем что использован кастомный маппинг
        report_indices = {r["name"]: r["index"] for r in data["reports"]}
        assert report_indices["Report1"] == "Index_A"
        assert report_indices["Report2"] == "Index_B"

    def test_reports_sorted_by_name(self, full_descriptions):
        """
        Проверяет что отчеты отсортированы по имени для детерминированности.
        """
        json_string = build_json_container(full_descriptions)
        data = json.loads(json_string)

        names = [r["name"] for r in data["reports"]]
        assert names == sorted(names), "Отчеты должны быть отсортированы по имени"


# === ТЕСТЫ ВСПОМОГАТЕЛЬНЫХ ФУНКЦИЙ ===

class TestGetJsonContainerStats:
    """Тесты функции get_json_container_stats."""

    def test_stats_structure(self, sample_descriptions, sample_mapping):
        """
        Проверяет структуру возвращаемой статистики.
        """
        json_string = build_json_container(
            sample_descriptions,
            report_to_index=sample_mapping
        )
        stats = get_json_container_stats(json_string)

        assert "total_chars" in stats
        assert "estimated_tokens" in stats
        assert "total_reports" in stats
        assert "total_indices" in stats
        assert "reports_per_index" in stats
        assert "is_valid" in stats

    def test_stats_with_full_data(self, full_descriptions):
        """
        Проверяет статистику с полными данными.

        Реальный размер данных: ~91k символов, ~30k токенов.
        """
        json_string = build_json_container(full_descriptions)
        stats = get_json_container_stats(json_string)

        # Проверяем базовые значения
        assert stats["total_reports"] == 22
        assert stats["total_indices"] == 7
        assert stats["is_valid"] is True

        # Размер должен быть существенным (реальный размер ~91k символов)
        assert stats["total_chars"] > 80000, (
            f"Ожидается > 80k символов, получено {stats['total_chars']}"
        )

        # Оценка токенов (~30k для реальных данных)
        assert stats["estimated_tokens"] > 25000, (
            f"Ожидается > 25k токенов, получено {stats['estimated_tokens']}"
        )

    def test_stats_reports_per_index(self, full_descriptions):
        """
        Проверяет количество отчетов по индексам.
        """
        json_string = build_json_container(full_descriptions)
        stats = get_json_container_stats(json_string)

        rpi = stats["reports_per_index"]

        # Проверяем ожидаемое распределение
        assert rpi.get("Dizayn") == 1, "Dizayn должен иметь 1 отчет"
        assert rpi.get("Intervyu") == 3, "Intervyu должен иметь 3 отчета"
        assert rpi.get("Itogovye_otchety") == 6, "Itogovye_otchety должен иметь 6 отчетов"
        assert rpi.get("Otchety_po_dizaynu") == 5, "Otchety_po_dizaynu должен иметь 5 отчетов"
        assert rpi.get("Otchety_po_obsledovaniyu") == 5, "Otchety_po_obsledovaniyu должен иметь 5 отчетов"

    def test_stats_with_invalid_json(self):
        """
        Проверяет обработку невалидного JSON.
        """
        invalid_json = "{ invalid json }"
        stats = get_json_container_stats(invalid_json)

        assert stats["is_valid"] is False
        assert "error" in stats
        assert stats["total_reports"] == 0
        assert stats["total_indices"] == 0


# === ИНТЕГРАЦИОННЫЕ ТЕСТЫ ===

class TestIntegration:
    """Интеграционные тесты с реальными данными."""

    def test_full_workflow(self):
        """
        Полный workflow: загрузка -> создание контейнера -> статистика.
        """
        # Загрузка описаний
        descriptions = load_report_descriptions()
        assert len(descriptions) == 22

        # Создание контейнера
        json_string = build_json_container(descriptions)

        # Получение статистики
        stats = get_json_container_stats(json_string)

        # Финальная проверка
        assert stats["is_valid"] is True
        assert stats["total_reports"] == 22
        assert stats["total_indices"] == 7

        # Вывод информации для отладки
        print("\n=== Статистика JSON-контейнера ===")  # SonarCloud fix: removed empty f-string prefix
        print(f"Размер: {stats['total_chars']:,} символов")
        print(f"Токенов: ~{stats['estimated_tokens']:,}")
        print(f"Отчетов: {stats['total_reports']}")
        print(f"Индексов: {stats['total_indices']}")
        print(f"Распределение по индексам: {stats['reports_per_index']}")

    def test_json_container_size_acceptable(self, full_descriptions):
        """
        Проверяет что размер контейнера приемлем для API.

        Реальный размер: ~91k символов = ~30k токенов (помещается в контекст).
        """
        json_string = build_json_container(full_descriptions)
        stats = get_json_container_stats(json_string)

        # Размер должен быть в ожидаемых пределах
        # 80k-120k символов
        assert 80000 < stats["total_chars"] < 120000, (
            f"Размер вне ожидаемого диапазона: {stats['total_chars']} символов"
        )

        # Токены: 25k-40k
        assert 25000 < stats["estimated_tokens"] < 40000, (
            f"Токенов вне ожидаемого диапазона: {stats['estimated_tokens']}"
        )


if __name__ == "__main__":
    # Запуск тестов с выводом
    pytest.main([__file__, "-v", "--tb=short"])
