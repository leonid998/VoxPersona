"""
Модуль оценки релевантности отчетов для Router Agent.

Использует Claude Haiku 4.5 API для оценки релевантности каждого из 22 типов отчетов
для вопроса пользователя. Работает параллельно через asyncio для оптимизации производительности.

Основная функция: evaluate_report_relevance()
    - Принимает вопрос пользователя и словарь описаний отчетов
    - Возвращает словарь с процентами релевантности (0-100) для каждого отчета
    - Использует параллельные async запросы к Claude API
    - Применяет rate limiting (max 10 concurrent запросов)

Примеры использования см. в tests/test_relevance_evaluator.py
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Dict

import anthropic
from anthropic import RateLimitError

from config import ANTHROPIC_API_KEY

# Константы
HAIKU_MODEL = "claude-haiku-4-5-20251001"  # Модель Haiku 4.5 для быстрой оценки
MAX_TOKENS = 50  # Достаточно для ответа с одним числом
TEMPERATURE = 0  # Детерминированный режим для консистентности
MAX_CONCURRENT_REQUESTS = 10  # Ограничение параллельных запросов (избежать 429)
REQUEST_TIMEOUT = 30  # Таймаут на один запрос (секунды)
MAX_RETRIES = 3  # Максимум попыток при ошибке

# Путь к директории с описаниями отчетов
REPORT_DESCRIPTIONS_DIR = Path(__file__).parent.parent / "Description" / "Report content"

logger = logging.getLogger(__name__)


def load_report_descriptions() -> Dict[str, str]:
    """
    Загрузить все 22 описания отчетов из файловой системы.

    Сканирует директорию Description/Report content/ рекурсивно,
    находит все .md файлы и загружает их содержимое.

    Returns:
        Dict[str, str]: Словарь {имя_отчета: содержимое_файла}
                       Имя отчета извлекается из названия файла
                       (убирается префикс "Содержание_отчетов_" и расширение ".md")

    Raises:
        FileNotFoundError: Если директория не существует
        ValueError: Если найдено меньше 22 файлов (ожидаемое количество)

    Example:
        >>> descriptions = load_report_descriptions()
        >>> len(descriptions)
        22
        >>> "Структурированный_отчет_аудита" in descriptions
        True
    """
    if not REPORT_DESCRIPTIONS_DIR.exists():
        raise FileNotFoundError(
            f"Директория с описаниями отчетов не найдена: {REPORT_DESCRIPTIONS_DIR}"
        )

    # Рекурсивный поиск всех .md файлов
    md_files = list(REPORT_DESCRIPTIONS_DIR.rglob("*.md"))

    if len(md_files) < 22:
        logger.warning(
            f"Найдено только {len(md_files)} файлов описаний отчетов "
            f"(ожидалось 22). Директория: {REPORT_DESCRIPTIONS_DIR}"
        )

    descriptions = {}
    for md_file in md_files:
        try:
            # Извлечь имя отчета из имени файла
            # Пример: "Содержание_отчетов_Структурированный_отчет_аудита.md"
            # → "Структурированный_отчет_аудита"
            report_name = md_file.stem  # Без расширения

            # Убрать префиксы (различные варианты)
            prefixes = [
                "Содержание_отчетов_",
                "Содержание отчетов_",
                "Содержание отчетов "
            ]
            for prefix in prefixes:
                if report_name.startswith(prefix):
                    report_name = report_name[len(prefix):]
                    break

            # Загрузить содержимое файла
            content = md_file.read_text(encoding="utf-8")
            descriptions[report_name] = content

            logger.debug(f"Загружен отчет: {report_name} ({len(content)} символов)")

        except Exception as e:
            logger.error(f"Ошибка загрузки файла {md_file}: {e}")
            continue

    logger.info(f"Загружено {len(descriptions)} описаний отчетов")
    return descriptions


def build_relevance_prompt(question: str, report_description: str) -> str:
    """
    Построить промпт для оценки релевантности одного отчета.

    Промпт инструктирует Claude Haiku оценить в процентах (0-100)
    насколько данный тип отчета релевантен для поиска ответа на вопрос.

    Args:
        question: Вопрос пользователя
        report_description: Полное описание типа отчета (содержимое .md файла)

    Returns:
        str: Готовый промпт для отправки в Claude API

    Example:
        >>> prompt = build_relevance_prompt(
        ...     "проблемы с освещением в ресторане",
        ...     "Отчет содержит анализ дизайна интерьера..."
        ... )
        >>> "0-100" in prompt
        True
    """
    # Промпт оптимизирован с контекстом о системе индексов
    # для более точного определения релевантности
    prompt = f"""Задача: Оцени релевантность этого типа отчета для вопроса пользователя.

