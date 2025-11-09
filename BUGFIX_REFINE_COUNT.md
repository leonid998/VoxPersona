# Исправление Ошибки 5: Сброс счетчика refine_count

## Проблема
Защита от зацикливания НЕ работала - счетчик `refine_count` сбрасывался в 0 при каждом уточнении вопроса.

## Причина
Счетчик НЕ передавался между функциями через параметры:
- `make_query_expansion_markup()` - не принимала параметр
- `show_expanded_query_menu()` - не принимала параметр
- `handle_expand_refine()` - не передавала параметр при вызове

## Решение (4 шага)

### ✅ ШАГ 1: markups.py (строки 340-345, 360, 381)
**Было:**
```python
def make_query_expansion_markup(
    original_question: str,
    expanded_question: str,
    conversation_id: str,
    deep_search: bool
) -> InlineKeyboardMarkup:
    ...
    user_states[temp_key] = {
        ...
        "refine_count": 0  # ❌ ВСЕГДА 0!
    }
```

**Стало:**
```python
def make_query_expansion_markup(
    original_question: str,
    expanded_question: str,
    conversation_id: str,
    deep_search: bool,
    refine_count: int = 0  # ✅ Добавлен параметр
) -> InlineKeyboardMarkup:
    ...
    user_states[temp_key] = {
        ...
        "refine_count": refine_count  # ✅ Сохраняем переданное значение
    }
```

### ✅ ШАГ 2: run_analysis.py (строки 122-129, 143, 161)
**Было:**
```python
async def show_expanded_query_menu(
    chat_id: int,
    app: Client,
    original: str,
    expanded: str,
    conversation_id: str,
    deep_search: bool
):
    ...
    markup = make_query_expansion_markup(
        ...
        deep_search=deep_search
        # ❌ refine_count НЕ передается!
    )
```

**Стало:**
```python
async def show_expanded_query_menu(
    chat_id: int,
    app: Client,
    original: str,
    expanded: str,
    conversation_id: str,
    deep_search: bool,
    refine_count: int = 0  # ✅ Добавлен параметр
):
    ...
    markup = make_query_expansion_markup(
        ...
        deep_search=deep_search,
        refine_count=refine_count  # ✅ Передаем счетчик
    )
```

### ✅ ШАГ 3: run_analysis.py (строка 187)
**Было:**
```python
await show_expanded_query_menu(
    ...
    deep_search=deep_search
)
```

**Стало:**
```python
await show_expanded_query_menu(
    ...
    deep_search=deep_search,
    refine_count=0  # ✅ Первая попытка
)
```

### ✅ ШАГ 4: handlers.py (строка 2597)
**Было:**
```python
await show_expanded_query_menu(
    ...
    deep_search=deep_search
)
```

**Стало:**
```python
await show_expanded_query_menu(
    ...
    deep_search=deep_search,
    refine_count=refine_count + 1  # ✅ Передаем инкрементированный счетчик
)
```

## Результат

### Как это работает теперь:

1. **Первый вопрос** → `refine_count=0` (run_analysis.py:187)
2. **Уточнение 1** → `refine_count=1` (handlers.py:2597)
3. **Уточнение 2** → `refine_count=2`
4. **Уточнение 3** → `refine_count=3`
5. **Попытка 4** → ❌ БЛОКИРОВКА (handlers.py:2568-2573)

### Защита от зацикливания:
```python
if refine_count >= 3:
    await callback.answer(
        "⚠️ Достигнут лимит уточнений (3). Отправьте вопрос как есть или начните заново.",
        show_alert=True
    )
    return
```

## Измененные файлы:
- ✅ `src/markups.py` (строки 340-395)
- ✅ `src/run_analysis.py` (строки 122-188)
- ✅ `src/handlers.py` (строка 2597)

## Тестирование:
```bash
# Проверка синтаксиса
cd C:/Users/l0934/Projects/VoxPersona
python -m py_compile src/handlers.py src/markups.py src/run_analysis.py
✅ Все файлы синтаксически корректны
```

## Статус: ✅ ИСПРАВЛЕНО
Теперь счетчик `refine_count` **сохраняется** между вызовами и **защищает** от зацикливания.
