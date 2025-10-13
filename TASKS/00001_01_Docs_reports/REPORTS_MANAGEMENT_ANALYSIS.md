# 📋 ДЕТАЛЬНЫЙ ОТЧЕТ: Анализ и План Реализации "Мои Отчеты"

**Дата:** 13.10.2025
**Проект:** VoxPersona
**Задача:** Реализация управления отчетами через TXT файл со списком

---

## 🔍 ИТОГИ АНАЛИЗА КОДА

### 1. ✅ СУЩЕСТВУЮЩИЕ РЕШЕНИЯ, КОТОРЫЕ НУЖНО ИСПОЛЬЗОВАТЬ

#### **1.1. Хранение отчетов (md_storage.py)**
**Локация:** `src/md_storage.py`

**Что есть:**
- ✅ Класс `MDStorageManager` - полноценный менеджер отчетов
- ✅ `ReportMetadata` - метаданные каждого отчета (file_path, user_id, username, timestamp, question, size_bytes, tokens, search_type)
- ✅ `index.json` - централизованный индекс всех отчетов
- ✅ Структура файлов: `md_reports/user_{user_id}/voxpersona_YYYYMMDD_HHMMSS.txt`

**Ключевые методы:**
```python
# Получить отчеты пользователя
md_storage_manager.get_user_reports(user_id, limit=None)  # limit=None для ВСЕХ

# Получить путь к файлу отчета
md_storage_manager.get_report_file_path(relative_path)

# Форматировать список для отображения
md_storage_manager.format_user_reports_for_display(user_id)

# Удалить запись из индекса
md_storage_manager._remove_from_index([file_paths])
```

#### **1.2. Работа с текстовыми файлами (file_sender.py)**
**Локация:** `src/file_sender.py`

**Что есть:**
- ✅ Функция `format_reports_for_file(reports)` - форматирует список отчетов в TXT
- ✅ Использование `BytesIO` для оптимальной работы с файлами
- ✅ Отправка через `app.send_document()`

**Пример использования:**
```python
from io import BytesIO
from file_sender import format_reports_for_file

# Получить отчеты
reports = md_storage_manager.get_user_reports(user_id, limit=None)

# Форматировать в текст
text_content = format_reports_for_file(reports)

# Создать TXT файл в памяти
txt_file = BytesIO(text_content.encode('utf-8'))
txt_file.name = f"reports_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# Отправить
await app.send_document(chat_id, txt_file, caption="📄 Список ваших отчетов")
```

#### **1.3. Автоматическая очистка меню (message_tracker.py)**
**Локация:** `src/message_tracker.py`

**Что есть:**
- ✅ Класс `MessageTracker` - интеллектуальная система отслеживания
- ✅ Автоматическая очистка устаревших элементов
- ✅ Типы сообщений: `menu`, `input_request`, `confirmation`, `status_message`, `info_message`

**Использование:**
```python
from message_tracker import track_and_send, clear_tracked_messages

# Отправить меню с автоочисткой
await track_and_send(
    chat_id=chat_id,
    app=app,
    text="Выберите действие:",
    reply_markup=keyboard,
    message_type="menu"  # или "input_request", "confirmation"
)

# Очистить все отслеживаемые сообщения
clear_tracked_messages(chat_id)
```

#### **1.4. Система callback'ов (handlers.py)**
**Локация:** `src/handlers.py`

**Что есть:**
- ✅ Обработчик callback'ов в функции `on_callback_query`
- ✅ Паттерн обработки: `data.startswith("префикс||")`
- ✅ Извлечение параметров: `data.split("||", 1)[1]`

---

## 🎯 ЧТО НУЖНО ДОПОЛНИТЕЛЬНО РЕАЛИЗОВАТЬ

### 2. 🆕 НОВАЯ ФУНКЦИОНАЛЬНОСТЬ

#### **2.1. Новые callback handlers**

**В файле:** `src/handlers.py`

