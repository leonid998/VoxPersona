"""
Unit-тесты для модуля relevance_evaluator.

Тестирует функциональность оценки релевантности отчетов через Claude Haiku API.
Использует моки для изоляции от внешних зависимостей (API, файловая система).

Запуск тестов:
    pytest tests/test_relevance_evaluator.py -v
    pytest tests/test_relevance_evaluator.py::test_load_report_descriptions -v
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# Импорт тестируемых функций
from src.relevance_evaluator import (
    load_report_descriptions,
    build_relevance_prompt,
    evaluate_single_report,
    evaluate_report_relevance,
    HAIKU_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
    REPORT_DESCRIPTIONS_DIR
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
def mock_anthropic_response():
    """Мок ответа от Anthropic API."""
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "85"  # Процент релевантности
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


# === ТЕСТЫ ОСНОВНОЙ ФУНКЦИИ ===

@pytest.mark.asyncio
async def test_evaluate_report_relevance_success(sample_report_descriptions):
    """
    Тест успешной оценки релевантности всех отчетов.

    Проверяет:
    - Параллельную обработку всех отчетов
    - Возврат словаря с релевантностью для каждого отчета
    - Корректные значения в диапазоне 0-100
    """
    question = "проблемы с освещением"
    api_key = "test_api_key"

    # Мок ответов для каждого отчета
    mock_responses = {
        "Структурированный_отчет_аудита": 70.0,
        "Общие_факторы": 30.0,
        "Световой_дизайн": 95.0
    }

    async def mock_evaluate_single(question, report_name, report_description, semaphore, api_key):
        return (report_name, mock_responses.get(report_name, 0.0))

    with patch('src.relevance_evaluator.evaluate_single_report', side_effect=mock_evaluate_single):
        result = await evaluate_report_relevance(
            question=question,
            report_descriptions=sample_report_descriptions,
            api_key=api_key
        )

        # Проверки
        assert len(result) == 3
        assert result["Структурированный_отчет_аудита"] == 70.0
        assert result["Общие_факторы"] == 30.0
        assert result["Световой_дизайн"] == 95.0


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

    async def mock_evaluate_single(question, report_name, report_description, semaphore, api_key):
        return (report_name, 50.0)

    with patch('src.relevance_evaluator.load_report_descriptions', return_value=mock_descriptions):
        with patch('src.relevance_evaluator.evaluate_single_report', side_effect=mock_evaluate_single):
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
async def test_relevance_score_range(sample_report_descriptions):
    """
    Тест диапазона значений релевантности.

    Проверяет, что все возвращенные значения находятся в диапазоне 0-100.
    """
    question = "тестовый вопрос"
    api_key = "test_api_key"

    # Мок с различными значениями релевантности
    async def mock_evaluate_single(question, report_name, report_description, semaphore, api_key):
        # Возвращаем разные значения для разных отчетов
        values = {
            "Структурированный_отчет_аудита": 0.0,
            "Общие_факторы": 50.5,
            "Световой_дизайн": 100.0
        }
        return (report_name, values.get(report_name, 75.0))

    with patch('src.relevance_evaluator.evaluate_single_report', side_effect=mock_evaluate_single):
        result = await evaluate_report_relevance(
            question=question,
            report_descriptions=sample_report_descriptions,
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
    assert len(result) == 2
    assert "Световой_дизайн" in result
    assert "Общие_факторы" in result

    # Световой дизайн должен быть более релевантен для вопроса об освещении
    assert result["Световой_дизайн"] > result["Общие_факторы"]

    # Performance check (должно быть быстрее 10 секунд для 2 отчетов)
    assert elapsed < 10.0, f"Слишком долго: {elapsed}s"

    print(f"\n✅ Интеграционный тест пройден за {elapsed:.2f}s")
    print(f"   Световой_дизайн: {result['Световой_дизайн']:.1f}%")
    print(f"   Общие_факторы: {result['Общие_факторы']:.1f}%")


# === ТЕСТЫ EDGE CASES ===

@pytest.mark.asyncio
async def test_evaluate_report_relevance_concurrent_limit():
    """
    Тест ограничения параллельных запросов (semaphore).

    Проверяет, что не более MAX_CONCURRENT_REQUESTS (10) запросов
    выполняются одновременно.
    """
    # Создать 20 тестовых отчетов
    many_descriptions = {f"Отчет_{i}": f"Описание {i}" for i in range(20)}

    api_key = "test_api_key"
    max_concurrent_observed = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def mock_evaluate_with_tracking(question, report_name, report_description, semaphore, api_key):
        nonlocal current_concurrent, max_concurrent_observed

        # ВАЖНО: используем семафор который передается в функцию
        async with semaphore:
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent_observed:
                    max_concurrent_observed = current_concurrent

            # Симулируем работу
            await asyncio.sleep(0.1)

            async with lock:
                current_concurrent -= 1

        return (report_name, 50.0)

    with patch('src.relevance_evaluator.evaluate_single_report', side_effect=mock_evaluate_with_tracking):
        await evaluate_report_relevance(
            question="test",
            report_descriptions=many_descriptions,
            api_key=api_key
        )

        # Максимальное количество concurrent запросов не должно превышать MAX_CONCURRENT_REQUESTS
        from src.relevance_evaluator import MAX_CONCURRENT_REQUESTS
        assert max_concurrent_observed <= MAX_CONCURRENT_REQUESTS, \
            f"Observed {max_concurrent_observed} concurrent requests, expected <= {MAX_CONCURRENT_REQUESTS}"


@pytest.mark.asyncio
async def test_evaluate_report_relevance_unicode_question():
    """
    Тест обработки вопроса с unicode символами (русский, эмодзи).

    Проверяет корректную работу с различными языками и специальными символами.
    """
    unicode_questions = [
        "Проблемы с освещением 💡",
        "Как улучшить дизайн? 🎨",
        "Что делать с кондиционером ❄️"
    ]

    descriptions = {"Тест": "Описание"}
    api_key = "test_api_key"

    async def mock_evaluate(question, report_name, report_description, semaphore, api_key):
        return (report_name, 50.0)

    with patch('src.relevance_evaluator.evaluate_single_report', side_effect=mock_evaluate):
        for question in unicode_questions:
            result = await evaluate_report_relevance(
                question=question,
                report_descriptions=descriptions,
                api_key=api_key
            )
            assert len(result) == 1
            assert "Тест" in result


if __name__ == "__main__":
    """
    Запуск тестов напрямую через Python.

    Example:
        python tests/test_relevance_evaluator.py
    """
    pytest.main([__file__, "-v", "--tb=short"])
