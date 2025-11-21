"""
Модуль оценки релевантности отчетов для Router Agent.

Использует Claude Haiku 4.5 API для оценки релевантности каждого из 22 типов отчетов
для вопроса пользователя. Применяет batch-механизм: все описания упаковываются в
JSON-контейнер и оцениваются за один API запрос.

Основная функция: evaluate_report_relevance()
    - Принимает вопрос пользователя и словарь описаний отчетов
    - Возвращает словарь с процентами релевантности (0-100) для каждого отчета
    - Использует batch-запрос через evaluate_batch_relevance()
    - Один API вызов вместо 22 параллельных

Вспомогательные функции:
    - build_json_container() - упаковка 22 описаний в JSON
    - build_batch_relevance_prompt() - формирование промпта для batch-оценки
    - evaluate_batch_relevance() - выполнение batch-запроса к Claude API

Примеры использования см. в tests/test_relevance_evaluator.py
"""

import asyncio
import json
import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

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

# Константы для batch-оценки
BATCH_MAX_TOKENS = 4000  # Достаточно для JSON с 22 оценками и обоснованиями
BATCH_REQUEST_TIMEOUT = 60  # Таймаут для batch-запроса (секунды)

# Путь к директории с описаниями отчетов
REPORT_DESCRIPTIONS_DIR = Path(__file__).parent.parent / "Description" / "Report content"

logger = logging.getLogger(__name__)


# === МАППИНГ ОТЧЕТОВ НА ИНДЕКСЫ ===
# Корректный маппинг с реальными именами файлов после обработки load_report_descriptions()
# Структура соответствует папкам в Description/Report content/
# ВАЖНО: Имена должны точно соответствовать файлам после удаления префикса "Содержание_отчетов_" или "Содержание отчетов_"

REPORT_TO_INDEX_MAPPING: Dict[str, str] = {
    # Dizayn (1 отчет) - Содержание_Дизайн
    "Структурированный_отчет_аудита": "Dizayn",

    # Intervyu (3 отчета) - Содержание_Интервью
    "Общие_факторы": "Intervyu",
    "Отчет_о_связках": "Intervyu",
    "Факторы_в_этом_заведении": "Intervyu",

    # Iskhodniki_dizayn (1 отчет) - Содержание_Исходники_Аудит_Дизайна
    "Аудит_Дизайна": "Iskhodniki_dizayn",

    # Iskhodniki_obsledovanie (1 отчет) - Содержание_Исходники_Обследование
    "Обследование": "Iskhodniki_obsledovanie",

    # Itogovye_otchety (6 отчетов) - Содержание_Итоговые отчеты
    "Главная": "Itogovye_otchety",
    "Заполняемость_и_бронирование": "Itogovye_otchety",
    "Итоговый_отчет": "Itogovye_otchety",
    "Отдых_и_восстановление": "Itogovye_otchety",
    "Ощущения_от_отеля": "Itogovye_otchety",
    "Рекомендации_по_улучшению": "Itogovye_otchety",

    # Otchety_po_dizaynu (5 отчетов) - Содержание_Дизайн отчеты
    "Дизайн_и_архитектура": "Otchety_po_dizaynu",
    "Недостатки_дизайна": "Otchety_po_dizaynu",
    "Ожидания_и_реальность": "Otchety_po_dizaynu",
    "Противоречия_концепции_и_дизайна": "Otchety_po_dizaynu",
    "Сильные_стороны_дизайна": "Otchety_po_dizaynu",

    # Otchety_po_obsledovaniyu (5 отчетов) - Содержание_Обследование отчеты
    "Востребованность_гостиничного_хозяйства": "Otchety_po_obsledovaniyu",
    "Качество_инфраструктуры": "Otchety_po_obsledovaniyu",
    "Клиентский_опыт": "Otchety_po_obsledovaniyu",
    "Маршруты_и_безопасность": "Otchety_po_obsledovaniyu",
    "Обустройство_гостиничного_хозяйства": "Otchety_po_obsledovaniyu",
}

