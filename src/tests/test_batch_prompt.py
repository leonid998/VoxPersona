"""
Тесты для функции build_batch_relevance_prompt().

Проверяет корректность генерации промпта для batch-оценки релевантности
всех 22 отчетов за один запрос к Claude API.

Запуск тестов:
    pytest src/tests/test_batch_prompt.py -v
    pytest src/tests/test_batch_prompt.py -v --tb=short
"""

import json
import pytest
import sys
from pathlib import Path

# Добавляем путь к src для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from relevance_evaluator import (
    build_batch_relevance_prompt,
    build_json_container,
    load_report_descriptions,
    REPORT_TO_INDEX_MAPPING,
    INDEX_DISPLAY_NAMES
)


# === FIXTURES ===

@pytest.fixture
def sample_question() -> str:
    """Примерный вопрос пользователя для тестов."""
    return "Какое освещение в номерах?"


@pytest.fixture
def sample_json_container() -> str:
    """
    Минимальный JSON-контейнер для тестов.
    Содержит 3 отчета для быстрой проверки.
    """
    container = {
        "reports": [
            {
                "id": 1,
                "name": "Структурированный_отчет_аудита",
                "index": "Dizayn",
                "description": "Описание аудита дизайна с информацией об освещении, мебели и цветах."
            },
            {
                "id": 2,
                "name": "Общие_факторы",
                "index": "Intervyu",
                "description": "Интервью с гостями о впечатлениях от отеля."
            },
            {
                "id": 3,
                "name": "Итоговый_отчет",
                "index": "Itogovye_otchety",
                "description": "Сводный отчет с рекомендациями по улучшению."
            }
        ],
        "indices": [
            {"name": "Dizayn", "display_name": "Дизайн", "report_ids": [1]},
            {"name": "Intervyu", "display_name": "Интервью", "report_ids": [2]},
            {"name": "Itogovye_otchety", "display_name": "Итоговые", "report_ids": [3]}
        ],
        "total_reports": 3,
        "total_indices": 3
    }
    return json.dumps(container, ensure_ascii=False)


@pytest.fixture
def real_json_container() -> str:
    """
    Реальный JSON-контейнер с 22 отчетами.
    Загружается из файловой системы.
    """
    try:
        descriptions = load_report_descriptions()
        return build_json_container(descriptions)
    except FileNotFoundError:
        pytest.skip("Директория с описаниями отчетов не найдена")


# === ТЕСТЫ БАЗОВОЙ ФУНКЦИОНАЛЬНОСТИ ===

def test_prompt_contains_question(sample_question: str, sample_json_container: str):
    """
    Проверяет, что вопрос пользователя включен в промпт.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    assert sample_question in prompt, (
        f"Вопрос '{sample_question}' должен быть включен в промпт"
    )


def test_prompt_contains_json_container(sample_question: str, sample_json_container: str):
    """
    Проверяет, что JSON-контейнер полностью включен в промпт.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    assert sample_json_container in prompt, (
        "JSON-контейнер должен быть полностью включен в промпт"
    )


def test_prompt_requires_json_response(sample_question: str, sample_json_container: str):
    """
    Проверяет, что промпт требует JSON-ответ без markdown-разметки.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Проверяем ключевые фразы о формате ответа
    assert "evaluations" in prompt, "Промпт должен требовать формат с 'evaluations'"
    assert "JSON" in prompt, "Промпт должен упоминать JSON"
    assert "markdown" in prompt.lower(), "Промпт должен упоминать запрет на markdown"

    # Проверяем требование к структуре ответа
    assert '"id"' in prompt, "Промпт должен требовать поле 'id'"
    assert '"name"' in prompt, "Промпт должен требовать поле 'name'"
    assert '"relevance"' in prompt, "Промпт должен требовать поле 'relevance'"
    assert '"reason"' in prompt, "Промпт должен требовать поле 'reason'"


def test_prompt_has_evaluation_scale(sample_question: str, sample_json_container: str):
    """
    Проверяет, что промпт содержит шкалу оценки релевантности.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Проверяем наличие диапазонов шкалы
    assert "80-100" in prompt, "Промпт должен содержать диапазон 80-100"
    assert "50-79" in prompt, "Промпт должен содержать диапазон 50-79"
    assert "20-49" in prompt, "Промпт должен содержать диапазон 20-49"
    assert "0-19" in prompt, "Промпт должен содержать диапазон 0-19"

    # Проверяем описания уровней
    assert "ПРЯМОЙ ОТВЕТ" in prompt or "прямой ответ" in prompt.lower(), (
        "Промпт должен описывать высокую релевантность"
    )
    assert "НЕ РЕЛЕВАНТЕН" in prompt or "не релевантен" in prompt.lower(), (
        "Промпт должен описывать низкую релевантность"
    )


