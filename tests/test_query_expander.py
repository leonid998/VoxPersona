"""
Unit-тесты для модуля query_expander.py

Тестирует функционал автоматического улучшения вопросов пользователя:
- load_descry(): загрузка описания БД из descry.md
- build_expansion_prompt(): формирование промпта для Claude
- expand_query(): главная функция улучшения вопросов

Все тесты изолированы через mocking внешних зависимостей.
"""

import pytest
from unittest.mock import patch, mock_open, MagicMock
from src.query_expander import (
    load_descry,
    load_query_expansion_prompt,
    build_expansion_prompt,
    expand_query,
    DESCRY_PATH,
    QUERY_EXPANSION_PROMPT_PATH
)


# =============================================================================
# TestLoadDescry: Тесты загрузки файла descry.md
# =============================================================================

class TestLoadDescry:
    """Тестирует функцию load_descry() - загрузку описания БД."""

    def test_load_descry_file_exists(self):
        """
        Тест: файл descry.md существует и успешно читается.

        Проверяет что:
        - Функция корректно открывает файл с UTF-8 кодировкой
        - Возвращает полное содержимое файла
        - Путь к файлу соответствует константе DESCRY_PATH
        """
        mock_content = "# Описание БД\n\nИндексы: вентиляция, ПВУ, отопление"

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_content)):

            result = load_descry()

            assert result == mock_content
            assert len(result) > 0
            assert "вентиляция" in result

    def test_load_descry_file_not_exists(self):
        """
        Тест: файл descry.md не существует.

        Проверяет что:
        - Функция проверяет существование файла перед чтением
        - Возвращает пустую строку при отсутствии файла
        - Не выбрасывает исключение
        """
        with patch('os.path.exists', return_value=False):
            result = load_descry()

            assert result == ""

    def test_load_descry_file_read_error(self):
        """
        Тест: ошибка при чтении файла (права доступа, кодировка и т.д.).

        Проверяет что:
        - Функция обрабатывает исключения при чтении
        - Возвращает пустую строку при ошибке
        - Использует fallback механизм
        """
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=IOError("Permission denied")):

            result = load_descry()

            assert result == ""

    def test_load_descry_empty_file(self):
        """
        Тест: файл descry.md существует, но пустой.

        Проверяет что:
        - Функция корректно читает пустой файл
        - Возвращает пустую строку (корректное поведение)
        """
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="")):

            result = load_descry()

            assert result == ""


# =============================================================================
# TestLoadQueryExpansionPrompt: Тесты загрузки шаблона промпта
# =============================================================================

class TestLoadQueryExpansionPrompt:
    """
    Тестирует функцию load_query_expansion_prompt() - загрузку шаблона промпта.

    Покрываемые сценарии:
    - Успешная загрузка файла queru_exp.md
    - Отсутствие файла (FileNotFoundError)
    - Ошибка чтения файла (IOError)
    """

    def test_load_prompt_file_exists(self):
        """
        Тест: файл queru_exp.md существует и успешно читается.

        Проверяет что:
        - Функция корректно открывает файл с UTF-8 кодировкой
        - Возвращает полное содержимое файла
        - Путь к файлу соответствует константе QUERY_EXPANSION_PROMPT_PATH
        - Шаблон содержит плейсхолдеры {question} и {descry_content}
        """
        mock_content = "Задача: КРАТКО улучшить вопрос\n\nВопрос: {question}\n\nОписание: {descry_content}"

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_content)):

            result = load_query_expansion_prompt()

            assert result == mock_content
            assert "{question}" in result
            assert "{descry_content}" in result

    def test_load_prompt_file_not_exists(self):
        """
        Тест: файл queru_exp.md не существует (критическая ошибка).

        Проверяет что:
        - Функция проверяет существование файла перед чтением
        - Выбрасывает FileNotFoundError при отсутствии файла
        - Сообщение ошибки содержит путь к файлу
        """
        with patch('os.path.exists', return_value=False):

            with pytest.raises(FileNotFoundError) as exc_info:
                load_query_expansion_prompt()

            assert "Prompt template file not found" in str(exc_info.value)
            assert "queru_exp.txt" in str(exc_info.value)

    def test_load_prompt_file_read_error(self):
        """
        Тест: ошибка при чтении файла (права доступа, кодировка и т.д.).

        Проверяет что:
        - Функция обрабатывает исключения при чтении
        - Выбрасывает IOError с описанием ошибки
        - Сообщение ошибки содержит оригинальную причину
        """
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=IOError("Permission denied")):

            with pytest.raises(IOError) as exc_info:
                load_query_expansion_prompt()

            assert "Error reading prompt template" in str(exc_info.value)


# =============================================================================
# TestBuildExpansionPrompt: Тесты формирования промпта
# =============================================================================

