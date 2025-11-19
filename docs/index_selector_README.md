# Index Selector - Выбор релевантного индекса

## Описание

`index_selector.py` - модуль для выбора наиболее релевантного RAG индекса на основе оценок отчетов. Является второй частью Router Agent системы VoxPersona.

## Архитектура

```
Запрос пользователя
        ↓
relevance_evaluator.py → {report_name: relevance_score}
        ↓
index_selector.py → {index_name: avg_relevance}
        ↓
Выбран индекс с max(avg_relevance)
```

## Основные компоненты

### 1. INDEX_MAPPING

Константа, содержащая маппинг 7 индексов на 22 отчета:

| Индекс | Количество отчетов | Отчеты |
|--------|-------------------|---------|
| `Dizayn` | 1 | Структурированный_отчет_аудита |
| `Intervyu` | 3 | Общие_факторы, Отчет_о_связках, Факторы_в_этом_заведении |
| `Iskhodniki_dizayn` | 1 | Аудит_Дизайна |
| `Iskhodniki_obsledovanie` | 1 | Обследование |
| `Itogovye_otchety` | 6 | Краткое резюме, Ощущения, Заполняемость, Итоговый, Отдых, Рекомендации |
| `Otchety_po_dizaynu` | 5 | Дизайн и архитектура, Сильные стороны, Недостатки, Ожидания, Противоречия |
| `Otchety_po_obsledovaniyu` | 5 | Востребованность, Качество инфраструктуры, Клиентский опыт, Маршруты, Обустройство |

**Всего: 22 отчета**

### 2. select_most_relevant_index()

Главная функция модуля. Выбирает индекс с наивысшей совокупной релевантностью.

**Алгоритм:**
1. Для каждого индекса находит все его отчеты в `report_relevance`
2. Вычисляет среднее арифметическое релевантностей найденных отчетов
3. Выбирает индекс с максимальной средней релевантностью
4. При равных оценках выбирается первый по алфавиту

**Параметры:**
- `report_relevance: Dict[str, float]` - словарь релевантностей отчетов от `relevance_evaluator`
- `index_mapping: Optional[Dict[str, List[str]]]` - кастомный маппинг (по умолчанию `INDEX_MAPPING`)

**Возвращает:**
- `str` - название индекса с наивысшей релевантностью

**Пример использования:**

```python
from src.index_selector import select_most_relevant_index

# Релевантности отчетов (от relevance_evaluator)
report_relevance = {
    "Дизайн и архитектура": 0.95,
    "Сильные стороны": 0.90,
    "Недостатки": 0.85,
    "Обследование": 0.30
}

# Выбор индекса
best_index = select_most_relevant_index(report_relevance)
print(f"Выбран индекс: {best_index}")
# Вывод: Выбран индекс: Otchety_po_dizaynu
```

### 3. validate_index_mapping()

Проверяет корректность маппинга индексов.

**Проверки:**
- Все индексы существуют в `available_rags` (если передан)
- Нет пустых списков отчетов
- Нет дублирующихся отчетов между индексами

**Пример:**

```python
from src.index_selector import validate_index_mapping, INDEX_MAPPING

# Валидация дефолтного маппинга
is_valid = validate_index_mapping(INDEX_MAPPING)
print(f"INDEX_MAPPING валиден: {is_valid}")
# Вывод: INDEX_MAPPING валиден: True
```

### 4. get_index_statistics()

Возвращает статистику по маппингу индексов.

**Пример:**

```python
from src.index_selector import get_index_statistics

stats = get_index_statistics()
for index_name, count in sorted(stats.items()):
    print(f"{index_name}: {count} отчетов")

# Вывод:
# Dizayn: 1 отчетов
# Intervyu: 3 отчетов
# Iskhodniki_dizayn: 1 отчетов
# Iskhodniki_obsledovanie: 1 отчетов
# Itogovye_otchety: 6 отчетов
# Otchety_po_dizaynu: 5 отчетов
# Otchety_po_obsledovaniyu: 5 отчетов
```

## Обработка граничных случаев

### 1. Пустой словарь релевантностей

```python
select_most_relevant_index({})
# Raises: ValueError("report_relevance не может быть пустым")
```

### 2. Отсутствующие отчеты

Если ни один отчет индекса не найден в `report_relevance`, индекс получает релевантность `0.0`:

```python
report_rel = {
    "Неизвестный отчет 1": 0.9,
    "Неизвестный отчет 2": 0.8
}

result = select_most_relevant_index(report_rel)
# Вывод: 'Dizayn' (индекс по умолчанию при всех нулях)
```

