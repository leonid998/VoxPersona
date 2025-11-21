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
from typing import Dict, List

from config import ANTHROPIC_API_KEY
from index_selector import INDEX_MAPPING, INDEX_DISPLAY_NAMES
from constants import CLAUDE_ERROR_MESSAGE
from analysis import send_msg_to_model

# Константы модели
HAIKU_MODEL = "claude-3-5-haiku-20241022"  # Модель Haiku 3.5 для улучшения вопроса
MAX_TOKENS = 500  # Достаточно для улучшенного вопроса (150-300 символов)
TEMPERATURE = 0.1  # Низкая температура для консистентности

# Константы валидации
MAX_QUESTION_LENGTH = 500  # Максимальная длина входного вопроса
MIN_ENHANCED_LENGTH = 20  # Минимальная длина улучшенного вопроса
MAX_ENHANCED_LENGTH = 500  # Максимальная длина улучшенного вопроса
DESCRIPTION_TRUNCATE_LENGTH = 500  # Длина для обрезки описаний отчетов

logger = logging.getLogger(__name__)


def _validate_enhancement_inputs(
    original_question: str,
    selected_index: str,
    report_descriptions: Dict[str, str],
    api_key: str | None
) -> tuple[str, str]:
    """
    Валидация входных параметров для enhance_question_for_index.

    Извлечено из enhance_question_for_index для снижения Cognitive Complexity.
    SonarCloud: CC 19 -> <=15

    Args:
        original_question: Исходный вопрос пользователя
        selected_index: Название выбранного индекса
        report_descriptions: Словарь описаний отчетов
        api_key: API ключ (может быть None)

    Returns:
        tuple[str, str]: (validated_question, resolved_api_key)

    Raises:
        ValueError: При невалидных входных данных
    """
    # Валидация original_question
    if not original_question or not original_question.strip():
        logger.error("Получен пустой вопрос")
        raise ValueError("original_question не может быть пустым")

    # Валидация длины вопроса (защита от prompt injection)
    validated_question = original_question
    if len(original_question) > MAX_QUESTION_LENGTH:
        logger.warning(
            f"Вопрос пользователя слишком длинный ({len(original_question)} символов). "
            f"Обрезаем до {MAX_QUESTION_LENGTH}."
        )
        validated_question = original_question[:MAX_QUESTION_LENGTH]

    # Валидация selected_index
    if selected_index not in INDEX_MAPPING:
        logger.error(f"Неизвестный индекс: '{selected_index}'")
        raise ValueError(
            f"selected_index '{selected_index}' не найден в INDEX_MAPPING. "
            f"Доступные индексы: {list(INDEX_MAPPING.keys())}"
        )

    # Валидация report_descriptions
    if not report_descriptions:
        logger.error("Получен пустой словарь описаний отчетов")
        raise ValueError("report_descriptions не может быть пустым")

    # Получить и валидировать API key
    resolved_api_key = api_key if api_key is not None else ANTHROPIC_API_KEY

    if not resolved_api_key:
        logger.error("ANTHROPIC_API_KEY не установлен")
        raise ValueError(
            "ANTHROPIC_API_KEY не установлен. "
            "Проверьте файл .env или передайте api_key явно."
        )

    return validated_question, resolved_api_key


def _validate_and_sanitize_result(
    enhanced_question: str,
    original_question: str
) -> str | None:
    """
    Валидация и очистка результата от Claude API.

    Извлечено из enhance_question_for_index для снижения Cognitive Complexity.
    SonarCloud: CC 19 -> <=15

    Args:
        enhanced_question: Ответ от Claude API
        original_question: Исходный вопрос (для fallback)

    Returns:
        str | None: Очищенный улучшенный вопрос или None при ошибке валидации
    """
    # Проверка на ошибку API
    if enhanced_question == CLAUDE_ERROR_MESSAGE or not enhanced_question:
        logger.warning("API вернул ошибку. Возвращаем original_question")
        return None

    # Убрать кавычки если модель добавила (вопреки инструкции)
    sanitized = enhanced_question.strip().strip('"').strip("'")

    # Проверка минимальной длины
    if len(sanitized) < MIN_ENHANCED_LENGTH:
        logger.warning(
            f"Улучшенный вопрос слишком короткий ({len(sanitized)} символов). "
            f"Возвращаем original_question"
        )
        return None

    # Проверка максимальной длины
    if len(sanitized) > MAX_ENHANCED_LENGTH:
        logger.warning(
            f"Улучшенный вопрос слишком длинный ({len(sanitized)} символов). "
            f"Обрезаем до {MAX_ENHANCED_LENGTH} символов."
        )
        sanitized = sanitized[:MAX_ENHANCED_LENGTH]

    return sanitized


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
        if len(description) > DESCRIPTION_TRUNCATE_LENGTH:
            truncated = description[:DESCRIPTION_TRUNCATE_LENGTH] + "..."
        else:
            truncated = description
        formatted_lines.append(f"{i}. {report_name}:\n{truncated}\n")

    return "\n".join(formatted_lines)


