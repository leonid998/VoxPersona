"""
Тесты для модуля question_enhancer.py.

Тестируется:
1. Основная функция enhance_question_for_index
2. Вспомогательные функции build_enhancement_prompt и format_index_descriptions
3. Валидация входных данных
4. Обработка ошибок API
5. Fallback на original_question при ошибках
6. Проверка длины улучшенного вопроса

Используется pytest с mock для API вызовов.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.constants import CLAUDE_ERROR_MESSAGE

from src.question_enhancer import (
    enhance_question_for_index,
    build_enhancement_prompt,
    format_index_descriptions
)
from src.index_selector import INDEX_MAPPING


# === FIXTURES ===

@pytest.fixture
def sample_report_descriptions():
    """
    Пример описаний отчетов для тестирования.

    Содержит описания для нескольких индексов из INDEX_MAPPING.
    """
    return {
        # Dizayn
        "Структурированный_отчет_аудита": "Структурированный отчет содержит детальный анализ дизайна интерьера отеля...",

        # Otchety_po_dizaynu
        "Дизайн и архитектура": "Анализ архитектурных решений и дизайна интерьера отеля, включая стилистику, цветовую гамму...",
        "Сильные стороны": "Описание сильных сторон дизайна отеля: уникальные элементы, качество материалов...",
        "Недостатки": "Анализ недостатков дизайна: устаревшие элементы, несоответствия стилю...",
        "Ожидания": "Соответствие дизайна ожиданиям гостей: комфорт, эстетика, функциональность...",
        "Противоречия": "Противоречия в дизайне: несовместимые стили, нелогичные решения...",

        # Itogovye_otchety
        "Краткое резюме": "Краткое резюме результатов аудита отеля...",
        "Ощущения": "Общие ощущения от пребывания в отеле...",
        "Заполняемость": "Анализ факторов влияющих на заполняемость отеля...",

        # Intervyu
        "Общие_факторы": "Общие факторы влияющие на бизнес отеля по результатам интервью...",
        "Отчет_о_связках": "Связи между различными факторами из интервью...",

        # Iskhodniki_dizayn
        "Аудит_Дизайна": "Исходный аудит дизайна отеля с детальными наблюдениями...",

        # Iskhodniki_obsledovanie
        "Обследование": "Исходное обследование территории и инфраструктуры отеля...",

        # Otchety_po_obsledovaniyu
        "Востребованность": "Анализ востребованности различных услуг и зон отеля...",
        "Качество инфраструктуры": "Оценка качества инфраструктуры отеля...",
        "Клиентский опыт": "Описание клиентского опыта в отеле...",
    }


@pytest.fixture
def sample_enhanced_response():
    """
    Пример ответа от Claude API с улучшенным вопросом.
    """
    return (
        "Анализ проблем освещения в ресторане отеля: недостаточная яркость, "
        "несоответствие атмосфере, устаревшие светильники. Изучить типы отчетов: "
        "Дизайн и архитектура, Недостатки дизайна. Ответ для управляющего отелем."
    )


# === ТЕСТЫ ВСПОМОГАТЕЛЬНЫХ ФУНКЦИЙ ===

def test_format_index_descriptions_basic(sample_report_descriptions):
    """
    Тест форматирования описаний отчетов индекса.

    Проверяет:
    - Корректное форматирование описаний
    - Наличие названия индекса
    - Наличие имен отчетов
    """
    selected_index = "Otchety_po_dizaynu"

    # Отфильтровать описания для индекса
    report_names_in_index = INDEX_MAPPING[selected_index]
    filtered = {
        name: desc
        for name, desc in sample_report_descriptions.items()
        if name in report_names_in_index
    }

    # Форматировать
    result = format_index_descriptions(selected_index, filtered)

    # Проверки
    assert selected_index in result
    assert "Дизайн и архитектура" in result
    assert "Сильные стороны" in result
    assert "Недостатки" in result


def test_format_index_descriptions_empty():
    """
    Тест форматирования с пустым словарем описаний.
    """
    result = format_index_descriptions("Dizayn", {})

    assert "Dizayn" in result
    assert "описания отчетов отсутствуют" in result


def test_format_index_descriptions_long_text(sample_report_descriptions):
    """
    Тест обрезки длинных описаний до 500 символов.
    """
    # Создать описание длиннее 500 символов
    long_description = "A" * 1000

    filtered = {
        "Тестовый_отчет": long_description
    }

    result = format_index_descriptions("Test_Index", filtered)

    # Проверить что описание обрезано
    assert "..." in result
    # Длина результата должна быть меньше исходного описания
    assert len(result) < len(long_description) + 200  # +200 на форматирование


def test_build_enhancement_prompt_structure():
    """
    Тест структуры промпта для улучшения вопроса.

    Проверяет наличие всех обязательных элементов.
    """
    original_q = "Какие проблемы с освещением?"
    index = "Otchety_po_dizaynu"
    descriptions = "Индекс содержит: Дизайн и архитектура..."

    prompt = build_enhancement_prompt(original_q, index, descriptions)

    # Обязательные элементы промпта
    assert original_q in prompt
    assert index in prompt
    assert descriptions in prompt
    assert "Алгоритм улучшения" in prompt
    assert "150-300 символов" in prompt
    assert "утверждение" in prompt.lower()
    assert "Верни ТОЛЬКО улучшенный вопрос" in prompt


# === ТЕСТЫ ОСНОВНОЙ ФУНКЦИИ ===

@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_for_index_basic(
    mock_send_msg,
    sample_report_descriptions,
    sample_enhanced_response
):
    """
    Основной тест улучшения вопроса.

    Проверяет:
    - Корректная фильтрация описаний по индексу
    - Вызов API с правильными параметрами
    - Возврат улучшенного вопроса
    """
    # Mock API response
    mock_send_msg.return_value = sample_enhanced_response

    # Вызвать функцию
    original = "Какие проблемы с освещением в ресторане?"
    index = "Otchety_po_dizaynu"

    result = enhance_question_for_index(
        original_question=original,
        selected_index=index,
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Проверки
    assert result == sample_enhanced_response
    assert mock_send_msg.called
    assert mock_send_msg.call_count == 1

    # Проверить параметры вызова API
    call_args = mock_send_msg.call_args
    assert call_args.kwargs['model'] == "claude-haiku-4-5-20250929"
    assert call_args.kwargs['max_tokens'] == 500
    assert call_args.kwargs['api_key'] == "test_key"

    # Проверить что промпт содержит правильные описания
    messages = call_args.kwargs['messages']
    assert len(messages) == 1
    prompt = messages[0]['content']
    assert original in prompt
    assert index in prompt
    assert "Дизайн и архитектура" in prompt


@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_strips_quotes(mock_send_msg, sample_report_descriptions):
    """
    Тест удаления кавычек из ответа API.

    Claude иногда возвращает результат в кавычках вопреки инструкции.
    """
    # API вернул результат в кавычках
    mock_send_msg.return_value = '"Улучшенный вопрос в кавычках"'

    result = enhance_question_for_index(
        original_question="тест",
        selected_index="Dizayn",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Кавычки должны быть удалены
    assert result == "Улучшенный вопрос в кавычках"
    assert not result.startswith('"')
    assert not result.endswith('"')


@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_truncates_long_response(mock_send_msg, sample_report_descriptions):
    """
    Тест обрезки слишком длинного ответа API.

    Ожидаемая длина улучшенного вопроса: 150-300 символов.
    Максимум: 500 символов.
    """
    # API вернул очень длинный ответ
    long_response = "A" * 1000

    mock_send_msg.return_value = long_response

    result = enhance_question_for_index(
        original_question="тест",
        selected_index="Dizayn",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Результат должен быть обрезан до 500 символов
    assert len(result) == 500
    assert result == "A" * 500


# === ТЕСТЫ ВАЛИДАЦИИ ===

def test_enhance_question_empty_question(sample_report_descriptions):
    """
    Тест валидации: пустой вопрос.
    """
    with pytest.raises(ValueError, match="не может быть пустым"):
        enhance_question_for_index(
            original_question="",
            selected_index="Dizayn",
            report_descriptions=sample_report_descriptions
        )

    with pytest.raises(ValueError, match="не может быть пустым"):
        enhance_question_for_index(
            original_question="   ",  # Только пробелы
            selected_index="Dizayn",
            report_descriptions=sample_report_descriptions
        )


def test_enhance_question_unknown_index(sample_report_descriptions):
    """
    Тест валидации: неизвестный индекс.
    """
    with pytest.raises(ValueError, match="не найден в INDEX_MAPPING"):
        enhance_question_for_index(
            original_question="тест",
            selected_index="UNKNOWN_INDEX",
            report_descriptions=sample_report_descriptions
        )


def test_enhance_question_empty_descriptions():
    """
    Тест валидации: пустой словарь описаний.
    """
    with pytest.raises(ValueError, match="не может быть пустым"):
        enhance_question_for_index(
            original_question="тест",
            selected_index="Dizayn",
            report_descriptions={}
        )


def test_enhance_question_no_matching_reports(sample_report_descriptions):
    """
    Тест fallback: ни один отчет индекса не найден в report_descriptions.

    Должен вернуть original_question без улучшения.
    """
    # Создать описания которые не содержат отчетов из "Dizayn"
    descriptions = {
        "Несуществующий_отчет": "Тест..."
    }

    result = enhance_question_for_index(
        original_question="тестовый вопрос",
        selected_index="Dizayn",
        report_descriptions=descriptions,
        api_key="test_key"
    )

    # Должен вернуться original_question без вызова API
    assert result == "тестовый вопрос"


# === ТЕСТЫ ОБРАБОТКИ ОШИБОК ===

@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_api_error_fallback(mock_send_msg, sample_report_descriptions):
    """
    Тест fallback при ошибке API.

    При любой ошибке должен вернуться original_question.
    """
    # API выбросил исключение
    mock_send_msg.side_effect = Exception("API Error")

    original = "тестовый вопрос"

    result = enhance_question_for_index(
        original_question=original,
        selected_index="Dizayn",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Должен вернуться original_question
    assert result == original


@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_api_returns_error_message(mock_send_msg, sample_report_descriptions):
    """
    Тест fallback когда API возвращает сообщение об ошибке.

    send_msg_to_model возвращает err строку при ошибке вместо исключения.
    """
    # API вернул сообщение об ошибке
    mock_send_msg.return_value = CLAUDE_ERROR_MESSAGE

    original = "тестовый вопрос"

    result = enhance_question_for_index(
        original_question=original,
        selected_index="Dizayn",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Должен вернуться original_question
    assert result == original


@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_too_short_response(mock_send_msg, sample_report_descriptions):
    """
    Тест fallback: ответ API слишком короткий (<20 символов).

    Может указывать на некорректный ответ модели.
    """
    # API вернул слишком короткий ответ (<20 символов)
    mock_send_msg.return_value = "Короткий"

    original = "тестовый вопрос"

    result = enhance_question_for_index(
        original_question=original,
        selected_index="Dizayn",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Должен вернуться original_question
    assert result == original




@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_truncates_long_question(mock_send_msg, sample_report_descriptions):
    """
    Тест обрезки слишком длинного вопроса пользователя.
    """
    mock_send_msg.return_value = "Улучшенный вопрос про освещение в ресторане"
    
    # Очень длинный вопрос (> 500 символов)
    long_question = "Какие проблемы с освещением? " * 50  # ~1500 символов
    
    result = enhance_question_for_index(
        original_question=long_question,
        selected_index="Dizayn",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )
    
    # Проверяем что функция не упала
    assert result == "Улучшенный вопрос про освещение в ресторане"
    
    # Проверяем что в промпт передан обрезанный вопрос
    call_args = mock_send_msg.call_args
    messages = call_args[1]['messages']
    prompt = messages[0]['content']
    
    # Проверяем что исходный вопрос был обрезан до 500 символов в промпте
    assert len(long_question) > 500  # Исходный вопрос длинный
    # В промпте не должно быть полного длинного вопроса
    assert prompt.count("Какие проблемы с освещением? ") < 50




def test_enhance_question_invalid_index_mapping_type(sample_report_descriptions):
    """
    Тест обработки некорректного типа в INDEX_MAPPING.
    """
    from src.index_selector import INDEX_MAPPING
    
    # Сохраняем оригинальное значение
    original_mapping = INDEX_MAPPING.copy()
    
    try:
        # Подменяем на некорректный тип
        INDEX_MAPPING["Dizayn"] = "не список, а строка"  # Некорректно!
        
        result = enhance_question_for_index(
            original_question="тестовый вопрос",
            selected_index="Dizayn",
            report_descriptions=sample_report_descriptions,
            api_key="test_key"
        )
        
        # Должен вернуть original_question при некорректном INDEX_MAPPING
        assert result == "тестовый вопрос"
        
    finally:
        # Восстанавливаем оригинальное значение
        INDEX_MAPPING.update(original_mapping)


# === ТЕСТЫ ДЛИНЫ ОТВЕТА ===

@patch('src.question_enhancer.send_msg_to_model')
def test_enhanced_question_length_validation(
    mock_send_msg,
    sample_report_descriptions,
    sample_enhanced_response
):
    """
    Тест проверки длины улучшенного вопроса.

    Ожидаемая длина: 150-300 символов (оптимально для embedding).
    Допустимая длина: 20-500 символов.
    """
    mock_send_msg.return_value = sample_enhanced_response

    result = enhance_question_for_index(
        original_question="тест",
        selected_index="Otchety_po_dizaynu",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Проверить что длина в допустимых пределах
    assert 20 <= len(result) <= 500
    # Проверить что результат это sample_enhanced_response
    assert result == sample_enhanced_response


@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_different_indices(mock_send_msg, sample_report_descriptions):
    """
    Тест улучшения вопроса для различных индексов.

    Проверяет что промпт содержит описания ТОЛЬКО из выбранного индекса.
    """
    mock_send_msg.return_value = "Улучшенный вопрос для тестирования"

    # Тест для "Intervyu"
    enhance_question_for_index(
        original_question="тест",
        selected_index="Intervyu",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Проверить что промпт содержит описания из "Intervyu"
    call_args = mock_send_msg.call_args
    prompt = call_args.kwargs['messages'][0]['content']

    assert "Intervyu" in prompt
    assert "Общие_факторы" in prompt
    assert "Отчет_о_связках" in prompt

    # НЕ должен содержать описания из других индексов
    assert "Дизайн и архитектура" not in prompt  # Из Otchety_po_dizaynu

    # Сбросить mock
    mock_send_msg.reset_mock()

    # Тест для "Itogovye_otchety"
    enhance_question_for_index(
        original_question="тест",
        selected_index="Itogovye_otchety",
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    call_args = mock_send_msg.call_args
    prompt = call_args.kwargs['messages'][0]['content']

    assert "Itogovye_otchety" in prompt
    assert "Краткое резюме" in prompt
    assert "Заполняемость" in prompt

    # НЕ должен содержать описания из других индексов
    assert "Общие_факторы" not in prompt  # Из Intervyu


# === ИНТЕГРАЦИОННЫЙ ТЕСТ ===

@patch('src.question_enhancer.send_msg_to_model')
def test_enhance_question_integration_flow(
    mock_send_msg,
    sample_report_descriptions,
    sample_enhanced_response
):
    """
    Интеграционный тест полного flow улучшения вопроса.

    Проверяет:
    1. Корректная фильтрация описаний по индексу
    2. Правильное форматирование промпта
    3. Вызов API с правильными параметрами
    4. Post-processing результата (удаление кавычек, валидация длины)
    """
    mock_send_msg.return_value = f'"{sample_enhanced_response}"'  # В кавычках

    original = "Какие проблемы с освещением в ресторане?"
    index = "Otchety_po_dizaynu"

    result = enhance_question_for_index(
        original_question=original,
        selected_index=index,
        report_descriptions=sample_report_descriptions,
        api_key="test_key"
    )

    # Проверки результата
    assert result == sample_enhanced_response  # Кавычки удалены
    assert 20 <= len(result) <= 500  # Длина корректна
    assert "освещ" in result.lower()  # Сохранен смысл вопроса

    # Проверки вызова API
    assert mock_send_msg.call_count == 1
    call_kwargs = mock_send_msg.call_args.kwargs

    # Параметры API
    assert call_kwargs['model'] == "claude-haiku-4-5-20250929"
    assert call_kwargs['max_tokens'] == 500
    assert call_kwargs['api_key'] == "test_key"

    # Проверка промпта
    prompt = call_kwargs['messages'][0]['content']
    assert original in prompt
    assert index in prompt

    # Описания ТОЛЬКО из Otchety_po_dizaynu
    for report_name in INDEX_MAPPING[index]:
        if report_name in sample_report_descriptions:
            assert report_name in prompt

    # НЕ содержит описания из других индексов
    assert "Общие_факторы" not in prompt  # Из Intervyu
    assert "Обследование" not in prompt  # Из Iskhodniki_obsledovanie


if __name__ == "__main__":
    """
    Запуск тестов.

    Команда:
        pytest tests/test_question_enhancer.py -v
    """
    pytest.main([__file__, "-v", "-s"])