# Человекочитаемые названия индексов
INDEX_DISPLAY_NAMES: Dict[str, str] = {
    "Dizayn": "Дизайн (Структурированные аудиты)",
    "Intervyu": "Интервью (Транскрипции)",
    "Otchety_po_dizaynu": "Отчеты по дизайну (60 отелей РФ)",
    "Otchety_po_obsledovaniyu": "Отчеты по обследованию (Инфраструктура)",
    "Itogovye_otchety": "Итоговые отчеты (Сводная аналитика)",
    "Iskhodniki_dizayn": "Исходники (Дизайн)",
    "Iskhodniki_obsledovanie": "Исходники (Обследование)"
}


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

            # Нормализация Unicode в форму NFC (precomposed)
            # Это решает проблему с разными представлениями буквы "й"
            # macOS часто использует NFD (decomposed), а Windows/код - NFC
            report_name = unicodedata.normalize("NFC", report_name)

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


def build_json_container(
    report_descriptions: Dict[str, str],
    report_to_index: Dict[str, str] | None = None
) -> str:
    """
    Упаковывает все описания отчетов в JSON-контейнер для batch-оценки.

    Создает структурированный JSON с описаниями всех 22 отчетов,
    их принадлежностью к индексам и метаданными. Используется для
    отправки всех описаний в одном запросе к Claude API для оценки
    релевантности.

    Args:
        report_descriptions: Словарь {имя_отчета: описание}.
                            Обычно результат load_report_descriptions().
        report_to_index: Словарь {имя_отчета: имя_индекса}.
                        Если None, используется REPORT_TO_INDEX_MAPPING.

    Returns:
        JSON-строка со структурой:
        {
          "reports": [
            {
              "id": 1,
              "name": "Структурированный_отчет_аудита",
              "index": "Dizayn",
              "description": "..."
            },
            ...
          ],
          "indices": [
            {"name": "Dizayn", "display_name": "...", "report_ids": [1]},
            ...
          ],
          "total_reports": 22,
          "total_indices": 7
        }

    Raises:
        ValueError: Если report_descriptions пустой или не все 22 отчета включены.

    Example:
        >>> descriptions = load_report_descriptions()
        >>> json_container = build_json_container(descriptions)
        >>> data = json.loads(json_container)
        >>> data["total_reports"]
        22
        >>> data["total_indices"]
        7

    Notes:
        - Сохраняет полные описания без обрезки (помещается в ~55k токенов)
        - ID отчетов начинаются с 1 и идут по порядку сортировки по имени
        - Логирует размер итогового JSON в символах
    """
    # Валидация входных данных
    if not report_descriptions:
        raise ValueError("report_descriptions не может быть пустым")

    # Использовать маппинг по умолчанию если не передан
    mapping = report_to_index if report_to_index is not None else REPORT_TO_INDEX_MAPPING

    # Проверка что все отчеты из маппинга присутствуют
    missing_reports = set(mapping.keys()) - set(report_descriptions.keys())
    if missing_reports:
        logger.warning(
            f"Отчеты из маппинга отсутствуют в descriptions: {missing_reports}"
        )

    # Проверка что все загруженные отчеты есть в маппинге
    unmapped_reports = set(report_descriptions.keys()) - set(mapping.keys())
    if unmapped_reports:
        logger.warning(
            f"Загруженные отчеты отсутствуют в маппинге: {unmapped_reports}"
        )

    # === Построение структуры reports ===
    reports: List[Dict[str, Any]] = []
    report_id_by_name: Dict[str, int] = {}  # Для построения indices

    # Сортируем по имени для детерминированного порядка
    sorted_report_names = sorted(report_descriptions.keys())

    for idx, report_name in enumerate(sorted_report_names, start=1):
        description = report_descriptions[report_name]
        index_name = mapping.get(report_name, "Unknown")

        report_entry = {
            "id": idx,
            "name": report_name,
            "index": index_name,
            "description": description  # Полное описание без обрезки
        }
        reports.append(report_entry)
        report_id_by_name[report_name] = idx

        logger.debug(
            f"Добавлен отчет #{idx}: {report_name} -> {index_name} "
            f"({len(description)} символов)"
        )

    # === Построение структуры indices ===
    # Группируем отчеты по индексам
    index_to_report_ids: Dict[str, List[int]] = {}

    for report_name, index_name in mapping.items():
        if report_name in report_id_by_name:
            if index_name not in index_to_report_ids:
                index_to_report_ids[index_name] = []
            index_to_report_ids[index_name].append(report_id_by_name[report_name])

    # Формируем список индексов
    indices: List[Dict[str, Any]] = []

    for index_name in sorted(index_to_report_ids.keys()):
        report_ids = sorted(index_to_report_ids[index_name])
        display_name = INDEX_DISPLAY_NAMES.get(index_name, index_name)

        index_entry = {
            "name": index_name,
            "display_name": display_name,
            "report_ids": report_ids
        }
        indices.append(index_entry)

        logger.debug(
            f"Индекс '{index_name}': {len(report_ids)} отчетов, "
            f"IDs: {report_ids}"
        )

    # === Сборка итогового контейнера ===
    container = {
        "reports": reports,
        "indices": indices,
        "total_reports": len(reports),
        "total_indices": len(indices)
    }

    # Конвертация в JSON строку
    # ensure_ascii=False для сохранения русских символов без экранирования
    # indent=None для компактности (без отступов)
    json_string = json.dumps(container, ensure_ascii=False)

    # Логирование статистики
    total_chars = len(json_string)
    # Грубая оценка токенов: ~3 символа = 1 токен для русского текста
    estimated_tokens = total_chars // 3

    logger.info(
        f"JSON-контейнер создан: {len(reports)} отчетов, {len(indices)} индексов"
    )
    logger.info(
        f"Размер JSON: {total_chars:,} символов (~{estimated_tokens:,} токенов)"
    )

    # Валидация: проверяем что все 22 отчета включены
    if len(reports) != 22:
        logger.warning(
            f"Ожидалось 22 отчета, но включено {len(reports)}. "
            f"Проверьте загрузку описаний."
        )

    # Валидация: проверяем что все 7 индексов представлены
    if len(indices) != 7:
        logger.warning(
            f"Ожидалось 7 индексов, но получено {len(indices)}. "
            f"Проверьте маппинг отчетов."
        )

    return json_string


