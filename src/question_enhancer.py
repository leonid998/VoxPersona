"""
Модуль улучшения вопроса пользователя для выбранного индекса.

Третий компонент Router Agent, который:
1. Получает выбранный индекс от index_selector
2. Фильтрует описания отчетов - оставляет только отчеты выбранного индекса
3. Отправляет промпт в Claude Haiku 4.5 для улучшения вопроса
4. Возвращает улучшенный вопрос оптимизированный для семантического поиска

Архитектура:
- Импортирует INDEX_MAPPING из index_selector для фильтрации отчетов
- Использует send_msg_to_model из analysis.py для синхронного API вызова
- Промпт адаптирован из Description/queru_exp.txt
- Fallback: возвращает original_question при ошибках

Пример использования:
    from question_enhancer import enhance_question_for_index
    from relevance_evaluator import load_report_descriptions

    # Загрузить описания отчетов
    descriptions = load_report_descriptions()

    # Улучшить вопрос для выбранного индекса
    enhanced = enhance_question_for_index(
        original_question="Какие проблемы с освещением в ресторане?",
        selected_index="Otchety_po_dizaynu",
        report_descriptions=descriptions
    )
    print(enhanced)
"""

import logging
import time
from typing import Dict

from config import ANTHROPIC_API_KEY
from index_selector import INDEX_MAPPING
from constants import CLAUDE_ERROR_MESSAGE
from analysis import send_msg_to_model

# Константы
HAIKU_MODEL = "claude-3-5-haiku-20241022"  # Модель Haiku 3.5 для улучшения вопроса
MAX_TOKENS = 500  # Достаточно для улучшенного вопроса (150-300 символов)
TEMPERATURE = 0.1  # Низкая температура для консистентности

logger = logging.getLogger(__name__)


def format_index_descriptions(
    selected_index: str,
    filtered_descriptions: Dict[str, str]
) -> str:
    """
    Форматирует описания отчетов выбранного индекса для промпта.

    Создает читаемый список описаний отчетов с нумерацией для включения в промпт.
    Каждое описание обрезается до 500 символов для экономии токенов.

    Args:
        selected_index: Название выбранного индекса (например, "Otchety_po_dizaynu")
        filtered_descriptions: Словарь {имя_отчета: содержимое} для отчетов индекса

    Returns:
        str: Форматированная строка с описаниями отчетов

    Example:
        >>> descriptions = {
        ...     "Дизайн и архитектура": "Анализ дизайна отеля...",
        ...     "Сильные стороны": "Сильные стороны дизайна..."
        ... }
        >>> result = format_index_descriptions("Otchety_po_dizaynu", descriptions)
        >>> "Дизайн и архитектура" in result
        True
    """
    if not filtered_descriptions:
        return f"Индекс '{selected_index}' (описания отчетов отсутствуют)"

    # Создать нумерованный список описаний
    formatted_lines = [f"Индекс '{selected_index}' содержит следующие типы отчетов:\n"]

    for i, (report_name, description) in enumerate(filtered_descriptions.items(), 1):
        # Обрезать длинные описания для экономии токенов
        # WHY: полные описания могут быть очень длинными (>2000 символов)
        # и не нужны для понимания контекста индекса
        truncated = description[:500] + "..." if len(description) > 500 else description
        formatted_lines.append(f"{i}. {report_name}:\n{truncated}\n")

    return "\n".join(formatted_lines)


def build_enhancement_prompt(
    original_question: str,
    selected_index: str,
    index_descriptions: str
) -> str:
    """
    Построить промпт для улучшения вопроса под выбранный индекс.

    Промпт адаптирован из Description/queru_exp.txt с модификациями:
    - Фокус на конкретном индексе (не вся БД)
    - Инструкция добавить термины из описаний отчетов индекса
    - Требование указать типы отчетов для изучения
    - Добавление контекста "Ответ для управляющего отелем"
    - Ограничение длины 150-300 символов для оптимального embedding

    Args:
        original_question: Исходный вопрос пользователя
        selected_index: Название выбранного индекса
        index_descriptions: Форматированные описания отчетов индекса

    Returns:
        str: Готовый промпт для отправки в Claude API

    Example:
        >>> prompt = build_enhancement_prompt(
        ...     "проблемы с освещением",
        ...     "Otchety_po_dizaynu",
        ...     "Индекс содержит: Дизайн..."
        ... )
        >>> "150-300 символов" in prompt
        True
    """
    # WHY: Промпт структурирован для получения краткого улучшенного вопроса
    # который оптимально работает с векторным поиском (утверждение вместо вопроса)
    prompt = f"""Задача: Улучшить вопрос пользователя для семантического поиска в индексе '{selected_index}'.

Вопрос пользователя:
{original_question}

Описания отчетов в индексе:
{index_descriptions}

Алгоритм улучшения:

1. Найди ключевые концепции в вопросе пользователя
2. Добавь соответствующие технические термины из описаний отчетов выше
3. Преобразуй вопрос в утверждение (НЕ вопрос) для векторного поиска
4. Укажи конкретные типы отчетов из индекса для изучения
5. Добавь контекст: "Ответ для управляющего отелем/рестораном"

Требования к улучшенному вопросу:

* Сохранить смысл исходного вопроса
* Преобразовать в утверждение (избегать вопросительных слов: что, как, почему)
* Использовать технические термины из описаний отчетов выше
* Указать типы отчетов для изучения
* НЕ добавлять инструкции для ответа (типа "дай рекомендации")
* НЕ задавать встречные вопросы
* **ВАЖНО: Длина улучшенного вопроса — 150-300 символов (оптимально для embedding)**

Верни ТОЛЬКО улучшенный вопрос (без пояснений, без вводных фраз, без кавычек).
"""

    return prompt


