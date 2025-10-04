# Чеклист интеграции ConversationManager с Telegram ботом

## ✅ Что уже готово

- [x] Модели данных (`conversations.py`)
- [x] Менеджер чатов (`conversation_manager.py`)
- [x] Конфигурация (`config.py` - добавлен `CONVERSATIONS_DIR`)
- [x] Тестовые скрипты
- [x] Документация и примеры

## 📋 Шаги интеграции

### 1. Обновить обработчик сообщений бота

**Файл**: `src/bot.py` (или ваш основной файл бота)

#### 1.1. Добавить импорты

```python
from conversation_manager import conversation_manager
from conversations import ConversationMessage
from datetime import datetime
```

#### 1.2. При получении сообщения от пользователя

**Было** (примерно):
```python
@bot.message_handler(...)
async def handle_message(message):
    user_id = message.from_user.id
    text = message.text

    # Обрабатываем сообщение
    response = process_with_claude(text)

    # Отправляем ответ
    await bot.send_message(user_id, response)
```

**Стало**:
```python
@bot.message_handler(...)
async def handle_message(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    text = message.text

    # 1. Получаем активный чат или создаем новый
    active_id = conversation_manager.get_active_conversation_id(user_id)
    if not active_id:
        active_id = conversation_manager.create_conversation(
            user_id=user_id,
            username=username,
            first_question=text
        )

    # 2. Сохраняем вопрос пользователя
    user_msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=message.message_id,
        type="user_question",
        text=text,
        tokens=count_tokens(text),  # Ваша функция подсчета
        search_type="fast"  # или "deep" если пользователь выбрал
    )
    conversation_manager.add_message(user_id, active_id, user_msg)

    # 3. Получаем контекст для Claude
    history = conversation_manager.get_messages(user_id, active_id, limit=20)
    context = []
    for msg in history:
        role = "user" if msg.type == "user_question" else "assistant"
        context.append({"role": role, "content": msg.text})

    # 4. Обрабатываем с Claude (передаем контекст)
    response = process_with_claude(text, context=context)

    # 5. Сохраняем ответ бота
    bot_msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=message.message_id + 1,
        type="bot_answer",
        text=response,
        tokens=count_tokens(response),
        sent_as="message" if len(response) < 1200 else "file"
    )
    conversation_manager.add_message(user_id, active_id, bot_msg)

    # 6. Отправляем ответ пользователю
    await bot.send_message(user_id, response)
```

### 2. Добавить команды управления чатами

#### 2.1. Команда `/new_chat` - создать новый чат

```python
@bot.message_handler(commands=['new_chat'])
async def cmd_new_chat(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""

    # Создаем новый чат
    new_id = conversation_manager.create_conversation(
        user_id=user_id,
        username=username,
        first_question="Новый чат"
    )

    await bot.send_message(
        user_id,
        "✅ Создан новый чат. Старый чат сохранен, можете вернуться к нему позже."
    )
```

#### 2.2. Команда `/list_chats` - список всех чатов

```python
@bot.message_handler(commands=['list_chats'])
async def cmd_list_chats(message):
    user_id = message.from_user.id

    conversations = conversation_manager.list_conversations(user_id)

    if not conversations:
        await bot.send_message(user_id, "У вас пока нет чатов.")
        return

    # Формируем список с кнопками
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    markup = InlineKeyboardMarkup()
    text = "📋 Ваши чаты:\n\n"

    for i, conv in enumerate(conversations, 1):
        active_mark = "🔵" if conv.is_active else "⚪"
        text += f"{active_mark} {i}. {conv.name}\n"
        text += f"   📊 {conv.message_count} сообщений, {conv.total_tokens} токенов\n"
        text += f"   📅 {conv.updated_at[:10]}\n\n"

        # Кнопка для переключения
        button_text = "▶️ Активировать" if not conv.is_active else "✅ Активен"
        callback_data = f"switch_chat:{conv.conversation_id}"
        markup.add(InlineKeyboardButton(
            f"{i}. {button_text}",
            callback_data=callback_data
        ))

    await bot.send_message(user_id, text, reply_markup=markup)
```

#### 2.3. Обработчик переключения чатов

```python
@bot.callback_query_handler(func=lambda call: call.data.startswith("switch_chat:"))
async def callback_switch_chat(call):
    user_id = call.from_user.id
    conv_id = call.data.split(":")[1]

    # Переключаем активный чат
    success = conversation_manager.set_active_conversation(user_id, conv_id)

    if success:
        await bot.answer_callback_query(
            call.id,
            "✅ Чат переключен"
        )
        # Обновляем сообщение
        await cmd_list_chats(call.message)
    else:
        await bot.answer_callback_query(
            call.id,
            "❌ Ошибка переключения"
        )
```

#### 2.4. Команда `/delete_chat` - удалить чат

