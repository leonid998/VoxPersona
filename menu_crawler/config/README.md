# 🌳 Menu Graph Configuration

**Автоматически сгенерированный граф меню VoxPersona**

---

## 📊 Статистика

| Метрика | Значение |
|---------|----------|
| **Узлов (nodes)** | 104 |
| **Связей (edges)** | 123 |
| **Уникальных callback_data** | 101 |
| **Динамических узлов** | 11 |
| **FSM узлов** | 25 |
| **Условных связей (super_admin)** | 62 |

---

## 📁 Структура

### nodes

Узлы представляют собой состояния меню или действия:

```json
{
  "node_id": {
    "type": "menu|action|view",
    "depth": 0-7,
    "description": "Описание узла",
    "dynamic": true,  // опционально - динамические узлы
    "fsm": true       // опционально - FSM узлы
  }
}
```

**Типы узлов:**
- `menu` (22 шт) - навигационные меню
- `action` (66 шт) - действия пользователя
- `view` (16 шт) - просмотр информации

**Глубина вложенности:**
- Depth 0: 1 узел (menu_main)
- Depth 1: 6 узлов
- Depth 2: 14 узлов
- Depth 3: 12 узлов
- Depth 4: 36 узлов
- Depth 5: 24 узла
- Depth 6: 7 узлов
- Depth 7: 4 узла

### edges

Связи между узлами (переходы):

```json
{
  "from": "source_node",
  "to": "target_node",
  "callback_data": "callback_value",
  "button_text": "Текст кнопки",
  "condition": "user_role == super_admin"  // опционально
}
```

---

## 🔐 Условная видимость

**62 связи** доступны только для `super_admin`:

- Все узлы под "Настройки доступа" (`menu_access`)
- Управление пользователями (`access_users_menu`)
- Приглашения (`access_invitations_menu`)
- Настройки безопасности (`access_security_menu`)

**Условие:** `user_role == super_admin`

---

## 🔗 Динамические узлы

**11 узлов** генерируют динамический контент:

| Узел | Описание | Callback паттерн |
|------|----------|------------------|
| `chat_actions` | Действия с чатом | `chat_actions||{conversation_id}` |
| `send_report` | Отправка отчета | `send_report||{report_id}` |
| `access_user_details` | Детали пользователя | `access_user_details||{user_id}` |
| `access_invite_details` | Детали приглашения | `access_invite_details||{invite_code}` |
| `access_list_users||page` | Пагинация пользователей | `access_list_users||page||{n}` |
| `access_list_invites||page` | Пагинация приглашений | `access_list_invites||page||{n}` |
| `view||audio` | Просмотр аудио | `view||audio` |
| `select||audio` | Выбор аудио | `select||{filename}` |
| `delete||audio` | Удаление аудио | `delete||{filename}` |
| `access_edit_user` | Редактирование пользователя | `access_edit_user||{user_id}` |
| `access_set_role` | Установка роли | `access_set_role||{user_id}||{role}` |
| `access_set_user_cleanup` | Очистка для пользователя | `access_set_user_cleanup||{user_id}` |

---

## 🤖 FSM узлы

**25 узлов** требуют FSM (Finite State Machine) для ввода данных:

### Основные FSM узлы:

| Узел | Назначение |
|------|------------|
| `new_chat` | Создание нового чата |
| `rename_chat` | Переименование чата |
| `report_rename` | Переименование отчета |
| `upload||audio` | Загрузка аудио файла |

### Auth FSM узлы:

| Узел | Назначение |
|------|------------|
| `invite_password_input` | Ввод пароля при активации |
| `invite_password_confirm` | Подтверждение пароля |
| `change_password_current` | Ввод текущего пароля |
| `change_password_new` | Ввод нового пароля |
| `change_password_confirm` | Подтверждение нового пароля |

### Access FSM узлы:

| Узел | Назначение |
|------|------------|
| `access_search_user` | Поиск пользователя |
| `access_set_cleanup` | Установка автоочистки |
| `access_create_invite_admin` | Создание приглашения админа |
| `access_create_invite_user` | Создание приглашения пользователя |
| `access_set_invite_expiry` | Установка срока действия |
| `access_set_cleanup_hours` | Установка времени очистки |
| `access_set_user_cleanup` | Очистка для пользователя |
| `access_set_min_length` | Минимальная длина пароля |
| `access_set_password_ttl` | Срок действия пароля |