def enhance_question_for_index(
    original_question: str,
    selected_index: str,
    report_descriptions: Dict[str, str],
    api_key: str | None = None
) -> str:
    """
    Улучшить вопрос пользователя для поиска в выбранном индексе.

    ОСНОВНАЯ ФУНКЦИЯ МОДУЛЯ.

    Алгоритм:
    1. Валидация входных данных
    2. Импорт INDEX_MAPPING и фильтрация описаний отчетов для selected_index
    3. Форматирование описаний для промпта
    4. Построение промпта для Claude Haiku
    5. Вызов Claude API через send_msg_to_model
    6. Валидация и возврат улучшенного вопроса

    Args:
        original_question: Исходный вопрос пользователя
        selected_index: Название выбранного индекса (из INDEX_MAPPING)
        report_descriptions: Словарь {имя_отчета: содержимое} для ВСЕХ отчетов
        api_key: Anthropic API key (если None - использует ANTHROPIC_API_KEY из config)

    Returns:
        str: Улучшенный вопрос оптимизированный для семантического поиска
             При ошибке возвращает original_question (fallback)

    Raises:
        ValueError: Если original_question пустой или selected_index не в INDEX_MAPPING

    Performance:
        - Синхронный вызов API (не async)
        - Типичное время выполнения: 1-2 секунды
        - Retry логика встроена в send_msg_to_model

    Example:
        >>> from relevance_evaluator import load_report_descriptions
        >>> descriptions = load_report_descriptions()
        >>> enhanced = enhance_question_for_index(
        ...     original_question="Какие проблемы с освещением в ресторане?",
        ...     selected_index="Otchety_po_dizaynu",
        ...     report_descriptions=descriptions
        ... )
        >>> len(enhanced) > len("Какие проблемы с освещением в ресторане?")
        True
        >>> "проблемы" in enhanced.lower() or "освещ" in enhanced.lower()
        True
    """
    # === 1. Валидация входных данных ===

    if not original_question or not original_question.strip():
        logger.error("Получен пустой вопрос")
        raise ValueError("original_question не может быть пустым")


    # Валидация длины вопроса (защита от prompt injection)
    # WHY: Пользователь может передать очень длинный вопрос или подозрительный паттерн
    # Ограничиваем длину для безопасности и экономии токенов
    MAX_QUESTION_LENGTH = 500
    if len(original_question) > MAX_QUESTION_LENGTH:
        logger.warning(
            f"Вопрос пользователя слишком длинный ({len(original_question)} символов). "
            f"Обрезаем до {MAX_QUESTION_LENGTH}."
        )
        original_question = original_question[:MAX_QUESTION_LENGTH]

    if selected_index not in INDEX_MAPPING:
        logger.error(f"Неизвестный индекс: '{selected_index}'")
        raise ValueError(
            f"selected_index '{selected_index}' не найден в INDEX_MAPPING. "
            f"Доступные индексы: {list(INDEX_MAPPING.keys())}"
        )

    if not report_descriptions:
        logger.error("Получен пустой словарь описаний отчетов")
        raise ValueError("report_descriptions не может быть пустым")

    # Получить API key
    if api_key is None:
        api_key = ANTHROPIC_API_KEY

    if not api_key:
        logger.error("ANTHROPIC_API_KEY не установлен")
        raise ValueError(
            "ANTHROPIC_API_KEY не установлен. "
            "Проверьте файл .env или передайте api_key явно."
        )

    logger.info(
        f"Начинаем улучшение вопроса для индекса '{selected_index}': "
        f"'{original_question[:100]}...'"
    )

    # === 2. Фильтрация описаний отчетов для выбранного индекса ===

    # WHY: Нужно оставить только описания отчетов которые принадлежат selected_index
    # чтобы промпт был релевантен и не содержал информацию из других индексов
    report_names_in_index = INDEX_MAPPING[selected_index]

    # Проверка типа (defensive programming)
    # WHY: INDEX_MAPPING должен возвращать список строк, но может быть изменен некорректно
    # Проверяем тип чтобы избежать крашей в дальнейшей логике
    if not isinstance(report_names_in_index, (list, tuple)) or not report_names_in_index:
        logger.error(
            f"INDEX_MAPPING['{selected_index}'] содержит некорректные данные: "
            f"{type(report_names_in_index)}. Ожидался непустой список."
        )
        return original_question


    filtered_descriptions = {
        name: description
        for name, description in report_descriptions.items()
        if name in report_names_in_index
    }

    if not filtered_descriptions:
        logger.warning(
            f"Ни один отчет индекса '{selected_index}' не найден в report_descriptions. "
            f"Ожидались: {report_names_in_index}"
        )
        logger.warning("Возвращаем original_question без улучшения")
        return original_question

    logger.debug(
        f"Отфильтровано {len(filtered_descriptions)} описаний отчетов "
        f"для индекса '{selected_index}'"
    )

    # === 3. Форматирование описаний для промпта ===

    index_descriptions = format_index_descriptions(selected_index, filtered_descriptions)

    # === 4. Построение промпта ===

    prompt = build_enhancement_prompt(
        original_question=original_question,
        selected_index=selected_index,
        index_descriptions=index_descriptions
    )

    logger.debug(f"Промпт построен, длина: {len(prompt)} символов")

    # === 5. Вызов Claude Haiku API ===

    try:
        start_time = time.time()

        # WHY: Используем send_msg_to_model из analysis.py (синхронная функция)
        # потому что она уже имеет retry логику с exponential backoff
        # и обработку RateLimitError
        enhanced_question = send_msg_to_model(
            messages=[{"role": "user", "content": prompt}],
            system=None,  # Промпт уже содержит всю необходимую информацию
            max_tokens=MAX_TOKENS,
            model=HAIKU_MODEL,
            api_key=api_key
        )

        elapsed = time.time() - start_time

        # === 6. Валидация и возврат результата ===

        # Проверка на ошибку API (send_msg_to_model возвращает err при ошибке)
        # Проверка на ошибку API
        # WHY: send_msg_to_model возвращает CLAUDE_ERROR_MESSAGE при ошибке вместо исключения
        # Используем константу из constants.py вместо хрупкой строковой проверки
        if enhanced_question == CLAUDE_ERROR_MESSAGE or not enhanced_question:
            logger.warning(
                f"API вернул ошибку. Возвращаем original_question"
            )
            return original_question


        # Убрать кавычки если модель добавила (вопреки инструкции)
        enhanced_question = enhanced_question.strip().strip('"').strip("'")

        # Проверка длины (ожидаем 150-300 символов)
        # WHY: Порог 20 символов вместо 50 - чтобы не отсекать короткие но валидные ответы
        # после удаления кавычек (например, "'Улучшенный вопрос в кавычках'" -> 28 символов)
        if len(enhanced_question) < 20:
            logger.warning(
                f"Улучшенный вопрос слишком короткий ({len(enhanced_question)} символов). "
                f"Возвращаем original_question"
            )
            return original_question

        if len(enhanced_question) > 500:
            logger.warning(
                f"Улучшенный вопрос слишком длинный ({len(enhanced_question)} символов). "
                f"Обрезаем до 500 символов."
            )
            enhanced_question = enhanced_question[:500]

        logger.info(
            f"Вопрос улучшен за {elapsed:.2f}s. "
            f"Длина: {len(original_question)} → {len(enhanced_question)} символов"
        )
        logger.debug(f"Улучшенный вопрос: '{enhanced_question}'")

        return enhanced_question

    except Exception as e:
        # Fallback: вернуть original_question при любой ошибке
        logger.exception(
            f"Ошибка улучшения вопроса: {e}. "
            f"Возвращаем original_question"
        )
        return original_question


if __name__ == "__main__":
    """
    Пример использования модуля (для тестирования).

    Запуск:
        python src/question_enhancer.py
    """
    import sys
    from relevance_evaluator import load_report_descriptions

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s'
    )

    try:
        # Загрузить описания отчетов
        logger.info("Загрузка описаний отчетов...")
        descriptions = load_report_descriptions()

        # Пример вопроса
        question = "Какие проблемы с освещением в ресторане?"
        selected_idx = "Otchety_po_dizaynu"

        logger.info(f"\nИсходный вопрос: {question}")
        logger.info(f"Выбранный индекс: {selected_idx}")

        # Улучшить вопрос
        enhanced = enhance_question_for_index(
            original_question=question,
            selected_index=selected_idx,
            report_descriptions=descriptions
        )

        print("\n" + "="*80)
        print("РЕЗУЛЬТАТ УЛУЧШЕНИЯ ВОПРОСА")
        print("="*80)
        print(f"\nИсходный вопрос ({len(question)} символов):")
        print(f"  {question}")
        print(f"\nУлучшенный вопрос ({len(enhanced)} символов):")
        print(f"  {enhanced}")
        print("\n" + "="*80)

    except Exception as e:
        logger.exception(f"Ошибка: {e}")
        sys.exit(1)