```python
# 1. Отправка списка отчетов TXT
async def handle_reports_list_txt(chat_id: int, app: Client):
    """Отправляет список всех отчетов в виде TXT файла"""
    try:
        # Получить ВСЕ отчеты
        reports = md_storage_manager.get_user_reports(chat_id, limit=None)

        if not reports:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="📁 У вас пока нет отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            return

        # Форматировать в TXT
        from file_sender import format_reports_for_file
        text_content = format_reports_for_file(reports)

        # Создать файл в памяти
        txt_file = BytesIO(text_content.encode('utf-8'))
        txt_file.name = f"reports_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # Отправить файл
        await app.send_document(
            chat_id,
            txt_file,
            caption=f"📄 **Список ваших отчетов** ({len(reports)} шт.)\n\n"
                    "Укажите номер отчета для действий:"
        )

        # Отправить меню управления
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ Посмотреть", callback_data="report_action||view")],
            [InlineKeyboardButton("✏️ Переименовать", callback_data="report_action||rename")],
            [InlineKeyboardButton("🗑️ Удалить", callback_data="report_action||delete")],
            [InlineKeyboardButton("« Назад", callback_data="menu_chats")]
        ])

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="Выберите действие:",
            reply_markup=keyboard,
            message_type="menu"
        )

    except Exception as e:
        logging.error(f"Error sending reports list: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Ошибка при формировании списка отчетов.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )


# 2. Обработчик выбора действия
async def handle_report_action(chat_id: int, action: str, app: Client, user_states: dict):
    """Обработчик кнопок действий с отчетами"""

    # Сохранить выбранное действие в состоянии
    if chat_id not in user_states:
        user_states[chat_id] = {}
    user_states[chat_id]["report_action"] = action

    action_names = {
        "view": "👁️ Посмотреть отчет",
        "rename": "✏️ Переименовать отчет",
        "delete": "🗑️ Удалить отчет"
    }

    # Запросить номер отчета
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"**{action_names[action]}**\n\n"
             f"Введите номер отчета из списка:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ]),
        message_type="input_request"
    )


# 3. Обработчик ввода номера отчета
async def handle_report_number_input(message, app: Client, user_states: dict):
    """Обработчик ввода номера отчета"""
    chat_id = message.chat.id
    user_input = message.text.strip()

    # Проверить что пользователь в нужном состоянии
    if chat_id not in user_states or "report_action" not in user_states[chat_id]:
        return

    # Проверить что введено число
    try:
        report_num = int(user_input)
    except ValueError:
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Введите корректный номер отчета (число):",
            message_type="status_message"
        )
        return

    # Получить отчеты
    reports = md_storage_manager.get_user_reports(chat_id, limit=None)

    # Проверить номер
    if report_num < 1 or report_num > len(reports):
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=f"❌ Неверный номер. Введите число от 1 до {len(reports)}:",
            message_type="status_message"
        )
        return

    # Получить отчет
    selected_report = reports[report_num - 1]
    action = user_states[chat_id]["report_action"]

    # Сохранить выбранный отчет
    user_states[chat_id]["selected_report"] = selected_report

    # Выполнить действие
    if action == "view":
        await handle_report_view(chat_id, selected_report, app)
    elif action == "rename":
        await handle_report_rename_request(chat_id, selected_report, app, user_states)
    elif action == "delete":
        await handle_report_delete_confirm(chat_id, selected_report, app)


# 4. Просмотр отчета
async def handle_report_view(chat_id: int, report: ReportMetadata, app: Client):
    """Отправляет файл отчета пользователю"""
    try:
        file_path = md_storage_manager.get_report_file_path(report.file_path)

        if file_path and file_path.exists():
            await app.send_document(
                chat_id,
                str(file_path),
                caption=f"📄 **Отчет:**\n{report.question[:100]}"
            )

            # Меню "Назад к отчетам"
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="Отчет отправлен.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Назад к отчетам", callback_data="show_my_reports")]
                ]),
                message_type="menu"
            )
        else:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Файл отчета не найден.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Назад к отчетам", callback_data="show_my_reports")]
                ]),
                message_type="menu"
            )
    except Exception as e:
        logging.error(f"Error viewing report: {e}")


# 5. Запрос на переименование
async def handle_report_rename_request(chat_id: int, report: ReportMetadata, app: Client, user_states: dict):
    """Запрашивает новое название отчета"""
    user_states[chat_id]["awaiting_rename"] = True

    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"✏️ **Переименование отчета**\n\n"
             f"**Текущее название:**\n{report.question}\n\n"
             f"Введите новое название:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ]),
        message_type="input_request"
    )


# 6. Выполнение переименования
async def handle_report_rename_execute(message, app: Client, user_states: dict):
    """Выполняет переименование отчета"""
    chat_id = message.chat.id
    new_name = message.text.strip()

    if not new_name:
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Название не может быть пустым. Введите название:",
            message_type="status_message"
        )
        return

    selected_report = user_states[chat_id].get("selected_report")
    if not selected_report:
        return

    # Обновить question в индексе
    reports = md_storage_manager.load_reports_index()

    for report in reports:
        if report.file_path == selected_report.file_path:
            report.question = new_name
            break

    md_storage_manager.save_reports_index(reports)

    # Очистить состояние
    user_states[chat_id].pop("awaiting_rename", None)
    user_states[chat_id].pop("selected_report", None)
    user_states[chat_id].pop("report_action", None)

    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"✅ Отчет переименован:\n**{new_name}**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Назад к отчетам", callback_data="show_my_reports")]
        ]),
        message_type="menu"
    )


# 7. Подтверждение удаления
async def handle_report_delete_confirm(chat_id: int, report: ReportMetadata, app: Client):
    """Запрашивает подтверждение удаления"""

    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"⚠️ **Удаление отчета**\n\n"
             f"**Название:**\n{report.question[:100]}\n\n"
             f"Вы уверены?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"report_delete_yes||{report.file_path}")],
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ]),
        message_type="confirmation"
    )


# 8. Выполнение удаления
async def handle_report_delete_execute(chat_id: int, file_path: str, app: Client, user_states: dict):
    """Выполняет удаление отчета"""
    try:
        # Удалить физический файл
        full_path = md_storage_manager.get_report_file_path(file_path)
        if full_path and full_path.exists():
            full_path.unlink()

        # Удалить из индекса
        md_storage_manager._remove_from_index([file_path])

        # Очистить состояние
        if chat_id in user_states:
            user_states[chat_id].pop("selected_report", None)
            user_states[chat_id].pop("report_action", None)

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="✅ Отчет успешно удален.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к отчетам", callback_data="show_my_reports")]
            ]),
            message_type="menu"
        )
    except Exception as e:
        logging.error(f"Error deleting report: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Ошибка при удалении отчета.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к отчетам", callback_data="show_my_reports")]
            ]),
            message_type="menu"
        )
```

