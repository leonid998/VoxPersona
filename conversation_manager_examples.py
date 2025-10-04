"""
Примеры использования ConversationManager в реальных сценариях VoxPersona бота.
"""

import sys
import os
from datetime import datetime

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from conversation_manager import conversation_manager
from conversations import ConversationMessage


# ============================================================================
# Пример 1: Обработка первого сообщения от нового пользователя
# ============================================================================

def handle_first_message_from_new_user():
    """
    Сценарий: Пользователь впервые пишет боту.
    Нужно создать первый чат и сохранить сообщение.
    """
    print("\n" + "="*60)
    print("ПРИМЕР 1: Первое сообщение от нового пользователя")
    print("="*60)

    # Данные от Telegram
    user_id = 12345
    username = "new_user"
    user_message = "Проанализируй интервью с клиентом из отеля Москва"
    telegram_msg_id = 100

    # 1. Создаем первый чат (название генерируется автоматически)
    conv_id = conversation_manager.create_conversation(
        user_id=user_id,
        username=username,
        first_question=user_message
    )
    print(f"✅ Создан первый чат ID: {conv_id}")

    # 2. Сохраняем вопрос пользователя
    user_msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=telegram_msg_id,
        type="user_question",
        text=user_message,
        tokens=150,  # Подсчитать через tiktoken
        search_type="fast"
    )
    conversation_manager.add_message(user_id, conv_id, user_msg)
    print(f"✅ Сохранен вопрос пользователя")

    # 3. После обработки сохраняем ответ бота
    bot_answer = "Анализ выполнен. Основные проблемы клиента: ..."
    bot_msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=telegram_msg_id + 1,
        type="bot_answer",
        text=bot_answer,
        tokens=500,
        sent_as="message"  # или "file" если длинный
    )
    conversation_manager.add_message(user_id, conv_id, bot_msg)
    print(f"✅ Сохранен ответ бота")

    # Проверяем результат
    conversation = conversation_manager.load_conversation(user_id, conv_id)
    print(f"\n📊 Статистика чата:")
    print(f"   Название: {conversation.metadata.name}")
    print(f"   Сообщений: {conversation.metadata.message_count}")
    print(f"   Токенов: {conversation.metadata.total_tokens}")


# ============================================================================
# Пример 2: Продолжение диалога в текущем чате
# ============================================================================

def handle_continuation_of_dialog():
    """
    Сценарий: Пользователь продолжает диалог в текущем чате.
    """
    print("\n" + "="*60)
    print("ПРИМЕР 2: Продолжение диалога")
    print("="*60)

    user_id = 12345

    # 1. Получаем активный чат
    active_id = conversation_manager.get_active_conversation_id(user_id)
    print(f"✅ Активный чат: {active_id}")

    # 2. Если активного нет (пользователь удалил все) - создаем новый
    if not active_id:
        print("⚠️  Активного чата нет, создаем новый...")
        active_id = conversation_manager.create_conversation(
            user_id=user_id,
            username="new_user",
            first_question="Новый чат"
        )

    # 3. Добавляем новое сообщение
    new_question = "Какие еще проблемы были у клиента?"
    msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=200,
        type="user_question",
        text=new_question,
        tokens=100
    )
    conversation_manager.add_message(user_id, active_id, msg)
    print(f"✅ Добавлено новое сообщение в активный чат")


# ============================================================================
# Пример 3: Создание нового чата (пользователь хочет новую тему)
# ============================================================================

def handle_new_chat_creation():
    """
    Сценарий: Пользователь хочет создать новый чат для новой темы.
    """
    print("\n" + "="*60)
    print("ПРИМЕР 3: Создание нового чата")
    print("="*60)

    user_id = 12345
    username = "new_user"

    # Пользователь нажимает кнопку "Новый чат"
    new_question = "Расскажи про лучшие практики интервью"

    # Создаем новый чат (старый автоматически станет неактивным)
    new_conv_id = conversation_manager.create_conversation(
        user_id=user_id,
        username=username,
        first_question=new_question
    )
    print(f"✅ Создан новый чат ID: {new_conv_id}")

    # Проверяем список чатов
    conversations = conversation_manager.list_conversations(user_id)
    print(f"\n📋 Список чатов пользователя ({len(conversations)} шт):")
    for i, conv in enumerate(conversations, 1):
        active_mark = "🔵" if conv.is_active else "⚪"
        print(f"   {active_mark} {i}. {conv.name}")
        print(f"      Сообщений: {conv.message_count}, Токенов: {conv.total_tokens}")


# ============================================================================
# Пример 4: Переключение между чатами
# ============================================================================

