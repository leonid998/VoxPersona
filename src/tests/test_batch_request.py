"""
Тесты для функции evaluate_batch_relevance() и связанных функций парсинга.

Этот модуль содержит unit-тесты для:
- parse_batch_response() - парсинг JSON из ответа модели
- validate_batch_evaluations() - валидация списка оценок
- convert_evaluations_to_dict() - преобразование в словарь
- evaluate_batch_relevance() - основная функция batch-оценки (с моками)

Все тесты используют моки для API вызовов - реальные запросы НЕ отправляются.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path

# Добавить src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from relevance_evaluator import (
    parse_batch_response,
    validate_batch_evaluations,
    convert_evaluations_to_dict,
    evaluate_batch_relevance,
    BATCH_MAX_TOKENS,
    BATCH_REQUEST_TIMEOUT,
    MAX_RETRIES,
)


# === FIXTURES ===

@pytest.fixture
def valid_response_json():
    """Корректный JSON ответ от модели с 22 оценками."""
    evaluations = []
    report_names = [
        "Аудит_Дизайна", "Востребованность_гостиничного_хозяйства",
        "Главная_Краткое резюме комплексного обследования", "Дизайн и архитектура",
        "Заполняемость_и_бронирование", "Итоговый_отчет",
        "Качество_инфраструктуры", "Клиентский_опыт",
        "Маршруты_и_безопасность", "Недостатки_дизайна",
        "Обследование", "Обустройство_гостиничного_хозяйства",
        "Общие_факторы", "Ожидания_и_реальность",
        "Отдых_и_восстановление", "Отчет_о_связках",
        "Ощущения от отеля", "Противоречия_концепции_и_дизайна",
        "Рекомендации_по_улучшению", "Сильные стороны дизайна",
        "Структурированный_отчет_аудита", "Факторы_в_этом_заведении"
    ]

    for i, name in enumerate(report_names, start=1):
        evaluations.append({
            "id": i,
            "name": name,
            "relevance": 50 + (i % 50),  # Релевантность от 51 до 100
            "reason": f"Тестовое обоснование для {name}"
        })

    return json.dumps({"evaluations": evaluations}, ensure_ascii=False)


@pytest.fixture
def valid_evaluations():
    """Корректный список из 22 оценок."""
    evaluations = []
    for i in range(1, 23):
        evaluations.append({
            "id": i,
            "name": f"Report_{i}",
            "relevance": i * 4,  # 4, 8, 12, ..., 88
            "reason": f"Обоснование #{i}"
        })
    return evaluations


@pytest.fixture
def sample_json_container():
    """Пример JSON-контейнера для тестов."""
    return json.dumps({
        "reports": [
            {"id": 1, "name": "Test_Report", "index": "Test", "description": "Тестовое описание"}
        ],
        "indices": [{"name": "Test", "display_name": "Тест", "report_ids": [1]}],
        "total_reports": 1,
        "total_indices": 1
    }, ensure_ascii=False)


# === ТЕСТЫ parse_batch_response() ===

class TestParseBatchResponse:
    """Тесты для функции parse_batch_response()."""

    def test_parse_valid_response(self, valid_response_json):
        """Тест парсинга корректного JSON ответа."""
        result = parse_batch_response(valid_response_json)

        assert "evaluations" in result
        assert isinstance(result["evaluations"], list)
        assert len(result["evaluations"]) == 22

        # Проверка структуры первого элемента
        first_eval = result["evaluations"][0]
        assert "id" in first_eval
        assert "name" in first_eval
        assert "relevance" in first_eval
        assert "reason" in first_eval

    def test_parse_response_with_markdown_json(self):
        """Тест парсинга JSON в markdown-блоке ```json ... ```."""
        markdown_response = '''```json
{
  "evaluations": [
    {"id": 1, "name": "Test", "relevance": 85, "reason": "Test reason"}
  ]
}
```'''
        result = parse_batch_response(markdown_response)

        assert "evaluations" in result
        assert len(result["evaluations"]) == 1
        assert result["evaluations"][0]["relevance"] == 85

    def test_parse_response_with_markdown_no_lang(self):
        """Тест парсинга JSON в markdown-блоке без указания языка."""
        markdown_response = '''```
{
  "evaluations": [
    {"id": 1, "name": "Test", "relevance": 75, "reason": "Test"}
  ]
}
```'''
        result = parse_batch_response(markdown_response)

        assert len(result["evaluations"]) == 1
        assert result["evaluations"][0]["relevance"] == 75

    def test_parse_response_with_text_before_json(self):
        """Тест парсинга JSON с текстом до JSON объекта."""
        response_with_text = '''Вот результаты оценки:

{
  "evaluations": [
    {"id": 1, "name": "Test", "relevance": 90, "reason": "Test"}
  ]
}'''
        result = parse_batch_response(response_with_text)

        assert result["evaluations"][0]["relevance"] == 90

    def test_parse_response_with_text_after_json(self):
        """Тест парсинга JSON с текстом после JSON объекта."""
        response_with_text = '''{
  "evaluations": [
    {"id": 1, "name": "Test", "relevance": 65, "reason": "Test"}
  ]
}

Надеюсь, это поможет!'''
        result = parse_batch_response(response_with_text)

        assert result["evaluations"][0]["relevance"] == 65

    def test_parse_response_with_trailing_comma(self):
        """Тест парсинга JSON с trailing comma (типичная ошибка)."""
        response_with_comma = '''{
  "evaluations": [
    {"id": 1, "name": "Test1", "relevance": 80, "reason": "Test"},
    {"id": 2, "name": "Test2", "relevance": 60, "reason": "Test"},
  ]
}'''
        result = parse_batch_response(response_with_comma)

        assert len(result["evaluations"]) == 2

    def test_parse_empty_response_raises_error(self):
        """Тест ошибки при пустом ответе."""
        with pytest.raises(ValueError, match="Пустой ответ"):
            parse_batch_response("")

        with pytest.raises(ValueError, match="Пустой ответ"):
            parse_batch_response("   ")

    def test_parse_response_no_json_raises_error(self):
        """Тест ошибки при отсутствии JSON в ответе."""
        with pytest.raises(ValueError, match="Не найден JSON"):
            parse_batch_response("Это просто текст без JSON")

    def test_parse_response_no_evaluations_key_raises_error(self):
        """Тест ошибки при отсутствии ключа 'evaluations'."""
        invalid_json = '{"results": [{"id": 1, "name": "Test"}]}'

        with pytest.raises(ValueError, match="отсутствует ключ 'evaluations'"):
            parse_batch_response(invalid_json)

    def test_parse_response_evaluations_not_list_raises_error(self):
        """Тест ошибки когда 'evaluations' не является списком."""
        invalid_json = '{"evaluations": "not a list"}'

        with pytest.raises(ValueError, match="должен быть списком"):
            parse_batch_response(invalid_json)

    def test_parse_response_with_russian_text(self):
        """Тест парсинга JSON с русским текстом."""
        russian_response = '''{
  "evaluations": [
    {
      "id": 1,
      "name": "Структурированный_отчет_аудита",
      "relevance": 95,
      "reason": "Содержит анализ освещения в ресторанах"
    }
  ]
}'''
        result = parse_batch_response(russian_response)

        assert result["evaluations"][0]["name"] == "Структурированный_отчет_аудита"
        assert "освещения" in result["evaluations"][0]["reason"]


# === ТЕСТЫ validate_batch_evaluations() ===

class TestValidateBatchEvaluations:
    """Тесты для функции validate_batch_evaluations()."""

    def test_validation_all_reports_success(self, valid_evaluations):
        """Тест успешной валидации 22 оценок."""
        is_valid, errors = validate_batch_evaluations(valid_evaluations)

        assert is_valid is True
        assert len(errors) == 0

    def test_validation_custom_expected_count(self):
        """Тест валидации с кастомным ожидаемым количеством."""
        evaluations = [
            {"id": 1, "name": "Test1", "relevance": 50},
            {"id": 2, "name": "Test2", "relevance": 60}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=2)

        assert is_valid is True
        assert len(errors) == 0

    def test_validation_wrong_count(self):
        """Тест ошибки при неправильном количестве оценок."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": 50}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=22)

        assert is_valid is False
        assert any("Ожидалось 22" in e for e in errors)

    def test_validation_range_valid(self):
        """Тест валидации релевантности в корректном диапазоне 0-100."""
        evaluations = [
            {"id": 1, "name": "Test1", "relevance": 0},
            {"id": 2, "name": "Test2", "relevance": 50},
            {"id": 3, "name": "Test3", "relevance": 100}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=3)

        assert is_valid is True

    def test_validation_range_invalid_negative(self):
        """Тест ошибки при отрицательной релевантности."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": -10}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is False
        assert any("вне диапазона" in e for e in errors)

    def test_validation_range_invalid_over_100(self):
        """Тест ошибки при релевантности > 100."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": 150}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is False
        assert any("вне диапазона" in e for e in errors)

    def test_validation_missing_id(self):
        """Тест ошибки при отсутствии поля 'id'."""
        evaluations = [
            {"name": "Test", "relevance": 50}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is False
        assert any("отсутствует поле 'id'" in e for e in errors)

    def test_validation_missing_name(self):
        """Тест ошибки при отсутствии поля 'name'."""
        evaluations = [
            {"id": 1, "relevance": 50}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is False
        assert any("отсутствует поле 'name'" in e for e in errors)

    def test_validation_missing_relevance(self):
        """Тест ошибки при отсутствии поля 'relevance'."""
        evaluations = [
            {"id": 1, "name": "Test"}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is False
        assert any("отсутствует поле 'relevance'" in e for e in errors)

    def test_validation_duplicate_ids(self):
        """Тест ошибки при дублирующихся id."""
        evaluations = [
            {"id": 1, "name": "Test1", "relevance": 50},
            {"id": 1, "name": "Test2", "relevance": 60}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=2)

        assert is_valid is False
        assert any("дублирующийся id" in e for e in errors)

    def test_validation_duplicate_names(self):
        """Тест ошибки при дублирующихся именах."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": 50},
            {"id": 2, "name": "Test", "relevance": 60}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=2)

        assert is_valid is False
        assert any("дублирующееся имя" in e for e in errors)

    def test_validation_relevance_wrong_type(self):
        """Тест ошибки при неправильном типе relevance."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": "high"}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is False
        assert any("должен быть числом" in e for e in errors)

    def test_validation_float_relevance_valid(self):
        """Тест корректной валидации float релевантности."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": 75.5}
        ]

        is_valid, errors = validate_batch_evaluations(evaluations, expected_count=1)

        assert is_valid is True


# === ТЕСТЫ convert_evaluations_to_dict() ===

class TestConvertEvaluationsToDict:
    """Тесты для функции convert_evaluations_to_dict()."""

    def test_convert_basic(self):
        """Тест базового преобразования списка в словарь."""
        evaluations = [
            {"id": 1, "name": "Report_A", "relevance": 85},
            {"id": 2, "name": "Report_B", "relevance": 30}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert result == {"Report_A": 85.0, "Report_B": 30.0}

    def test_convert_float_values(self):
        """Тест преобразования с float значениями."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": 75.5}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert result["Test"] == 75.5

    def test_convert_clamp_negative(self):
        """Тест clamp отрицательных значений до 0."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": -50}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert result["Test"] == 0.0

    def test_convert_clamp_over_100(self):
        """Тест clamp значений > 100 до 100."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": 150}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert result["Test"] == 100.0

    def test_convert_missing_name(self):
        """Тест обработки отсутствующего имени."""
        evaluations = [
            {"id": 1, "relevance": 50}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert "Unknown" in result
        assert result["Unknown"] == 50.0

    def test_convert_missing_relevance(self):
        """Тест обработки отсутствующей релевантности."""
        evaluations = [
            {"id": 1, "name": "Test"}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert result["Test"] == 0.0

    def test_convert_invalid_relevance_type(self):
        """Тест обработки невалидного типа релевантности."""
        evaluations = [
            {"id": 1, "name": "Test", "relevance": "invalid"}
        ]

        result = convert_evaluations_to_dict(evaluations)

        assert result["Test"] == 0.0

    def test_convert_empty_list(self):
        """Тест преобразования пустого списка."""
        result = convert_evaluations_to_dict([])

        assert result == {}

    def test_convert_22_reports(self, valid_evaluations):
        """Тест преобразования 22 отчетов."""
        result = convert_evaluations_to_dict(valid_evaluations)

        assert len(result) == 22
        # Проверка формата значений
        for name, score in result.items():
            assert isinstance(score, float)
            assert 0 <= score <= 100


# === ТЕСТЫ evaluate_batch_relevance() ===

class TestEvaluateBatchRelevance:
    """Тесты для функции evaluate_batch_relevance() с моками API."""

    @pytest.mark.asyncio
    async def test_evaluate_batch_success(self, sample_json_container, valid_response_json):
        """Тест успешного выполнения batch-оценки."""
        # Мок ответа от API
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_response_json)]

        with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await evaluate_batch_relevance(
                question="Тестовый вопрос",
                json_container=sample_json_container,
                api_key="test-api-key"
            )

            # Проверка результата
            assert isinstance(result, dict)
            assert len(result) == 22

            # Проверка что API был вызван
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["max_tokens"] == BATCH_MAX_TOKENS
            assert call_args.kwargs["temperature"] == 0

    @pytest.mark.asyncio
    async def test_evaluate_batch_empty_question_raises_error(self, sample_json_container):
        """Тест ошибки при пустом вопросе."""
        with pytest.raises(ValueError, match="Вопрос не может быть пустым"):
            await evaluate_batch_relevance(
                question="",
                json_container=sample_json_container,
                api_key="test-api-key"
            )

    @pytest.mark.asyncio
    async def test_evaluate_batch_empty_container_raises_error(self):
        """Тест ошибки при пустом JSON-контейнере."""
        with pytest.raises(ValueError, match="JSON-контейнер не может быть пустым"):
            await evaluate_batch_relevance(
                question="Тестовый вопрос",
                json_container="",
                api_key="test-api-key"
            )

    @pytest.mark.asyncio
    async def test_evaluate_batch_no_api_key_raises_error(self, sample_json_container):
        """Тест ошибки при отсутствии API ключа."""
        with patch("relevance_evaluator.ANTHROPIC_API_KEY", None):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY не установлен"):
                await evaluate_batch_relevance(
                    question="Тестовый вопрос",
                    json_container=sample_json_container,
                    api_key=None
                )

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, sample_json_container, valid_response_json):
        """Тест retry логики при RateLimitError."""
        from anthropic import RateLimitError

        # Мок ответа после retry
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_response_json)]

        # Создаем fake RateLimitError
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit"}}
        )

        with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            # Первый вызов - ошибка, второй - успех
            mock_client.messages.create = AsyncMock(
                side_effect=[rate_limit_error, mock_response]
            )
            mock_client_class.return_value = mock_client

            with patch("relevance_evaluator.asyncio.sleep", new_callable=AsyncMock):
                result = await evaluate_batch_relevance(
                    question="Тестовый вопрос",
                    json_container=sample_json_container,
                    api_key="test-api-key"
                )

            # Проверка что было 2 попытки
            assert mock_client.messages.create.call_count == 2
            assert len(result) == 22

    @pytest.mark.asyncio
    async def test_return_empty_dict_on_timeout(self, sample_json_container):
        """Тест возврата пустого словаря при timeout."""
        with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            mock_client_class.return_value = mock_client

            result = await evaluate_batch_relevance(
                question="Тестовый вопрос",
                json_container=sample_json_container,
                api_key="test-api-key"
            )

            assert result == {}

    @pytest.mark.asyncio
    async def test_return_empty_dict_on_parse_error(self, sample_json_container):
        """Тест возврата пустого словаря при ошибке парсинга."""
        # Невалидный JSON в ответе
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON")]

        with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await evaluate_batch_relevance(
                question="Тестовый вопрос",
                json_container=sample_json_container,
                api_key="test-api-key"
            )

            assert result == {}

    @pytest.mark.asyncio
    async def test_return_empty_dict_after_max_retries(self, sample_json_container):
        """Тест возврата пустого словаря после исчерпания попыток."""
        from anthropic import RateLimitError

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit"}}
        )

        with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            # Все попытки возвращают ошибку
            mock_client.messages.create = AsyncMock(
                side_effect=[rate_limit_error] * MAX_RETRIES
            )
            mock_client_class.return_value = mock_client

            with patch("relevance_evaluator.asyncio.sleep", new_callable=AsyncMock):
                result = await evaluate_batch_relevance(
                    question="Тестовый вопрос",
                    json_container=sample_json_container,
                    api_key="test-api-key"
                )

            assert result == {}
            assert mock_client.messages.create.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_api_key_from_config(self, sample_json_container, valid_response_json):
        """Тест использования API ключа из конфига."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_response_json)]

        with patch("relevance_evaluator.ANTHROPIC_API_KEY", "config-api-key"):
            with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                # Вызов без явного api_key
                result = await evaluate_batch_relevance(
                    question="Тестовый вопрос",
                    json_container=sample_json_container,
                    api_key=None
                )

                # Проверка что клиент создан с ключом из конфига
                mock_client_class.assert_called_once_with(api_key="config-api-key")

    @pytest.mark.asyncio
    async def test_result_format_compatible(self, sample_json_container, valid_response_json):
        """Тест совместимости формата результата с evaluate_report_relevance()."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=valid_response_json)]

        with patch("relevance_evaluator.anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await evaluate_batch_relevance(
                question="Тестовый вопрос",
                json_container=sample_json_container,
                api_key="test-api-key"
            )

            # Проверка формата: Dict[str, float]
            assert isinstance(result, dict)
            for name, score in result.items():
                assert isinstance(name, str)
                assert isinstance(score, float)
                assert 0 <= score <= 100