def format_top_indices_context(top_indices: List[tuple]) -> str:
    """
    Форматирует контекст топ-3 индексов для включения в промпт.

    ЗАДАЧА 2.3: Создает информативный контекст о релевантных индексах,
    который помогает Claude лучше улучшить вопрос.

    Args:
        top_indices: Список кортежей (index_name, score) от get_top_relevant_indices().
                    Score ожидается в процентах (0-100).

    Returns:
        str: Форматированная строка с контекстом топ-3 индексов.

    Example:
        >>> top = [("Otchety_po_dizaynu", 85.3), ("Itogovye_otchety", 72.1)]
        >>> context = format_top_indices_context(top)
        >>> "Отчеты по дизайну" in context
        True
    """
    if not top_indices:
        return ""

    lines = ["Топ-3 релевантных индекса для этого вопроса (по результатам анализа):"]

    for idx, (index_name, score) in enumerate(top_indices, 1):
        # Получаем человекочитаемое название индекса
        display_name = INDEX_DISPLAY_NAMES.get(index_name, index_name)

        # Формируем строку с процентами
        lines.append(f"{idx}. {display_name} - релевантность {score:.1f}%")

    # Добавляем инструкцию для Claude
    lines.append("")
    lines.append("Учитывай эту информацию о релевантных индексах при улучшении вопроса.")
    lines.append("Особенно обращай внимание на термины и концепции из топ-1 индекса.")

    return "\n".join(lines)