def get_json_container_stats(json_container: str) -> Dict[str, Any]:
    """
    Получить статистику по JSON-контейнеру.

    Полезно для отладки и мониторинга размера данных.

    Args:
        json_container: JSON-строка от build_json_container()

    Returns:
        Dict со статистикой:
        {
            "total_chars": int,
            "estimated_tokens": int,
            "total_reports": int,
            "total_indices": int,
            "reports_per_index": Dict[str, int],
            "is_valid": bool
        }

    Example:
        >>> json_str = build_json_container(descriptions)
        >>> stats = get_json_container_stats(json_str)
        >>> print(f"Токенов: {stats['estimated_tokens']}")
    """
    try:
        data = json.loads(json_container)
    except json.JSONDecodeError as e:
        return {
            "total_chars": len(json_container),
            "estimated_tokens": len(json_container) // 3,
            "total_reports": 0,
            "total_indices": 0,
            "reports_per_index": {},
            "is_valid": False,
            "error": str(e)
        }

    # Подсчет отчетов по индексам
    reports_per_index = {}
    for index_info in data.get("indices", []):
        index_name = index_info.get("name", "Unknown")
        report_ids = index_info.get("report_ids", [])
        reports_per_index[index_name] = len(report_ids)

    total_chars = len(json_container)

    return {
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 3,
        "total_reports": data.get("total_reports", 0),
        "total_indices": data.get("total_indices", 0),
        "reports_per_index": reports_per_index,
        "is_valid": (
            data.get("total_reports", 0) == 22 and
            data.get("total_indices", 0) == 7
        )
    }


def build_batch_relevance_prompt(question: str, json_container: str) -> str:
    """
    Создает промпт для batch-оценки релевантности всех 22 отчетов за один запрос.

    Загружает шаблон промпта из файла data/batch_relevance_prompt.md и подставляет
    вопрос пользователя и JSON-контейнер с описаниями отчетов.

    Args:
        question: Вопрос пользователя (строка на русском или английском)
        json_container: JSON-контейнер с описаниями всех 22 отчетов
                       (результат build_json_container())

    Returns:
        str: Полный промпт для отправки в Claude API.

    Notes:
        - Шаблон промпта хранится в data/batch_relevance_prompt.md
        - Промпт требует JSON-ответ БЕЗ markdown-разметки
        - Рекомендуется использовать с temperature=0 для консистентности
    """
    # Валидация входных данных
    if not question or not question.strip():
        raise ValueError("Вопрос не может быть пустым")

    if not json_container or not json_container.strip():
        raise ValueError("JSON-контейнер не может быть пустым")

    # Путь к файлу шаблона промпта
    prompt_template_path = Path(__file__).parent.parent / "data" / "batch_relevance_prompt.md"

    # Загрузка шаблона из файла
    if prompt_template_path.exists():
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        # Подстановка переменных
        prompt = prompt_template.format(
            question=question,
            json_container=json_container
        )
    else:
        # Fallback - если файл не найден, выбрасываем ошибку
        raise FileNotFoundError(f"Файл шаблона промпта не найден: {prompt_template_path}")

    # Логирование размера промпта
    prompt_size = len(prompt)
    prompt_without_json = prompt_size - len(json_container)

    logger.debug(
        f"Batch-промпт создан: {prompt_size:,} символов "
        f"(~{prompt_size // 3:,} токенов), "
        f"из них промпт без JSON: {prompt_without_json:,} символов"
    )

    return prompt


