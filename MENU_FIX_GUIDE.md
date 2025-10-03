# 🎯 Руководство по исправлению меню VoxPersona

## Проблема

**Сейчас**: В чате остаются копии старых меню, загромождая переписку.

**Должно быть**:
1. Старое меню **исчезает** (кнопки удаляются)
2. Новое меню **ВСЕГДА появляется внизу** чата
3. Пользователь **никогда не остается** без активного меню

## Решение: MenuManager

### Импорт

```python
from menu_manager import send_menu_and_remove_old, clear_menus
from markups import (
    main_menu_markup,
    chats_menu_markup_dynamic,
    make_dialog_markup
)
```

### Основной паттерн

```python
# ✅ ПРАВИЛЬНО: Старое меню удаляется, новое появляется внизу
await send_menu_and_remove_old(
    chat_id=chat_id,
    app=app,
    text="Текст сообщения",
    reply_markup=get_menu()
)
```

## 📋 Примеры исправлений

### Пример 1: Удаление чата

**БЫЛО** (3 сообщения подряд):
```python
def handle_delete_chat_confirm(chat_id, conversation_id, username, app):
    conversation_manager.delete_conversation(chat_id, conversation_id)

    # Сообщение 1
    app.send_message(chat_id, "✅ Чат удален")

    # Сообщение 2 с меню
    app.send_message(
        chat_id,
        "Ваши чаты:",
        reply_markup=chats_menu_markup_dynamic(chat_id)
    )
```

**СТАЛО** (1 сообщение + меню внизу):
```python
async def handle_delete_chat_confirm(chat_id, conversation_id, username, app):
    conversation_manager.delete_conversation(chat_id, conversation_id)

    # Одно сообщение с результатом + меню внизу
    text = "✅ Чат удален\n\nВаши чаты:"

    await send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=chats_menu_markup_dynamic(chat_id)
    )
```

### Пример 2: Создание нового чата

**БЫЛО** (2 сообщения):
```python
def handle_new_chat(chat_id, app):
    new_conversation_id = conversation_manager.create_conversation(
        user_id=chat_id,
        username=username,
        first_question="Новый чат"
    )

    # Сообщение 1
    app.send_message(
        chat_id=chat_id,
        text="✨ Новый чат создан!"
    )

    # Сообщение 2 с меню
    app.send_message(
        chat_id=chat_id,
        text="Выберите действие:",
        reply_markup=make_dialog_markup(False)
    )
```

**СТАЛО** (1 сообщение + меню):
```python
async def handle_new_chat(chat_id, app):
    username = get_username_from_chat(chat_id, app)

    new_conversation_id = conversation_manager.create_conversation(
        user_id=chat_id,
        username=username,
        first_question="Новый чат"
    )

    # Очищаем историю меню (новый контекст)
    clear_menus(chat_id)

    # Объединяем текст + меню
    text = (
        "✨ Новый чат создан!\n\n"
        "Какую информацию вы хотели бы получить?\n\n"
        "Выберите действие:"
    )

    await send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=make_dialog_markup(False)
    )
```

### Пример 3: Переключение чата

**БЫЛО** (4+ сообщений):
```python
def handle_switch_chat_confirm(chat_id, conversation_id, app):
    conversation_manager.set_active_conversation(chat_id, conversation_id)
    conversation = conversation_manager.load_conversation(chat_id, conversation_id)

    # Сообщение 1
    app.send_message(chat_id, f"✅ Переключено на чат: {conversation.metadata.title}")

    # Сообщение 2
    app.send_message(chat_id, "📜 Последние сообщения:")

    # Сообщения 3, 4, 5... (история)
    for msg in messages:
        app.send_message(chat_id, f"{role_emoji} {msg.text}")

    # Последнее сообщение с меню
    app.send_message(
        chat_id,
        "Выберите действие:",
        reply_markup=make_dialog_markup(False)
    )
```

**СТАЛО** (1 сообщение + меню):
```python
async def handle_switch_chat_confirm(chat_id, conversation_id, app):
    conversation_manager.set_active_conversation(chat_id, conversation_id)
    conversation = conversation_manager.load_conversation(chat_id, conversation_id)

    if not conversation:
        app.send_message(chat_id, "❌ Не удалось загрузить чат")
        return

    messages = conversation_manager.get_messages(chat_id, conversation_id, limit=5)

    # Объединяем всё в одно сообщение
    text = f"✅ Переключено на чат: {conversation.metadata.title}\n\n"

    if messages:
        text += "📜 Последние 5 сообщений:\n\n"
        for msg in messages:
            role_emoji = "👤" if msg.type == "user_question" else "🤖"
            # Обрезаем длинные сообщения
            msg_preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
            text += f"{role_emoji} {msg_preview}\n\n"
    else:
        text += "💬 История пуста.\n\n"

    text += "Выберите действие:"

    await send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=make_dialog_markup(False)
    )
```