#### **2.2. Интеграция в систему обработки**

**В функции `on_callback_query` (handlers.py):**

```python
# Добавить в существующую цепочку elif
elif data == "show_my_reports":
    # ИЗМЕНИТЬ: Вызывать новый обработчик вместо старого
    await handle_reports_list_txt(c_id, app)

elif data.startswith("report_action||"):
    action = data.split("||", 1)[1]
    await handle_report_action(c_id, action, app, user_states)

elif data.startswith("report_delete_yes||"):
    file_path = data.split("||", 1)[1]
    await handle_report_delete_execute(c_id, file_path, app, user_states)
```

**В функции обработки текстовых сообщений:**

```python
# Добавить проверку состояния
if c_id in user_states:
    state = user_states[c_id]

    # Обработка ввода номера отчета
    if "report_action" in state and "awaiting_rename" not in state:
        await handle_report_number_input(message, app, user_states)
        return

    # Обработка ввода нового названия
    if "awaiting_rename" in state:
        await handle_report_rename_execute(message, app, user_states)
        return
```

---

## 📊 СВОДНАЯ ТАБЛИЦА: ЧТО ИСПОЛЬЗОВАТЬ VS ЧТО РЕАЛИЗОВАТЬ

| Компонент | Использовать существующее | Реализовать новое |
|-----------|---------------------------|-------------------|
| **Хранение отчетов** | ✅ `MDStorageManager` | ❌ Ничего |
| **Получение списка** | ✅ `get_user_reports(limit=None)` | ❌ Ничего |
| **Формирование TXT** | ✅ `format_reports_for_file()` | ❌ Ничего |
| **Отправка файла** | ✅ `app.send_document()` + `BytesIO` | ❌ Ничего |
| **Очистка меню** | ✅ `track_and_send()` | ❌ Ничего |
| **Callback система** | ✅ Паттерн `data.startswith()` | ❌ Ничего |
| **Обработчик "Мои отчеты"** | ❌ Старый (с inline кнопками) | ✅ **handle_reports_list_txt()** |
| **Выбор действия** | ❌ Нет | ✅ **handle_report_action()** |
| **Ввод номера** | ❌ Нет | ✅ **handle_report_number_input()** |
| **Просмотр** | ❌ Нет | ✅ **handle_report_view()** |
| **Переименование** | ❌ Нет | ✅ **handle_report_rename_***()** |
| **Удаление** | ❌ Нет | ✅ **handle_report_delete_***()** |