КОНТЕКСТ СИСТЕМЫ:
В базе данных 7 категорий отчетов по отелям:
1. Дизайн интерьера - структурированные аудиты дизайна (освещение, мебель, цвета)
2. Интервью с гостями - мнения, отзывы, впечатления посетителей
3. Итоговые отчеты - сводная аналитика, рекомендации, резюме
4. Отчеты по дизайну - анализ сильных/слабых сторон, противоречия
5. Отчеты по обследованию - инфраструктура, маршруты, востребованность
6. Исходники дизайна - первичные замеры, фото, технические данные
7. Исходники обследования - технические параметры инженерных систем

Вопрос пользователя:
{question}

Описание типа отчета:
{report_description}

Инструкция:
Оцени СТРОГО в процентах (0-100%) насколько ИМЕННО этот тип отчета является ЕДИНСТВЕННО правильным источником.
ВАЖНО: 100% ставь ТОЛЬКО если это ИДЕАЛЬНОЕ совпадение тематики!

Примеры правильной оценки:
- Вопрос про мнения гостей → Интервью: 95%, Дизайн: 10%
- Вопрос про освещение → Дизайн интерьера: 95%, Интервью: 20%
- Вопрос про инфраструктуру → Обследование: 90%, Дизайн: 15%

Шкала:
0-20% - не тот тип отчета
20-50% - косвенно связан
50-80% - частично релевантен
80-100% - основной источник (только для прямого совпадения!)