```python
@bot.message_handler(commands=['delete_chat'])
async def cmd_delete_chat(message):
    user_id = message.from_user.id

    conversations = conversation_manager.list_conversations(user_id)

    if len(conversations) <= 1:
        await bot.send_message(
            user_id,
            "❌ Нельзя удалить последний чат."
        )
        return

    # Показываем список с кнопками удаления
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    markup = InlineKeyboardMarkup()
    text = "🗑️ Выберите чат для удаления:\n\n"

    for i, conv in enumerate(conversations, 1):
        text += f"{i}. {conv.name}\n"

        markup.add(InlineKeyboardButton(
            f"🗑️ Удалить #{i}",
            callback_data=f"delete_chat:{conv.conversation_id}"
        ))

    markup.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

    await bot.send_message(user_id, text, reply_markup=markup)
```

#### 2.5. Обработчик удаления

```python
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_chat:"))
async def callback_delete_chat(call):
    user_id = call.from_user.id
    conv_id = call.data.split(":")[1]

    # Удаляем чат
    success = conversation_manager.delete_conversation(user_id, conv_id)

    if success:
        await bot.answer_callback_query(call.id, "✅ Чат удален")
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        await bot.send_message(user_id, "✅ Чат успешно удален")
    else:
        await bot.answer_callback_query(call.id, "❌ Ошибка удаления")
```

### 3. Обновить функцию подсчета токенов

**Добавить** (если еще нет):

```python
def count_tokens(text: str) -> int:
    """Подсчитывает количество токенов в тексте."""
    from config import ENC
    return len(ENC.encode(text))
```

### 4. Обновить меню бота

**Добавить кнопки** в главное меню:

```python
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("📋 Мои чаты"))
    markup.add(KeyboardButton("➕ Новый чат"))
    markup.add(KeyboardButton("🗑️ Удалить чат"))
    return markup
```

**Обработчики кнопок**:

```python
@bot.message_handler(func=lambda msg: msg.text == "📋 Мои чаты")
async def btn_list_chats(message):
    await cmd_list_chats(message)

@bot.message_handler(func=lambda msg: msg.text == "➕ Новый чат")
async def btn_new_chat(message):
    await cmd_new_chat(message)

@bot.message_handler(func=lambda msg: msg.text == "🗑️ Удалить чат")
async def btn_delete_chat(message):
    await cmd_delete_chat(message)
```

### 5. Миграция существующих данных (опционально)

Если у вас уже есть пользователи с историей чатов:

```python
def migrate_old_chats_to_new_system():
    """
    Миграция старых чатов в новую систему.
    Запустить один раз при деплое.
    """
    # Ваша логика миграции
    # Например, создать один чат на пользователя
    # и перенести все старые сообщения в него
    pass
```

### 6. Добавить переменную окружения

**В `.env`** (на сервере):

```bash
# Директория для хранения чатов
CONVERSATIONS_DIR=/home/voxpersona_user/VoxPersona/conversations
```

### 7. Тестирование

#### 7.1. Локальное тестирование

```bash
# Запуск тестов
python test_conversation_manager.py

# Запуск примеров
python conversation_manager_examples.py
```

#### 7.2. Тестирование на сервере

```bash
# SSH на сервер
ssh root@172.237.73.207

# Перейти в директорию проекта
cd /root/Vox/VoxPersona

# Запустить тесты
python test_conversation_manager.py

# Проверить создание директорий
ls -la /home/voxpersona_user/VoxPersona/conversations/
```

### 8. Мониторинг и логирование

**Добавить в логи**:

```python
import logging

logger = logging.getLogger(__name__)

# При создании чата
logger.info(f"User {user_id} created new chat {conv_id}")

# При переключении
logger.info(f"User {user_id} switched to chat {conv_id}")

# При удалении
logger.warning(f"User {user_id} deleted chat {conv_id}")
```

## 🚀 Деплой

### 1. Коммит изменений

```bash
git add src/conversation_manager.py
git add src/conversations.py
git add src/config.py
git add src/bot.py  # если обновлялся
git commit -m "Add multi-chat support with ConversationManager"
```

### 2. Отправка на сервер

```bash
git push origin main
```

### 3. На сервере

```bash
ssh root@172.237.73.207

cd /root/Vox/VoxPersona
git pull

# Создать директорию для чатов
mkdir -p /home/voxpersona_user/VoxPersona/conversations
chown -R voxpersona_user:voxpersona_user /home/voxpersona_user/VoxPersona/conversations

# Перезапустить бота
docker-compose restart voxpersona_bot
```

## ✅ Финальный чеклист

- [ ] Импорты добавлены
- [ ] Обработчик сообщений обновлен
- [ ] Команды добавлены (`/new_chat`, `/list_chats`, `/delete_chat`)
- [ ] Обработчики callback добавлены
- [ ] Меню бота обновлено
- [ ] Переменная `CONVERSATIONS_DIR` добавлена в `.env`
- [ ] Локальные тесты пройдены
- [ ] Изменения закоммичены
- [ ] Деплой на сервер выполнен
- [ ] Директория создана на сервере
- [ ] Бот перезапущен
- [ ] Функциональность протестирована вручную

## 📞 Поддержка

При возникновении проблем проверьте:
1. Логи бота: `docker logs voxpersona_bot`
2. Права на директорию: `ls -la /home/voxpersona_user/VoxPersona/conversations/`
3. Структуру файлов: `cat /home/voxpersona_user/VoxPersona/conversations/user_*/index.json`

---

**Создано**: 2025-10-03
**Версия**: 1.0
**Принцип**: KISS (Keep It Simple, Stupid)