---

## 🎯 ФИНАЛЬНАЯ АРХИТЕКТУРА

### **FLOW НОВОЙ СИСТЕМЫ:**

```
1. Пользователь нажимает "📄 Мои отчеты"
   ↓
2. Бот отправляет TXT файл со списком (format_reports_for_file)
   + Меню с кнопками [Посмотреть] [Переименовать] [Удалить] [Назад]
   ↓
3. Пользователь нажимает кнопку действия
   ↓
4. Бот запрашивает номер отчета (input_request)
   ↓
5. Пользователь вводит номер
   ↓
6. В зависимости от действия:
   - Посмотреть → отправка файла отчета
   - Переименовать → запрос нового названия → обновление index.json
   - Удалить → подтверждение → удаление файла + запись из index.json
   ↓
7. Возврат к меню "Мои отчеты" или главному меню
```

### **КЛЮЧЕВЫЕ ПРЕИМУЩЕСТВА:**

✅ **Компактность** - используются ВСЕ существующие решения
✅ **Автоочистка** - `track_and_send()` убирает старые меню автоматически
✅ **Нумерация** - отчеты нумеруются в TXT файле (1, 2, 3...)
✅ **Подтверждения** - перед удалением требуется подтверждение
✅ **Переименование** - изменяет `question` в `index.json`
✅ **Удаление** - физическое удаление файла + запись из индекса

---

## 💡 ИТОГОВЫЙ ОТВЕТ

### **СУЩЕСТВУЮЩИЕ РЕШЕНИЯ:**
1. **MDStorageManager** - хранение и управление отчетами
2. **format_reports_for_file()** - формирование TXT списка
3. **track_and_send()** - автоматическая очистка меню
4. **BytesIO + send_document()** - отправка файлов
5. **Callback система** - обработка действий пользователя
6. **user_states** - хранение состояния пользователя

### **ЧТО НУЖНО ДОПОЛНИТЕЛЬНО:**
1. ✅ **handle_reports_list_txt()** - замена старого обработчика
2. ✅ **handle_report_action()** - обработка кнопок Посмотреть/Переименовать/Удалить
3. ✅ **handle_report_number_input()** - обработка ввода номера
4. ✅ **handle_report_view()** - отправка файла отчета
5. ✅ **handle_report_rename_***()** - переименование (2 функции)
6. ✅ **handle_report_delete_***()** - удаление (2 функции)
7. ✅ Интеграция в `on_callback_query` и обработку текста

**ИТОГО:** ~250-300 строк нового кода + минимальные изменения в существующих обработчиках.

Решение **максимально компактное**, использует все имеющиеся механизмы и добавляет только необходимый минимум для новой функциональности! 🚀

---

## 📁 СТРУКТУРА ФАЙЛОВ

### **Изменяемые файлы:**
1. `src/handlers.py` - добавление новых функций и интеграция
2. Никаких других изменений не требуется!

### **Используемые модули:**
- `src/md_storage.py` - без изменений
- `src/file_sender.py` - без изменений
- `src/message_tracker.py` - без изменений
- `src/markups.py` - без изменений

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

1. **Не удалять старую реализацию сразу** - оставить закомментированной для возможного отката
2. **Тестировать на реальных данных** - проверить работу с большим количеством отчетов
3. **Логирование** - добавить подробное логирование для отладки
4. **Обработка ошибок** - все функции имеют try/except блоки
5. **Очистка состояния** - после каждого действия очищать `user_states`

---

**Конец отчета**