### 3. Частичное покрытие отчетов индекса

Среднее вычисляется **только по присутствующим** отчетам:

```python
report_rel = {
    "Краткое резюме": 1.0,      # Itogovye_otchety
    "Ощущения": 0.9,            # Itogovye_otchety
    # Остальные 4 отчета из Itogovye_otchety отсутствуют
    "Обследование": 0.5         # Iskhodniki_obsledovanie
}

result = select_most_relevant_index(report_rel)
# Itogovye_otchety: (1.0 + 0.9) / 2 = 0.95
# Iskhodniki_obsledovanie: 0.5 / 1 = 0.5
# Вывод: 'Itogovye_otchety'
```

## Логирование

Модуль использует стандартный Python `logging`:

**INFO уровень:**
- Начало выбора индекса
- Топ-3 индекса с релевантностями
- Выбранный индекс и его релевантность

**WARNING уровень:**
- Индексы без найденных отчетов в `report_relevance`
- Возврат индекса по умолчанию при всех нулях

**DEBUG уровень:**
- Входные данные (`report_relevance`)
- Релевантность каждого индекса

**Пример настройки логирования:**

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest tests/test_index_selector.py -v

# С покрытием кода
pytest tests/test_index_selector.py -v --cov=src.index_selector --cov-report=term-missing

# Только определенный класс тестов
pytest tests/test_index_selector.py::TestSelectMostRelevantIndex -v
```

### Покрытие кода

Текущее покрытие: **83%**

Непокрытые строки: только блок `if __name__ == "__main__"` (демонстрационные примеры)

### Категории тестов

| Категория | Количество тестов | Описание |
|-----------|------------------|----------|
| TestSelectMostRelevantIndex | 8 | Тесты основной функции выбора |
| TestValidateIndexMapping | 6 | Тесты валидации маппинга |
| TestIndexMappingStructure | 6 | Тесты структуры INDEX_MAPPING |
| TestGetIndexStatistics | 3 | Тесты статистики |
| TestLoadIndexMappingFromFile | 1 | Тест незавершенной функциональности |
| TestIntegration | 3 | Интеграционные тесты |
| TestLogging | 2 | Тесты логирования |

**Всего: 29 тестов**

## Интеграция с Router Agent

### Полный workflow

```python
from src.relevance_evaluator import evaluate_report_relevance
from src.index_selector import select_most_relevant_index

# Шаг 1: Оценка релевантности отчетов
user_query = "Какие проблемы с дизайном отеля?"
report_relevance = evaluate_report_relevance(user_query)
# Результат: {'Дизайн и архитектура': 0.95, 'Сильные стороны': 0.90, ...}

# Шаг 2: Выбор индекса
best_index = select_most_relevant_index(report_relevance)
# Результат: 'Otchety_po_dizaynu'

# Шаг 3: Использование выбранного индекса
# ... запрос к RAG с индексом best_index
```

## Производительность

- **Время выполнения:** O(N), где N - количество индексов (константа = 7)
- **Память:** O(M), где M - количество отчетов в `report_relevance` (обычно ≤ 22)
- **Синхронная функция** - не требует async/await

Типичное время выполнения: **< 1 мс**

## Будущие улучшения

### Планируемая функциональность

1. **load_index_mapping_from_file()**
   - Автоматический парсинг `Description/files_list.md`
   - Динамическое построение INDEX_MAPPING
   - Кэширование результата

2. **Альтернативные методы агрегации**
   - Взвешенное среднее (приоритет основным отчетам)
   - Максимальная релевантность (вместо средней)
   - Медиана релевантностей

3. **Метрики качества**
   - Уверенность в выборе индекса
   - Расстояние между топ-1 и топ-2 индексами
   - Coverage score (процент найденных отчетов индекса)

4. **Экспорт результатов**
   - JSON отчет с детальными метриками
   - Визуализация распределения релевантностей
   - История выборов для A/B тестирования

## Константы и настройки

| Константа | Значение | Описание |
|-----------|---------|----------|
| `DEFAULT_INDEX` | `"Dizayn"` | Индекс по умолчанию при неудачном выборе |
| Количество индексов | 7 | Фиксированное количество RAG индексов |
| Количество отчетов | 22 | Общее количество отчетов |

## Авторы

VoxPersona Development Team

## Лицензия

Proprietary - VoxPersona Project