# === BATCH ОЦЕНКА РЕЛЕВАНТНОСТИ ===


def parse_batch_response(response_text: str) -> Dict[str, Any]:
    """
    Парсит ответ модели Claude и извлекает JSON с оценками.

    Обрабатывает различные форматы ответа:
    - Чистый JSON
    - JSON в markdown-блоке (```json ... ```)
    - JSON с текстом до/после

    Args:
        response_text: Текст ответа от Claude API

    Returns:
        Dict с распарсенным JSON (содержит "evaluations")

    Raises:
        ValueError: Если не удалось распарсить JSON

    Example:
        >>> response = '{"evaluations": [{"id": 1, "name": "Test", "relevance": 85}]}'
        >>> result = parse_batch_response(response)
        >>> result["evaluations"][0]["relevance"]
        85
    """
    if not response_text or not response_text.strip():
        raise ValueError("Пустой ответ от API")

    text = response_text.strip()

    # Попытка 1: Убрать markdown-разметку ```json ... ```
    # Паттерн для блока кода с json или без указания языка
    markdown_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    match = re.search(markdown_pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()
        logger.debug("Убрана markdown-разметка из ответа")

    # Попытка 2: Найти JSON объект в тексте (от первой { до последней })
    json_start = text.find('{')
    json_end = text.rfind('}')

    if json_start == -1 or json_end == -1 or json_start >= json_end:
        raise ValueError(f"Не найден JSON объект в ответе: {text[:200]}...")

    json_text = text[json_start:json_end + 1]

    # Попытка парсинга JSON
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        # Попытка исправить типичные ошибки
        # 1. Trailing commas
        json_text_fixed = re.sub(r',\s*([}\]])', r'\1', json_text)
        try:
            data = json.loads(json_text_fixed)
            logger.debug("JSON распарсен после удаления trailing commas")
        except json.JSONDecodeError:
            raise ValueError(f"Ошибка парсинга JSON: {e}. Текст: {json_text[:500]}...")

    # Валидация структуры
    if "evaluations" not in data:
        raise ValueError(f"В ответе отсутствует ключ 'evaluations': {list(data.keys())}")

    if not isinstance(data["evaluations"], list):
        raise ValueError(f"'evaluations' должен быть списком, получено: {type(data['evaluations'])}")

    return data


def validate_batch_evaluations(
    evaluations: List[Dict[str, Any]],
    expected_count: int = 22
) -> tuple[bool, List[str]]:
    """
    Валидирует список оценок из batch-ответа.

    Проверяет:
    - Количество оценок (ожидается 22)
    - Наличие обязательных полей (id, name, relevance)
    - Диапазон релевантности (0-100)

    Args:
        evaluations: Список оценок из parse_batch_response()
        expected_count: Ожидаемое количество оценок (по умолчанию 22)

    Returns:
        tuple[bool, List[str]]: (is_valid, list_of_errors)

    Example:
        >>> evals = [{"id": 1, "name": "Test", "relevance": 85, "reason": "..."}]
        >>> is_valid, errors = validate_batch_evaluations(evals, expected_count=1)
        >>> is_valid
        True
    """
    errors = []

    # Проверка количества
    if len(evaluations) != expected_count:
        errors.append(
            f"Ожидалось {expected_count} оценок, получено {len(evaluations)}"
        )

    # Проверка каждой оценки
    seen_ids = set()
    seen_names = set()

    for i, eval_item in enumerate(evaluations):
        # Проверка обязательных полей
        if "id" not in eval_item:
            errors.append(f"Оценка #{i}: отсутствует поле 'id'")
        else:
            eval_id = eval_item["id"]
            if eval_id in seen_ids:
                errors.append(f"Оценка #{i}: дублирующийся id={eval_id}")
            seen_ids.add(eval_id)

        if "name" not in eval_item:
            errors.append(f"Оценка #{i}: отсутствует поле 'name'")
        else:
            name = eval_item["name"]
            if name in seen_names:
                errors.append(f"Оценка #{i}: дублирующееся имя '{name}'")
            seen_names.add(name)

        if "relevance" not in eval_item:
            errors.append(f"Оценка #{i}: отсутствует поле 'relevance'")
        else:
            relevance = eval_item["relevance"]
            # Проверка типа
            if not isinstance(relevance, (int, float)):
                errors.append(
                    f"Оценка #{i} ({eval_item.get('name', '?')}): "
                    f"relevance должен быть числом, получено {type(relevance)}"
                )
            # Проверка диапазона
            elif not (0 <= relevance <= 100):
                errors.append(
                    f"Оценка #{i} ({eval_item.get('name', '?')}): "
                    f"relevance={relevance} вне диапазона 0-100"
                )

    is_valid = len(errors) == 0
    return is_valid, errors


def convert_evaluations_to_dict(evaluations: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Преобразует список оценок в словарь {имя_отчета: релевантность}.

    Формат совместим с возвратом evaluate_report_relevance().

    Args:
        evaluations: Список оценок из parse_batch_response()

    Returns:
        Dict[str, float]: {имя_отчета: релевантность (0-100)}

    Example:
        >>> evals = [
        ...     {"id": 1, "name": "Report_A", "relevance": 85},
        ...     {"id": 2, "name": "Report_B", "relevance": 30}
        ... ]
        >>> convert_evaluations_to_dict(evals)
        {'Report_A': 85.0, 'Report_B': 30.0}
    """
    result = {}

    for eval_item in evaluations:
        name = eval_item.get("name", "Unknown")
        relevance = eval_item.get("relevance", 0)

        # Преобразование в float и clamp в диапазон 0-100
        try:
            relevance_float = float(relevance)
            relevance_float = max(0.0, min(100.0, relevance_float))
        except (TypeError, ValueError):
            logger.warning(f"Не удалось преобразовать relevance для '{name}': {relevance}")
            relevance_float = 0.0

        result[name] = relevance_float

    return result


async def evaluate_batch_relevance(
    question: str,
    json_container: str,
    api_key: str | None = None
) -> Dict[str, float]:
    """
    Выполняет batch-оценку релевантности всех отчетов за один API запрос.

    Отправляет JSON-контейнер с описаниями всех 22 отчетов и получает
    оценки релевантности для каждого из них за один вызов Claude API.

    Args:
        question: Вопрос пользователя
        json_container: JSON-контейнер с описаниями всех 22 отчетов
                       (результат build_json_container())
        api_key: API ключ Anthropic. Если None, используется ANTHROPIC_API_KEY из config

    Returns:
        Dict[str, float]: {имя_отчета: оценка_релевантности (0-100)}
        Формат совместим с evaluate_report_relevance()

    Raises:
        ValueError: Если question или json_container пустые, или api_key недоступен

    Performance:
        - Один API запрос вместо 22 параллельных
        - Типичное время выполнения: 5-15 секунд (зависит от размера контейнера)
        - MAX_TOKENS: 4000 (достаточно для JSON с 22 оценками и обоснованиями)

    Example:
        >>> descriptions = load_report_descriptions()
        >>> json_container = build_json_container(descriptions)
        >>> results = await evaluate_batch_relevance(
        ...     "Какое освещение в номерах?",
        ...     json_container
        ... )
        >>> len(results)
        22
        >>> results["Структурированный_отчет_аудита"] > 50
        True

    Notes:
        - Использует retry логику с exponential backoff (3 попытки)
        - При ошибке парсинга возвращает пустой словарь с логированием
        - Temperature=0 для консистентности оценок
    """
    # Валидация входных данных
    if not question or not question.strip():
        raise ValueError("Вопрос не может быть пустым")

    if not json_container or not json_container.strip():
        raise ValueError("JSON-контейнер не может быть пустым")

    # Получить API key
    if api_key is None:
        api_key = ANTHROPIC_API_KEY

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY не установлен. "
            "Проверьте файл .env или передайте api_key явно."
        )

    # Построить промпт
    prompt = build_batch_relevance_prompt(question, json_container)

    logger.info(
        f"Начинаем batch-оценку релевантности для вопроса: '{question[:100]}...'"
    )

    # Создать клиент
    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Retry с exponential backoff
    backoff = 1

    start_time = time.time()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Async запрос к Claude API с таймаутом
            response = await asyncio.wait_for(
                client.messages.create(
                    model=HAIKU_MODEL,
                    max_tokens=BATCH_MAX_TOKENS,
                    temperature=TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=BATCH_REQUEST_TIMEOUT
            )

            # Извлечь текст ответа
            response_text = response.content[0].text

            logger.debug(f"Получен ответ от API: {len(response_text)} символов")

            # Парсинг ответа
            parsed_data = parse_batch_response(response_text)
            evaluations = parsed_data["evaluations"]

            # Валидация оценок
            is_valid, errors = validate_batch_evaluations(evaluations)

            if not is_valid:
                logger.warning(f"Проблемы с валидацией оценок: {errors}")
                # Продолжаем с тем что есть, но логируем ошибки

            # Преобразование в словарь
            relevance_scores = convert_evaluations_to_dict(evaluations)

            elapsed = time.time() - start_time

            logger.info(
                f"Batch-оценка релевантности завершена за {elapsed:.2f}s. "
                f"Обработано {len(relevance_scores)} отчетов."
            )

            # Топ-3 логируется в вызывающей функции evaluate_report_relevance()
            # чтобы избежать дублирования в логах

            return relevance_scores

        except RateLimitError as e:
            if attempt == MAX_RETRIES:
                logger.error(
                    f"Rate limit после {MAX_RETRIES} попыток. "
                    f"Используется пустой словарь."
                )
                return {}

            logger.warning(
                f"Rate limit (попытка {attempt}/{MAX_RETRIES}). "
                f"Ожидание {backoff}s перед повтором..."
            )
            await asyncio.sleep(backoff)
            backoff *= 2  # Exponential backoff: 1s, 2s, 4s

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout ({BATCH_REQUEST_TIMEOUT}s) для batch-запроса. "
                f"Используется пустой словарь."
            )
            return {}

        except ValueError as e:
            # Ошибка парсинга JSON
            logger.error(f"Ошибка парсинга ответа: {e}")
            return {}

        except Exception as e:
            logger.exception(f"Ошибка batch-оценки релевантности: {e}")
            return {}

    # Если все попытки исчерпаны
    logger.error(
        f"Исчерпаны попытки для batch-запроса. Используется пустой словарь."
    )
    return {}


# Старый inline код перемещен в файл data/batch_relevance_prompt.md
# Функция теперь загружает шаблон из файла для удобства редактирования
# DEPRECATED функция _legacy_build_relevance_prompt_inline() удалена - содержала ошибки


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

    Использует batch-механизм для оценки релевантности всех 22 типов отчетов
    за один API запрос к Claude Haiku 4.5. Все описания отчетов упаковываются
    в JSON-контейнер и отправляются одним запросом.

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
        - Один API запрос вместо 22 параллельных
        - JSON-контейнер содержит все описания (~55k токенов)
        - Типичное время выполнения: 5-15 секунд

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

    # === BATCH-МЕХАНИЗМ ОЦЕНКИ РЕЛЕВАНТНОСТИ ===
    #
    # Вместо 22 параллельных запросов используем один batch-запрос:
    # 1. build_json_container() упаковывает все 22 описания отчетов в структурированный JSON
    #    Это позволяет передать всю информацию в одном запросе к Claude API
    #
    # 2. evaluate_batch_relevance() отправляет JSON-контейнер и получает оценки для всех отчетов
    #    Возвращает Dict[str, float] - тот же формат что и раньше
    #    Это снижает количество API вызовов с 22 до 1, уменьшая latency и стоимость

    # Упаковать все описания отчетов в единый JSON-контейнер
    # JSON содержит структуру: reports (22 шт), indices (7 категорий), метаданные
    json_container = build_json_container(report_descriptions)
    logger.info(f"JSON-контейнер создан: {len(json_container)} символов")

    # Выполнить batch-оценку релевантности за один API запрос
    # evaluate_batch_relevance() внутри вызывает build_batch_relevance_prompt()
    # и возвращает Dict[str, float] - совместимо с предыдущим форматом
    start_time = time.time()
    relevance_scores = await evaluate_batch_relevance(
        question=question,
        json_container=json_container,
        api_key=api_key
    )
    elapsed = time.time() - start_time

    # Результат уже в формате Dict[str, float], совместимом с возвращаемым типом
    # Нет необходимости в преобразовании - evaluate_batch_relevance() возвращает готовый словарь

    logger.info(
        f"Оценка релевантности завершена за {elapsed:.2f}s. "
        f"Обработано {len(relevance_scores)} отчетов."
    )

    # Логировать топ-3 наиболее релевантных отчета
    if relevance_scores:
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
