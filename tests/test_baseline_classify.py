"""
Baseline тесты для classify_query.

ЦЕЛЬ: Зафиксировать текущее поведение classify_query перед внедрением Router Agent.

ТЕКУЩАЯ СИСТЕМА:
- Функция расположена в src/analysis.py (строки 432-444)
- Различает только 2 категории: "дизайн" и "интервью"
- Использует Claude API через send_msg_to_model (медленно, дорого)
- Использует fetch_prompt_by_name для получения промпта из БД
- Покрывает только 2/7 индексов (28.6% функциональности)

BASELINE МЕТРИКИ (ожидаемые):
- Точность: невозможно оценить без Router Agent (7 индексов → 2 категории)
- Среднее время: ~1-2 секунды на вопрос (зависит от Claude API)
- Покрытие индексов: 2/7 (Dizayn, Intervyu)
- Распределение:
  * "дизайн" - вопросы о дизайне интерьера
  * "интервью" - вопросы о мнениях и впечатлениях гостей
  * "Не определено" - ошибки парсинга JSON или исключения

ЗАПУСК ТЕСТОВ:
- Быстрые (с мокированием): pytest tests/test_baseline_classify.py
- Медленные (с API): pytest tests/test_baseline_classify.py -m slow
- С выводом метрик: pytest tests/test_baseline_classify.py -m slow -s

ПРИМЕЧАНИЕ:
Integration тест делает реальные API вызовы к Claude Anthropic API.
Рекомендуется запускать редко, только для фиксации baseline метрик.
"""

import sys
import json
import time
import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch, MagicMock

import pytest

# Добавить src в PYTHONPATH для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Импорты из project
from analysis import classify_query, send_msg_to_model


# ============================================================================
# UNIT ТЕСТЫ С МОКИРОВАНИЕМ (быстрые, не требуют API)
# ============================================================================