### Пример 4: Переименование чата

**БЫЛО** (2 сообщения):
```python
def handle_rename_chat_input(chat_id, new_name, app):
    conversation.metadata.title = new_name.strip()
    conversation_manager.save_conversation(conversation)

    # Сообщение 1
    app.send_message(chat_id, f"✅ Чат переименован в '{new_name}'")

    # Сообщение 2
    app.send_message(
        chat_id,
        "Ваши чаты:",
        reply_markup=chats_menu_markup_dynamic(chat_id)
    )
```

**СТАЛО** (1 сообщение + меню):
```python
async def handle_rename_chat_input(chat_id, new_name, app):
    state = user_states.get(chat_id, {})
    conversation_id = state.get("conversation_id")

    conversation = conversation_manager.load_conversation(chat_id, conversation_id)
    conversation.metadata.title = new_name.strip()
    conversation_manager.save_conversation(conversation)

    user_states[chat_id] = {}

    # Объединяем результат + меню
    text = f"✅ Чат переименован в '{new_name}'\n\nВаши чаты:"

    await send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=chats_menu_markup_dynamic(chat_id)
    )
```

## 🎯 Ключевые правила

### 1. ВСЕГДА объединяй текст и меню

```python
# ❌ ПЛОХО: 2 сообщения
app.send_message(chat_id, "Результат действия")
app.send_message(chat_id, "Меню", reply_markup=menu)

# ✅ ХОРОШО: 1 сообщение + меню
text = "Результат действия\n\nМеню"
await send_menu_and_remove_old(chat_id, app, text, menu)
```

### 2. Очищай историю при смене контекста

```python
# При создании нового чата
clear_menus(chat_id)
await send_menu_and_remove_old(...)

# При удалении последнего чата (создается новый)
clear_menus(chat_id)
await send_menu_and_remove_old(...)
```

### 3. После действия → результат + то же меню

```python
# Пользователь в "Меню чатов"
# → Удаляет чат
# → Показываем результат + возвращаем в "Меню чатов"

async def handle_delete_chat_confirm(...):
    # Удаляем чат
    conversation_manager.delete_conversation(...)

    # Результат + возврат в то же меню
    text = "✅ Чат удален\n\nВаши чаты:"
    await send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=chats_menu_markup_dynamic(chat_id)  # ← То же меню!
    )
```

## 📝 Чек-лист миграции функции

Для каждой функции проверь:

- [ ] Используется `send_menu_and_remove_old()` вместо прямой отправки
- [ ] Все сообщения объединены в одно (результат + меню)
- [ ] Если меняется контекст - вызван `clear_menus(chat_id)`
- [ ] После действия возвращается то же меню (если уместно)
- [ ] Длинные тексты обрезаются (preview для истории сообщений)

## 🛠️ Функции для исправления

### Высокий приоритет (критические):

1. **conversation_handlers.py**:
   - `handle_new_chat()` - строка 106-116
   - `handle_switch_chat_confirm()` - строка 198-228
   - `handle_rename_chat_input()` - строка 342-346
   - `handle_delete_chat_confirm()` - строка 449-453

2. **handlers.py**:
   - `handle_reports_command()` - строка 273-278
   - `handle_show_my_reports()` - строка 552-556
   - `handle_confirm_data()` - строка 690-692

### Средний приоритет:

3. **handlers.py**:
   - `handle_file_deletion()` - строка 632

## 🧪 Тестирование

После каждого исправления проверь:

1. ✅ Старое меню исчезает (кнопки удаляются)
2. ✅ Новое меню появляется внизу
3. ✅ В чате НЕТ дубликатов меню
4. ✅ Пользователь НЕ остается без меню

## ⏱️ Оценка времени

- 1 простая функция: **5-10 минут**
- 1 сложная функция (с историей сообщений): **15-20 минут**

**Всего**: 8 функций × 10 мин = **~1.5 часа**

## 🚀 Порядок действий

1. Открой `src/conversation_handlers.py`
2. Найди функцию `handle_delete_chat_confirm` (строка 449)
3. Примени паттерн из Примера 1
4. Сохрани и протестируй
5. Повтори для остальных функций

**Готов начать? Начнем с самой простой - `handle_rename_chat_input`!**
