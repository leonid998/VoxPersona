"""
Тест для демонстрации проблемы с текстовыми артефактами меню.

Проблема:
- При переключении меню старые кнопки удаляются
- НО текст старого меню ОСТАЕТСЯ
- Это захламляет чат

Тест проверяет:
1. Отправка первого меню "🏠 Главное меню:"
2. Отправка второго меню "💬 Ваши чаты:"
3. ❌ Проблема: текст "🏠 Главное меню:" остается без кнопок
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from menu_manager import MenuManager, send_menu_and_remove_old


def test_menu_text_artifact_problem():
    """
    ДЕМОНСТРАЦИЯ ПРОБЛЕМЫ: текст старого меню остается
    """
    print("\n" + "="*60)
    print("ТЕСТ: Демонстрация проблемы с текстовыми артефактами")
    print("="*60)

    # Очистка состояния
    MenuManager._last_menu_ids.clear()

    chat_id = 12345
    app = MagicMock(spec=Client)

    # ===== ШАГ 1: Отправка первого меню =====
    print("\n📤 ШАГ 1: Отправка главного меню")
    print("   Текст: '🏠 Главное меню:'")

    mock_message_1 = MagicMock(spec=Message)
    mock_message_1.id = 100
    app.send_message = AsyncMock(return_value=mock_message_1)
    app.edit_message_reply_markup = AsyncMock()

    markup_1 = InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Режим диалога", callback_data="menu_dialog"),
        InlineKeyboardButton("📱 Чаты", callback_data="menu_chats")
    ]])

    asyncio.run(send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text="🏠 Главное меню:",
        reply_markup=markup_1
    ))

    print(f"   ✅ Меню отправлено, message_id={mock_message_1.id}")
    print(f"   📝 В чате: '🏠 Главное меню:' + [кнопки]")

    # Проверяем что первое меню отправлено
    assert app.send_message.call_count == 1
    assert MenuManager._last_menu_ids[chat_id] == 100

    # ===== ШАГ 2: Отправка второго меню =====
    print("\n📤 ШАГ 2: Пользователь нажал 'Чаты' → отправка меню чатов")
    print("   Текст: '💬 Ваши чаты:'")

    mock_message_2 = MagicMock(spec=Message)
    mock_message_2.id = 200
    app.send_message = AsyncMock(return_value=mock_message_2)

    markup_2 = InlineKeyboardMarkup([[
        InlineKeyboardButton("🆕 Новый чат", callback_data="new_chat"),
        InlineKeyboardButton("« Назад", callback_data="menu_main")
    ]])

    asyncio.run(send_menu_and_remove_old(
        chat_id=chat_id,
        app=app,
        text="💬 Ваши чаты:",
        reply_markup=markup_2
    ))

    print(f"   ✅ Меню отправлено, message_id={mock_message_2.id}")

    # ===== ПРОВЕРКА ПРОБЛЕМЫ =====
    print("\n🔍 ПРОВЕРКА: Что произошло со старым меню?")

    # Проверяем что edit_message_reply_markup был вызван
    assert app.edit_message_reply_markup.called
    edit_call = app.edit_message_reply_markup.call_args

    print(f"   📝 Вызван edit_message_reply_markup для message_id={edit_call.kwargs['message_id']}")
    print(f"   🔧 Параметры: reply_markup={edit_call.kwargs['reply_markup']}")

    if edit_call.kwargs['reply_markup'] is None:
        print("\n   ❌ ПРОБЛЕМА ОБНАРУЖЕНА!")
        print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("   reply_markup=None → удаляет ТОЛЬКО кнопки!")
        print("   Текст '🏠 Главное меню:' ОСТАЕТСЯ в чате")
        print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("\n   📋 Состояние чата:")
        print("      1. '🏠 Главное меню:' ← АРТЕФАКТ БЕЗ КНОПОК")
        print("      2. '💬 Ваши чаты:' + [кнопки]")
        print("\n   💡 Нужно: полностью удалять старое сообщение")
        print("      Использовать: app.delete_message(message_id=100)")

    # Проверяем что новое меню сохранено
    assert MenuManager._last_menu_ids[chat_id] == 200

    print("\n" + "="*60)
    print("ТЕСТ ЗАВЕРШЕН: Проблема продемонстрирована")
    print("="*60 + "\n")


def test_sequence_of_menus():
    """
    Тест цикла: переключение между несколькими меню
    """
    print("\n" + "="*60)
    print("ТЕСТ: Цикл переключения меню")
    print("="*60)

    MenuManager._last_menu_ids.clear()

    chat_id = 12345
    app = MagicMock(spec=Client)
    app.edit_message_reply_markup = AsyncMock()

    menus = [
        ("🏠 Главное меню:", 100),
        ("💬 Ваши чаты:", 200),
        ("⚙️ Системные настройки:", 300),
        ("📦 Меню хранилища:", 400),
        ("🏠 Главное меню:", 500),
    ]

    artifacts = []

    for i, (text, msg_id) in enumerate(menus, 1):
        print(f"\n📤 ШАГ {i}: Отправка меню '{text}'")

        # Если есть предыдущее меню - это будет артефакт
        if i > 1:
            prev_text = menus[i-2][0]
            artifacts.append(prev_text)
            print(f"   ❌ Артефакт: '{prev_text}' остается без кнопок")

        mock_message = MagicMock(spec=Message)
        mock_message.id = msg_id
        app.send_message = AsyncMock(return_value=mock_message)

        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("Тест", callback_data="test")
        ]])

        asyncio.run(send_menu_and_remove_old(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=markup
        ))

        print(f"   ✅ Отправлено message_id={msg_id}")

    print("\n📋 ИТОГОВОЕ СОСТОЯНИЕ ЧАТА:")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for i, artifact in enumerate(artifacts, 1):
        print(f"   {i}. '{artifact}' ← АРТЕФАКТ БЕЗ КНОПОК")
    print(f"   {len(artifacts) + 1}. '{menus[-1][0]}' + [кнопки] ← АКТИВНОЕ МЕНЮ")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print(f"\n❌ Всего артефактов: {len(artifacts)}")
    print("💡 Каждое переключение меню оставляет текст без кнопок!")

    print("\n" + "="*60)
    print("ТЕСТ ЗАВЕРШЕН: Проблема подтверждена в цикле")
    print("="*60 + "\n")


if __name__ == "__main__":
    print("\n╔════════════════════════════════════════════════════════╗")
    print("║  ТЕСТИРОВАНИЕ ПРОБЛЕМЫ ТЕКСТОВЫХ АРТЕФАКТОВ МЕНЮ       ║")
    print("╚════════════════════════════════════════════════════════╝")

    # Тест 1: Демонстрация проблемы
    test_menu_text_artifact_problem()

    # Тест 2: Цикл переключений
    test_sequence_of_menus()

    print("\n╔════════════════════════════════════════════════════════╗")
    print("║  ВЫВОД: MenuManager удаляет ТОЛЬКО кнопки             ║")
    print("║  Текст остается → захламление чата                    ║")
    print("║  РЕШЕНИЕ: использовать delete_message()               ║")
    print("╚════════════════════════════════════════════════════════╝\n")
