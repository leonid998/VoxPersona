"""
Модуль выбора наиболее релевантного индекса на основе оценок отчетов.

Этот модуль является второй частью Router Agent и отвечает за:
1. Группировку 22 отчетов в 7 индексов
2. Вычисление совокупной релевантности каждого индекса
3. Выбор индекса с максимальной релевантностью

Архитектура:
- Получает словарь релевантностей отчетов от relevance_evaluator
- Агрегирует оценки по индексам (среднее арифметическое)
- Возвращает название наиболее релевантного индекса

Пример использования:
    from relevance_evaluator import evaluate_report_relevance
    from index_selector import select_most_relevant_index

    # Получаем оценки отчетов
    report_relevance = evaluate_report_relevance(user_query)

    # Выбираем индекс
    best_index = select_most_relevant_index(report_relevance)
    print(f"Выбран индекс: {best_index}")
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Маппинг индексов на отчеты (согласно files_list.md и impl_plan.md)
INDEX_MAPPING: Dict[str, List[str]] = {
    "Dizayn": [
        "Структурированный_отчет_аудита"
    ],
    "Intervyu": [
        "Общие_факторы",
        "Отчет_о_связках",
        "Факторы_в_этом_заведении"
    ],
    "Iskhodniki_dizayn": [
        "Аудит_Дизайна"
    ],
    "Iskhodniki_obsledovanie": [
        "Обследование"
    ],
    "Itogovye_otchety": [
        "Краткое резюме",
        "Ощущения",
        "Заполняемость",
        "Итоговый",
        "Отдых",
        "Рекомендации"
    ],
    "Otchety_po_dizaynu": [
        "Дизайн и архитектура",
        "Сильные стороны",
        "Недостатки",
        "Ожидания",
        "Противоречия"
    ],
    "Otchety_po_obsledovaniyu": [
        "Востребованность",
        "Качество инфраструктуры",
        "Клиентский опыт",
        "Маршруты",
        "Обустройство"
    ]
}

# Индекс по умолчанию (если не удалось выбрать другой)
DEFAULT_INDEX = "Dizayn"

# Маппинг коротких имен индексов на человекочитаемые названия
# ФАЗА 3: Router Agent - UI отображение выбранного индекса
# Используется в handlers.py и run_analysis.py
INDEX_DISPLAY_NAMES: Dict[str, str] = {
    "Dizayn": "Дизайн (Структурированные аудиты)",
    "Intervyu": "Интервью (Транскрипции)",
    "Otchety_po_dizaynu": "Отчеты по дизайну (60 отелей РФ)",
    "Otchety_po_obsledovaniyu": "Отчеты по обследованию (Инфраструктура)",
    "Itogovye_otchety": "Итоговые отчеты (Сводная аналитика)",
    "Iskhodniki_dizayn": "Исходники (Дизайн)",
    "Iskhodniki_obsledovanie": "Исходники (Обследование)"
}


def select_most_relevant_index(
    report_relevance: Dict[str, float],
    index_mapping: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Выбирает индекс с наивысшей совокупной релевантностью.

    Алгоритм:
    1. Для каждого индекса находим все его отчеты
    2. Вычисляем среднее арифметическое релевантностей отчетов индекса
    3. Выбираем индекс с максимальной средней релевантностью
    4. При равных оценках выбирается первый по алфавиту

    Args:
        report_relevance: Словарь {report_name: relevance_score} от relevance_evaluator.
                         Все оценки должны быть в диапазоне [0, 1].
        index_mapping: Словарь {index_name: [report_names]} - маппинг отчетов на индексы.
                      Если None - использует INDEX_MAPPING по умолчанию.

    Returns:
        str: Название индекса с наивысшей релевантностью.

    Raises:
        ValueError: Если report_relevance пустой или None.

    Examples:
        >>> report_rel = {
        ...     "Дизайн и архитектура": 0.95,
        ...     "Сильные стороны": 0.90,
        ...     "Обследование": 0.30
        ... }
        >>> select_most_relevant_index(report_rel)
        'Otchety_po_dizaynu'

        >>> # При равных оценках выбирается первый по алфавиту
        >>> report_rel = {
        ...     "Структурированный_отчет_аудита": 0.5,
        ...     "Общие_факторы": 0.5
        ... }
        >>> select_most_relevant_index(report_rel)
        'Dizayn'
    """
    # Валидация входных данных
    if not report_relevance:
        logger.error("Получен пустой словарь релевантностей отчетов")
        raise ValueError("report_relevance не может быть пустым")

    # Используем маппинг по умолчанию если не передан
    mapping = index_mapping if index_mapping is not None else INDEX_MAPPING

    logger.info(f"Начинаем выбор индекса на основе {len(report_relevance)} оценок отчетов")
    logger.debug(f"Релевантности отчетов: {report_relevance}")

    # Вычисляем релевантность каждого индекса
    index_scores: Dict[str, float] = {}

    for index_name, report_names in mapping.items():
        # Находим релевантности отчетов, которые есть в report_relevance
        relevant_scores = [
            report_relevance[report_name]
            for report_name in report_names
            if report_name in report_relevance
        ]

        if relevant_scores:
            # Среднее арифметическое релевантностей отчетов индекса
            avg_score = sum(relevant_scores) / len(relevant_scores)
            index_scores[index_name] = avg_score
            logger.debug(
                f"Индекс '{index_name}': {len(relevant_scores)} отчетов, "
                f"средняя релевантность = {avg_score:.4f}"
            )
        else:
            # Если ни один отчет индекса не найден в report_relevance
            index_scores[index_name] = 0.0
            logger.warning(
                f"Индекс '{index_name}': ни один отчет не найден в report_relevance"
            )

    # Проверка: если все индексы имеют релевантность 0
    if all(score == 0.0 for score in index_scores.values()):
        logger.warning(
            "Все индексы имеют релевантность 0.0, возвращаем индекс по умолчанию"
        )
        return DEFAULT_INDEX

    # Выбираем индекс с максимальной релевантностью
    # При равных оценках выбирается первый по алфавиту (sorted обеспечивает детерминизм)
    best_index = max(
        sorted(index_scores.keys()),  # Сортировка для детерминированности при равенстве
        key=lambda idx: index_scores[idx]
    )
    best_score = index_scores[best_index]

    # Логируем топ-3 индекса для анализа
    top_3_indices = sorted(
        index_scores.items(),
        key=lambda x: (-x[1], x[0])  # По убыванию score, затем по имени
    )[:3]

    logger.info(f"Топ-3 индекса:")
    for i, (idx, score) in enumerate(top_3_indices, 1):
        logger.info(f"  {i}. {idx}: {score:.4f}")

    logger.info(f"Выбран индекс: '{best_index}' с релевантностью {best_score:.4f}")

    return best_index