Верни ТОЛЬКО число (0-100) без пояснений."""

    return prompt


async def evaluate_single_report(
    question: str,
    report_name: str,
    report_description: str,
    semaphore: asyncio.Semaphore,
    api_key: str
) -> tuple[str, float]:
    """
    Оценить релевантность одного отчета через Claude Haiku API.

    Выполняет async запрос к Claude API с retry логикой и exponential backoff
    при ошибках rate limiting. Использует семафор для ограничения concurrent запросов.

    Args:
        question: Вопрос пользователя
        report_name: Имя отчета (для логирования и возврата)
        report_description: Полное описание типа отчета
        semaphore: asyncio.Semaphore для ограничения параллелизма
        api_key: Anthropic API key

    Returns:
        tuple[str, float]: (имя_отчета, процент_релевантности)
                          Релевантность в диапазоне 0-100

    Raises:
        asyncio.TimeoutError: Если запрос превысил REQUEST_TIMEOUT секунд

    Notes:
        - При ошибке парсинга ответа возвращает 0.0 (fallback)
        - При RateLimitError делает retry с exponential backoff (1s, 2s, 4s)
        - Все остальные ошибки логируются и возвращают 0.0

    Example:
        >>> semaphore = asyncio.Semaphore(10)
        >>> name, score = await evaluate_single_report(
        ...     "проблемы с освещением",
        ...     "Световой_дизайн",
        ...     "Описание анализа освещения...",
        ...     semaphore,
        ...     api_key
        ... )
        >>> 0 <= score <= 100
        True
    """
    async with semaphore:  # Ограничение concurrent запросов
        client = anthropic.AsyncAnthropic(api_key=api_key)
        prompt = build_relevance_prompt(question, report_description)

        # Retry с exponential backoff
        backoff = 1
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Async запрос к Claude API с таймаутом
                response = await asyncio.wait_for(
                    client.messages.create(
                        model=HAIKU_MODEL,
                        max_tokens=MAX_TOKENS,
                        temperature=TEMPERATURE,
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=REQUEST_TIMEOUT
                )

                # Извлечь текст ответа
                answer = response.content[0].text.strip()

                # Парсинг ответа: ожидаем число (0-100)
                # Используем regex для извлечения первого числа из ответа
                # (на случай если модель добавила пояснения вопреки инструкции)
                match = re.search(r'-?\d+(?:\.\d+)?', answer)
                if not match:
                    logger.warning(
                        f"Не удалось распарсить ответ для '{report_name}': '{answer}'. "
                        f"Используется fallback 0.0"
                    )
                    return (report_name, 0.0)

                relevance = float(match.group())

                # Валидация диапазона
                if not (0 <= relevance <= 100):
                    logger.warning(
                        f"Релевантность вне диапазона для '{report_name}': {relevance}. "
                        f"Используется clamp."
                    )
                    relevance = max(0.0, min(100.0, relevance))

                logger.debug(f"Отчет '{report_name}': релевантность {relevance}%")
                return (report_name, relevance)

            except RateLimitError as e:
                last_exception = e
                if attempt == MAX_RETRIES:
                    logger.error(
                        f"Rate limit для '{report_name}' после {MAX_RETRIES} попыток. "
                        f"Используется fallback 0.0"
                    )
                    return (report_name, 0.0)

                logger.warning(
                    f"Rate limit для '{report_name}' (попытка {attempt}/{MAX_RETRIES}). "
                    f"Ожидание {backoff}s перед повтором..."
                )
                await asyncio.sleep(backoff)
                backoff *= 2  # Exponential backoff: 1s, 2s, 4s

            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout ({REQUEST_TIMEOUT}s) для отчета '{report_name}'. "
                    f"Используется fallback 0.0"
                )
                return (report_name, 0.0)

            except Exception as e:
                logger.exception(
                    f"Ошибка оценки релевантности для '{report_name}': {e}. "
                    f"Используется fallback 0.0"
                )
                return (report_name, 0.0)

        # Если все попытки исчерпаны (не должно случиться при правильной логике)
        logger.error(
            f"Исчерпаны попытки для '{report_name}'. Используется fallback 0.0"
        )
        return (report_name, 0.0)


async def evaluate_report_relevance(
    question: str,
    report_descriptions: Dict[str, str] | None = None,
    api_key: str | None = None
) -> Dict[str, float]:
    """
    Оценить релевантность всех отчетов для вопроса пользователя.

    ОСНОВНАЯ ФУНКЦИЯ МОДУЛЯ.

    Параллельно отправляет запросы к Claude Haiku 4.5 API для оценки релевантности
    каждого типа отчета. Использует asyncio.gather() для параллельной обработки
    с ограничением concurrent запросов через семафор.

    Args:
        question: Вопрос пользователя (строка на русском или английском)
        report_descriptions: Словарь {имя_отчета: содержимое_файла}.
                            Если None, автоматически загружается через load_report_descriptions()
        api_key: Anthropic API key. Если None, используется ANTHROPIC_API_KEY из config

    Returns:
        Dict[str, float]: Словарь {имя_отчета: процент_релевантности}
                         Релевантность в диапазоне 0-100

    Raises:
        ValueError: Если question пустой или api_key недоступен
        FileNotFoundError: Если descriptions не переданы и не удалось загрузить из файлов

    Performance:
        - Параллельная обработка: 22 отчета оцениваются одновременно
        - Rate limiting: max 10 concurrent запросов
        - Типичное время выполнения: 3-5 секунд (зависит от API latency)

    Example:
        >>> # Автоматическая загрузка описаний
        >>> results = await evaluate_report_relevance(
        ...     "проблемы с освещением в ресторане"
        ... )
        >>> len(results)
        22
        >>> results["Световой_дизайн"] > results["Водоснабжение"]
        True

        >>> # С предзагруженными описаниями
        >>> descriptions = load_report_descriptions()
        >>> results = await evaluate_report_relevance(
        ...     "как повысить заполняемость отеля",
        ...     report_descriptions=descriptions
        ... )
    """
    # Валидация входных данных
    if not question or not question.strip():
        raise ValueError("Вопрос не может быть пустым")

    # Получить API key
    if api_key is None:
        api_key = ANTHROPIC_API_KEY

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY не установлен. "
            "Проверьте файл .env или передайте api_key явно."
        )

    # Загрузить описания отчетов если не переданы
    if report_descriptions is None:
        logger.info("Загрузка описаний отчетов из файловой системы...")
        report_descriptions = load_report_descriptions()

    if not report_descriptions:
        raise ValueError("Не удалось загрузить описания отчетов")

    logger.info(
        f"Начинаем оценку релевантности {len(report_descriptions)} отчетов "
        f"для вопроса: '{question[:100]}...'"
    )

    # Создать семафор для ограничения параллельных запросов
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # Создать задачи для параллельного выполнения
    tasks = [
        evaluate_single_report(
            question=question,
            report_name=name,
            report_description=description,
            semaphore=semaphore,
            api_key=api_key
        )
        for name, description in report_descriptions.items()
    ]

    # Выполнить все задачи параллельно
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=False)
    elapsed = time.time() - start_time

    # Преобразовать список кортежей в словарь
    relevance_scores = dict(results)

    logger.info(
        f"Оценка релевантности завершена за {elapsed:.2f}s. "
        f"Обработано {len(relevance_scores)} отчетов."
    )

    # Логировать топ-3 наиболее релевантных отчета
    top_3 = sorted(relevance_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    logger.info("Топ-3 релевантных отчета:")
    for rank, (name, score) in enumerate(top_3, 1):
        logger.info(f"  {rank}. {name}: {score:.1f}%")

    return relevance_scores


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОТЛАДКИ ===

def print_relevance_report(relevance_scores: Dict[str, float]) -> None:
    """
    Вывести отчет о релевантности в консоль (для отладки).

    Args:
        relevance_scores: Результат evaluate_report_relevance()

    Example:
        >>> scores = await evaluate_report_relevance("вопрос пользователя")
        >>> print_relevance_report(scores)
        === ОТЧЕТ О РЕЛЕВАНТНОСТИ ===
        1. Световой_дизайн: 85.5%
        2. Дизайн_интерьера: 72.3%
        ...
    """
    print("\n" + "="*50)
    print("=== ОТЧЕТ О РЕЛЕВАНТНОСТИ ===")
    print("="*50 + "\n")

    sorted_scores = sorted(relevance_scores.items(), key=lambda x: x[1], reverse=True)

    for rank, (name, score) in enumerate(sorted_scores, 1):
        bar_length = int(score / 2)  # 50 символов = 100%
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"{rank:2}. {name:50} {bar} {score:5.1f}%")

    print("\n" + "="*50)


if __name__ == "__main__":
    """
    Пример использования модуля (для тестирования).

    Запуск:
        python src/relevance_evaluator.py
    """
    import sys

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s'
    )

    async def main():
        # Пример вопроса
        question = "Какие проблемы с освещением в ресторане?"

        try:
            # Оценить релевантность
            scores = await evaluate_report_relevance(question)

            # Вывести отчет
            print_relevance_report(scores)

        except Exception as e:
            logger.exception(f"Ошибка: {e}")
            sys.exit(1)

    # Запустить async main
    asyncio.run(main())
