#!/usr/bin/env python3
"""
Скрипт для применения исправления #1 в access_handlers.py
Заменяет функцию handle_confirm_block (строки 913-1015)
"""

import re

# Путь к файлу
file_path = "src/access_handlers.py"

# Прочитать файл
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Старая функция (pattern для поиска)
old_pattern = r'async def handle_confirm_block\(chat_id: int, user_id: str, app: Client\):.*?(?=\nasync def handle_delete_user)'

# Новая функция
new_function = """async def handle_confirm_block(chat_id: int, user_id: str, app: Client):
    \"\"\"
    Заблокировать/разблокировать пользователя (Шаг 2: изменение статуса).

    callback_data: "access_confirm_block||{user_id}"

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для блокировки
        app: Pyrogram Client
    \"\"\"
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить администратора и пользователя
        admin_user = auth.storage.get_user_by_telegram_id(chat_id)
        target_user = auth.storage.get_user(user_id)

        if not admin_user or not target_user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Пользователь не найден.",
                message_type="status_message"
            )
            return

        # Проверка: нельзя заблокировать самого себя
        if admin_user.user_id == user_id:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="⚠️ Вы не можете заблокировать себя.",
                message_type="status_message"
            )
            await handle_user_details(chat_id, user_id, app)
            return

        # Переключить статус блокировки
        # СИНХРОНИЗАЦИЯ: is_active и is_blocked должны быть инверсны
        # Блокируем: is_active=False, is_blocked=True
        # Разблокируем: is_active=True, is_blocked=False
        new_active_status = target_user.is_blocked  # Инверсия: если был заблокирован → делаем активным

        # Обновить оба поля синхронно (единый источник истины)
        target_user.is_active = new_active_status
        target_user.is_blocked = not new_active_status  # Инверсия is_active
        target_user.updated_at = datetime.now()
        success = auth.storage.update_user(target_user)

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось изменить статус пользователя.",
                message_type="status_message"
            )
            return

        # Вычислить новый статус блокировки для логирования (на основе is_active)
        new_blocked_status = not target_user.is_active

        # Определить текст события для логирования
        event_type = "USER_BLOCKED" if new_blocked_status else "USER_UNBLOCKED"
        action_text = "заблокирован" if new_blocked_status else "разблокирован"
        emoji = "🚫" if new_blocked_status else "✅"

        # Audit logging
        auth.storage.log_auth_event(
            AuthAuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                user_id=user_id,
                details={
                    "admin_id": admin_user.user_id,
                    "new_status": "blocked" if new_blocked_status else "active"
                }
            )
        )

        # Уведомление о успехе
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                f"{emoji} **Пользователь {action_text}**\\n\\n"
                f"Пользователь: {target_user.username}\\n"
                f"Новый статус: {'🚫 Заблокирован' if new_blocked_status else '✅ Активен'}"
            ),
            message_type="status_message"
        )

        await handle_user_details(chat_id, user_id, app)

        logger.info(
            f"User block toggled: admin_id={admin_user.user_id}, "
            f"target_user_id={user_id}, new_blocked={new_blocked_status}"
        )

    except Exception as e:
        logger.error(f"Error in handle_confirm_block: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при изменении статуса пользователя.",
            message_type="status_message"
        )


"""

# Применить замену
new_content = re.sub(old_pattern, new_function, content, flags=re.DOTALL)

# Проверка что замена произошла
if new_content == content:
    print("❌ ОШИБКА: Замена не произошла! Паттерн не найден.")
    exit(1)

# Сохранить изменённый файл
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Исправление #1 применено успешно!")
print("Функция handle_confirm_block обновлена (строки 913-1015)")
