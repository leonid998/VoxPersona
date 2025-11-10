"""
Модуль автоматического улучшения вопросов пользователя.

Использует описание БД (descry.md) для обогащения вопросов терминологией
и повышения точности поиска. Работает через Claude API для семантического
анализа и перестроения вопросов.

Основной алгоритм:
1. Загрузка описания БД из файла descry.md
2. Формирование промпта с вопросом пользователя и описанием БД
3. Отправка промпта в Claude для улучшения вопроса
4. Возврат улучшенного вопроса или fallback к исходному при ошибках

Модуль разработан для легкой интеграции в существующую логику бота.
"""

import os
import logging
from typing import Dict
from analysis import send_msg_to_model

# Настройка логгера для диагностики работы модуля
logger = logging.getLogger(__name__)

# Константа: путь к файлу с описанием БД (индексы)
DESCRY_PATH = "Description/descry.md"


def load_descry() -> str:
    """
    Загружает файл с описанием структуры БД (индексы и содержание).

    Файл descry.md содержит описание того, какая информация находится в БД,
    что помогает Claude понимать доступную терминологию для улучшения вопросов.

    Returns:
        str: Содержимое файла descry.md. Пустая строка если файл не существует
             или произошла ошибка чтения.

    Notes:
        - Путь к файлу задается константой DESCRY_PATH
        - Файл читается с кодировкой UTF-8
        - Отсутствие файла не считается ошибкой (возвращается пустая строка)

    Examples:
        >>> content = load_descry()
        >>> if content:
        ...     print(f"Загружено {len(content)} символов описания БД")
    """
    # Проверка существования файла перед чтением
    # Это безопасный подход: если файл не готов, просто вернем пустую строку
    if not os.path.exists(DESCRY_PATH):
        return ""

    try:
        # Читаем файл с явным указанием кодировки UTF-8
        # Это гарантирует корректное чтение русских символов
        with open(DESCRY_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        # При любой ошибке чтения (права доступа, кодировка и т.д.)
        # возвращаем пустую строку для безопасного fallback
        return ""


# Константа: путь к файлу с промптом для улучшения вопросов
QUERY_EXPANSION_PROMPT_PATH = "Description/queru_exp.txt"


def load_query_expansion_prompt() -> str:
    """
    Загружает шаблон промпта для улучшения вопросов пользователя.

    Файл queru_exp.txt содержит инструкции для Claude по улучшению вопросов
    с использованием терминологии из описания БД.

    Returns:
        str: Содержимое файла queru_exp.txt (шаблон промпта с плейсхолдерами).

    Raises:
        FileNotFoundError: Если файл не существует (критическая ошибка конфигурации).
        IOError: Если произошла ошибка чтения файла.

    Notes:
        - Путь к файлу задается константой QUERY_EXPANSION_PROMPT_PATH
        - Файл читается с кодировкой UTF-8
        - Отсутствие файла считается критической ошибкой
        - Промпт содержит плейсхолдеры {question} и {descry_content}

    Examples:
        >>> template = load_query_expansion_prompt()
        >>> prompt = template.format(question="Проблемы с вентиляцией", descry_content="...")
    """
    # Проверка существования файла
    if not os.path.exists(QUERY_EXPANSION_PROMPT_PATH):
        error_msg = f"[Query Expansion] Prompt template file not found: {QUERY_EXPANSION_PROMPT_PATH}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        # Читаем файл с явным указанием кодировки UTF-8
        with open(QUERY_EXPANSION_PROMPT_PATH, 'r', encoding='utf-8') as f:
            template = f.read()

        logger.info(f"[Query Expansion] Loaded prompt template from {QUERY_EXPANSION_PROMPT_PATH} ({len(template)} chars)")
        return template
    except Exception as e:
        error_msg = f"[Query Expansion] Error reading prompt template: {e}"
        logger.error(error_msg)
        raise IOError(error_msg) from e


def build_expansion_prompt(question: str, descry_content: str) -> str:
    """
    Формирует промпт для Claude согласно алгоритму улучшения вопросов.

    FIX (2025-11-10): Промпт загружается из файла Description/queru_exp.txt
    ИЗМЕНЕНИЕ: Вместо хардкод f-string используется шаблон из файла
    ЗАЧЕМ: Упрощение редактирования промпта без изменения кода
    ПРЕИМУЩЕСТВА:
    - A/B тестирование разных версий промпта
    - Редактирование без пересборки Docker образа (при hot-reload)
    - Версионирование промпта в git (отдельный файл)

    Промпт загружается из файла queru_exp.txt и содержит плейсхолдеры:
    - {question} - подставляется исходный вопрос пользователя
    - {descry_content} - подставляется содержимое файла descry.md

    Args:
        question: Исходный вопрос пользователя
        descry_content: Содержимое файла descry.md с описанием БД

    Returns:
        str: Полный промпт для отправки в Claude API

    Raises:
        FileNotFoundError: Если файл queru_exp.txt не найден
        IOError: Если произошла ошибка чтения файла
        ValueError: Если шаблон не содержит необходимых плейсхолдеров

    Notes:
        - Использует load_query_expansion_prompt() для загрузки шаблона
        - Подстановка значений через .format() (не f-string)
        - Промпт инструктирует Claude вернуть ТОЛЬКО улучшенный вопрос
        - Не допускается добавление информации, отсутствующей в descry.md

    Связь: TASKS/00007_20251105_YEIJEG/010_search_imp/03_promt_out/inspection.md

    Examples:
        >>> prompt = build_expansion_prompt(
        ...     "Какие проблемы с вентиляцией?",
        ...     "Индексы: вентиляция, ПВУ, воздуховоды..."
        ... )
        >>> assert "Алгоритм улучшения" in prompt
    """
    # Загружаем шаблон промпта из файла
    # ВАЖНО: При отсутствии файла будет выброшено исключение FileNotFoundError
    # ЗАЧЕМ: Отсутствие промпта = критическая ошибка конфигурации, должна быть явной
    prompt_template = load_query_expansion_prompt()

    # Подставляем значения в шаблон
    # Используем .format() вместо f-string для runtime подстановки
    # ЗАЧЕМ: f-string выполняется при определении функции, а нам нужна подстановка во время вызова
    try:
        return prompt_template.format(
            question=question,
            descry_content=descry_content
        )
    except KeyError as e:
        # Защита от некорректного шаблона (отсутствует плейсхолдер)
        # ЗАЧЕМ: Если пользователь удалит {question} или {descry_content} из файла, код упадет явно
        error_msg = f"[Query Expansion] Invalid prompt template: missing placeholder {e}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e


def expand_query(question: str, max_retries: int = 3) -> Dict[str, str]:
    """
    Улучшает вопрос пользователя через Claude API с использованием descry.md.

    Главная функция модуля. Координирует весь процесс улучшения вопроса:
    1. Валидация входного вопроса
    2. Загрузка описания БД
    3. Формирование промпта
    4. Отправка в Claude
    5. Обработка и валидация ответа

    Функция безопасна: при любых ошибках возвращает исходный вопрос.

    Args:
        question: Исходный вопрос пользователя
        max_retries: Максимум попыток улучшения (защита от зацикливания).
                     Параметр зарезервирован для будущего использования.

    Returns:
        Dict[str, str]: Словарь с ключами:
            - "original": исходный вопрос пользователя
            - "expanded": улучшенный вопрос (или исходный при ошибках)
            - "used_descry": True если использовался descry.md, иначе False
            - "error": None если успех, иначе текст ошибки

    Notes:
        - Минимальная длина вопроса: 3 символа
        - При отсутствии descry.md возвращается исходный вопрос
        - При ошибке API также возвращается исходный вопрос (fallback)
        - Используется существующая функция send_msg_to_model из analysis.py

    Examples:
        >>> result = expand_query("проблемы с вентиляцией")
        >>> print(result["expanded"])
        "Какие неисправности обнаружены в системах вентиляции (ПВУ)?"
        >>> print(result["used_descry"])
        True
        >>> print(result["error"])
        None
    """
    # Шаг 1: Валидация входного вопроса
    # Проверяем что вопрос не пустой и имеет минимальную длину
    if not question or len(question.strip()) < 3:
        logger.warning(f"[Query Expansion] Empty or too short question: {repr(question)}")
        return {
            "original": question,
            "expanded": question,
            "used_descry": False,
            "error": "Вопрос слишком короткий"
        }

    # Шаг 2: Загрузка описания БД
    # Используем load_descry() для получения содержимого descry.md
    descry_content = load_descry()

    # Шаг 3: Проверка доступности descry.md
    # Если файл не найден или пуст - возвращаем исходный вопрос
    # Это нормальная ситуация: пользователь еще не подготовил файл
    if not descry_content:
        return {
            "original": question,
            "expanded": question,
            "used_descry": False,
            "error": "descry.md не найден или пуст"
        }

    # Шаг 4: Проверка размера descry.md
    # Если файл очень большой (>50000 символов ≈ 12500 токенов)
    # это может вызвать проблемы с контекстом Claude
    if len(descry_content) > 50000:
        # TODO: Реализовать chunking или summarization для больших файлов
        # Возможные решения:
        # 1. Разбить descry.md на части и делать несколько запросов
        # 2. Использовать summarization для сжатия описания
        # 3. Индексировать descry.md и искать только релевантные секции
        pass

    # Шаг 5: Попытка улучшения через Claude API
    try:
        # Формируем промпт с вопросом и описанием БД
        prompt = build_expansion_prompt(question, descry_content)

        # Логирование для диагностики промптов
        logger.info(f"[Query Expansion] User question: {question}")
        logger.info(f"[Query Expansion] Prompt sent to Claude (first 500 chars): {prompt[:500]}...")

        # Отправляем в Claude через существующую функцию из analysis.py
        # ВАЖНО: Используется актуальная модель Claude Sonnet 4.5 (исправлено: ранее была несуществующая модель claude-sonnet-4-20250514)
        # Это гарантирует корректную работу API без ошибок 400
        # Модель указывается явно для консистентности с RAG системой
        expanded = send_msg_to_model(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,  # Улучшенный вопрос редко превышает 200 токенов
            model="claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5 (актуальная версия из CLAUDE.md)
        )

        # Логирование полного ответа Claude
        logger.info(f"[Query Expansion] Claude response: {expanded}")

        # Шаг 6: Очистка и валидация ответа
        # Удаляем лишние пробелы и переносы строк
        expanded_clean = expanded.strip()

        # Логирование очищенного ответа
        logger.info(f"[Query Expansion] Cleaned response: {expanded_clean}")

        # Проверяем что Claude вернул корректный ответ
        # Если ответ пустой или идентичен исходному - это проблема
        if not expanded_clean or expanded_clean == question:
            logger.warning(f"[Query Expansion] Claude returned empty or unchanged answer")
            return {
                "original": question,
                "expanded": question,
                "used_descry": True,  # descry использовался, но не помог
                "error": "Claude вернул пустой ответ или не улучшил вопрос"
            }

        # Шаг 7: Успешное улучшение
        # Возвращаем улучшенный вопрос без ошибок
        logger.info(f"[Query Expansion] Successfully expanded question")
        return {
            "original": question,
            "expanded": expanded_clean,
            "used_descry": True,
            "error": None
        }

    except Exception as e:
        # Шаг 8: Обработка ошибок (fallback)
        # При любой ошибке API или обработки - возвращаем исходный вопрос
        # Это гарантирует что бот продолжит работать даже при проблемах
        logger.error(f"[Query Expansion] API Error: {str(e)}", exc_info=True)
        return {
            "original": question,
            "expanded": question,
            "used_descry": False,
            "error": f"Ошибка API: {str(e)}"
        }
