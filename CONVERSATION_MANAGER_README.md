# ConversationManager - Менеджер мультичатов

## Описание

Простой и надежный менеджер для работы с мультичатами в VoxPersona боте. Реализован по принципу KISS (Keep It Simple, Stupid).

## Структура хранения

```
/home/voxpersona_user/VoxPersona/conversations/
└── user_{user_id}/
    ├── index.json              # Индекс всех чатов пользователя
    ├── {conversation_id}.json  # Чат 1
    ├── {conversation_id}.json  # Чат 2
    └── ...
```

### Формат `index.json`

```json
{
  "user_id": 123456,
  "username": "test_user",
  "last_active_conversation_id": "uuid-1234",
  "conversations": [
    {
      "conversation_id": "uuid-1234",
      "user_id": 123456,
      "username": "test_user",
      "name": "Анализ аудио интервью",
      "created_at": "2025-10-03T10:30:00",
      "updated_at": "2025-10-03T12:45:00",
      "is_active": true,
      "message_count": 15,
      "total_tokens": 8500
    }
  ]
}
```

### Формат `{conversation_id}.json`

```json
{
  "metadata": {
    "conversation_id": "uuid-1234",
    "user_id": 123456,
    "username": "test_user",
    "name": "Анализ аудио интервью",
    "created_at": "2025-10-03T10:30:00",
    "updated_at": "2025-10-03T12:45:00",
    "is_active": true,
    "message_count": 15,
    "total_tokens": 8500
  },
  "messages": [
    {
      "timestamp": "2025-10-03T10:30:00",
      "message_id": 1,
      "type": "user_question",
      "text": "Проанализируй это интервью",
      "tokens": 150,
      "sent_as": null,
      "file_path": null,
      "search_type": "fast"
    }
  ]
}
```

## API

### Импорт

```python
from conversation_manager import conversation_manager
from conversations import ConversationMessage
```

### CRUD операции

#### Создание нового чата

```python
conversation_id = conversation_manager.create_conversation(
    user_id=12345,
    username="test_user",
    first_question="Проанализируй интервью с клиентом"
)
# Возвращает: UUID нового чата (str)
```

#### Загрузка чата

```python
conversation = conversation_manager.load_conversation(
    user_id=12345,
    conversation_id="uuid-1234"
)
# Возвращает: Conversation или None
```

#### Сохранение чата

```python
success = conversation_manager.save_conversation(conversation)
# Возвращает: True/False
```

#### Удаление чата

```python
success = conversation_manager.delete_conversation(
    user_id=12345,
    conversation_id="uuid-1234"
)
# Возвращает: True/False
# Автоматически переключает активный чат если удаляется текущий
```

### Управление активным чатом

#### Получить ID активного чата

```python
active_id = conversation_manager.get_active_conversation_id(user_id=12345)
# Возвращает: UUID активного чата (str) или None
```

#### Установить чат как активный

```python
success = conversation_manager.set_active_conversation(
    user_id=12345,
    conversation_id="uuid-1234"
)
# Возвращает: True/False
```

### Работа с сообщениями

#### Добавить сообщение

```python
from datetime import datetime

message = ConversationMessage(
    timestamp=datetime.now().isoformat(),
    message_id=123,
    type="user_question",  # или "bot_answer"
    text="Текст сообщения",
    tokens=150,
    sent_as="message",  # или "file"
    file_path=None,
    search_type="fast"  # или "deep"
)

success = conversation_manager.add_message(
    user_id=12345,
    conversation_id="uuid-1234",
    message=message
)
# Возвращает: True/False
# Автоматически обновляет metadata (message_count, total_tokens, updated_at)
```

#### Получить последние сообщения

```python
messages = conversation_manager.get_messages(
    user_id=12345,
    conversation_id="uuid-1234",
    limit=20  # По умолчанию 20
)
# Возвращает: List[ConversationMessage]
```

### Работа с индексом

#### Загрузить индекс

```python
index_data = conversation_manager.load_index(user_id=12345)
# Возвращает: dict с полной структурой индекса
```

#### Список всех чатов

```python
conversations = conversation_manager.list_conversations(user_id=12345)
# Возвращает: List[ConversationMetadata]

for conv in conversations:
    print(f"{conv.name} - {conv.message_count} сообщений")
```

## Типичные сценарии использования

### 1. Новый пользователь впервые пишет боту

```python
# Создаем первый чат
conv_id = conversation_manager.create_conversation(
    user_id=user_id,
    username=username,
    first_question=user_message
)

# Добавляем первое сообщение
msg = ConversationMessage(
    timestamp=datetime.now().isoformat(),
    message_id=telegram_msg.message_id,
    type="user_question",
    text=user_message,
    tokens=count_tokens(user_message)
)
conversation_manager.add_message(user_id, conv_id, msg)
```

### 2. Пользователь продолжает диалог

```python
# Получаем активный чат
active_id = conversation_manager.get_active_conversation_id(user_id)

if not active_id:
    # Создаем новый если нет активного
    active_id = conversation_manager.create_conversation(
        user_id, username, user_message
    )

# Добавляем новое сообщение
msg = ConversationMessage(...)
conversation_manager.add_message(user_id, active_id, msg)
```

### 3. Пользователь переключается между чатами

```python
# Показываем список чатов
conversations = conversation_manager.list_conversations(user_id)

for i, conv in enumerate(conversations, 1):
    print(f"{i}. {conv.name} ({conv.message_count} сообщений)")

# Пользователь выбирает чат #2
selected_conv = conversations[1]
conversation_manager.set_active_conversation(
    user_id,
    selected_conv.conversation_id
)
```

### 4. Получение контекста для LLM

```python
# Получаем последние 20 сообщений
active_id = conversation_manager.get_active_conversation_id(user_id)
messages = conversation_manager.get_messages(user_id, active_id, limit=20)

# Формируем контекст для Claude
context = []
for msg in messages:
    role = "user" if msg.type == "user_question" else "assistant"
    context.append({"role": role, "content": msg.text})
```

## Особенности реализации

### Atomic writes

Все операции записи используют атомарную запись через временный файл:
```python
# Сначала пишем в .tmp файл
with open(temp_file, 'w') as f:
    json.dump(data, f)

# Потом переименовываем
temp_file.replace(target_file)
```

### Автоматическая генерация названий чатов

Названия чатов генерируются из первых слов вопроса (до 30 символов):
- "Проанализируй интервью с клиентом из отеля" → "Проанализируй интервью с..."

### Обработка ошибок

Все методы имеют try/except блоки с логированием:
```python
try:
    # Операция
except Exception as e:
    logger.error(f"Failed to ...: {e}")
    return False  # или None
```

### Автоматическое управление активным чатом

- При создании нового чата он автоматически становится активным
- При удалении активного чата система автоматически выбирает другой
- Если чатов не осталось - создается новый

## Конфигурация

В `config.py` добавлена константа:
```python
CONVERSATIONS_DIR = os.getenv(
    "CONVERSATIONS_DIR",
    "/home/voxpersona_user/VoxPersona/conversations"
)
```

Можно переопределить через переменную окружения `CONVERSATIONS_DIR`.

## Тестирование

Запуск тестов:
```bash
python test_conversation_manager.py
```

Тесты покрывают:
- Создание и удаление чатов
- Добавление сообщений
- Переключение активного чата
- Загрузку и сохранение данных
- Структуру индекса

## Требования

- Python 3.11+
- Зависимости: `pathlib`, `json`, `logging`, `uuid`, `datetime`, `dataclasses`

Все зависимости входят в стандартную библиотеку Python.