def validate_index_mapping(
    index_mapping: Dict[str, List[str]],
    available_rags: Optional[List[str]] = None
) -> bool:
    """
    Проверяет корректность маппинга индексов.

    Проверки:
    1. Все индексы из маппинга существуют в available_rags (если передан)
    2. Нет пустых списков отчетов
    3. Нет дублирующихся отчетов между индексами

    Args:
        index_mapping: Словарь {index_name: [report_names]} для проверки.
        available_rags: Список доступных RAG индексов (опционально).
                       Если None - пропускается проверка существования.

    Returns:
        bool: True если маппинг валидный, False в противном случае.

    Examples:
        >>> mapping = {
        ...     "Index1": ["Report1", "Report2"],
        ...     "Index2": ["Report3"]
        ... }
        >>> validate_index_mapping(mapping)
        True

        >>> # Проверка с доступными RAG
        >>> validate_index_mapping(mapping, available_rags=["Index1", "Index2"])
        True

        >>> # Невалидный маппинг - пустой список
        >>> mapping = {"Index1": []}
        >>> validate_index_mapping(mapping)
        False
    """
    if not index_mapping:
        logger.error("Маппинг индексов пуст")
        return False

    # Проверка 1: Существование индексов в available_rags
    if available_rags is not None:
        missing_indices = set(index_mapping.keys()) - set(available_rags)
        if missing_indices:
            logger.error(
                f"Индексы из маппинга отсутствуют в available_rags: {missing_indices}"
            )
            return False

    # Проверка 2: Нет пустых списков отчетов
    for index_name, report_names in index_mapping.items():
        if not report_names:
            logger.error(f"Индекс '{index_name}' имеет пустой список отчетов")
            return False

    # Проверка 3: Нет дублирующихся отчетов между индексами
    all_reports = []
    for report_names in index_mapping.values():
        all_reports.extend(report_names)

    if len(all_reports) != len(set(all_reports)):
        duplicates = [
            report for report in set(all_reports)
            if all_reports.count(report) > 1
        ]
        logger.error(f"Дублирующиеся отчеты между индексами: {duplicates}")
        return False

    logger.info(f"Маппинг индексов валиден: {len(index_mapping)} индексов, "
                f"{len(all_reports)} отчетов")
    return True


