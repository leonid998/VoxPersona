"""
Простой скрипт для тестирования ConversationManager.
Запуск: python test_conversation_manager.py
"""

import sys
import os
from datetime import datetime

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from conversation_manager import conversation_manager
from conversations import ConversationMessage


def test_basic_workflow():
    """Тестирует базовый сценарий работы с чатами."""

    print("\n" + "="*60)
    print("ТЕСТ: Базовый workflow мультичатов")
    print("="*60)

    user_id = 12345
    username = "test_user"

    # 1. Создаем первый чат
    print("\n1. Создание первого чата...")
    conv_id_1 = conversation_manager.create_conversation(
        user_id=user_id,
        username=username,
        first_question="Проанализируй интервью с клиентом из отеля Москва"
    )
    print(f"   ✅ Создан чат ID: {conv_id_1}")

    # 2. Добавляем сообщения в первый чат
    print("\n2. Добавление сообщений в первый чат...")
    msg1 = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=1,
        type="user_question",
        text="Проанализируй интервью с клиентом из отеля Москва",
        tokens=150
    )
    msg2 = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=2,
        type="bot_answer",
        text="Анализ выполнен. Клиент доволен обслуживанием.",
        tokens=200,
        sent_as="message"
    )

    conversation_manager.add_message(user_id, conv_id_1, msg1)
    conversation_manager.add_message(user_id, conv_id_1, msg2)
    print(f"   ✅ Добавлено 2 сообщения")

    # 3. Создаем второй чат
    print("\n3. Создание второго чата...")
    conv_id_2 = conversation_manager.create_conversation(
        user_id=user_id,
        username=username,
        first_question="Какие основные проблемы клиентов?"
    )
    print(f"   ✅ Создан чат ID: {conv_id_2}")

    # 4. Добавляем сообщение во второй чат
    print("\n4. Добавление сообщения во второй чат...")
    msg3 = ConversationMessage(
        timestamp=datetime.now().isoformat(),
        message_id=3,
        type="user_question",
        text="Какие основные проблемы клиентов?",
        tokens=100
    )
    conversation_manager.add_message(user_id, conv_id_2, msg3)
    print(f"   ✅ Добавлено 1 сообщение")

    # 5. Проверяем список всех чатов
    print("\n5. Список всех чатов пользователя:")
    conversations = conversation_manager.list_conversations(user_id)
    for conv in conversations:
        print(f"   - {conv.name}")
        print(f"     ID: {conv.conversation_id}")
        print(f"     Сообщений: {conv.message_count}, Токенов: {conv.total_tokens}")
        print(f"     Активный: {'Да' if conv.is_active else 'Нет'}")
        print(f"     Создан: {conv.created_at}")

    # 6. Проверяем активный чат
    print("\n6. Активный чат:")
    active_id = conversation_manager.get_active_conversation_id(user_id)
    print(f"   ✅ ID активного чата: {active_id}")
    print(f"   ✅ Должен быть второй: {active_id == conv_id_2}")

    # 7. Переключаемся на первый чат
    print("\n7. Переключение на первый чат...")
    conversation_manager.set_active_conversation(user_id, conv_id_1)
    active_id = conversation_manager.get_active_conversation_id(user_id)
    print(f"   ✅ Новый активный чат: {active_id}")
    print(f"   ✅ Должен быть первый: {active_id == conv_id_1}")

    # 8. Получаем сообщения из первого чата
    print("\n8. Сообщения из первого чата:")
    messages = conversation_manager.get_messages(user_id, conv_id_1)
    for i, msg in enumerate(messages, 1):
        print(f"   {i}. [{msg.type}] {msg.text[:50]}...")
        print(f"      Токенов: {msg.tokens}")

    # 9. Загружаем полный чат
    print("\n9. Загрузка полного чата:")
    conversation = conversation_manager.load_conversation(user_id, conv_id_1)
    if conversation:
        print(f"   ✅ Название: {conversation.metadata.name}")
        print(f"   ✅ Сообщений: {len(conversation.messages)}")
        print(f"   ✅ Всего токенов: {conversation.metadata.total_tokens}")

    # 10. Удаляем второй чат
    print("\n10. Удаление второго чата...")
    conversation_manager.delete_conversation(user_id, conv_id_2)
    conversations = conversation_manager.list_conversations(user_id)
    print(f"   ✅ Осталось чатов: {len(conversations)}")

    print("\n" + "="*60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
    print("="*60 + "\n")


def test_index_structure():
    """Проверяет структуру index.json."""

    print("\n" + "="*60)
    print("ТЕСТ: Структура index.json")
    print("="*60)

    user_id = 99999
    username = "index_test_user"

    # Создаем несколько чатов
    print("\n1. Создание 3 чатов...")
    conv_ids = []
    questions = [
        "Первый вопрос для тестирования",
        "Второй вопрос про что-то другое",
        "Третий вопрос самый длинный который точно будет обрезан потому что очень много букв"
    ]

    for q in questions:
        conv_id = conversation_manager.create_conversation(user_id, username, q)
        conv_ids.append(conv_id)

    # Проверяем индекс
    print("\n2. Проверка индекса:")
    index = conversation_manager.load_index(user_id)

    print(f"   User ID: {index['user_id']}")
    print(f"   Username: {index['username']}")
    print(f"   Last active: {index['last_active_conversation_id']}")
    print(f"   Количество чатов: {len(index['conversations'])}")

    print("\n3. Список чатов в индексе:")
    for i, conv in enumerate(index['conversations'], 1):
        print(f"   {i}. {conv['name']}")
        print(f"      Active: {conv['is_active']}")

    # Очистка
    print("\n4. Очистка тестовых данных...")
    for conv_id in conv_ids:
        conversation_manager.delete_conversation(user_id, conv_id)

    print("\n" + "="*60)
    print("✅ ТЕСТ СТРУКТУРЫ ЗАВЕРШЕН")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        test_basic_workflow()
        test_index_structure()

        print("\n🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ! 🎉\n")
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}\n")
        import traceback
        traceback.print_exc()