class TestClassifyQueryBaseline:
    """Unit тесты для classify_query с мокированием send_msg_to_model."""

    @pytest.fixture
    def mock_send_msg(self):
        """Фикстура для мокирования send_msg_to_model."""
        with patch('analysis.send_msg_to_model') as mock:
            yield mock

    @pytest.fixture
    def mock_fetch_prompt(self):
        """Фикстура для мокирования fetch_prompt_by_name."""
        with patch('analysis.fetch_prompt_by_name') as mock:
            mock.return_value = "Classify the query as 'дизайн' or 'интервью'"
            yield mock

    def test_classify_query_design(self, mock_send_msg, mock_fetch_prompt):
        """Тест классификации вопроса о дизайне.

        Когда send_msg_to_model возвращает JSON с категорией "дизайн",
        функция должна вернуть "дизайн".
        """
        # Arrange
        mock_response = '{"category": "дизайн"}'
        mock_send_msg.return_value = mock_response
        test_query = "как сделано освещение в холле отеля"

        # Act
        result = classify_query(test_query)

        # Assert
        assert result == "дизайн"
        mock_send_msg.assert_called_once()
        mock_fetch_prompt.assert_called_once_with(prompt_name="prompt_classify")

    def test_classify_query_interview(self, mock_send_msg, mock_fetch_prompt):
        """Тест классификации вопроса об интервью.

        Когда send_msg_to_model возвращает JSON с категорией "интервью",
        функция должна вернуть "интервью".
        """
        # Arrange
        mock_response = '{"category": "интервью"}'
        mock_send_msg.return_value = mock_response
        test_query = "что гости говорили о сервисе в ресторане"

        # Act
        result = classify_query(test_query)

        # Assert
        assert result == "интервью"
        mock_send_msg.assert_called_once()

    def test_classify_query_with_whitespace(self, mock_send_msg, mock_fetch_prompt):
        """Тест обработки лишних пробелов в ответе.

        send_msg_to_model может вернуть ответ с пробелами в начале/конце.
        Функция должна корректно их обрабатывать.
        """
        # Arrange
        mock_response = '  \n{"category": "дизайн"}\n  '
        mock_send_msg.return_value = mock_response
        test_query = "какой цвет стен"

        # Act
        result = classify_query(test_query)

        # Assert
        assert result == "дизайн"

    def test_classify_query_invalid_json(self, mock_send_msg, mock_fetch_prompt, caplog):
        """Тест обработки невалидного JSON в ответе.

        Когда send_msg_to_model возвращает невалидный JSON,
        функция должна вернуть "Не определено" и залогировать ошибку.
        """
        # Arrange
        mock_response = 'invalid json {{'
        mock_send_msg.return_value = mock_response
        test_query = "какой-то вопрос"

        # Act
        with caplog.at_level(logging.ERROR):
            result = classify_query(test_query)

        # Assert
        assert result == "Не определено"
        assert "Ошибка парсинга JSON" in caplog.text
        assert "invalid json" in caplog.text

    def test_classify_query_missing_category_field(self, mock_send_msg, mock_fetch_prompt):
        """Тест обработки JSON без поля 'category'.

        Когда JSON не содержит поле 'category',
        функция должна вернуть "Не определено".
        """
        # Arrange
        mock_response = '{"result": "some_value"}'
        mock_send_msg.return_value = mock_response
        test_query = "вопрос"

        # Act
        result = classify_query(test_query)

        # Assert
        assert result == "Не определено"

    def test_classify_query_empty_category(self, mock_send_msg, mock_fetch_prompt):
        """Тест обработки пустого значения в поле 'category'.

        Когда category пустое, функция возвращает пустую строку
        (это текущее поведение .get("category", "Не определено")).
        """
        # Arrange
        mock_response = '{"category": ""}'
        mock_send_msg.return_value = mock_response
        test_query = "вопрос"

        # Act
        result = classify_query(test_query)

        # Assert
        # Функция возвращает пустую строку, т.к. .get() вернет ""
        assert result == ""
        # Это указывает на потенциальный баг - следует возвращать "Не определено"
        # в случае пустой категории

    def test_classify_query_fetch_prompt_error(self, mock_send_msg, mock_fetch_prompt, caplog):
        """Тест обработки ошибки при получении промпта.

        Когда fetch_prompt_by_name выбрасывает исключение,
        ошибка не перехватывается - это текущее поведение.
        """
        # Arrange
        mock_fetch_prompt.side_effect = RuntimeError("DB error")
        test_query = "вопрос"

        # Act & Assert
        # Текущее поведение: исключение не перехватывается
        with pytest.raises(RuntimeError, match="DB error"):
            classify_query(test_query)

    def test_classify_query_send_msg_error(self, mock_send_msg, mock_fetch_prompt):
        """Тест обработки ошибки при вызове send_msg_to_model.

        Когда send_msg_to_model выбрасывает исключение,
        оно не перехватывается - это текущее поведение.

        ПРИМЕЧАНИЕ: Try-except блок в функции охватывает только парсинг JSON,
        не охватывает вызов send_msg_to_model.
        """
        # Arrange
        mock_send_msg.side_effect = RuntimeError("API error")
        test_query = "вопрос"

        # Act & Assert
        # Текущее поведение: исключение не перехватывается
        with pytest.raises(RuntimeError, match="API error"):
            classify_query(test_query)

    def test_classify_query_calls_with_correct_parameters(self, mock_send_msg, mock_fetch_prompt):
        """Тест проверки передачи правильных параметров.

        Функция должна вызывать send_msg_to_model с правильными параметрами.
        """
        # Arrange
        mock_response = '{"category": "дизайн"}'
        mock_send_msg.return_value = mock_response
        test_query = "тестовый вопрос"

        # Act
        classify_query(test_query)

        # Assert
        mock_send_msg.assert_called_once()
        call_kwargs = mock_send_msg.call_args[1]

        # Проверяем что был передан правильный prompt
        assert mock_fetch_prompt.call_args[1]['prompt_name'] == "prompt_classify"

        # Проверяем структуру messages
        messages = call_kwargs['messages']
        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        assert test_query in messages[0]['content']


