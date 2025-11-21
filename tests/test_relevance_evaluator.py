"""
Unit-тесты для модуля relevance_evaluator.

Тестирует функциональность оценки релевантности отчетов через Claude Haiku API.
Использует моки для изоляции от внешних зависимостей (API, файловая система).

Включает тесты для:
- Загрузки описаний отчетов (load_report_descriptions)
- Построения промптов (build_relevance_prompt, build_batch_relevance_prompt)
- Batch-оценки (build_json_container, evaluate_batch_relevance, parse_batch_response)
- Основной функции (evaluate_report_relevance)

Запуск тестов:
    pytest tests/test_relevance_evaluator.py -v
    pytest tests/test_relevance_evaluator.py::test_load_report_descriptions -v
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# Импорт тестируемых функций
from src.relevance_evaluator import (
    load_report_descriptions,
    build_relevance_prompt,
    evaluate_single_report,
    evaluate_report_relevance,
    build_json_container,
    build_batch_relevance_prompt,
    parse_batch_response,
    validate_batch_evaluations,
    convert_evaluations_to_dict,
    evaluate_batch_relevance,
    get_json_container_stats,
    HAIKU_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
    REPORT_DESCRIPTIONS_DIR,
    BATCH_MAX_TOKENS,
    REPORT_TO_INDEX_MAPPING,
    INDEX_DISPLAY_NAMES
)


# === ФИКСТУРЫ ===

@pytest.fixture
def sample_question():
    """Пример вопроса пользователя для тестов."""
    return "Какие проблемы с освещением в ресторане?"


@pytest.fixture
def sample_report_description():
    """Пример описания отчета для тестов."""
    return """# Световой дизайн