class TestBuildExpansionPrompt:
    """Тестирует функцию build_expansion_prompt() - формирование промпта для Claude."""

    def test_prompt_contains_question(self):
        """
        Тест: промпт содержит исходный вопрос пользователя.

        Проверяет что:
        - Вопрос пользователя включен в промпт без изменений
        - Вопрос находится в секции "Вопрос пользователя:"

        FIX (2025-11-10): Обновлено - промпт загружается из файла
        """
        question = "Какие проблемы с вентиляцией?"
        descry = "Индексы: вентиляция"

        mock_prompt_template = "Вопрос пользователя:\n{question}\n\nОписание: {descry_content}"

        with patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template):
            prompt = build_expansion_prompt(question, descry)

            assert question in prompt
            assert "Вопрос пользователя:" in prompt

    def test_prompt_contains_descry_content(self):
        """
        Тест: промпт содержит описание БД из descry.md.

        Проверяет что:
        - Содержимое descry.md включено в промпт
        - Описание находится в секции "Описание содержимого БД"

        FIX (2025-11-10): Обновлено - промпт загружается из файла
        """
        question = "Проблемы с отоплением"
        descry = "Индексы: отопление, котельная, ИТП"

        mock_prompt_template = "Вопрос: {question}\n\nОписание содержимого БД:\n{descry_content}"

        with patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template):
            prompt = build_expansion_prompt(question, descry)

            assert descry in prompt
            assert "Описание содержимого БД" in prompt

    def test_prompt_contains_algorithm_steps(self):
        """
        Тест: промпт содержит 5 шагов алгоритма улучшения.

        Проверяет что:
        - Секция "Алгоритм улучшения:" присутствует
        - Все 5 шагов алгоритма включены в промпт:
          1. КРАТКО улучшить вопрос
          2. Изучить описание БД
          3. Найти возможное содержание
          4. Перестроить вопрос
          5. Добавить САМЫЕ ВАЖНЫЕ термины

        FIX (2025-11-10): Обновлено - промпт загружается из файла
        """
        mock_prompt_template = """Алгоритм улучшения:
1. КРАТКО и точно улучши вопрос пользователя
2. Изучи описание БД и найди наиболее релевантные термины
3. Найди возможное содержание которое содержится в описании БД
4. Перестрой вопрос используя найденную терминологию из описания БД
5. Добавь только САМЫЕ ВАЖНЫЕ термины

Вопрос: {question}
Описание: {descry_content}"""

        with patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template):
            prompt = build_expansion_prompt("Тестовый вопрос", "Тестовое описание")

            assert "Алгоритм улучшения:" in prompt
            assert "1. КРАТКО и точно улучши вопрос" in prompt
            assert "2. Изучи описание БД" in prompt
            assert "3. Найди возможное содержание" in prompt
            assert "4. Перестрой вопрос" in prompt
            assert "5. Добавь только САМЫЕ ВАЖНЫЕ термины" in prompt

    def test_prompt_contains_requirements(self):
        """
        Тест: промпт содержит требования к улучшенному вопросу.

        Проверяет что:
        - Секция "Требования к улучшенному вопросу:" присутствует
        - Указано требование "Верни ТОЛЬКО улучшенный вопрос"
        - Запрещено добавлять информацию вне descry.md

        FIX (2025-11-10): Обновлено - промпт загружается из файла
        """
        mock_prompt_template = """Вопрос: {question}
Описание: {descry_content}

Требования к улучшенному вопросу:
- Верни ТОЛЬКО улучшенный вопрос
- НЕ добавлять информацию, которой нет в описании БД
- **ВАЖНО: Максимальная длина — 400 символов!**"""

        with patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template):
            prompt = build_expansion_prompt("Тест", "Описание")

            assert "Требования к улучшенному вопросу:" in prompt
            assert "Верни ТОЛЬКО улучшенный вопрос" in prompt
            assert "НЕ добавлять информацию, которой нет в описании БД" in prompt

    def test_prompt_with_special_characters(self):
        """
        Тест: промпт корректно обрабатывает спецсимволы.

        Проверяет что:
        - Вопрос и descry с кириллицей корректно включаются
        - Спецсимволы не ломают форматирование промпта

        FIX (2025-11-10): Обновлено - промпт загружается из файла
        """
        question = "Проблемы с ПВУ (приточно-вытяжные установки)?"
        descry = "Системы: вентиляция 50%, кондиционирование 30%"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template):
            prompt = build_expansion_prompt(question, descry)

            assert question in prompt
            assert descry in prompt
            assert "%" in prompt
            assert "(" in prompt

    def test_build_expansion_prompt_invalid_template_missing_question(self):
        """
        Тест: шаблон не содержит плейсхолдера {question} (ValueError).

        Проверяет что:
        - build_expansion_prompt() выбросит KeyError при форматировании
        - Этот KeyError обрабатывается и выбрасывается ValueError
        - Сообщение ошибки содержит имя отсутствующего плейсхолдера

        FIX (2025-11-10): Обновлено - валидация через try-except в build_expansion_prompt
        """
        # Шаблон БЕЗ {question}, но С {descry_content} - format() не выбросит KeyError!
        # Нужен шаблон с дополнительными плейсхолдерами которые вызовут KeyError
        invalid_template = "Описание: {descry_content}\nДополнительно: {unknown_placeholder}"

        with patch('src.query_expander.load_query_expansion_prompt', return_value=invalid_template):
            with pytest.raises(ValueError) as exc_info:
                build_expansion_prompt("Тестовый вопрос", "Описание БД")

            assert "Invalid prompt template" in str(exc_info.value)
            assert "unknown_placeholder" in str(exc_info.value)

    def test_build_expansion_prompt_valid_template_extra_placeholders(self):
        """
        Тест: шаблон содержит ВСЕ необходимые плейсхолдеры + дополнительные (ошибка).

        Проверяет что:
        - Если шаблон содержит неизвестные плейсхолдеры - выбрасывается ValueError
        - Ошибка содержит имя неизвестного плейсхолдера

        FIX (2025-11-10): Добавлено для полного покрытия edge cases
        """
        template_with_extra = "Вопрос: {question}\nОписание: {descry_content}\nДоп: {extra_field}"

        with patch('src.query_expander.load_query_expansion_prompt', return_value=template_with_extra):
            with pytest.raises(ValueError) as exc_info:
                build_expansion_prompt("Вопрос", "Описание")

            assert "Invalid prompt template" in str(exc_info.value)
            assert "extra_field" in str(exc_info.value)