# ============================================================================
# INTEGRATION ТЕСТЫ (медленные, используют реальный Claude API)
# ============================================================================


@pytest.mark.slow
class TestClassifyQueryBaselines:
    """Integration тесты для classify_query с реальным Claude API.

    Эти тесты делают РЕАЛЬНЫЕ API вызовы к Claude Anthropic.
    Запускать только для фиксации baseline метрик.

    ВНИМАНИЕ: Требует ANTHROPIC_API_KEY в окружении.
    """

    def test_baseline_on_golden_dataset(self):
        """Baseline метрики classify_query на golden dataset.

        ЦЕЛЬ: Зафиксировать текущее поведение classify_query на известном датасете.

        ВАЖНО: Этот тест делает реальные API вызовы к Claude.
        Запускать редко (только при необходимости зафиксировать baseline).

        МЕТРИКИ:
        - Распределение по категориям (дизайн/интервью/не определено)
        - Среднее время выполнения одного запроса
        - Общее время теста
        - Соответствие ожидаемым индексам (для последующего сравнения)
        """
        # Загрузить golden dataset
        dataset_path = Path(__file__).parent / "golden_dataset.json"

        if not dataset_path.exists():
            pytest.skip(f"Golden dataset не найден: {dataset_path}")

        with open(dataset_path) as f:
            dataset = json.load(f)

        results = []
        total_time = 0
        start_time_total = time.time()

        # Обработать каждый вопрос из датасета
        for idx, item in enumerate(dataset, 1):
            question = item["question"]
            expected_index = item["expected_index"]

            try:
                start_time = time.time()
                category = classify_query(question)
                elapsed = time.time() - start_time

                results.append({
                    "number": idx,
                    "question": question[:80] + "..." if len(question) > 80 else question,
                    "expected_index": expected_index,
                    "actual_category": category,
                    "time": elapsed,
                    "matches_expected": (
                        (expected_index == "Dizayn" and category == "дизайн") or
                        (expected_index == "Intervyu" and category == "интервью")
                    )
                })

                total_time += elapsed

                # Логирование прогресса каждые 5 вопросов
                if idx % 5 == 0:
                    print(f"\n  Обработано {idx}/{len(dataset)} вопросов...")

            except Exception as e:
                logging.error(f"Ошибка при обработке вопроса {idx}: {str(e)}")
                results.append({
                    "number": idx,
                    "question": question[:80] + "..." if len(question) > 80 else question,
                    "expected_index": expected_index,
                    "actual_category": "ERROR",
                    "time": 0,
                    "matches_expected": False,
                    "error": str(e)
                })

        total_time_elapsed = time.time() - start_time_total

        # Подсчет метрик
        categories = {}
        matches = 0

        for r in results:
            cat = r["actual_category"]
            categories[cat] = categories.get(cat, 0) + 1
            if r.get("matches_expected"):
                matches += 1

        # Вычисление времени (исключая ошибки)
        valid_times = [r["time"] for r in results if r["time"] > 0]
        avg_time = sum(valid_times) / len(valid_times) if valid_times else 0
        min_time = min(valid_times) if valid_times else 0
        max_time = max(valid_times) if valid_times else 0

        # ====== ВЫВОД BASELINE МЕТРИК ======
        print(f"\n{'='*70}")
        print(f"BASELINE МЕТРИКИ classify_query")
        print(f"{'='*70}")
        print(f"\nДАТА ТЕСТИРОВАНИЯ: {Path(__file__).stat().st_mtime}")
        print(f"\nОБЩАЯ СТАТИСТИКА:")
        print(f"  Всего вопросов: {len(results)}")
        print(f"  Успешно обработано: {sum(1 for r in results if r['actual_category'] != 'ERROR')}")
        print(f"  Ошибок: {sum(1 for r in results if r['actual_category'] == 'ERROR')}")

        print(f"\nРАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
        for cat, count in sorted(categories.items()):
            percentage = (count / len(results)) * 100
            print(f"  {cat:25} : {count:3} ({percentage:5.1f}%)")

        print(f"\nСООТВЕТСТВИЕ ОЖИДАНИЯМ:")
        match_percentage = (matches / len(results)) * 100 if results else 0
        print(f"  Совпадений: {matches}/{len(results)} ({match_percentage:.1f}%)")
        # ИСПРАВЛЕНО: убран f-префикс из строк без полей замены
        print("  (Совпадение = вопрос о дизайне классифицирован как 'дизайн'")
        print("            ИЛИ вопрос об интервью классифицирован как 'интервью')")

        print(f"\nВРЕМЕННЫЕ МЕТРИКИ:")
        print(f"  Среднее время на вопрос: {avg_time:.3f} сек")
        print(f"  Минимальное время: {min_time:.3f} сек")
        print(f"  Максимальное время: {max_time:.3f} сек")
        print(f"  Общее время теста: {total_time_elapsed:.1f} сек ({total_time_elapsed/60:.1f} мин)")

        print(f"\nДЕТАЛИ РЕЗУЛЬТАТОВ:")
        print(f"{'№':<3} {'Вопрос':<35} {'Ожидается':<12} {'Получено':<12} {'Совпадение':<8} {'Время (сек)':<10}")
        print(f"{'-'*80}")
        for r in results[:10]:  # Первые 10 для демонстрации
            match_str = "✓" if r.get("matches_expected") else "✗"
            print(f"{r['number']:<3} {r['question']:<35} {r['expected_index']:<12} {r['actual_category']:<12} {match_str:<8} {r['time']:<10.3f}")

        if len(results) > 10:
            print(f"... (еще {len(results) - 10} вопросов)")

        print(f"{'='*70}\n")

        # НЕ делаем assert - это baseline тест, он только фиксирует метрики
        # Метрики сохраняются в консоли для анализа

    def test_golden_dataset_exists(self):
        """Проверка что golden dataset существует.

        Этот тест проверяет наличие файла golden_dataset.json.
        Это предусловие для других baseline тестов.
        """
        dataset_path = Path(__file__).parent / "golden_dataset.json"
        assert dataset_path.exists(), f"Golden dataset не найден: {dataset_path}"

        # Проверка что файл валидный JSON
        with open(dataset_path) as f:
            data = json.load(f)

        assert isinstance(data, list), "Golden dataset должен быть списком"
        assert len(data) > 0, "Golden dataset не должен быть пустым"

        # Проверка структуры первого элемента
        first_item = data[0]
        assert "question" in first_item, "Каждый элемент должен иметь 'question'"
        assert "expected_index" in first_item, "Каждый элемент должен иметь 'expected_index'"
        assert "reasoning" in first_item, "Каждый элемент должен иметь 'reasoning'"


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ТЕСТЫ
# ============================================================================


@pytest.mark.slow
class TestClassifyQueryEdgeCases:
    """Тесты для edge cases classify_query с реальным API.

    Эти тесты проверяют поведение на граничных случаях.
    """

    def test_empty_query(self):
        """Тест поведения на пустом запросе.

        Функция должна вызвать API даже с пустым запросом.
        Результат зависит от ответа Claude.
        """
        result = classify_query("")
        # НЕ делаем assert - просто фиксируем поведение
        assert isinstance(result, str)

    def test_very_long_query(self):
        """Тест поведения на очень длинном запросе.

        Функция должна обработать длинный запрос без ошибок.
        """
        long_query = "вопрос о дизайне " * 100
        result = classify_query(long_query)
        # НЕ делаем assert - просто фиксируем поведение
        assert isinstance(result, str)

    def test_special_characters_in_query(self):
        """Тест поведения на спецсимволах.

        Функция должна корректно обработать спецсимволы и Unicode.
        """
        queries = [
            "как выглядит мебель? 🏨",
            "цена номера: 150$",
            "освещение: 100% яркости",
            "e-mail: test@example.com",
        ]

        for query in queries:
            result = classify_query(query)
            assert isinstance(result, str)


# ============================================================================
# ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ
# ============================================================================

def pytest_configure(config):
    """Добавить кастомные маркеры pytest."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