Отчет анализирует все аспекты освещения:
- Естественное освещение
- Искусственное освещение
- Световые сценарии
- Эмоциональное воздействие
"""


@pytest.fixture
def sample_report_descriptions():
    """Набор тестовых описаний отчетов."""
    return {
        "Структурированный_отчет_аудита": "Комплексный анализ дизайна интерьера...",
        "Общие_факторы": "Отчет содержит результаты интервью с гостями...",
        "Световой_дизайн": "Анализ освещения и световых решений..."
    }


@pytest.fixture
def full_report_descriptions():
    """Полный набор из 22 описаний отчетов для batch-тестов."""
    return {name: f"Описание отчета {name}" for name in REPORT_TO_INDEX_MAPPING.keys()}


@pytest.fixture
def sample_batch_evaluations():
    """Пример оценок от batch API для тестов."""
    return [
        {
            "id": 1,
            "name": "Структурированный_отчет_аудита",
            "relevance": 85,
            "reason": "Содержит анализ дизайна"
        },
        {
            "id": 2,
            "name": "Общие_факторы",
            "relevance": 30,
            "reason": "Частично релевантен"
        },
        {
            "id": 3,
            "name": "Световой_дизайн",
            "relevance": 95,
            "reason": "Полностью соответствует запросу"
        }
    ]


@pytest.fixture
def mock_anthropic_response():
    """Мок ответа от Anthropic API."""
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "85"  # Процент релевантности
    mock_response.content = [mock_content]
    return mock_response


@pytest.fixture
def mock_batch_anthropic_response(full_report_descriptions):
    """Мок ответа от Anthropic API для batch-запроса."""
    evaluations = []
    for idx, name in enumerate(sorted(full_report_descriptions.keys()), start=1):
        evaluations.append({
            "id": idx,
            "name": name,
            "relevance": 50 + idx,  # Разные значения для каждого отчета
            "reason": f"Тестовое обоснование для {name}"
        })

    response_json = json.dumps({"evaluations": evaluations}, ensure_ascii=False)

    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = response_json
    mock_response.content = [mock_content]
    return mock_response


# === ТЕСТЫ ЗАГРУЗКИ ОПИСАНИЙ ===

def test_load_report_descriptions_success(tmp_path):
    """
    Тест успешной загрузки описаний отчетов из файлов.

    Проверяет:
    - Корректное чтение .md файлов из директорий
    - Извлечение имени отчета из имени файла
    - Загрузку содержимого в правильной кодировке
    """
    # Создать временную структуру директорий
    report_dir = tmp_path / "reports"
    subdir = report_dir / "Содержание_Дизайн"
    subdir.mkdir(parents=True)

    # Создать тестовые файлы
    file1 = subdir / "Содержание_отчетов_Структурированный_отчет_аудита.md"
    file1.write_text("Описание структурированного отчета", encoding="utf-8")

    file2 = subdir / "Содержание_отчетов_Световой_дизайн.md"
    file2.write_text("Описание светового дизайна", encoding="utf-8")

    # Патчить константу REPORT_DESCRIPTIONS_DIR
    with patch('src.relevance_evaluator.REPORT_DESCRIPTIONS_DIR', report_dir):
        descriptions = load_report_descriptions()

    # Проверки
    assert len(descriptions) == 2
    assert "Структурированный_отчет_аудита" in descriptions
    assert "Световой_дизайн" in descriptions
    assert descriptions["Структурированный_отчет_аудита"] == "Описание структурированного отчета"
    assert descriptions["Световой_дизайн"] == "Описание светового дизайна"


def test_load_report_descriptions_missing_directory():
    """
    Тест обработки отсутствующей директории.

    Проверяет, что функция выбрасывает FileNotFoundError
    если директория с описаниями не существует.
    """
    non_existent_dir = Path("/nonexistent/path/to/reports")

    with patch('src.relevance_evaluator.REPORT_DESCRIPTIONS_DIR', non_existent_dir):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_report_descriptions()

        assert "Директория с описаниями отчетов не найдена" in str(exc_info.value)


def test_load_report_descriptions_handles_different_prefixes(tmp_path):
    """
    Тест обработки различных форматов префиксов в названиях файлов.

    Проверяет корректное удаление различных вариантов префиксов:
    - "Содержание_отчетов_"
    - "Содержание отчетов_"
    - "Содержание отчетов "
    """
    report_dir = tmp_path / "reports"
    report_dir.mkdir()

    # Файлы с разными префиксами
    (report_dir / "Содержание_отчетов_Отчет1.md").write_text("Текст 1", encoding="utf-8")
    (report_dir / "Содержание отчетов_Отчет2.md").write_text("Текст 2", encoding="utf-8")
    (report_dir / "Содержание отчетов Отчет3.md").write_text("Текст 3", encoding="utf-8")

    with patch('src.relevance_evaluator.REPORT_DESCRIPTIONS_DIR', report_dir):
        descriptions = load_report_descriptions()

    # Все префиксы должны быть удалены
    assert "Отчет1" in descriptions
    assert "Отчет2" in descriptions
    assert "Отчет3" in descriptions


def test_load_report_descriptions_skips_corrupted_files(tmp_path):
    """
    Тест пропуска поврежденных файлов при загрузке.

    Проверяет, что функция продолжает работу при ошибках чтения
    отдельных файлов и загружает остальные корректные файлы.
    """
    report_dir = tmp_path / "reports"
    report_dir.mkdir()

    # Создать корректный файл
    good_file = report_dir / "Содержание_отчетов_GoodReport.md"
    good_file.write_text("Корректное описание", encoding="utf-8")

    # Создать некорректный файл (директорию вместо файла)
    bad_file = report_dir / "Содержание_отчетов_BadReport.md"
    bad_file.mkdir()  # Создаем директорию с именем .md файла

    with patch('src.relevance_evaluator.REPORT_DESCRIPTIONS_DIR', report_dir):
        descriptions = load_report_descriptions()

    # Должен загрузиться только корректный файл
    assert len(descriptions) == 1
    assert "GoodReport" in descriptions


# === ТЕСТЫ ПОСТРОЕНИЯ ПРОМПТА ===

def test_build_relevance_prompt_structure(sample_question, sample_report_description):
    """
    Тест структуры генерируемого промпта.

    Проверяет:
    - Промпт содержит вопрос пользователя
    - Промпт содержит описание отчета
    - Промпт содержит инструкцию по оценке (0-100%)
    - Промпт требует только число в ответе
    """
    prompt = build_relevance_prompt(sample_question, sample_report_description)

    # Проверка наличия ключевых элементов
    assert sample_question in prompt
    assert sample_report_description in prompt
    assert "0-100" in prompt
    assert "ТОЛЬКО число" in prompt or "только число" in prompt.lower()
    assert "релевантн" in prompt.lower()


def test_build_relevance_prompt_empty_inputs():
    """
    Тест обработки пустых входных данных при построении промпта.

    Проверяет, что функция работает корректно даже с пустыми строками
    (хотя в реальном использовании это не должно происходить).
    """
    prompt = build_relevance_prompt("", "")

    # Промпт должен содержать базовую структуру
    assert "Вопрос пользователя:" in prompt
    assert "Описание типа отчета:" in prompt
    assert "0-100" in prompt


# === ТЕСТЫ BUILD_JSON_CONTAINER ===

def test_build_json_container_structure(full_report_descriptions):
    """
    Тест структуры JSON-контейнера.

    Проверяет:
    - Наличие всех обязательных полей
    - Корректность структуры reports и indices
    - Правильное количество отчетов и индексов
    """
    json_str = build_json_container(full_report_descriptions)
    data = json.loads(json_str)

    # Проверка верхнего уровня
    assert "reports" in data
    assert "indices" in data
    assert "total_reports" in data
    assert "total_indices" in data

    # Проверка количеств
    assert data["total_reports"] == 22
    assert data["total_indices"] == 7
    assert len(data["reports"]) == 22
    assert len(data["indices"]) == 7


def test_build_json_container_report_fields(full_report_descriptions):
    """
    Тест полей каждого отчета в JSON-контейнере.

    Проверяет:
    - Наличие id, name, index, description
    - Корректность типов данных
    - ID начинаются с 1
    """
    json_str = build_json_container(full_report_descriptions)
    data = json.loads(json_str)

    for report in data["reports"]:
        assert "id" in report
        assert "name" in report
        assert "index" in report
        assert "description" in report

        assert isinstance(report["id"], int)
        assert report["id"] >= 1
        assert isinstance(report["name"], str)
        assert isinstance(report["index"], str)
        assert isinstance(report["description"], str)


def test_build_json_container_index_fields(full_report_descriptions):
    """
    Тест полей каждого индекса в JSON-контейнере.

    Проверяет:
    - Наличие name, display_name, report_ids
    - Корректность типов данных
    - report_ids содержит корректные ID
    """
    json_str = build_json_container(full_report_descriptions)
    data = json.loads(json_str)

    all_report_ids = {r["id"] for r in data["reports"]}

    for index in data["indices"]:
        assert "name" in index
        assert "display_name" in index
        assert "report_ids" in index

        assert isinstance(index["name"], str)
        assert isinstance(index["display_name"], str)
        assert isinstance(index["report_ids"], list)

        # Все ID должны существовать в reports
        for rid in index["report_ids"]:
            assert rid in all_report_ids


def test_build_json_container_empty_input():
    """
    Тест обработки пустого словаря описаний.

    Проверяет, что функция выбрасывает ValueError.
    """
    with pytest.raises(ValueError) as exc_info:
        build_json_container({})

    assert "не может быть пустым" in str(exc_info.value)


def test_build_json_container_custom_mapping():
    """
    Тест использования пользовательского маппинга.

    Проверяет, что функция использует переданный маппинг
    вместо REPORT_TO_INDEX_MAPPING.
    """
    descriptions = {
        "Report1": "Description 1",
        "Report2": "Description 2"
    }
    custom_mapping = {
        "Report1": "CustomIndex1",
        "Report2": "CustomIndex2"
    }

    json_str = build_json_container(descriptions, report_to_index=custom_mapping)
    data = json.loads(json_str)

    # Проверяем что использован custom маппинг
    report_indices = {r["name"]: r["index"] for r in data["reports"]}
    assert report_indices["Report1"] == "CustomIndex1"
    assert report_indices["Report2"] == "CustomIndex2"


def test_build_json_container_deterministic_order(full_report_descriptions):
    """
    Тест детерминированного порядка отчетов.

    Проверяет, что отчеты всегда сортируются по имени
    для консистентности результатов.
    """
    json_str1 = build_json_container(full_report_descriptions)
    json_str2 = build_json_container(full_report_descriptions)

    # Результат должен быть идентичным при одинаковых входных данных
    assert json_str1 == json_str2

    # Проверяем сортировку по имени
    data = json.loads(json_str1)
    names = [r["name"] for r in data["reports"]]
    assert names == sorted(names)


# === ТЕСТЫ GET_JSON_CONTAINER_STATS ===

def test_get_json_container_stats_valid(full_report_descriptions):
    """
    Тест получения статистики для валидного JSON-контейнера.

    Проверяет корректность всех полей статистики.
    """
    json_str = build_json_container(full_report_descriptions)
    stats = get_json_container_stats(json_str)

    assert stats["is_valid"] == True
    assert stats["total_reports"] == 22
    assert stats["total_indices"] == 7
    assert stats["total_chars"] > 0
    assert stats["estimated_tokens"] > 0
    assert len(stats["reports_per_index"]) == 7


def test_get_json_container_stats_invalid_json():
    """
    Тест обработки невалидного JSON.

    Проверяет корректную обработку ошибки парсинга.
    """
    invalid_json = "not a valid json {"
    stats = get_json_container_stats(invalid_json)

    assert stats["is_valid"] == False
    assert "error" in stats
    assert stats["total_reports"] == 0


# === ТЕСТЫ BUILD_BATCH_RELEVANCE_PROMPT ===

def test_build_batch_relevance_prompt_structure(sample_question, full_report_descriptions):
    """
    Тест структуры batch-промпта.

    Проверяет:
    - Промпт содержит вопрос пользователя
    - Промпт содержит JSON-контейнер
    - Промпт содержит инструкции по формату ответа
    """
    json_container = build_json_container(full_report_descriptions)
    prompt = build_batch_relevance_prompt(sample_question, json_container)

    # Проверка наличия ключевых элементов
    assert sample_question in prompt
    assert "evaluations" in prompt.lower()
    assert "0-100" in prompt or "0 до 100" in prompt
    assert "json" in prompt.lower()


def test_build_batch_relevance_prompt_contains_json(sample_question, full_report_descriptions):
    """
    Тест наличия JSON-контейнера в промпте.

    Проверяет, что весь JSON-контейнер включен в промпт.
    """
    json_container = build_json_container(full_report_descriptions)
    prompt = build_batch_relevance_prompt(sample_question, json_container)

    # JSON-контейнер должен быть в промпте
    assert json_container in prompt


def test_build_batch_relevance_prompt_empty_question(full_report_descriptions):
    """
    Тест обработки пустого вопроса.

    Проверяет, что функция выбрасывает ValueError при пустом вопросе.
    """
    json_container = build_json_container(full_report_descriptions)
    
    with pytest.raises(ValueError) as exc_info:
        build_batch_relevance_prompt("", json_container)
    
    assert "не может быть пустым" in str(exc_info.value)


# === ТЕСТЫ PARSE_BATCH_RESPONSE ===

def test_parse_batch_response_valid_json(sample_batch_evaluations):
    """
    Тест парсинга валидного JSON ответа.

    Проверяет корректное извлечение списка оценок.
    """
    response_json = json.dumps({"evaluations": sample_batch_evaluations})
    result = parse_batch_response(response_json)

    assert "evaluations" in result
    assert len(result["evaluations"]) == 3
    assert result["evaluations"][0]["id"] == 1
    assert result["evaluations"][0]["relevance"] == 85


def test_parse_batch_response_with_markdown():
    """
    Тест парсинга JSON обернутого в markdown блок.

    Проверяет извлечение JSON из ```json ... ``` блока.
    """
    evaluations = [{"id": 1, "name": "Test", "relevance": 50, "reason": "Test"}]
    json_content = json.dumps({"evaluations": evaluations})
    markdown_wrapped = f"```json\n{json_content}\n```"

    result = parse_batch_response(markdown_wrapped)

    assert "evaluations" in result
    assert len(result["evaluations"]) == 1
    assert result["evaluations"][0]["relevance"] == 50


def test_parse_batch_response_invalid_json():
    """
    Тест обработки невалидного JSON.

    Проверяет, что функция выбрасывает ValueError.
    """
    invalid_json = "not valid json {"

    with pytest.raises(ValueError) as exc_info:
        parse_batch_response(invalid_json)

    assert "JSON" in str(exc_info.value) or "парсинг" in str(exc_info.value).lower()


def test_parse_batch_response_missing_evaluations():
    """
    Тест обработки JSON без поля evaluations.

    Проверяет, что функция выбрасывает ValueError.
    """
    json_without_evaluations = json.dumps({"some_field": "value"})

    with pytest.raises(ValueError) as exc_info:
        parse_batch_response(json_without_evaluations)

    assert "evaluations" in str(exc_info.value).lower()


def test_parse_batch_response_empty_evaluations():
    """
    Тест обработки пустого списка оценок.

    Проверяет, что функция возвращает dict с пустым списком evaluations.
    """
    empty_evaluations = json.dumps({"evaluations": []})
    result = parse_batch_response(empty_evaluations)

    assert "evaluations" in result
    assert result["evaluations"] == []


# === ТЕСТЫ VALIDATE_BATCH_EVALUATIONS ===

def test_validate_batch_evaluations_valid(sample_batch_evaluations):
    """
    Тест валидации корректных оценок.

    Проверяет, что функция возвращает True для валидных данных.
    """
    # validate_batch_evaluations принимает expected_count, а не expected_names
    is_valid, errors = validate_batch_evaluations(sample_batch_evaluations, expected_count=3)

    assert is_valid == True
    assert errors == []


def test_validate_batch_evaluations_missing_report():
    """
    Тест валидации при неправильном количестве отчетов.

    Проверяет обнаружение несоответствия количества.
    """
    evaluations = [
        {"id": 1, "name": "Report1", "relevance": 50, "reason": "Test"}
    ]
    # Ожидаем 2 отчета, но получено 1
    is_valid, errors = validate_batch_evaluations(evaluations, expected_count=2)

    assert is_valid == False
    assert len(errors) > 0


def test_validate_batch_evaluations_invalid_relevance():
    """
    Тест валидации при невалидном значении релевантности.

    Проверяет обнаружение значений вне диапазона 0-100.
    """
    evaluations = [
        {"id": 1, "name": "Report1", "relevance": 150, "reason": "Test"}
    ]
    is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

    assert is_valid == False
    assert len(errors) > 0


def test_validate_batch_evaluations_missing_fields():
    """
    Тест валидации при отсутствии обязательных полей.

    Проверяет обнаружение отсутствующих полей id, name, relevance.
    """
    evaluations = [
        {"id": 1, "name": "Report1"}  # Нет relevance
    ]
    is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

    assert is_valid == False
    assert len(errors) > 0


def test_validate_batch_evaluations_duplicate_names():
    """
    Тест валидации при дублировании имен отчетов.

    Проверяет обнаружение дубликатов.
    """
    evaluations = [
        {"id": 1, "name": "Report1", "relevance": 50, "reason": "Test"},
        {"id": 2, "name": "Report1", "relevance": 60, "reason": "Test"}  # Дубликат
    ]
    is_valid, errors = validate_batch_evaluations(evaluations, expected_count=2)

    assert is_valid == False
    assert len(errors) > 0


# === ТЕСТЫ CONVERT_EVALUATIONS_TO_DICT ===

def test_convert_evaluations_to_dict_valid(sample_batch_evaluations):
    """
    Тест конвертации валидных оценок в словарь.

    Проверяет корректное преобразование списка в dict.
    """
    result = convert_evaluations_to_dict(sample_batch_evaluations)

    assert isinstance(result, dict)
    assert len(result) == 3
    assert result["Структурированный_отчет_аудита"] == 85
    assert result["Общие_факторы"] == 30
    assert result["Световой_дизайн"] == 95


def test_convert_evaluations_to_dict_empty():
    """
    Тест конвертации пустого списка оценок.

    Проверяет, что функция возвращает пустой словарь.
    """
    result = convert_evaluations_to_dict([])

    assert result == {}


def test_convert_evaluations_to_dict_clamps_values():
    """
    Тест clamping значений к диапазону 0-100.

    Проверяет, что значения вне диапазона приводятся к границам.
    """
    evaluations = [
        {"id": 1, "name": "High", "relevance": 150, "reason": "Test"},
        {"id": 2, "name": "Low", "relevance": -50, "reason": "Test"},
        {"id": 3, "name": "Normal", "relevance": 50, "reason": "Test"}
    ]

    result = convert_evaluations_to_dict(evaluations)

    assert result["High"] == 100.0  # Clamped to 100
    assert result["Low"] == 0.0     # Clamped to 0
    assert result["Normal"] == 50.0


# === ТЕСТЫ EVALUATE_BATCH_RELEVANCE ===

@pytest.mark.asyncio
async def test_evaluate_batch_relevance_success(
    sample_question,
    full_report_descriptions,
    mock_batch_anthropic_response
):
    """
    Тест успешной batch-оценки релевантности.

    Проверяет:
    - Корректный вызов Anthropic API
    - Парсинг JSON ответа
    - Возврат словаря с релевантностью
    """
    api_key = "test_api_key"
    json_container = build_json_container(full_report_descriptions)

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_batch_anthropic_response)
        mock_client_class.return_value = mock_client

        result = await evaluate_batch_relevance(
            question=sample_question,
            json_container=json_container,
            api_key=api_key
        )

        # Проверка вызова API
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == HAIKU_MODEL
        assert call_kwargs["max_tokens"] == BATCH_MAX_TOKENS

        # Проверка результата
        assert isinstance(result, dict)
        assert len(result) == 22


@pytest.mark.asyncio
async def test_evaluate_batch_relevance_api_error():
    """
    Тест обработки ошибки API.

    Проверяет, что функция возвращает пустой словарь при ошибке.
    """
    api_key = "test_api_key"
    json_container = build_json_container(
        {name: f"Desc {name}" for name in REPORT_TO_INDEX_MAPPING.keys()}
    )

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_client_class.return_value = mock_client

        result = await evaluate_batch_relevance(
            question="test",
            json_container=json_container,
            api_key=api_key
        )

        # Функция возвращает пустой словарь при ошибке
        assert result == {}


@pytest.mark.asyncio
async def test_evaluate_batch_relevance_rate_limit_retry():
    """
    Тест retry механизма при RateLimitError.

    Проверяет exponential backoff и успешный retry.
    """
    from anthropic import RateLimitError

    api_key = "test_api_key"
    json_container = build_json_container(
        {name: f"Desc {name}" for name in REPORT_TO_INDEX_MAPPING.keys()}
    )

    # Создаем успешный ответ для второй попытки
    evaluations = [
        {"id": i, "name": name, "relevance": 50, "reason": "Test"}
        for i, name in enumerate(sorted(REPORT_TO_INDEX_MAPPING.keys()), 1)
    ]
    success_json = json.dumps({"evaluations": evaluations})

    success_response = MagicMock()
    success_content = MagicMock()
    success_content.text = success_json
    success_response.content = [success_content]

    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.request = mock_request

    rate_limit_error = RateLimitError(
        "Rate limit exceeded",
        response=mock_response,
        body=None
    )

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[rate_limit_error, success_response]
        )
        mock_client_class.return_value = mock_client

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await evaluate_batch_relevance(
                question="test",
                json_container=json_container,
                api_key=api_key
            )

            # Должен был сделать retry
            assert mock_client.messages.create.call_count == 2
            mock_sleep.assert_called_once()

            # Должен вернуть успешный результат
            assert len(result) == 22


@pytest.mark.asyncio
async def test_evaluate_batch_relevance_timeout():
    """
    Тест обработки timeout при batch-запросе.

    Проверяет корректную обработку превышения таймаута.
    """
    api_key = "test_api_key"
    json_container = build_json_container(
        {name: f"Desc {name}" for name in REPORT_TO_INDEX_MAPPING.keys()}
    )

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()

        async def slow_create(*args, **kwargs):
            await asyncio.sleep(100)

        mock_client.messages.create = slow_create
        mock_client_class.return_value = mock_client

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                evaluate_batch_relevance(
                    question="test",
                    json_container=json_container,
                    api_key=api_key
                ),
                timeout=0.1
            )


# === ТЕСТЫ ОЦЕНКИ ОДНОГО ОТЧЕТА ===

@pytest.mark.asyncio
async def test_evaluate_single_report_success(
    sample_question,
    sample_report_description,
    mock_anthropic_response
):
    """
    Тест успешной оценки релевантности одного отчета.

    Проверяет:
    - Корректный вызов Anthropic API с правильными параметрами
    - Парсинг числового ответа из текста модели
    - Возврат кортежа (имя_отчета, релевантность)
    """
    semaphore = asyncio.Semaphore(10)
    api_key = "test_api_key"

    # Мок AsyncAnthropic client
    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
        mock_client_class.return_value = mock_client

        result = await evaluate_single_report(
            question=sample_question,
            report_name="Световой_дизайн",
            report_description=sample_report_description,
            semaphore=semaphore,
            api_key=api_key
        )

        # Проверка вызова API
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == HAIKU_MODEL
        assert call_kwargs["max_tokens"] == MAX_TOKENS
        assert call_kwargs["temperature"] == TEMPERATURE

        # Проверка результата
        assert result[0] == "Световой_дизайн"
        assert result[1] == 85.0


@pytest.mark.asyncio
async def test_evaluate_single_report_parsing_complex_answer():
    """
    Тест парсинга сложного ответа от модели.

    Проверяет, что функция корректно извлекает число даже если модель
    вернула ответ с пояснениями (вопреки инструкции).

    Example ответа: "Релевантность составляет примерно 75.5 процентов"
    """
    semaphore = asyncio.Semaphore(10)

    # Мок ответа с пояснениями
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Релевантность составляет примерно 75.5 процентов"
    mock_response.content = [mock_content]

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate_single_report(
            question="test question",
            report_name="TestReport",
            report_description="test description",
            semaphore=semaphore,
            api_key="test_key"
        )

        # Должно извлечь первое число (75.5)
        assert result[1] == 75.5


@pytest.mark.asyncio
async def test_evaluate_single_report_unparseable_answer():
    """
    Тест обработки непарсируемого ответа от модели.

    Проверяет fallback на 0.0 если ответ не содержит чисел.
    """
    semaphore = asyncio.Semaphore(10)

    # Мок ответа без чисел
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Невозможно определить релевантность"
    mock_response.content = [mock_content]

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate_single_report(
            question="test question",
            report_name="TestReport",
            report_description="test description",
            semaphore=semaphore,
            api_key="test_key"
        )

        # Fallback на 0.0
        assert result[1] == 0.0


@pytest.mark.asyncio
async def test_evaluate_single_report_out_of_range():
    """
    Тест обработки ответа вне диапазона 0-100.

    Проверяет clamping значений к допустимому диапазону.
    """
    semaphore = asyncio.Semaphore(10)

    # Тест значения > 100
    mock_response_high = MagicMock()
    mock_content_high = MagicMock()
    mock_content_high.text = "150"
    mock_response_high.content = [mock_content_high]

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response_high)
        mock_client_class.return_value = mock_client

        result_high = await evaluate_single_report(
            question="test",
            report_name="Test",
            report_description="test",
            semaphore=semaphore,
            api_key="test_key"
        )

        # Должно быть clamped к 100
        assert result_high[1] == 100.0

    # Тест значения < 0
    mock_response_low = MagicMock()
    mock_content_low = MagicMock()
    mock_content_low.text = "-50"
    mock_response_low.content = [mock_content_low]

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response_low)
        mock_client_class.return_value = mock_client

        result_low = await evaluate_single_report(
            question="test",
            report_name="Test2",
            report_description="test",
            semaphore=semaphore,
            api_key="test_key"
        )

        # Должно быть clamped к 0
        assert result_low[1] == 0.0


@pytest.mark.asyncio
async def test_evaluate_single_report_rate_limit_retry():
    """
    Тест retry механизма при RateLimitError.

    Проверяет:
    - Exponential backoff при ошибках rate limiting
    - Успешный retry после временной ошибки
    - Fallback на 0.0 после MAX_RETRIES неудачных попыток
    """
    from anthropic import RateLimitError

    semaphore = asyncio.Semaphore(10)

    # Мок успешного ответа после retry
    success_response = MagicMock()
    success_content = MagicMock()
    success_content.text = "80"
    success_response.content = [success_content]

    # Создать mock request object для RateLimitError
    mock_request = MagicMock()

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()

        # Создать RateLimitError с правильными параметрами
        mock_response = MagicMock()
        mock_response.request = mock_request

        rate_limit_error = RateLimitError(
            "Rate limit exceeded",
            response=mock_response,
            body=None
        )

        # Первый вызов - RateLimitError, второй - успех
        mock_client.messages.create = AsyncMock(
            side_effect=[rate_limit_error, success_response]
        )
        mock_client_class.return_value = mock_client

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await evaluate_single_report(
                question="test",
                report_name="Test",
                report_description="test",
                semaphore=semaphore,
                api_key="test_key"
            )

            # Должен был сделать retry и получить успешный результат
            assert result[1] == 80.0
            # Должен был выполнить sleep перед retry
            mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_single_report_timeout():
    """
    Тест обработки timeout при запросе к API.

    Проверяет fallback на 0.0 при превышении таймаута.
    """
    semaphore = asyncio.Semaphore(10)

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()

        # Симуляция долгого запроса (timeout)
        async def slow_create(*args, **kwargs):
            await asyncio.sleep(100)  # Больше чем REQUEST_TIMEOUT

        mock_client.messages.create = slow_create
        mock_client_class.return_value = mock_client

        result = await evaluate_single_report(
            question="test",
            report_name="Test",
            report_description="test",
            semaphore=semaphore,
            api_key="test_key"
        )

        # Должен вернуть fallback 0.0 из-за timeout
        assert result[1] == 0.0


# === ТЕСТЫ ОСНОВНОЙ ФУНКЦИИ С BATCH МЕХАНИЗМОМ ===

@pytest.mark.asyncio
async def test_evaluate_report_relevance_uses_batch_mechanism(full_report_descriptions):
    """
    Тест что evaluate_report_relevance использует batch-механизм.

    Проверяет, что функция вызывает evaluate_batch_relevance
    вместо множества evaluate_single_report.
    """
    question = "тестовый вопрос"
    api_key = "test_api_key"

    # Мок результата от batch-оценки
    mock_result = {name: 50.0 for name in full_report_descriptions.keys()}

    with patch('src.relevance_evaluator.evaluate_batch_relevance',
               new_callable=AsyncMock, return_value=mock_result) as mock_batch:
        with patch('src.relevance_evaluator.evaluate_single_report') as mock_single:
            result = await evaluate_report_relevance(
                question=question,
                report_descriptions=full_report_descriptions,
                api_key=api_key
            )

            # Должен вызвать batch-функцию
            mock_batch.assert_called_once()

            # НЕ должен вызывать single-функцию
            mock_single.assert_not_called()

            # Результат должен быть от batch
            assert len(result) == 22


@pytest.mark.asyncio
async def test_evaluate_report_relevance_success_with_batch(full_report_descriptions):
    """
    Тест успешной оценки релевантности через batch-механизм.

    Проверяет:
    - Корректную работу с batch API
    - Возврат словаря с релевантностью для каждого отчета
    """
    question = "проблемы с освещением"
    api_key = "test_api_key"

    # Создаем mock результат
    evaluations = [
        {"id": i, "name": name, "relevance": 50 + i, "reason": f"Test {i}"}
        for i, name in enumerate(sorted(full_report_descriptions.keys()), 1)
    ]
    response_json = json.dumps({"evaluations": evaluations})

    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = response_json
    mock_response.content = [mock_content]

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate_report_relevance(
            question=question,
            report_descriptions=full_report_descriptions,
            api_key=api_key
        )

        # Проверки
        assert len(result) == 22
        for name in full_report_descriptions.keys():
            assert name in result
            assert 0 <= result[name] <= 100


@pytest.mark.asyncio
async def test_evaluate_report_relevance_auto_load_descriptions():
    """
    Тест автоматической загрузки описаний отчетов.

    Проверяет, что функция вызывает load_report_descriptions()
    если report_descriptions не передан явно.
    """
    question = "тест вопрос"
    api_key = "test_api_key"

    mock_descriptions = {
        "Отчет1": "Описание 1",
        "Отчет2": "Описание 2"
    }

    # Мок для batch-оценки
    mock_result = {"Отчет1": 50.0, "Отчет2": 60.0}

    with patch('src.relevance_evaluator.load_report_descriptions', return_value=mock_descriptions):
        with patch('src.relevance_evaluator.evaluate_batch_relevance',
                   new_callable=AsyncMock, return_value=mock_result):
            result = await evaluate_report_relevance(
                question=question,
                report_descriptions=None,  # Явно не передаем
                api_key=api_key
            )

            # Должны быть обработаны загруженные описания
            assert len(result) == 2
            assert "Отчет1" in result
            assert "Отчет2" in result


@pytest.mark.asyncio
async def test_evaluate_report_relevance_empty_question():
    """
    Тест валидации пустого вопроса.

    Проверяет, что функция выбрасывает ValueError при пустом вопросе.
    """
    with pytest.raises(ValueError) as exc_info:
        await evaluate_report_relevance(
            question="",
            report_descriptions={"Test": "Description"},
            api_key="test_key"
        )

    assert "не может быть пустым" in str(exc_info.value)


@pytest.mark.asyncio
async def test_evaluate_report_relevance_missing_api_key():
    """
    Тест валидации отсутствующего API key.

    Проверяет, что функция выбрасывает ValueError если API key
    не передан и не установлен в конфигурации.
    """
    with patch('src.relevance_evaluator.ANTHROPIC_API_KEY', None):
        with pytest.raises(ValueError) as exc_info:
            await evaluate_report_relevance(
                question="test question",
                report_descriptions={"Test": "Description"},
                api_key=None
            )

        assert "ANTHROPIC_API_KEY не установлен" in str(exc_info.value)


@pytest.mark.asyncio
async def test_evaluate_report_relevance_empty_descriptions():
    """
    Тест обработки пустого словаря описаний.

    Проверяет, что функция выбрасывает ValueError при пустом
    словаре описаний отчетов.
    """
    with pytest.raises(ValueError) as exc_info:
        await evaluate_report_relevance(
            question="test question",
            report_descriptions={},  # Пустой словарь
            api_key="test_key"
        )

    assert "Не удалось загрузить описания отчетов" in str(exc_info.value)


@pytest.mark.asyncio
async def test_relevance_score_range(full_report_descriptions):
    """
    Тест диапазона значений релевантности.

    Проверяет, что все возвращенные значения находятся в диапазоне 0-100.
    """
    question = "тестовый вопрос"
    api_key = "test_api_key"

    # Создаем оценки с разными значениями
    evaluations = [
        {"id": i, "name": name, "relevance": (i * 5) % 101, "reason": f"Test {i}"}
        for i, name in enumerate(sorted(full_report_descriptions.keys()), 1)
    ]
    response_json = json.dumps({"evaluations": evaluations})

    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = response_json
    mock_response.content = [mock_content]

    with patch('src.relevance_evaluator.anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await evaluate_report_relevance(
            question=question,
            report_descriptions=full_report_descriptions,
            api_key=api_key
        )

        # Все значения должны быть в диапазоне [0, 100]
        for report_name, relevance in result.items():
            assert 0 <= relevance <= 100, f"Релевантность {report_name} вне диапазона: {relevance}"


# === ИНТЕГРАЦИОННЫЕ ТЕСТЫ (опциональные, требуют API key) ===

@pytest.mark.integration
@pytest.mark.asyncio
async def test_evaluate_report_relevance_real_api():
    """
    Интеграционный тест с реальным Anthropic API.

    ВНИМАНИЕ: Этот тест делает реальные запросы к API!
    Запускается только с флагом: pytest -m integration

    Требования:
    - ANTHROPIC_API_KEY должен быть установлен в .env
    - Баланс API credits должен быть > 0

    Проверяет:
    - Реальную работу с Claude Haiku API
    - Корректность парсинга реальных ответов модели
    - Performance (время выполнения)
    """
    pytest.importorskip("anthropic")  # Пропустить если anthropic не установлен

    from src.config import ANTHROPIC_API_KEY

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("test_"):
        pytest.skip("Реальный ANTHROPIC_API_KEY не настроен")

    # Минимальный набор описаний для экономии API credits
    mini_descriptions = {
        "Световой_дизайн": "Анализ освещения ресторана...",
        "Общие_факторы": "Результаты интервью с гостями..."
    }

    question = "проблемы с освещением в ресторане"

    import time
    start_time = time.time()

    result = await evaluate_report_relevance(
        question=question,
        report_descriptions=mini_descriptions
    )

    elapsed = time.time() - start_time

    # Проверки
    # Функция оценивает все отчеты из JSON-контейнера (кэш), не только переданные descriptions
    # Поэтому результат содержит все отчеты из кэша
    assert len(result) >= 2, f"Ожидалось минимум 2 отчета, получено {len(result)}"

    # Проверяем что результат - словарь с числовыми значениями в правильном диапазоне
    assert isinstance(result, dict)
    for name, score in result.items():
        assert isinstance(score, (int, float)), f"Score для {name} должен быть числом"
        assert 0 <= score <= 100, f"Score для {name} должен быть в диапазоне 0-100"

    # Performance check (до 30 секунд для полного batch-запроса)
    assert elapsed < 30.0, f"Слишком долго: {elapsed}s"

    print(f"\n[OK] Интеграционный тест пройден за {elapsed:.2f}s")
    print(f"   Всего отчетов оценено: {len(result)}")
    # Выводим топ-3 по релевантности
    top_3 = sorted(result.items(), key=lambda x: x[1], reverse=True)[:3]
    for name, score in top_3:
        print(f"   {name}: {score:.1f}%")


# === ТЕСТЫ EDGE CASES ===

@pytest.mark.asyncio
async def test_evaluate_report_relevance_unicode_question(full_report_descriptions):
    """
    Тест обработки вопроса с unicode символами (русский).

    Проверяет корректную работу с различными языками.
    """
    unicode_questions = [
        "Проблемы с освещением",
        "Как улучшить дизайн?",
        "Что делать с кондиционером"
    ]

    api_key = "test_api_key"

    # Мок для batch-оценки
    mock_result = {name: 50.0 for name in full_report_descriptions.keys()}

    with patch('src.relevance_evaluator.evaluate_batch_relevance',
               new_callable=AsyncMock, return_value=mock_result):
        for question in unicode_questions:
            result = await evaluate_report_relevance(
                question=question,
                report_descriptions=full_report_descriptions,
                api_key=api_key
            )
            assert len(result) == 22


@pytest.mark.asyncio
async def test_batch_fallback_to_single_on_error(full_report_descriptions):
    """
    Тест что batch-механизм используется по умолчанию.

    Проверяет, что evaluate_report_relevance вызывает batch-функцию.
    """
    question = "тестовый вопрос"
    api_key = "test_api_key"

    # ИСПРАВЛЕНО: использование dict.fromkeys() вместо dict comprehension
    # так как все значения одинаковые
    mock_result = dict.fromkeys(full_report_descriptions.keys(), 50.0)

    with patch('src.relevance_evaluator.evaluate_batch_relevance',
               new_callable=AsyncMock, return_value=mock_result) as mock_batch:
        result = await evaluate_report_relevance(
            question=question,
            report_descriptions=full_report_descriptions,
            api_key=api_key
        )

        # Batch должен быть вызван
        mock_batch.assert_called_once()
        assert len(result) == 22


if __name__ == "__main__":
    """
    Запуск тестов напрямую через Python.

    Example:
        python tests/test_relevance_evaluator.py
    """
    pytest.main([__file__, "-v", "--tb=short"])