# === ИНТЕГРАЦИОННЫЕ ТЕСТЫ (БЕЗ РЕАЛЬНЫХ API ВЫЗОВОВ) ===

class TestBatchRequestIntegration:
    """Интеграционные тесты для полного пайплайна batch-запроса."""

    def test_full_pipeline_parse_validate_convert(self, valid_response_json):
        """Тест полного пайплайна: parse -> validate -> convert."""
        # Шаг 1: Парсинг
        parsed = parse_batch_response(valid_response_json)

        # Шаг 2: Валидация
        is_valid, errors = validate_batch_evaluations(parsed["evaluations"])
        assert is_valid is True

        # Шаг 3: Конвертация
        result = convert_evaluations_to_dict(parsed["evaluations"])

        # Финальная проверка
        assert len(result) == 22
        assert all(isinstance(v, float) for v in result.values())
        assert all(0 <= v <= 100 for v in result.values())

    def test_pipeline_with_validation_warnings(self):
        """Тест пайплайна с предупреждениями валидации (но не ошибками)."""
        # JSON с 21 оценкой вместо 22
        response = json.dumps({
            "evaluations": [
                {"id": i, "name": f"Report_{i}", "relevance": 50}
                for i in range(1, 22)  # Только 21
            ]
        })

        parsed = parse_batch_response(response)
        is_valid, errors = validate_batch_evaluations(parsed["evaluations"])

        # Валидация должна выдать ошибку о количестве
        assert is_valid is False
        assert len(errors) > 0

        # Но конвертация все равно работает
        result = convert_evaluations_to_dict(parsed["evaluations"])
        assert len(result) == 21


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
