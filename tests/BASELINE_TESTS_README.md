# Baseline Тесты для classify_query

Документация по baseline тестам функции `classify_query` из модуля `src/analysis.py`.

## Назначение

Baseline тесты предназначены для **фиксации текущего поведения** функции `classify_query` перед внедрением Router Agent.

## Текущее состояние системы

- **Функция**: `classify_query(text: str) -> str`
- **Локация**: `src/analysis.py` строки 432-444
- **Функциональность**: Классификация запроса на 2 категории
  - "дизайн" - вопросы о дизайне интерьера отеля
  - "интервью" - вопросы о мнениях и впечатлениях гостей
  - "Не определено" - для ошибок парсинга JSON
- **Покрытие**: 2/7 индексов (28.6%)

## Структура тестов

### Unit тесты (быстрые, с мокированием)

Файл: `tests/test_baseline_classify.py`

Класс: `TestClassifyQueryBaseline`

Тесты с мокированием `send_msg_to_model` и `fetch_prompt_by_name`. Не требуют API вызовов.

**Список тестов:**

| Тест | Описание |
|------|---------|
| `test_classify_query_design` | Классификация вопроса о дизайне → "дизайн" |
| `test_classify_query_interview` | Классификация вопроса об интервью → "интервью" |
| `test_classify_query_with_whitespace` | Обработка пробелов в начале/конце ответа |
| `test_classify_query_invalid_json` | Обработка невалидного JSON (логирование ошибки) |
| `test_classify_query_missing_category_field` | Отсутствие поля "category" в JSON |
| `test_classify_query_empty_category` | Пустое значение category (возвращает "") |
| `test_classify_query_fetch_prompt_error` | Ошибка при получении промпта (не перехватывается) |
| `test_classify_query_send_msg_error` | Ошибка API при вызове (не перехватывается) |
| `test_classify_query_calls_with_correct_parameters` | Проверка правильности передачи параметров |

**Запуск:**
```bash
# Все unit тесты
pytest tests/test_baseline_classify.py -m "not slow"

# Конкретный тест
pytest tests/test_baseline_classify.py::TestClassifyQueryBaseline::test_classify_query_design -v

# С выводом переменных и логов
pytest tests/test_baseline_classify.py -m "not slow" -v -s
```

**Результаты:** 9 тестов, ~6 секунд

### Integration тесты (медленные, с реальным API)

Класс: `TestClassifyQueryBaselines`

**@pytest.mark.slow** - тесты запускаются только явно

Тесты используют реальный Claude Anthropic API и golden dataset.

**Список тестов:**

| Тест | Описание |
|------|---------|
| `test_baseline_on_golden_dataset` | Baseline метрики на 7+ вопросах из golden_dataset.json |
| `test_golden_dataset_exists` | Проверка существования и валидности golden dataset |

### Edge Case тесты (медленные, с API)

Класс: `TestClassifyQueryEdgeCases`

**@pytest.mark.slow** - тесты запускаются только явно

**Список тестов:**

| Тест | Описание |
|------|---------|
| `test_empty_query` | Поведение на пустом запросе |
| `test_very_long_query` | Поведение на очень длинном запросе |
| `test_special_characters_in_query` | Поведение на спецсимволах и Unicode |

## Запуск тестов

### Вариант 1: Только быстрые unit тесты (по умолчанию)

```bash
cd /c/Users/l0934/Projects/VoxPersona
pytest tests/test_baseline_classify.py
```

Результат: 9 пройденных тестов за ~6 секунд

### Вариант 2: Unit тесты с подробным выводом

```bash
pytest tests/test_baseline_classify.py::TestClassifyQueryBaseline -v
```

### Вариант 3: Все тесты включая медленные

```bash
pytest tests/test_baseline_classify.py -m slow -v -s
```

ВНИМАНИЕ: Будет сделано множество API вызовов к Claude. Может занять 1-3 минуты и потребить ограничение API.

### Вариант 4: Только медленные baseline тесты

```bash
pytest tests/test_baseline_classify.py::TestClassifyQueryBaselines::test_baseline_on_golden_dataset -v -s
```

Это выведет подробные baseline метрики:
- Распределение по категориям
- Среднее/мин/макс время выполнения
- Процент совпадений с ожиданиями
- Первые 10 примеров

### Вариант 5: Пропустить медленные тесты

```bash
pytest tests/test_baseline_classify.py -m "not slow" -v
```

## Baseline метрики

### Текущие показатели

На основе текущей реализации функции:

| Метрика | Значение | Примечание |
|---------|----------|-----------|
| Количество категорий | 2 | "дизайн", "интервью" |
| Покрытие индексов | 2/7 (28.6%) | Dizayn, Intervyu |
| Среднее время вызова | 1-2 сек | Зависит от Claude API |
| Обработка ошибок | Частичная | Только парсинг JSON |
| Точность | Неизмеримо | 7 индексов → 2 категории |

### Обнаруженные особенности

**Особенность 1: Пустая категория**
```python
# Текущее поведение
result_json.get("category", "Не определено")
# Если category = "", возвращает пустую строку
# Ожидаемое: возвращать "Не определено"
```

**Особенность 2: Отсутствие обработки исключений API**
```python
# Ошибки fetch_prompt_by_name не перехватываются
# Ошибки send_msg_to_model не перехватываются
# Try-except охватывает только json.loads()
```

## Golden Dataset

Файл: `tests/golden_dataset.json`

Структура:
```json
[
  {
    "question": "как сделано освещение в холле отеля",
    "expected_index": "Dizayn",
    "reasoning": "Вопрос о дизайне..."
  },
  ...
]
```

Используется для integration тестов и оценки baseline метрик.

## Использование результатов для Router Agent

После внедрения Router Agent, эти тесты позволяют:

1. **Сравнить производительность**
   - Новая система должна классифицировать все 7 индексов
   - Baseline показывает текущее состояние (2 индекса)

2. **Отследить регрессию**
   - Baseline metrics в test_baseline_on_golden_dataset
   - Сравнение с новой реализацией

3. **Выявить edge cases**
   - Edge case тесты покрывают граничные ситуации
   - Полезны для повышения надежности Router Agent

## PEP 8 и стандарты кода

- Type hints для всех функций и параметров
- Google style docstrings
- Следует PEP 8
- Использует pytest fixtures
- Mock/patch для изоляции тестов

## Примечания

- Integration тесты требуют `ANTHROPIC_API_KEY` в окружении
- Golden dataset содержит 7 вопросов
- Все быстрые тесты проходят на любой машине
- Медленные тесты требуют доступа в интернет

## Связь с проектом VoxPersona

- Проект: Система анализа отелей на основе RAG
- Модуль: `src/analysis.py`
- Функция: `classify_query(text: str) -> str`
- Роль: Маршрутизация запросов на разные RAG индексы
- Статус: Baseline для планируемого Router Agent

---

**Дата создания:** 2025-11-19
**Версия:** 1.0
**Автор:** Claude Code