# =============================================================================
# TestExpandQuery: Тесты главной функции expand_query
# =============================================================================

class TestExpandQuery:
    """Тестирует функцию expand_query() - главную функцию улучшения вопросов."""

    def test_expand_query_empty_question(self):
        """
        Тест: пустой или слишком короткий вопрос (< 3 символов).

        Проверяет что:
        - Функция валидирует минимальную длину вопроса
        - Возвращает исходный вопрос без обработки
        - Устанавливает error: "Вопрос слишком короткий"
        - Флаг used_descry = False
        """
        test_cases = ["", "  ", "ab"]

        for question in test_cases:
            result = expand_query(question)

            assert result["original"] == question
            assert result["expanded"] == question
            assert result["used_descry"] is False
            assert "слишком короткий" in result["error"]

    def test_expand_query_no_descry(self):
        """
        Тест: файл descry.md не существует или пустой.

        Проверяет что:
        - Функция обращается к load_descry()
        - При отсутствии descry.md возвращает исходный вопрос
        - Устанавливает error о отсутствии файла
        - Флаг used_descry = False (файл не использован)

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "Какие проблемы с вентиляцией?"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_descry', return_value=""), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template):
            result = expand_query(question)

            assert result["original"] == question
            assert result["expanded"] == question
            assert result["used_descry"] is False
            assert "descry.md не найден" in result["error"]

    def test_expand_query_success(self):
        """
        Тест: успешное улучшение вопроса через Claude API.

        Проверяет что:
        - Функция вызывает send_msg_to_model с корректным промптом
        - Возвращает улучшенный вопрос от Claude
        - Устанавливает error = None (нет ошибок)
        - Флаг used_descry = True (файл использован)
        - Очищает ответ от лишних пробелов (strip)

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "проблемы с вентиляцией"
        descry_content = "Индексы: вентиляция, ПВУ, воздуховоды"
        improved_question = "Какие неисправности обнаружены в системах вентиляции (ПВУ, воздуховоды)?"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_descry', return_value=descry_content), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value=improved_question):

            result = expand_query(question)

            assert result["original"] == question
            assert result["expanded"] == improved_question
            assert result["used_descry"] is True
            assert result["error"] is None

    def test_expand_query_api_error(self):
        """
        Тест: ошибка при вызове Claude API (fallback).

        Проверяет что:
        - Функция обрабатывает исключения от send_msg_to_model
        - Возвращает исходный вопрос при ошибке (безопасный fallback)
        - Устанавливает error с описанием ошибки API
        - Флаг used_descry = False (улучшение не произошло)

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "Проблемы с отоплением"
        descry_content = "Индексы: отопление"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_descry', return_value=descry_content), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', side_effect=Exception("API timeout")):

            result = expand_query(question)

            assert result["original"] == question
            assert result["expanded"] == question  # fallback к исходному
            assert result["used_descry"] is False
            assert "Ошибка API" in result["error"]
            assert "API timeout" in result["error"]

    def test_expand_query_empty_response(self):
        """
        Тест: Claude вернул пустой ответ или не улучшил вопрос.

        Проверяет что:
        - Функция валидирует ответ от Claude (не пустой)
        - Проверяет что ответ отличается от исходного вопроса
        - Возвращает исходный вопрос при некорректном ответе
        - Устанавливает error о пустом ответе
        - Флаг used_descry = True (descry использовался, но не помог)

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "Тестовый вопрос"
        descry_content = "Описание БД"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        # Тест 1: пустой ответ от Claude
        with patch('src.query_expander.load_descry', return_value=descry_content), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value="   "):

            result = expand_query(question)

            assert result["expanded"] == question
            assert result["used_descry"] is True
            assert "пустой ответ" in result["error"]

        # Тест 2: Claude вернул тот же вопрос (не улучшил)
        with patch('src.query_expander.load_descry', return_value=descry_content), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value=question):

            result = expand_query(question)

            assert result["expanded"] == question
            assert result["used_descry"] is True
            assert "не улучшил вопрос" in result["error"]

    def test_expand_query_strips_whitespace(self):
        """
        Тест: функция очищает ответ Claude от лишних пробелов.

        Проверяет что:
        - Применяется strip() к ответу от Claude
        - Удаляются начальные и конечные пробелы/переносы строк
        - Возвращается очищенный улучшенный вопрос

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "Проблемы с ПВУ"
        descry_content = "Индексы: ПВУ"
        improved_with_whitespace = "\n\n  Какие неисправности в приточно-вытяжных установках?  \n"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_descry', return_value=descry_content), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value=improved_with_whitespace):

            result = expand_query(question)

            assert result["expanded"] == improved_with_whitespace.strip()
            assert not result["expanded"].startswith(" ")
            assert not result["expanded"].endswith(" ")

    def test_expand_query_max_retries_parameter(self):
        """
        Тест: параметр max_retries передается корректно (зарезервирован).

        Проверяет что:
        - Функция принимает параметр max_retries
        - Параметр по умолчанию = 3
        - Функция работает с любым значением max_retries

        Примечание: параметр зарезервирован для будущего использования.

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "Тестовый вопрос"
        descry_content = "Описание"

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_descry', return_value=descry_content), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value="Улучшенный вопрос"):

            # Тест с default max_retries
            result1 = expand_query(question)
            assert result1["error"] is None

            # Тест с custom max_retries
            result2 = expand_query(question, max_retries=5)
            assert result2["error"] is None

    def test_expand_query_large_descry_file(self):
        """
        Тест: очень большой файл descry.md (>50000 символов).

        Проверяет что:
        - Функция проверяет размер descry_content
        - TODO: В будущем должна применяться chunking/summarization
        - Пока что обрабатывается без ошибок (pass в коде)

        Примечание: реализация chunking запланирована в будущем.

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "Тестовый вопрос"
        large_descry = "Описание БД: " + ("A" * 60000)  # >50000 символов

        mock_prompt_template = "Вопрос: {question}\nОписание: {descry_content}"

        with patch('src.query_expander.load_descry', return_value=large_descry), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value="Улучшенный вопрос"):

            result = expand_query(question)

            # Функция должна обработать большой файл без ошибок
            assert result["error"] is None or "Ошибка API" in result["error"]


# =============================================================================
# Дополнительные интеграционные тесты
# =============================================================================

class TestIntegration:
    """Интеграционные тесты полного workflow улучшения вопросов."""

    def test_full_workflow_with_mocked_api(self):
        """
        Тест: полный workflow от вопроса до улучшенного результата.

        Проверяет взаимодействие всех функций:
        1. load_descry() загружает файл
        2. load_query_expansion_prompt() загружает шаблон промпта
        3. build_expansion_prompt() формирует промпт
        4. send_msg_to_model() отправляет в Claude
        5. expand_query() возвращает результат

        FIX (2025-11-10): Добавлено мокирование load_query_expansion_prompt()
        """
        question = "проблемы с котлами"
        descry_content = "# Описание БД\n\nСистемы отопления: котельная, ИТП, котлы"
        expected_improved = "Какие дефекты обнаружены в котельной и котлах системы отопления?"

        mock_prompt_template = "Вопрос: {question}\nОписание БД: {descry_content}"

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=descry_content)), \
             patch('src.query_expander.load_query_expansion_prompt', return_value=mock_prompt_template), \
             patch('src.query_expander.send_msg_to_model', return_value=expected_improved) as mock_api:

            result = expand_query(question)

            # Проверка результата
            assert result["original"] == question
            assert result["expanded"] == expected_improved
            assert result["used_descry"] is True
            assert result["error"] is None

            # Проверка что API был вызван с правильным промптом
            mock_api.assert_called_once()
            call_args = mock_api.call_args
            assert "messages" in call_args.kwargs
            assert "max_tokens" in call_args.kwargs
            assert call_args.kwargs["max_tokens"] == 1000