def build_enhancement_prompt(
    original_question: str,
    selected_index: str,
    index_descriptions: str,
    top_indices_context: str = ""
) -> str:
    """
    Построить промпт для улучшения вопроса под выбранный индекс.

    Промпт адаптирован из Description/queru_exp.txt с модификациями:
    - Фокус на конкретном индексе (не вся БД)
    - Инструкция добавить термины из описаний отчетов индекса
    - Требование указать типы отчетов для изучения
    - Добавление контекста "Ответ для управляющего отелем"
    - Ограничение длины 150-300 символов для оптимального embedding

    ЗАДАЧА 2.3: Добавлена поддержка контекста топ-3 индексов для улучшения качества.

    Args:
        original_question: Исходный вопрос пользователя
        selected_index: Название выбранного индекса
        index_descriptions: Форматированные описания отчетов индекса
        top_indices_context: Контекст топ-3 индексов для улучшения качества (опционально)

    Returns:
        str: Готовый промпт для отправки в Claude API

    Example:
        >>> prompt = build_enhancement_prompt(
        ...     "проблемы с освещением",
        ...     "Otchety_po_dizaynu",
        ...     "Индекс содержит: Дизайн...",
        ...     "Топ-3 индексов: ..."
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

    # ЗАДАЧА 2.3: Добавляем контекст топ-3 индексов для улучшения качества
    # WHY: Информация о релевантных индексах помогает Claude понять контекст вопроса
    # и добавить более точные термины из соответствующих областей
    if top_indices_context:
        prompt += f"\n\n{top_indices_context}"

    return prompt


def enhance_question_for_index(
    original_question: str,
    selected_index: str,
    report_descriptions: Dict[str, str],
    api_key: str | None = None,
    top_indices: List[tuple] | None = None
) -> str:
    """
    Улучшить вопрос пользователя для поиска в выбранном индексе.

    ОСНОВНАЯ ФУНКЦИЯ МОДУЛЯ.

    Алгоритм:
    1. Валидация входных данных
    2. Импорт INDEX_MAPPING и фильтрация описаний отчетов для selected_index
    3. Форматирование описаний для промпта
    4. Построение промпта для Claude Haiku (с учетом top_indices если переданы)
    5. Вызов Claude API через send_msg_to_model
    6. Валидация и возврат улучшенного вопроса

    ЗАДАЧА 2.3: Добавлена поддержка параметра top_indices для улучшения качества
    enhanced_question на основе информации о топ-3 релевантных индексах.

    Args:
        original_question: Исходный вопрос пользователя
        selected_index: Название выбранного индекса (из INDEX_MAPPING)
        report_descriptions: Словарь {имя_отчета: содержимое} для ВСЕХ отчетов
        api_key: Anthropic API key (если None - использует ANTHROPIC_API_KEY из config)
        top_indices: Список топ-K релевантных индексов с scores от Router Agent
                    Формат: [(index_name, score), ...]
                    Используется для улучшения качества enhanced_question

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
        >>> # С топ-3 индексами для улучшения качества
        >>> top_indices = [("Otchety_po_dizaynu", 85.3), ("Itogovye_otchety", 72.1)]
        >>> enhanced = enhance_question_for_index(
        ...     original_question="Какие проблемы с освещением в ресторане?",
        ...     selected_index="Otchety_po_dizaynu",
        ...     report_descriptions=descriptions,
        ...     top_indices=top_indices
        ... )
        >>> len(enhanced) > len("Какие проблемы с освещением в ресторане?")
        True
    """
    # === 1. Валидация входных данных ===
    # Извлечено в _validate_enhancement_inputs() для снижения CC
    validated_question, resolved_api_key = _validate_enhancement_inputs(
        original_question, selected_index, report_descriptions, api_key
    )

    logger.info(
        f"Начинаем улучшение вопроса для индекса '{selected_index}': "
        f"'{validated_question[:100]}...'"
    )

    # Логируем информацию о top_indices если переданы
    if top_indices:
        logger.info(f"Используется контекст топ-{len(top_indices)} индексов для улучшения качества")
        for idx, (index_name, score) in enumerate(top_indices, 1):
            logger.debug(f"  {idx}. {index_name}: {score:.1f}%")

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

    # === 3.1 Форматирование контекста топ-3 индексов (ЗАДАЧА 2.3) ===
    # WHY: Контекст топ-3 индексов помогает Claude понять какие темы релевантны
    # и добавить более точные термины из соответствующих областей
    top_indices_context = ""
    if top_indices:
        top_indices_context = format_top_indices_context(top_indices)
        logger.debug(f"Добавлен контекст топ-3 индексов в промпт")

    # === 4. Построение промпта ===

    prompt = build_enhancement_prompt(
        original_question=validated_question,
        selected_index=selected_index,
        index_descriptions=index_descriptions,
        top_indices_context=top_indices_context  # ЗАДАЧА 2.3: передаем контекст
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
            api_key=resolved_api_key
        )

        elapsed = time.time() - start_time

        # === 6. Валидация и возврат результата ===
        # Извлечено в _validate_and_sanitize_result() для снижения CC
        sanitized_result = _validate_and_sanitize_result(
            enhanced_question, validated_question
        )

        if sanitized_result is None:
            return validated_question

        logger.info(
            f"Вопрос улучшен за {elapsed:.2f}s. "
            f"Длина: {len(validated_question)} -> {len(sanitized_result)} символов"
        )
        logger.debug(f"Улучшенный вопрос: '{sanitized_result}'")

        return sanitized_result

    except Exception as e:
        # Fallback: вернуть validated_question при любой ошибке
        logger.exception(
            f"Ошибка улучшения вопроса: {e}. "
            f"Возвращаем validated_question"
        )
        return validated_question


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

        # Пример топ-3 индексов (ЗАДАЧА 2.3)
        example_top_indices = [
            ("Otchety_po_dizaynu", 85.3),
            ("Itogovye_otchety", 72.1),
            ("Dizayn", 45.0)
        ]

        logger.info(f"\nИсходный вопрос: {question}")
        logger.info(f"Выбранный индекс: {selected_idx}")
        logger.info(f"Топ-3 индексов: {example_top_indices}")

        # Улучшить вопрос с контекстом топ-3
        enhanced = enhance_question_for_index(
            original_question=question,
            selected_index=selected_idx,
            report_descriptions=descriptions,
            top_indices=example_top_indices  # ЗАДАЧА 2.3: передаем топ-3
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