### Audio processing FSM узлы:

| Узел | Назначение |
|------|------------|
| `edit_audio_number` | Редактирование номера файла |
| `edit_date` | Редактирование даты |
| `edit_employee` | Редактирование ФИО |
| `edit_place_name` | Редактирование заведения |
| `edit_city` | Редактирование города |
| `edit_zone_name` | Редактирование зоны |
| `edit_client` | Редактирование клиента |

---

## 📌 Entry Points

### Основной entry point
- `menu_main` (depth 0) - Главное меню, доступно через `/start`

### Дополнительные entry points
- `confirm_menu` - Обработка аудио (при отправке аудио файла)
- `invite_password_input` - Активация приглашения (при `/start {INVITE_CODE}`)
- `change_password_current` - Смена пароля (при `/change_password`)

---

## 🔍 Изолированные узлы

**14 узлов** изолированы от основного графа (это нормально):

| Узел | Причина изоляции |
|------|------------------|
| `confirm_menu` | Entry point для аудио обработки |
| `confirm_data` | Подменю аудио обработки |
| `edit_data` | Подменю аудио обработки |
| `edit_menu` | Подменю аудио обработки |
| `building_type_menu` | Подменю аудио обработки |
| `interview_menu` | Подменю аудио обработки |
| `design_menu` | Подменю аудио обработки |
| `choose_building||*` | Действия аудио обработки |
| `mode_fast`, `mode_deep` | Действия аудио обработки |
| `edit_building_type` | Действия аудио обработки |
| `edit_mode` | Действия аудио обработки |
| `back_to_confirm` | Действия аудио обработки |

Эти узлы вызываются **отдельным workflow** при обработке аудио файлов, а не через основное меню навигации.

---

## 🛠️ Как использовать

### Python

```python
import json

# Загрузка графа
with open('menu_graph.json', encoding='utf-8') as f:
    graph = json.load(f)

# Получение узла
node = graph['nodes']['menu_main']
print(f"Type: {node['type']}, Depth: {node['depth']}")

# Поиск связей от узла
edges_from_main = [
    e for e in graph['edges']
    if e['from'] == 'menu_main'
]

for edge in edges_from_main:
    print(f"-> {edge['to']} ({edge['button_text']})")
```

### Валидация callback_data

```python
def validate_callback(callback_data: str, graph: dict) -> bool:
    """Проверка существования callback_data в графе"""
    # Очистка от динамических параметров
    clean_callback = callback_data.split('||')[0]

    # Поиск в edges
    for edge in graph['edges']:
        edge_clean = edge['callback_data'].split('||')[0]
        if edge_clean == clean_callback:
            return True

    return False
```

### Получение пути к узлу

```python
def find_path(graph: dict, target: str, start: str = 'menu_main') -> list:
    """BFS поиск пути от start до target"""
    from collections import deque

    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        node, path = queue.popleft()

        if node == target:
            return path

        for edge in graph['edges']:
            if edge['from'] == node and edge['to'] not in visited:
                visited.add(edge['to'])
                queue.append((edge['to'], path + [edge['to']]))

    return None  # Путь не найден (изолированный узел)
```

---

## 📝 Генерация

**Файл создан автоматически:**
- **Скрипт:** `menu_crawler/scripts/build_menu_graph_v3.py`
- **Источник:** `TASKS/00005_20251014_HRYHG/Implemt/menu_crawler/COMPLETE_MENU_TREE.md`
- **Дата:** 22 октября 2025

**Для регенерации:**

```bash
cd menu_crawler/scripts
python build_menu_graph_v3.py
```

---

## ✅ Критерии успеха (Definition of Done)

- ✅ **101 callback_data** (ожидалось 81+) - **превышение на 24%**
- ✅ Граф связан от `menu_main` (кроме изолированных entry points)
- ✅ JSON синтаксис валиден
- ✅ Все узлы типизированы (`menu`, `action`, `view`)
- ✅ Динамические узлы помечены (`dynamic: true`)
- ✅ FSM узлы помечены (`fsm: true`)
- ✅ Условные узлы (`super_admin`) помечены (`condition`)
- ✅ Глубина вложенности рассчитана (0-7 уровней)

---

**Конец документации**