# === ТЕСТЫ КОНТЕКСТА И СТРУКТУРЫ ===

def test_prompt_contains_system_context(sample_question: str, sample_json_container: str):
    """
    Проверяет, что промпт содержит контекст о 7 категориях отчетов.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Проверяем упоминание всех 7 индексов
    expected_indices = [
        "Dizayn",
        "Intervyu",
        "Itogovye_otchety",
        "Otchety_po_dizaynu",
        "Otchety_po_obsledovaniyu",
        "Iskhodniki_dizayn",
        "Iskhodniki_obsledovanie"
    ]

    for index in expected_indices:
        assert index in prompt, f"Промпт должен упоминать индекс '{index}'"


def test_prompt_contains_evaluation_instructions(sample_question: str, sample_json_container: str):
    """
    Проверяет наличие инструкций по оценке в промпте.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Ключевые инструкции
    assert "ИНСТРУКЦИИ" in prompt or "инструкции" in prompt.lower(), (
        "Промпт должен содержать секцию инструкций"
    )
    assert "ПРАВИЛА" in prompt or "правила" in prompt.lower(), (
        "Промпт должен содержать правила оценки"
    )


def test_prompt_contains_examples(sample_question: str, sample_json_container: str):
    """
    Проверяет наличие примеров правильной оценки в промпте.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Проверяем наличие примеров
    assert "ПРИМЕРЫ" in prompt or "примеры" in prompt.lower(), (
        "Промпт должен содержать примеры оценки"
    )
    assert "освещение" in prompt.lower(), (
        "Промпт должен содержать пример про освещение"
    )


# === ТЕСТЫ ВАЛИДАЦИИ ===

def test_empty_question_raises_error(sample_json_container: str):
    """
    Проверяет, что пустой вопрос вызывает ValueError.
    """
    with pytest.raises(ValueError, match="Вопрос не может быть пустым"):
        build_batch_relevance_prompt("", sample_json_container)

    with pytest.raises(ValueError, match="Вопрос не может быть пустым"):
        build_batch_relevance_prompt("   ", sample_json_container)


def test_empty_json_container_raises_error(sample_question: str):
    """
    Проверяет, что пустой JSON-контейнер вызывает ValueError.
    """
    with pytest.raises(ValueError, match="JSON-контейнер не может быть пустым"):
        build_batch_relevance_prompt(sample_question, "")

    with pytest.raises(ValueError, match="JSON-контейнер не может быть пустым"):
        build_batch_relevance_prompt(sample_question, "   ")


# === ТЕСТЫ РАЗМЕРА И ПРОИЗВОДИТЕЛЬНОСТИ ===

def test_prompt_size_without_json(sample_question: str, sample_json_container: str):
    """
    Проверяет размер промпта без JSON-контейнера.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Размер промпта без JSON
    prompt_without_json = len(prompt) - len(sample_json_container)

    # Ожидаемый размер: ~2500 символов (указано в docstring)
    # Допускаем отклонение +-500 символов
    assert 2000 <= prompt_without_json <= 3500, (
        f"Размер промпта без JSON ({prompt_without_json} символов) "
        f"должен быть в диапазоне 2000-3500 символов"
    )


def test_prompt_with_real_container(sample_question: str, real_json_container: str):
    """
    Проверяет промпт с реальным JSON-контейнером (22 отчета).
    """
    prompt = build_batch_relevance_prompt(sample_question, real_json_container)

    # Проверяем общий размер
    total_size = len(prompt)

    # Ожидаемый размер: ~94k символов (91k JSON + 3k промпт)
    assert total_size > 90000, (
        f"Общий размер промпта ({total_size} символов) "
        f"должен быть больше 90000 символов"
    )

    # Проверяем что все 22 отчета упомянуты
    assert "22" in prompt, "Промпт должен упоминать 22 отчета"


