#!/usr/bin/env python3
"""
Скрипт для применения всех трёх исправлений в VoxPersona
Исправляет конфликт is_active vs is_blocked
"""

def fix1_access_handlers_confirm_block():
    """
    Исправление #1: access_handlers.py строки 954-960
    Синхронизация is_active и is_blocked при блокировке/разблокировке
    """
    file_path = "src/access_handlers.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Заменить строки 954-960 (индексы 953-959)
    # Старые строки 954-960:
    # 954:         # Переключить статус блокировки
    # 955:         new_blocked_status = not target_user.is_blocked
    # 956:
    # 957:         # Обновить статус: изменить поля объекта и сохранить
    # 958:         target_user.is_blocked = new_blocked_status
    # 959:         target_user.updated_at = datetime.now()
    # 960:         success = auth.storage.update_user(target_user)

    new_lines = [
        "        # Переключить статус блокировки\n",
        "        # СИНХРОНИЗАЦИЯ: is_active и is_blocked должны быть инверсны\n",
        "        # Блокируем: is_active=False, is_blocked=True\n",
        "        # Разблокируем: is_active=True, is_blocked=False\n",
        "        new_active_status = target_user.is_blocked  # Инверсия: если был заблокирован → делаем активным\n",
        "\n",
        "        # Обновить оба поля синхронно (единый источник истины)\n",
        "        target_user.is_active = new_active_status\n",
        "        target_user.is_blocked = not new_active_status  # Инверсия is_active\n",
        "        target_user.updated_at = datetime.now()\n",
        "        success = auth.storage.update_user(target_user)\n"
    ]

    # Заменить строки 954-960 (7 строк → 11 строк)
    lines[953:960] = new_lines

    # Добавить строку вычисления new_blocked_status после строки 960 (теперь 964)
    # После:
    # 960:         success = auth.storage.update_user(target_user)
    # 961:
    # 962:         if not success:
    # Вставить перед "if not success" (индекс 961):
    # "        # Вычислить новый статус блокировки для логирования (на основе is_active)\n"
    # "        new_blocked_status = not target_user.is_active\n"
    # "\n"

    # Найти строку "if not success:" после изменений
    insert_idx = None
    for i in range(960, 970):
        if i < len(lines) and "if not success:" in lines[i]:
            insert_idx = i
            break

    if insert_idx:
        lines.insert(insert_idx, "\n")
        lines.insert(insert_idx, "        new_blocked_status = not target_user.is_active\n")
        lines.insert(insert_idx, "        # Вычислить новый статус блокировки для логирования (на основе is_active)\n")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("✅ Исправление #1: access_handlers.py строки 954-960 (handle_confirm_block)")


def fix2_access_handlers_toggle_block():
    """
    Исправление #2: access_handlers.py строки 879-885
    Вычисление is_blocked из is_active (единый источник истины)
    """
    file_path = "src/access_handlers.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Заменить строки 879-885 (индексы 878-884)
    # Старые строки:
    # 879:         action = "разблокировать" if user.is_blocked else "заблокировать"
    # 880:         emoji = "✅" if user.is_blocked else "🚫"
    # 881:
    # 882:         text = (
    # 883:             f"{emoji} **{'РАЗБЛОКИРОВКА' if user.is_blocked else 'БЛОКИРОВКА'} ПОЛЬЗОВАТЕЛЯ**\n\n"
    # 884:             f"Пользователь: {user.username}\n"
    # 885:             f"Текущий статус: {'🚫 Заблокирован' if user.is_blocked else '✅ Активен'}\n\n"

    new_lines = [
        "        # Вычислить статус блокировки из is_active (единый источник истины)\n",
        "        is_blocked = not user.is_active\n",
        "        action = \"разблокировать\" if is_blocked else \"заблокировать\"\n",
        "        emoji = \"✅\" if is_blocked else \"🚫\"\n",
        "\n",
        "        text = (\n",
        "            f\"{emoji} **{'РАЗБЛОКИРОВКА' if is_blocked else 'БЛОКИРОВКА'} ПОЛЬЗОВАТЕЛЯ**\\n\\n\"\n",
        "            f\"Пользователь: {user.username}\\n\"\n",
        "            f\"Текущий статус: {'🚫 Заблокирован' if is_blocked else '✅ Активен'}\\n\\n\"\n"
    ]

    # Заменить строки 879-885 (7 строк → 9 строк)
    lines[878:885] = new_lines

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("✅ Исправление #2: access_handlers.py строки 879-885 (handle_toggle_block_user)")


def fix3_access_markups():
    """
    Исправление #3: access_markups.py строка 141
    Динамическая кнопка на основе is_active
    """
    file_path = "src/access_markups.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Заменить строку 141 (индекс 140)
    # Старая строка:
    # 141:         [InlineKeyboardButton("        🚫 Заблокировать/Разблокировать        ", callback_data=f"access_toggle_block||{user_id}")],

    new_lines = [
        "        # Динамическая кнопка на основе is_active (единый источник истины)\n",
        "        is_blocked = not user.get(\"is_active\", True)\n",
        "        block_button_text = \"✅ Разблокировать\" if is_blocked else \"🚫 Заблокировать\"\n",
        "        [InlineKeyboardButton(f\"        {block_button_text}        \", callback_data=f\"access_toggle_block||{user_id}\")],\n"
    ]

    # Заменить строку 141 (1 строка → 4 строки)
    lines[140:141] = new_lines

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("✅ Исправление #3: access_markups.py строка 141 (access_user_details_markup)")


def main():
    print("🔧 Применение исправлений для синхронизации is_active и is_blocked\n")

    try:
        fix1_access_handlers_confirm_block()
        fix2_access_handlers_toggle_block()
        fix3_access_markups()

        print("\n✅ Все исправления применены успешно!")
        print("\n📋 Изменённые файлы:")
        print("  - src/access_handlers.py (2 места)")
        print("  - src/access_markups.py (1 место)")
        print("\n⚠️ Рекомендуется:")
        print("  1. Проверить синтаксис: python -m py_compile src/access_handlers.py src/access_markups.py")
        print("  2. Запустить тесты (если есть)")
        print("  3. Проверить работу в боте")

    except Exception as e:
        print(f"\n❌ Ошибка при применении исправлений: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