def handle_chat_switching():
    """
    Сценарий: Пользователь переключается между существующими чатами.
    """
    print("\n" + "="*60)
    print("ПРИМЕР 4: Переключение между чатами")
    print("="*60)

    user_id = 12345

    # 1. Показываем список чатов
    conversations = conversation_manager.list_conversations(user_id)
    print(f"\n📋 Ваши чаты:")
    for i, conv in enumerate(conversations, 1):
        active_mark = "🔵" if conv.is_active else "⚪"
        print(f"{active_mark} {i}. {conv.name} ({conv.message_count} сообщений)")

    # 2. Пользователь выбирает чат (например, первый)
    if len(conversations) > 0:
        selected_conv = conversations[0]
        print(f"\n👉 Переключаюсь на чат: {selected_conv.name}")

        # Устанавливаем выбранный чат как активный
        conversation_manager.set_active_conversation(
            user_id=user_id,
            conversation_id=selected_conv.conversation_id
        )
        print(f"✅ Чат переключен")

        # Проверяем
        active_id = conversation_manager.get_active_conversation_id(user_id)
        print(f"✅ Активный чат теперь: {active_id}")


# ============================================================================
# Пример 5: Удаление чата
# ============================================================================

def handle_chat_deletion():
    """
    Сценарий: Пользователь удаляет один из своих чатов.
    """
    print("\n" + "="*60)
    print("ПРИМЕР 5: Удаление чата")
    print("="*60)

    user_id = 12345

    # Получаем список чатов
    conversations = conversation_manager.list_conversations(user_id)
    print(f"\n📋 Чатов до удаления: {len(conversations)}")

    if len(conversations) > 1:
        # Удаляем последний чат
        last_conv = conversations[-1]
        print(f"🗑️  Удаляю чат: {last_conv.name}")

        conversation_manager.delete_conversation(
            user_id=user_id,
            conversation_id=last_conv.conversation_id
        )
        print(f"✅ Чат удален")

        # Проверяем результат
        conversations = conversation_manager.list_conversations(user_id)
        print(f"📋 Чатов после удаления: {len(conversations)}")

        # Проверяем активный чат
        active_id = conversation_manager.get_active_conversation_id(user_id)
        print(f"✅ Активный чат: {active_id}")


# ============================================================================
# Пример 6: Получение контекста для LLM
# ============================================================================

def get_context_for_llm():
    """
    Сценарий: Нужно получить историю чата для отправки в Claude.
    """
    print("\n" + "="*60)
    print("ПРИМЕР 6: Получение контекста для LLM")
    print("="*60)

    user_id = 12345

    # 1. Получаем активный чат
    active_id = conversation_manager.get_active_conversation_id(user_id)

    # 2. Загружаем последние 10 сообщений
    messages = conversation_manager.get_messages(
        user_id=user_id,
        conversation_id=active_id,
        limit=10
    )
    print(f"📥 Загружено {len(messages)} сообщений")

    # 3. Формируем контекст для Claude API
    context = []
    for msg in messages:
        role = "user" if msg.type == "user_question" else "assistant"
        context.append({
            "role": role,
            "content": msg.text
        })

    print(f"\n💬 Контекст для Claude ({len(context)} сообщений):")
    for i, msg_dict in enumerate(context, 1):
        role_emoji = "👤" if msg_dict["role"] == "user" else "🤖"
        preview = msg_dict["content"][:50] + "..." if len(msg_dict["content"]) > 50 else msg_dict["content"]
        print(f"   {role_emoji} {i}. {preview}")

    return context


# ============================================================================
# Пример 7: Интеграция с поиском (fast/deep)
# ============================================================================

def handle_message_with_search():
    """
    Сценарий: Пользователь задает вопрос с поиском (fast или deep).
    """
    print("\n" + "="*60)
    print("ПРИМЕР 7: Сообщение с поиском")
    print("="*60)

    user_id = 12345
    active_id = conversation_manager.get_active_conversation_id(user_id)

    # Пользователь выбрал "Fast Search"
    user_question = "Какие проблемы были в последних интервью?"
    search_type = "fast"  # или "deep"

    # Сохраняем вопрос с типом поиска
    msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=300,
        type="user_question",
        text=user_question,
        tokens=120,
        search_type=search_type
    )
    conversation_manager.add_message(user_id, active_id, msg)
    print(f"✅ Сохранен вопрос с поиском: {search_type}")

    # После получения ответа сохраняем его
    # Если ответ длинный - сохраняем как файл
    bot_answer = "Длинный отчет..." * 100
    file_path = "/home/voxpersona_user/VoxPersona/md_reports/report_300.md"

    answer_msg = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=301,
        type="bot_answer",
        text=bot_answer[:300] + "... (см. файл)",  # Preview
        tokens=5000,
        sent_as="file",
        file_path=file_path
    )
    conversation_manager.add_message(user_id, active_id, answer_msg)
    print(f"✅ Сохранен ответ (отправлен как файл)")


# ============================================================================
# Запуск всех примеров
# ============================================================================

if __name__ == "__main__":
    print("\n🚀 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ CONVERSATION MANAGER\n")

    try:
        # Основные сценарии
        handle_first_message_from_new_user()
        handle_continuation_of_dialog()
        handle_new_chat_creation()
        handle_chat_switching()
        handle_chat_deletion()
        get_context_for_llm()
        handle_message_with_search()

        print("\n" + "="*60)
        print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ УСПЕШНО")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}\n")
        import traceback
        traceback.print_exc()
