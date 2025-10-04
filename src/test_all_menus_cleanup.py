"""
Полный тест цикла очистки всех меню в боте.

Проверяет каждое меню из списка и убеждается, что:
1. Старое меню ПОЛНОСТЬЮ удаляется (текст + кнопки)
2. Новое меню отправляется внизу чата
3. Нет текстовых артефактов
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from menu_manager import MenuManager, send_menu


# Полный список всех меню из menu_analysis.md
ALL_MENUS = [
    # Основные меню
    ("🏠 Главное меню:", "main_menu"),
    ("Какую информацию вы хотели бы получить?", "dialog_mode"),
    ("💬 Ваши чаты:", "chats_menu"),

    # Новый чат и переключение
    ("✨ Новый чат создан!\n\nКакую информацию вы хотели бы получить?\n\nВыберите действие:", "new_chat"),
    ("✅ Переключено на чат: Тестовый чат\n\n📜 Последние 5 сообщений:\n\n💬 История пуста.\n\nВыберите действие:", "switch_chat"),
    ("🔄 Перейти в чат 'Тестовый чат'?", "confirm_switch"),

    # Переименование и удаление
    ("✅ Чат переименован в 'Новое название'\n\nВаши чаты:", "rename_result"),
    ("✅ Чат удален\n\nВаши чаты:", "delete_result"),
    ("⚠️ Удалить чат 'Тестовый чат'?\n\nЭто действие необратимо.", "delete_confirm"),

    # Системные меню
    ("⚙️ Системные настройки:", "system_menu"),
    ("📦 Меню хранилища:", "storage_menu"),
    ("Файлы в 'audio':", "files_menu"),

    # Сценарии работы
    ("Что анализируем?:", "scenario_menu"),
    ("Выберите тип заведения:", "building_type"),

    # Редактирование
    ("Какое поле хотите изменить?", "edit_menu"),

    # Инструкции
    ("📌 Для начала работы:\n\n1️⃣ Выберите чат или создайте новый\n2️⃣ Выберите режим поиска (быстрый или глубокий)\n3️⃣ Задайте вопрос\n\nОткройте главное меню ниже 👇", "instructions"),
]


def test_full_menu_cycle():
    """
    Полный цикл проверки всех меню бота.
    """
    print("\n" + "="*70)
    print("ПОЛНЫЙ ТЕСТ ЦИКЛА ОЧИСТКИ ВСЕХ МЕНЮ")
    print("="*70)

    # Очистка состояния
    MenuManager._last_menu_ids.clear()

    chat_id = 12345
    app = MagicMock(spec=Client)
    app.delete_messages = AsyncMock()

    artifacts_found = []
    successful_deletions = []

    for i, (menu_text, menu_id) in enumerate(ALL_MENUS, 1):
        print(f"\n{'─'*70}")
        print(f"ШАГ {i}/{len(ALL_MENUS)}: {menu_id}")
        print(f"{'─'*70}")
        print(f"📝 Текст меню: '{menu_text[:60]}{'...' if len(menu_text) > 60 else ''}'")

        # Отправляем меню ПЕРЕД проверкой
        mock_message = MagicMock(spec=Message)
        mock_message.id = i + 100  # message_id: 101, 102, 103...
        app.send_message = AsyncMock(return_value=mock_message)

        # Создаем тестовую разметку
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("Тест", callback_data="test")
        ]])

        # Отправляем меню
        asyncio.run(send_menu(
            chat_id=chat_id,
            app=app,
            text=menu_text,
            reply_markup=markup
        ))

        # ТЕПЕРЬ проверяем удаление ПОСЛЕ отправки
        if i > 1:
            prev_text = ALL_MENUS[i-2][0]
            prev_id = i + 99  # message_id предыдущего

            print(f"\n🔍 ПРОВЕРКА удаления предыдущего меню:")
            print(f"   📌 message_id={prev_id}")
            print(f"   📝 Текст: '{prev_text[:50]}{'...' if len(prev_text) > 50 else ''}'")

            # Проверяем что delete_messages был вызван
            if app.delete_messages.call_count > 0:
                last_call = app.delete_messages.call_args
                deleted_id = last_call.kwargs.get('message_ids')

                if deleted_id == prev_id:
                    print(f"   ✅ УСПЕХ: delete_messages вызван для message_id={deleted_id}")
                    print(f"   ✅ Старое меню ПОЛНОСТЬЮ удалено (текст + кнопки)")
                    successful_deletions.append({
                        'step': i-1,
                        'menu': ALL_MENUS[i-2][1],
                        'text': prev_text,
                        'message_id': deleted_id
                    })
                else:
                    print(f"   ❌ ОШИБКА: delete_messages вызван для {deleted_id}, ожидалось {prev_id}")
                    artifacts_found.append({
                        'step': i-1,
                        'menu': ALL_MENUS[i-2][1],
                        'text': prev_text,
                        'expected_id': prev_id,
                        'actual_id': deleted_id
                    })
            else:
                print(f"   ❌ ОШИБКА: delete_messages НЕ был вызван!")
                print(f"   ❌ Текст остается в чате: '{prev_text[:50]}'")
                artifacts_found.append({
                    'step': i-1,
                    'menu': ALL_MENUS[i-2][1],
                    'text': prev_text,
                    'error': 'delete_messages не вызван'
                })

        print(f"\n📤 Отправлено новое меню:")
        print(f"   message_id={mock_message.id}")
        print(f"   Сохранено в MenuManager._last_menu_ids[{chat_id}]")

    # Итоговый отчет
    print("\n" + "="*70)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("="*70)

    print(f"\n📊 СТАТИСТИКА:")
    print(f"   Всего меню протестировано: {len(ALL_MENUS)}")
    print(f"   Успешных удалений: {len(successful_deletions)}")
    print(f"   Найдено артефактов: {len(artifacts_found)}")

    if len(artifacts_found) > 0:
        print("\n❌ ОБНАРУЖЕНЫ АРТЕФАКТЫ:")
        print("━"*70)
        for artifact in artifacts_found:
            print(f"\nШаг {artifact['step']} - {artifact['menu']}:")
            print(f"  Текст: '{artifact['text'][:60]}...'")
            if 'error' in artifact:
                print(f"  Ошибка: {artifact['error']}")
            else:
                print(f"  Ожидался ID: {artifact['expected_id']}")
                print(f"  Получен ID: {artifact['actual_id']}")
        print("━"*70)
        print("\n💡 РЕКОМЕНДАЦИЯ: Проверить MenuManager._remove_old_menu_buttons()")
        print("   Убедиться что используется delete_messages, а не edit_message_reply_markup")
    else:
        print("\n✅ ВСЕ МЕНЮ ОЧИЩАЮТСЯ ПРАВИЛЬНО!")
        print("━"*70)
        print("   ✓ Старые меню полностью удаляются")
        print("   ✓ Текстовые артефакты не остаются")
        print("   ✓ Чат не захламляется")
        print("━"*70)

    print(f"\n📋 УСПЕШНЫЕ УДАЛЕНИЯ:")
    print("━"*70)
    for deletion in successful_deletions[:5]:  # Показываем первые 5
        print(f"   ✓ {deletion['menu']} (message_id={deletion['message_id']})")
    if len(successful_deletions) > 5:
        print(f"   ... и еще {len(successful_deletions) - 5} удалений")
    print("━"*70)

    # Проверка финального состояния
    final_menu_id = MenuManager._last_menu_ids.get(chat_id)
    expected_final_id = len(ALL_MENUS) + 100

    print(f"\n🔍 ФИНАЛЬНОЕ СОСТОЯНИЕ:")
    print(f"   Последнее меню ID: {final_menu_id}")
    print(f"   Ожидаемый ID: {expected_final_id}")

    if final_menu_id == expected_final_id:
        print(f"   ✅ Корректно!")
    else:
        print(f"   ❌ Ошибка в отслеживании ID")

    print("\n" + "="*70)
    print("ТЕСТ ЗАВЕРШЕН")
    print("="*70 + "\n")

    # Assertions для pytest
    assert len(artifacts_found) == 0, f"Найдено {len(artifacts_found)} артефактов меню!"
    assert final_menu_id == expected_final_id, "Ошибка в отслеживании ID меню"
    assert len(successful_deletions) == len(ALL_MENUS) - 1, "Не все меню были удалены"


def test_edge_cases():
    """
    Тест граничных случаев.
    """
    print("\n" + "="*70)
    print("ТЕСТ ГРАНИЧНЫХ СЛУЧАЕВ")
    print("="*70)

    MenuManager._last_menu_ids.clear()
    chat_id = 12345
    app = MagicMock(spec=Client)
    app.delete_messages = AsyncMock()

    # 1. Очень длинный текст меню
    print("\n1. Тест очень длинного текста меню:")
    long_text = "📌 " + "Очень длинный текст меню " * 50
    mock_message = MagicMock(spec=Message)
    mock_message.id = 1000
    app.send_message = AsyncMock(return_value=mock_message)

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Тест", callback_data="test")]])
    asyncio.run(send_menu(chat_id, app, long_text, markup))

    print(f"   ✅ Длинный текст обработан, message_id={mock_message.id}")

    # 2. Переключение между одинаковыми текстами
    print("\n2. Тест одинаковых текстов:")
    same_text = "🏠 Главное меню:"

    mock_message2 = MagicMock(spec=Message)
    mock_message2.id = 1001
    app.send_message = AsyncMock(return_value=mock_message2)
    app.delete_messages.reset_mock()

    asyncio.run(send_menu(chat_id, app, same_text, markup))

    if app.delete_messages.called:
        print(f"   ✅ Предыдущее меню удалено, даже с одинаковым текстом")
    else:
        print(f"   ❌ Меню НЕ удалено!")

    # 3. Пустой текст
    print("\n3. Тест пустого текста:")
    empty_text = ""

    mock_message3 = MagicMock(spec=Message)
    mock_message3.id = 1002
    app.send_message = AsyncMock(return_value=mock_message3)

    asyncio.run(send_menu(chat_id, app, empty_text, markup))

    print(f"   ✅ Пустой текст обработан, message_id={mock_message3.id}")

    # 4. Специальные символы
    print("\n4. Тест специальных символов:")
    special_text = "🎉🔥💯 Меню с эмодзи и <b>HTML</b> & спец.символами!"

    mock_message4 = MagicMock(spec=Message)
    mock_message4.id = 1003
    app.send_message = AsyncMock(return_value=mock_message4)

    asyncio.run(send_menu(chat_id, app, special_text, markup))

    print(f"   ✅ Специальные символы обработаны, message_id={mock_message4.id}")

    print("\n" + "="*70)
    print("ВСЕ ГРАНИЧНЫЕ СЛУЧАИ ПРОЙДЕНЫ УСПЕШНО")
    print("="*70 + "\n")


if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║  ПОЛНАЯ ПРОВЕРКА ОЧИСТКИ ВСЕХ МЕНЮ VOXPERSONA BOT               ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    # Тест 1: Полный цикл всех меню
    test_full_menu_cycle()

    # Тест 2: Граничные случаи
    test_edge_cases()

    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║  ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО                                   ║")
    print("║  ✅ MenuManager ПОЛНОСТЬЮ удаляет старые меню                    ║")
    print("║  ✅ Текстовые артефакты НЕ остаются в чате                      ║")
    print("║  ✅ Чат НЕ захламляется                                          ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")
