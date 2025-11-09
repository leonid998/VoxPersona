#!/usr/bin/env python3
"""
Финальный скрипт применения всех исправлений для синхронизации is_active и is_blocked.
Исправляет 3 места в 2 файлах.
"""

def apply_fixes():
    # ============ ФАЙЛ 1: access_handlers.py ============

    with open('src/access_handlers.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # --- ИЗМЕНЕНИЕ A: вызов access_user_details_markup (строка 346) ---
    content = content.replace(
        'reply_markup=access_user_details_markup(user_id),',
        'reply_markup=access_user_details_markup(user, user_id),'
    )
    print("✅ A: Обновлён вызов access_user_details_markup")

    # --- ИЗМЕНЕНИЕ B: handle_toggle_block_user (строки 878-887) ---
    old_b = '''        # Определить действие (блокировать или разблокировать)
        action = "разблокировать" if user.is_blocked else "заблокировать"
        emoji = "✅" if user.is_blocked else "🚫"

        text = (
            f"{emoji} **{'РАЗБЛОКИРОВКА' if user.is_blocked else 'БЛОКИРОВКА'} ПОЛЬЗОВАТЕЛЯ**\\n\\n"
            f"Пользователь: {user.username}\\n"
            f"Текущий статус: {'🚫 Заблокирован' if user.is_blocked else '✅ Активен'}\\n\\n"
            f"⚠️ Вы хотите {action} этого пользователя?\\n\\n"
            "**Вы уверены?**"
        )'''

    new_b = '''        # Определить действие (блокировать или разблокировать)
        # Вычислить статус блокировки из is_active (единый источник истины)
        is_blocked = not user.is_active
        action = "разблокировать" if is_blocked else "заблокировать"
        emoji = "✅" if is_blocked else "🚫"

        # Подготовить тексты для f-string (избегаем backslash)
        block_action = "РАЗБЛОКИРОВКА" if is_blocked else "БЛОКИРОВКА"
        status_display = "🚫 Заблокирован" if is_blocked else "✅ Активен"

        text = (
            f"{emoji} **{block_action} ПОЛЬЗОВАТЕЛЯ**\\n\\n"
            f"Пользователь: {user.username}\\n"
            f"Текущий статус: {status_display}\\n\\n"
            f"⚠️ Вы хотите {action} этого пользователя?\\n\\n"
            "**Вы уверены?**"
        )'''

    content = content.replace(old_b, new_b)
    print("✅ B: Обновлена функция handle_toggle_block_user")

    # --- ИЗМЕНЕНИЕ C: handle_confirm_block - синхронизация (строки 954-960) ---
    old_c = '''        # Переключить статус блокировки
        new_blocked_status = not target_user.is_blocked

        # Обновить статус: изменить поля объекта и сохранить
        target_user.is_blocked = new_blocked_status
        target_user.updated_at = datetime.now()
        success = auth.storage.update_user(target_user)'''

    new_c = '''        # Переключить статус блокировки
        # СИНХРОНИЗАЦИЯ: is_active и is_blocked должны быть инверсны
        # Блокируем: is_active=False, is_blocked=True
        # Разблокируем: is_active=True, is_blocked=False
        new_active_status = target_user.is_blocked  # Инверсия: если был заблокирован → делаем активным

        # Обновить оба поля синхронно (единый источник истины)
        target_user.is_active = new_active_status
        target_user.is_blocked = not new_active_status  # Инверсия is_active
        target_user.updated_at = datetime.now()
        success = auth.storage.update_user(target_user)'''

    content = content.replace(old_c, new_c)
    print("✅ C: Обновлена синхронизация is_active/is_blocked в handle_confirm_block")

    # --- ИЗМЕНЕНИЕ D: добавить вычисление new_blocked_status (после строки 960) ---
    old_d = '''            return

        # Определить текст события для логирования
        event_type = "USER_BLOCKED" if new_blocked_status else "USER_UNBLOCKED"'''

    new_d = '''            return

        # Вычислить новый статус блокировки для логирования (на основе is_active)
        new_blocked_status = not target_user.is_active

        # Определить текст события для логирования
        event_type = "USER_BLOCKED" if new_blocked_status else "USER_UNBLOCKED"'''

    content = content.replace(old_d, new_d)
    print("✅ D: Добавлено вычисление new_blocked_status для логирования")

    # Сохранить изменения
    with open('src/access_handlers.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n📄 Файл src/access_handlers.py обновлён (4 изменения)")

    # ============ ФАЙЛ 2: access_markups.py ============

    with open('src/access_markups.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # --- ИЗМЕНЕНИЕ E: access_user_details_markup - динамическая кнопка ---
    # Изменить сигнатуру функции
    content = content.replace(
        'def access_user_details_markup(user_id: str) -> InlineKeyboardMarkup:',
        'def access_user_details_markup(user, user_id: str) -> InlineKeyboardMarkup:'
    )

    # Заменить статичную кнопку на динамическую
    old_e = '''    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        ✏️ Редактировать        ", callback_data=f"access_edit_user||{user_id}")],
        [InlineKeyboardButton("        🚫 Заблокировать/Разблокировать        ", callback_data=f"access_toggle_block||{user_id}")],
        [InlineKeyboardButton("        🗑 Удалить        ", callback_data=f"access_delete_user_confirm||{user_id}")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_list_users")]
    ])'''

    new_e = '''    # Динамическая кнопка на основе is_active (единый источник истины)
    is_blocked = not user.is_active
    block_button_text = "✅ Разблокировать" if is_blocked else "🚫 Заблокировать"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        ✏️ Редактировать        ", callback_data=f"access_edit_user||{user_id}")],
        [InlineKeyboardButton(f"        {block_button_text}        ", callback_data=f"access_toggle_block||{user_id}")],
        [InlineKeyboardButton("        🗑 Удалить        ", callback_data=f"access_delete_user_confirm||{user_id}")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_list_users")]
    ])'''

    content = content.replace(old_e, new_e)
    print("✅ E: Динамическая кнопка блокировки в access_user_details_markup")

    # Сохранить изменения
    with open('src/access_markups.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n📄 Файл src/access_markups.py обновлён (1 изменение)")
    print("\n" + "="*60)
    print("✅ ВСЕ ИСПРАВЛЕНИЯ ПРИМЕНЕНЫ УСПЕШНО!")
    print("="*60)


if __name__ == '__main__':
    try:
        apply_fixes()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