# === ТЕСТЫ ФОРМАТА ОТВЕТА ===

def test_prompt_specifies_22_evaluations(sample_question: str, sample_json_container: str):
    """
    Проверяет, что промпт требует ровно 22 оценки.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Должно быть указано количество оценок
    assert "22" in prompt, "Промпт должен указывать требование 22 оценок"


def test_prompt_requires_russian_reason(sample_question: str, sample_json_container: str):
    """
    Проверяет, что промпт требует обоснование на русском языке.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    assert "русском" in prompt.lower() or "russian" in prompt.lower(), (
        "Промпт должен требовать обоснование на русском языке"
    )


def test_prompt_requires_integer_relevance(sample_question: str, sample_json_container: str):
    """
    Проверяет, что промпт требует целое число для relevance.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Проверяем указание типа данных
    assert "целое число" in prompt.lower() or "от 0 до 100" in prompt, (
        "Промпт должен указывать диапазон 0-100 для relevance"
    )


# === ТЕСТЫ СПЕЦИФИЧНЫХ ВОПРОСОВ ===

@pytest.mark.parametrize("question,expected_in_prompt", [
    ("Какое освещение в номерах?", "освещение"),
    ("Что гости говорят о завтраке?", "гости"),
    ("Как улучшить клиентский сервис?", "улучшить"),
    ("Проблемы с инфраструктурой", "инфраструктур"),
])
def test_different_questions(
    question: str,
    expected_in_prompt: str,
    sample_json_container: str
):
    """
    Проверяет корректную работу с разными типами вопросов.
    """
    prompt = build_batch_relevance_prompt(question, sample_json_container)

    # Вопрос должен быть включен
    assert question in prompt, f"Вопрос '{question}' должен быть в промпте"

    # Ключевое слово из вопроса тоже должно быть
    assert expected_in_prompt in prompt.lower(), (
        f"Ключевое слово '{expected_in_prompt}' должно быть в промпте"
    )


# === ТЕСТЫ СЕКЦИЙ ПРОМПТА ===

def test_prompt_has_clear_sections(sample_question: str, sample_json_container: str):
    """
    Проверяет наличие четко разделенных секций в промпте.
    """
    prompt = build_batch_relevance_prompt(sample_question, sample_json_container)

    # Должны быть разделители секций
    assert "===" in prompt, "Промпт должен содержать разделители секций '==='"

    # Проверяем основные секции
    assert "ВОПРОС ПОЛЬЗОВАТЕЛЯ" in prompt, "Должна быть секция с вопросом"
    assert "ДАННЫЕ ДЛЯ ОЦЕНКИ" in prompt or "JSON-КОНТЕЙНЕР" in prompt, (
        "Должна быть секция с данными"
    )
    assert "ФОРМАТ ОТВЕТА" in prompt, "Должна быть секция с форматом ответа"


# === ТЕСТ ИНТЕГРАЦИИ ===

def test_full_integration_with_real_data():
    """
    Интеграционный тест с реальными данными.

    Загружает описания отчетов, создает JSON-контейнер,
    генерирует промпт и проверяет его корректность.
    """
    try:
        # Загрузка реальных данных
        descriptions = load_report_descriptions()
        json_container = build_json_container(descriptions)

        # Генерация промпта
        question = "Какие проблемы с дизайном интерьера в ресторане отеля?"
        prompt = build_batch_relevance_prompt(question, json_container)

        # Проверки
        assert len(prompt) > 90000, "Промпт должен быть больше 90k символов"
        assert question in prompt, "Вопрос должен быть в промпте"
        assert '"evaluations"' in prompt, "Формат ответа должен требовать evaluations"

        # Проверяем что все 22 отчета в контейнере
        container_data = json.loads(json_container)
        assert container_data["total_reports"] == 22, "Должно быть 22 отчета"

        # Все имена отчетов должны быть в промпте
        for report in container_data["reports"]:
            assert report["name"] in prompt, (
                f"Отчет '{report['name']}' должен быть в промпте"
            )

    except FileNotFoundError:
        pytest.skip("Директория с описаниями отчетов не найдена")


if __name__ == "__main__":
    # Запуск тестов при прямом вызове файла
    pytest.main([__file__, "-v", "--tb=short"])