def load_index_mapping_from_file(filepath: str = "Description/files_list.md") -> Dict[str, List[str]]:
    """
    Загружает маппинг индексов из файла files_list.md.

    ВНИМАНИЕ: Эта функция пока не реализована и является заглушкой для будущего расширения.
    Текущая версия использует жестко закодированный INDEX_MAPPING.

    Планируемая функциональность:
    1. Парсинг структуры файлов из files_list.md
    2. Автоматическое построение маппинга индексов на отчеты
    3. Валидация соответствия структуры ожидаемому формату

    Args:
        filepath: Путь к файлу files_list.md относительно корня проекта.

    Returns:
        Dict[str, List[str]]: Маппинг индексов на отчеты.

    Raises:
        NotImplementedError: Функция не реализована в текущей версии.

    TODO:
        - Реализовать парсинг Markdown структуры
        - Добавить обработку различных форматов именования файлов
        - Добавить кэширование результата
    """
    raise NotImplementedError(
        "Загрузка маппинга из файла пока не реализована. "
        "Используйте INDEX_MAPPING по умолчанию."
    )


def get_index_statistics(index_mapping: Optional[Dict[str, List[str]]] = None) -> Dict[str, int]:
    """
    Возвращает статистику по маппингу индексов.

    Полезно для отладки и мониторинга покрытия отчетов.

    Args:
        index_mapping: Словарь {index_name: [report_names]}.
                      Если None - использует INDEX_MAPPING по умолчанию.

    Returns:
        Dict[str, int]: Статистика вида {index_name: количество_отчетов}.

    Examples:
        >>> get_index_statistics()
        {
            'Dizayn': 1,
            'Intervyu': 3,
            'Iskhodniki_dizayn': 1,
            'Iskhodniki_obsledovanie': 1,
            'Itogovye_otchety': 6,
            'Otchety_po_dizaynu': 5,
            'Otchety_po_obsledovaniyu': 5
        }
    """
    mapping = index_mapping if index_mapping is not None else INDEX_MAPPING

    stats = {
        index_name: len(report_names)
        for index_name, report_names in mapping.items()
    }

    total_reports = sum(stats.values())
    logger.debug(f"Статистика индексов: {stats}, всего отчетов: {total_reports}")

    return stats


if __name__ == "__main__":
    # Настройка логирования для демонстрации
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(name)s - %(message)s'
    )

    # Пример 1: Базовый выбор индекса
    print("=== Пример 1: Базовый выбор индекса ===")
    report_rel = {
        "Дизайн и архитектура": 0.95,
        "Сильные стороны": 0.90,
        "Недостатки": 0.85,
        "Обследование": 0.30
    }
    result = select_most_relevant_index(report_rel)
    print(f"Результат: {result}\n")

    # Пример 2: Статистика индексов
    print("=== Пример 2: Статистика индексов ===")
    stats = get_index_statistics()
    for idx, count in sorted(stats.items()):
        print(f"{idx}: {count} отчетов")
    print(f"Всего отчетов: {sum(stats.values())}\n")

    # Пример 3: Валидация маппинга
    print("=== Пример 3: Валидация маппинга ===")
    is_valid = validate_index_mapping(INDEX_MAPPING)
    print(f"Маппинг валиден: {is_valid}")
