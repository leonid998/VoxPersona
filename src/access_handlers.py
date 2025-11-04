"""
Handlers для управления доступом (Authorization System).

Модуль содержит 38 функций для управления:
- Пользователями (14 handlers)
- Приглашениями (7 handlers)
- Безопасностью (2 handlers)
- FSM смены пароля (4 handlers)
- Поиск и фильтры (6 handlers)
- Пагинация (2 handlers)
- Вспомогательные (3 handlers)

Интеграция:
- AuthManager через config.get_auth_manager()
- MessageTracker для автоудаления сообщений
- auth_filters.require_role("super_admin") для контроля доступа
- access_markups для UI разметки

Автор: backend-developer
Дата: 17 октября 2025
Задача: T13 (#00005_20251014_HRYHG)
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

# Импорты из существующих модулей
from config import get_auth_manager, user_states
from message_tracker import track_and_send
from access_markups import (
    # Главное меню
    access_main_menu_markup,
    # Управление пользователями
    access_users_menu_markup,
    access_user_list_markup,
    access_user_details_markup,
    access_edit_user_markup,
    access_role_selection_markup,
    access_filter_roles_markup,
    access_search_result_markup,
    # Приглашения
    access_invitations_menu_markup,
    access_invite_list_markup,
    access_invite_details_markup,
    access_invite_type_markup,
    # Безопасность
    access_security_menu_markup,
    access_audit_log_markup,
    access_cleanup_settings_markup,
    # Универсальные
    access_confirm_action_markup,
    access_back_markup,
    access_cancel_markup,
    access_pagination_markup,
)

logger = logging.getLogger(__name__)

# ========================================
# КОНСТАНТЫ
# ========================================

# Пагинация
USERS_PER_PAGE = 10
INVITES_PER_PAGE = 10
AUDIT_LOG_PER_PAGE = 20

# Времена автоудаления (секунды)
NOTIFICATION_DELETE_TIME = 15
ERROR_DELETE_TIME = 10
STATUS_DELETE_TIME = 10

# ========================================
# 1. ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ ДОСТУПОМ
# ========================================

async def handle_access_menu(chat_id: int, app: Client):
    """
    Главное меню управления доступом (Настройки доступа).

    Доступ: только super_admin
    Путь: Главное меню → Системная → Настройки доступа
    callback_data: "menu_access"

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Ошибка: система авторизации недоступна.",
                message_type="menu"
            )
            return

        # Получить информацию о пользователе
        user = auth.storage.get_user_by_telegram_id(chat_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Пользователь не найден.",
                message_type="menu"
            )
            return

        text = (
            "🔐 **НАСТРОЙКИ ДОСТУПА**\n\n"
            f"👤 Администратор: {user.username}\n"
            f"🎭 Роль: {user.role}\n\n"
            "Выберите раздел для управления:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_main_menu_markup(),
            message_type="menu"
        )

        logger.info(f"Access menu shown to chat_id={chat_id}, user_id={user.user_id}")

    except Exception as e:
        logger.error(f"Error in handle_access_menu: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке меню.",
            message_type="menu"
        )


# ========================================
# 2. УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (14 функций)
# ========================================

async def handle_users_menu(chat_id: int, app: Client):
    """
    Меню управления пользователями.

    callback_data: "access_users_menu"

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        text = (
            "👥 **УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ**\n\n"
            "Выберите действие:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_users_menu_markup(),
            message_type="menu"
        )

        logger.info(f"Users menu shown to chat_id={chat_id}")

    except Exception as e:
        logger.error(f"Error in handle_users_menu: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке меню пользователей.",
            message_type="menu"
        )


async def handle_list_users(chat_id: int, page: int = 1, app: Client = None, role_filter: Optional[str] = None):
    """
    Список пользователей с пагинацией (10 на страницу).

    callback_data: "access_list_users" или "access_list_users||page||{num}"
    Источник: 01_menu_structure.md:336-357, 02_menu_navigation.md:186-242

    Args:
        chat_id: Telegram chat_id
        page: Номер страницы (1-based)
        app: Pyrogram Client
        role_filter: Фильтр по роли (super_admin/admin/user/guest/all)
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить список всех пользователей
        all_users = auth.storage.list_users()

        # Применить фильтр по роли если задан
        if role_filter and role_filter != "all":
            all_users = [u for u in all_users if u.role == role_filter]

        # Пагинация
        total_users = len(all_users)
        total_pages = max(1, (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        users_page = all_users[start_idx:end_idx]

        # Преобразовать в словари для разметки
        users_dict = []
        for user in users_page:
            users_dict.append({
                "user_id": user.user_id,
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked
            })

        # Формат текста
        filter_text = f" (фильтр: {role_filter})" if role_filter and role_filter != "all" else ""
        text = (
            f"📋 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ**{filter_text}\n\n"
            f"Всего пользователей: {total_users}\n"
            f"Страница {page}/{total_pages}\n\n"
            "Выберите пользователя для просмотра деталей:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_user_list_markup(users_dict, page, total_pages),
            message_type="menu"
        )

        logger.info(f"User list shown to chat_id={chat_id}, page={page}/{total_pages}, filter={role_filter}")

    except Exception as e:
        logger.error(f"Error in handle_list_users: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке списка пользователей.",
            message_type="menu"
        )


async def handle_user_details(chat_id: int, user_id: str, app: Client):
    """
    Детали пользователя с действиями.

    callback_data: "access_user_details||{user_id}"
    Источник: 02_menu_navigation.md:188-228

    Args:
        chat_id: Telegram chat_id
        user_id: user_id пользователя для просмотра
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Пользователь с ID {user_id} не найден.",
                message_type="menu"
            )
            return

        # Эмодзи для статуса
        status_emoji = "✅" if user.is_active else "🚫"
        status_text = "Активен" if user.is_active else "Заблокирован"

        # Эмодзи для роли
        role_emojis = {
            "super_admin": "👑",
            "admin": "⚙️",
            "user": "👤",
            "guest": "🎭"
        }
        role_emoji = role_emojis.get(user.role, "👤")

        # Дата последнего входа
        last_login_text = "Никогда"
        if user.last_login_at:
            try:
                last_login = datetime.fromisoformat(user.last_login_at)
                last_login_text = last_login.strftime("%d.%m.%Y %H:%M")
            except:
                last_login_text = user.last_login_at

        # Требуется ли смена пароля
        password_change_text = "🔒 Требуется" if user.must_change_password else "✅ Не требуется"

        text = (
            f"👤 **ДЕТАЛИ ПОЛЬЗОВАТЕЛЯ**\n\n"
            f"**Имя:** {user.username}\n"
            f"**User ID:** `{user.user_id}`\n"
            f"**Telegram ID:** `{user.telegram_id}`\n"
            f"**Роль:** {role_emoji} {user.role}\n"
            f"**Статус:** {status_emoji} {status_text}\n"
            f"**Последний вход:** {last_login_text}\n"
            f"**Смена пароля:** {password_change_text}\n"
            f"**Дата создания:** {user.created_at[:10]}\n\n"
            "Выберите действие:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_user_details_markup(user_id),
            message_type="menu"
        )

        logger.info(f"User details shown: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_user_details: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке деталей пользователя.",
            message_type="menu"
        )


async def handle_edit_user(chat_id: int, user_id: str, app: Client):
    """
    Меню редактирования пользователя.

    callback_data: "access_edit_user||{user_id}"
    Источник: 01_menu_structure.md:360-377

    Args:
        chat_id: Telegram chat_id
        user_id: user_id пользователя для редактирования
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Пользователь с ID {user_id} не найден.",
                message_type="menu"
            )
            return

        text = (
            f"✏️ **РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ**\n\n"
            f"Пользователь: {user.username}\n"
            f"Текущая роль: {user.role}\n\n"
            "Выберите действие:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_edit_user_markup(user_id),
            message_type="menu"
        )

        logger.info(f"Edit user menu shown: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_edit_user: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке меню редактирования.",
            message_type="menu"
        )


async def handle_change_role(chat_id: int, user_id: str, app: Client):
    """
    Запустить FSM смены роли пользователя (Шаг 1: выбор роли).

    callback_data: "access_change_role||{user_id}"
    Источник: 02_menu_navigation.md:194-200

    Args:
        chat_id: Telegram chat_id
        user_id: user_id пользователя для смены роли
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Пользователь с ID {user_id} не найден.",
                message_type="menu"
            )
            return

        text = (
            f"🎭 **ИЗМЕНЕНИЕ РОЛИ**\n\n"
            f"Пользователь: {user.username}\n"
            f"Текущая роль: {user.role}\n\n"
            "Выберите новую роль:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_role_selection_markup(user_id),
            message_type="menu"
        )

        logger.info(f"Role selection shown: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_change_role: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке меню смены роли.",
            message_type="menu"
        )


async def handle_confirm_role_change(chat_id: int, user_id: str, role: str, app: Client):
    """
    Установить роль пользователя (Шаг 2: подтверждение).

    callback_data: "access_set_role||{user_id}||{role}"

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для смены роли
        role: Новая роль (super_admin/admin/user/guest)
        app: Pyrogram Client
    """
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

        # Проверка: нельзя изменить роль самого себя
        if admin_user.user_id == user_id:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="⚠️ Вы не можете изменить собственную роль.",
                message_type="status_message"
            )
            await asyncio.sleep(ERROR_DELETE_TIME)
            await handle_edit_user(chat_id, user_id, app)
            return

        # Валидация роли
        valid_roles = ["super_admin", "admin", "user", "guest"]
        if role not in valid_roles:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Недопустимая роль: {role}",
                message_type="status_message"
            )
            return

        # Сохранить старую роль для логирования
        old_role = target_user.role

        # Обновить роль через AuthManager
        success = auth.storage.update_user(
            user_id=user_id,
            role=role
        )

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось изменить роль пользователя.",
                message_type="status_message"
            )
            return

        # Audit logging
        auth.storage.log_auth_event(
            event_type="ROLE_CHANGED",
            user_id=user_id,
            metadata={
                "admin_id": admin_user.user_id,
                "old_role": old_role,
                "new_role": role,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Уведомление о успехе (автоудаление через 15 сек)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                f"✅ **Роль изменена**\n\n"
                f"Пользователь: {target_user.username}\n"
                f"Старая роль: {old_role}\n"
                f"Новая роль: {role}"
            ),
            message_type="status_message"
        )

        # Подождать перед возвратом к меню
        await asyncio.sleep(NOTIFICATION_DELETE_TIME)
        await handle_user_details(chat_id, user_id, app)

        logger.info(
            f"Role changed: admin_id={admin_user.user_id}, "
            f"target_user_id={user_id}, old_role={old_role}, new_role={role}"
        )

    except Exception as e:
        logger.error(f"Error in handle_confirm_role_change: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при смене роли.",
            message_type="status_message"
        )


async def handle_reset_password(chat_id: int, user_id: str, app: Client):
    """
    Запросить подтверждение сброса пароля (Шаг 1: подтверждение).

    callback_data: "access_reset_password||{user_id}"
    Источник: 02_menu_navigation.md:208-212

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для сброса пароля
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Пользователь с ID {user_id} не найден.",
                message_type="menu"
            )
            return

        text = (
            f"🔑 **СБРОС ПАРОЛЯ**\n\n"
            f"Пользователь: {user.username}\n"
            f"Telegram ID: `{user.telegram_id}`\n\n"
            "⚠️ Будет сгенерирован новый временный пароль (16 символов).\n"
            "Пользователю будет необходимо сменить его при следующем входе.\n\n"
            "**Вы уверены?**"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_confirm_action_markup(
                confirm_callback=f"access_confirm_reset||{user_id}",
                cancel_callback=f"access_edit_user||{user_id}"
            ),
            message_type="confirmation"
        )

        logger.info(f"Reset password confirmation shown: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_reset_password: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при запросе сброса пароля.",
            message_type="menu"
        )


async def handle_confirm_reset_password(chat_id: int, user_id: str, app: Client):
    """
    Сбросить пароль пользователя (Шаг 2: генерация нового).

    callback_data: "access_confirm_reset||{user_id}"

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для сброса пароля
        app: Pyrogram Client
    """
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

        # Генерировать новый временный пароль (16 символов)
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(16))

        # Установить срок действия временного пароля (3 дня)
        expires_at = datetime.now() + timedelta(days=3)

        # Обновить пароль через AuthManager
        success = auth.storage.update_user_password(
            user_id=user_id,
            new_password=new_password,
            must_change_password=True,
            temp_password_expires_at=expires_at.isoformat()
        )

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось сбросить пароль пользователя.",
                message_type="status_message"
            )
            return

        # Audit logging
        auth.storage.log_auth_event(
            event_type="PASSWORD_RESET",
            user_id=user_id,
            metadata={
                "admin_id": admin_user.user_id,
                "reset_by_admin": True,
                "expires_at": expires_at.isoformat(),
                "timestamp": datetime.now().isoformat()
            }
        )

        # Отправить пароль пользователю через Telegram
        try:
            await app.send_message(
                chat_id=target_user.telegram_id,
                text=(
                    "🔑 **Ваш пароль был сброшен администратором**\n\n"
                    f"Новый временный пароль: `{new_password}`\n\n"
                    "⚠️ **ВАЖНО:**\n"
                    "- Скопируйте пароль сейчас (он больше не будет показан)\n"
                    "- Срок действия: 3 дня\n"
                    "- При следующем входе вам нужно будет сменить пароль\n"
                    "- Используйте команду /change_password для смены"
                )
            )
            logger.info(f"Temporary password sent to user telegram_id={target_user.telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send password to user: {e}")
            # Продолжаем даже если не удалось отправить

        # Уведомление администратора
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                f"✅ **Пароль сброшен**\n\n"
                f"Пользователь: {target_user.username}\n"
                f"Новый пароль: `{new_password}`\n\n"
                f"Срок действия: {expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Пароль отправлен пользователю в личные сообщения."
            ),
            message_type="status_message"
        )

        # Подождать перед возвратом к меню
        await asyncio.sleep(NOTIFICATION_DELETE_TIME)
        await handle_user_details(chat_id, user_id, app)

        logger.info(
            f"Password reset: admin_id={admin_user.user_id}, "
            f"target_user_id={user_id}, expires_at={expires_at.isoformat()}"
        )

    except Exception as e:
        logger.error(f"Error in handle_confirm_reset_password: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при сбросе пароля.",
            message_type="status_message"
        )


async def handle_toggle_block_user(chat_id: int, user_id: str, app: Client):
    """
    Запросить подтверждение блокировки/разблокировки (Шаг 1: подтверждение).

    callback_data: "access_toggle_block||{user_id}"
    Источник: 02_menu_navigation.md:216-220

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для блокировки
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Пользователь с ID {user_id} не найден.",
                message_type="menu"
            )
            return

        # Определить действие (блокировать или разблокировать)
        action = "разблокировать" if user.is_blocked else "заблокировать"
        emoji = "✅" if user.is_blocked else "🚫"

        text = (
            f"{emoji} **{'РАЗБЛОКИРОВКА' if user.is_blocked else 'БЛОКИРОВКА'} ПОЛЬЗОВАТЕЛЯ**\n\n"
            f"Пользователь: {user.username}\n"
            f"Текущий статус: {'🚫 Заблокирован' if user.is_blocked else '✅ Активен'}\n\n"
            f"⚠️ Вы хотите {action} этого пользователя?\n\n"
            "**Вы уверены?**"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_confirm_action_markup(
                confirm_callback=f"access_confirm_block||{user_id}",
                cancel_callback=f"access_user_details||{user_id}"
            ),
            message_type="confirmation"
        )

        logger.info(f"Toggle block confirmation shown: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_toggle_block_user: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при запросе блокировки.",
            message_type="menu"
        )


async def handle_confirm_block(chat_id: int, user_id: str, app: Client):
    """
    Заблокировать/разблокировать пользователя (Шаг 2: изменение статуса).

    callback_data: "access_confirm_block||{user_id}"

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для блокировки
        app: Pyrogram Client
    """
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
            await asyncio.sleep(ERROR_DELETE_TIME)
            await handle_user_details(chat_id, user_id, app)
            return

        # Переключить статус блокировки
        new_blocked_status = not target_user.is_blocked
        new_active_status = not new_blocked_status  # is_active противоположен is_blocked

        # Обновить статус через AuthManager
        success = auth.storage.update_user(
            user_id=user_id,
            is_blocked=new_blocked_status,
            is_active=new_active_status
        )

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось изменить статус пользователя.",
                message_type="status_message"
            )
            return

        # Определить текст события для логирования
        event_type = "USER_BLOCKED" if new_blocked_status else "USER_UNBLOCKED"
        action_text = "заблокирован" if new_blocked_status else "разблокирован"
        emoji = "🚫" if new_blocked_status else "✅"

        # Audit logging
        auth.storage.log_auth_event(
            event_type=event_type,
            user_id=user_id,
            metadata={
                "admin_id": admin_user.user_id,
                "new_status": "blocked" if new_blocked_status else "active",
                "timestamp": datetime.now().isoformat()
            }
        )

        # Уведомление о успехе
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                f"{emoji} **Пользователь {action_text}**\n\n"
                f"Пользователь: {target_user.username}\n"
                f"Новый статус: {'🚫 Заблокирован' if new_blocked_status else '✅ Активен'}"
            ),
            message_type="status_message"
        )

        # Подождать перед возвратом к меню
        await asyncio.sleep(NOTIFICATION_DELETE_TIME)
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


async def handle_delete_user(chat_id: int, user_id: str, app: Client):
    """
    Запросить подтверждение удаления (Шаг 1: подтверждение).

    callback_data: "access_delete_user_confirm||{user_id}"
    Источник: 02_menu_navigation.md:222-226

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для удаления
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Пользователь с ID {user_id} не найден.",
                message_type="menu"
            )
            return

        text = (
            f"🗑 **УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ**\n\n"
            f"Пользователь: {user.username}\n"
            f"User ID: `{user.user_id}`\n"
            f"Роль: {user.role}\n\n"
            "⚠️ **ВНИМАНИЕ:**\n"
            "- Будут удалены ВСЕ данные пользователя\n"
            "- Будут удалены ВСЕ сессии пользователя\n"
            "- Это действие **НЕОБРАТИМО**\n\n"
            "**Вы АБСОЛЮТНО уверены?**"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_confirm_action_markup(
                confirm_callback=f"access_confirm_delete||{user_id}",
                cancel_callback=f"access_user_details||{user_id}"
            ),
            message_type="confirmation"
        )

        logger.info(f"Delete user confirmation shown: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_delete_user: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при запросе удаления.",
            message_type="menu"
        )


async def handle_confirm_delete(chat_id: int, user_id: str, app: Client):
    """
    Удалить пользователя (Шаг 2: удаление).

    callback_data: "access_confirm_delete||{user_id}"

    Args:
        chat_id: Telegram chat_id администратора
        user_id: user_id пользователя для удаления
        app: Pyrogram Client
    """
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

        # Проверка: нельзя удалить самого себя
        if admin_user.user_id == user_id:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="⚠️ Вы не можете удалить себя.",
                message_type="status_message"
            )
            await asyncio.sleep(ERROR_DELETE_TIME)
            await handle_user_details(chat_id, user_id, app)
            return

        # Сохранить данные для логирования
        deleted_username = target_user.username
        deleted_role = target_user.role

        # Удалить все сессии пользователя
        try:
            auth.storage.delete_all_sessions(user_id)
            logger.info(f"All sessions deleted for user_id={user_id}")
        except Exception as e:
            logger.error(f"Failed to delete sessions for user_id={user_id}: {e}")

        # Удалить пользователя через AuthManager
        success = auth.storage.delete_user(user_id)

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось удалить пользователя.",
                message_type="status_message"
            )
            return

        # Audit logging
        auth.storage.log_auth_event(
            event_type="USER_DELETED",
            user_id=user_id,
            metadata={
                "admin_id": admin_user.user_id,
                "deleted_username": deleted_username,
                "deleted_role": deleted_role,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Уведомление о успехе
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                f"✅ **Пользователь удален**\n\n"
                f"Пользователь: {deleted_username}\n"
                f"Роль: {deleted_role}\n"
                f"Все данные и сессии удалены."
            ),
            message_type="status_message"
        )

        # Подождать перед возвратом к списку пользователей
        await asyncio.sleep(NOTIFICATION_DELETE_TIME)
        await handle_list_users(chat_id, 1, app)

        logger.info(
            f"User deleted: admin_id={admin_user.user_id}, "
            f"deleted_user_id={user_id}, username={deleted_username}"
        )

    except Exception as e:
        logger.error(f"Error in handle_confirm_delete: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при удалении пользователя.",
            message_type="status_message"
        )


async def handle_filter_users_by_role(chat_id: int, app: Client):
    """
    Фильтр по ролям для списка пользователей.

    callback_data: "access_filter_roles"
    Источник: 02_menu_navigation.md:231-238

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        text = (
            "🎭 **ФИЛЬТР ПО РОЛЯМ**\n\n"
            "Выберите роль для фильтрации списка пользователей:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_filter_roles_markup(),
            message_type="menu"
        )

        logger.info(f"Role filter menu shown to chat_id={chat_id}")

    except Exception as e:
        logger.error(f"Error in handle_filter_users_by_role: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке фильтра.",
            message_type="menu"
        )


async def handle_search_user(chat_id: int, app: Client):
    """
    FSM: поиск пользователя (Шаг 1: запрос ввода имени/ID).

    callback_data: "access_search_user"
    Источник: 02_menu_navigation.md:230, 712-713

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        # Установить FSM состояние
        user_states[chat_id] = {
            "step": "access_search_user_input",
            "previous_menu": "access_users_menu"
        }

        text = (
            "🔍 **ПОИСК ПОЛЬЗОВАТЕЛЯ**\n\n"
            "Введите:\n"
            "- Имя пользователя (username)\n"
            "- Telegram ID\n"
            "- User ID\n\n"
            "Для отмены нажмите кнопку ниже."
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_cancel_markup("access_users_menu"),
            message_type="input_request"
        )

        logger.info(f"Search user input request sent to chat_id={chat_id}")

    except Exception as e:
        logger.error(f"Error in handle_search_user: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при запуске поиска.",
            message_type="menu"
        )


async def handle_search_user_input(chat_id: int, query: str, app: Client):
    """
    Обработать ввод поискового запроса (Шаг 2: показ результатов).

    FSM step: "access_search_user_input"

    Args:
        chat_id: Telegram chat_id
        query: Поисковый запрос (username, telegram_id, user_id)
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Поиск пользователей
        all_users = auth.storage.list_users()
        found_users = []

        query_lower = query.lower().strip()

        for user in all_users:
            # Поиск по username
            if user.username and query_lower in user.username.lower():
                found_users.append(user)
                continue

            # Поиск по telegram_id
            if str(user.telegram_id) == query_lower:
                found_users.append(user)
                continue

            # Поиск по user_id
            if user.user_id.lower() == query_lower:
                found_users.append(user)
                continue

        # Очистить FSM состояние
        if chat_id in user_states:
            user_states.pop(chat_id)

        # Показать результаты
        if not found_users:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=(
                    f"🔍 **РЕЗУЛЬТАТЫ ПОИСКА**\n\n"
                    f"По запросу \"{query}\" ничего не найдено.\n\n"
                    "Попробуйте:\n"
                    "- Проверить правильность написания\n"
                    "- Использовать точный Telegram ID\n"
                    "- Использовать User ID"
                ),
                reply_markup=access_back_markup("access_users_menu"),
                message_type="menu"
            )
            logger.info(f"Search completed: chat_id={chat_id}, query={query}, found=0")
            return

        # Преобразовать в словари для разметки
        users_dict = []
        for user in found_users[:10]:  # Ограничение 10 результатов
            users_dict.append({
                "user_id": user.user_id,
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked
            })

        text = (
            f"🔍 **РЕЗУЛЬТАТЫ ПОИСКА**\n\n"
            f"По запросу \"{query}\" найдено: {len(found_users)}\n"
            f"Показаны первые {min(len(found_users), 10)} результатов:\n\n"
            "Выберите пользователя:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_search_result_markup(users_dict),
            message_type="menu"
        )

        logger.info(f"Search completed: chat_id={chat_id}, query={query}, found={len(found_users)}")

    except Exception as e:
        logger.error(f"Error in handle_search_user_input: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при поиске пользователей.",
            message_type="menu"
        )


# ========================================
# 3. ПРИГЛАШЕНИЯ (7 функций)
# ========================================

async def handle_invitations_menu(chat_id: int, app: Client):
    """
    Меню управления приглашениями.

    callback_data: "access_invitations_menu"
    Источник: 01_menu_structure.md:380-397

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        text = (
            "📨 **УПРАВЛЕНИЕ ПРИГЛАШЕНИЯМИ**\n\n"
            "Создавайте пригласительные ссылки для новых пользователей.\n\n"
            "Выберите действие:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_invitations_menu_markup(),
            message_type="menu"
        )

        logger.info(f"Invitations menu shown to chat_id={chat_id}")

    except Exception as e:
        logger.error(f"Error in handle_invitations_menu: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке меню приглашений.",
            message_type="menu"
        )


async def handle_create_invitation(chat_id: int, role: str, app: Client):
    """
    Выбор типа приглашения для создания.

    callback_data: "access_create_invite_admin" или "access_create_invite_user"
    Источник: 02_menu_navigation.md:251-259

    Args:
        chat_id: Telegram chat_id администратора
        role: Роль для приглашения (admin или user)
        app: Pyrogram Client
    """
    try:
        # K-02: RBAC проверка - получить пользователя и проверить роль
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        current_user = auth.storage.get_user_by_telegram_id(chat_id)
        if not current_user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Пользователь не найден.",
                message_type="status_message"
            )
            return

        # K-02: КРИТИЧНО - проверка роли
        if current_user.role != "admin":
            # Audit logging: попытка нарушения RBAC
            auth.storage.log_auth_event(
                event_type="RBAC_VIOLATION",
                user_id=current_user.user_id,
                metadata={
                    "action": "create_invitation_request",
                    "required_role": "admin",
                    "actual_role": current_user.role,
                    "telegram_id": chat_id,
                    "timestamp": datetime.now().isoformat()
                }
            )

            logger.warning(
                f"RBAC violation: user_id={current_user.user_id} "
                f"(role={current_user.role}) attempted to create invitation"
            )

            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ **Доступ запрещен**\n\nТолько администраторы могут создавать приглашения.",
                message_type="status_message"
            )
            return

        # Валидация роли
        if role not in ["admin", "user"]:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Недопустимая роль для приглашения: {role}",
                message_type="status_message"
            )
            return

        role_emoji = "⚙️" if role == "admin" else "👤"
        role_name = "Администратора" if role == "admin" else "Пользователя"

        # Установить FSM состояние
        user_states[chat_id] = {
            "step": "creating_invitation",
            "role": role,
            "expires_hours": 720  # По умолчанию 30 дней
        }

        text = (
            f"{role_emoji} **СОЗДАНИЕ ПРИГЛАШЕНИЯ ДЛЯ {role_name.upper()}**\n\n"
            f"Роль: {role_name}\n"
            f"Срок действия: 30 дней (720 часов)\n\n"
            "Будет создано приглашение с уникальной ссылкой и QR-кодом.\n\n"
            "**Продолжить?**"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_confirm_action_markup(
                confirm_callback=f"access_confirm_create_invite||{role}",
                cancel_callback="access_invitations_menu"
            ),
            message_type="confirmation"
        )

        logger.info(f"Create invitation confirmation shown: chat_id={chat_id}, role={role}")

    except Exception as e:
        logger.error(f"Error in handle_create_invitation: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при создании приглашения.",
            message_type="menu"
        )


async def handle_confirm_create_invite(chat_id: int, role: str, app: Client):
    """
    Создать приглашение (Шаг 2: генерация).

    callback_data: "access_confirm_create_invite||{role}"

    Args:
        chat_id: Telegram chat_id администратора
        role: Роль для приглашения (admin или user)
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить администратора
        admin_user = auth.storage.get_user_by_telegram_id(chat_id)
        if not admin_user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Администратор не найден.",
                message_type="status_message"
            )
            return

        # K-02: КРИТИЧНО - проверка роли
        if admin_user.role != "admin":
            # Audit logging: попытка нарушения RBAC
            auth.storage.log_auth_event(
                event_type="RBAC_VIOLATION",
                user_id=admin_user.user_id,
                metadata={
                    "action": "create_invitation",
                    "required_role": "admin",
                    "actual_role": admin_user.role,
                    "telegram_id": chat_id,
                    "timestamp": datetime.now().isoformat()
                }
            )

            logger.warning(
                f"RBAC violation: user_id={admin_user.user_id} "
                f"(role={admin_user.role}) attempted to create invitation"
            )

            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ **Доступ запрещен**\n\nТолько администраторы могут создавать приглашения.",
                message_type="status_message"
            )
            return

        # Получить срок действия из FSM или использовать по умолчанию
        state = user_states.get(chat_id, {})
        expires_hours = state.get("expires_hours", 720)
        expires_at = datetime.now() + timedelta(hours=expires_hours)

        # Генерировать invite_code через AuthSecurityManager
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        invite_code = ''.join(secrets.choice(alphabet) for _ in range(32))

        # Создать приглашение через AuthManager
        success = auth.storage.create_invitation(
            invite_code=invite_code,
            role=role,
            created_by=admin_user.user_id,
            expires_at=expires_at.isoformat()
        )

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось создать приглашение.",
                message_type="status_message"
            )
            return

        # Очистить FSM состояние
        if chat_id in user_states:
            user_states.pop(chat_id)

        # Генерировать ссылку приглашения
        bot_username = (await app.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start={invite_code}"

        # Генерировать QR-код (если доступна библиотека qrcode)
        qr_code_sent = False
        try:
            import qrcode
            from io import BytesIO

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(invite_link)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)

            # Отправить QR-код
            await app.send_photo(
                chat_id=chat_id,
                photo=buf,
                caption=f"QR-код приглашения ({role})"
            )
            qr_code_sent = True

        except ImportError:
            logger.warning("qrcode library not available, skipping QR generation")
        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")

        # Audit logging
        auth.storage.log_auth_event(
            event_type="INVITE_CREATED",
            user_id=admin_user.user_id,
            metadata={
                "invite_code": invite_code,
                "role": role,
                "expires_at": expires_at.isoformat(),
                "timestamp": datetime.now().isoformat()
            }
        )

        # Уведомление о успехе
        qr_text = "\n✅ QR-код отправлен выше" if qr_code_sent else ""

        text = (
            f"✅ **ПРИГЛАШЕНИЕ СОЗДАНО**\n\n"
            f"Роль: {role}\n"
            f"Код: `{invite_code}`\n"
            f"Срок действия: {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"**Ссылка для приглашения:**\n"
            f"{invite_link}\n{qr_text}\n\n"
            "Отправьте эту ссылку новому пользователю."
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_back_markup("access_invitations_menu"),
            message_type="menu"
        )

        logger.info(
            f"Invitation created: admin_id={admin_user.user_id}, "
            f"invite_code={invite_code}, role={role}"
        )

    except Exception as e:
        logger.error(f"Error in handle_confirm_create_invite: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при создании приглашения.",
            message_type="status_message"
        )


async def handle_list_invitations(chat_id: int, page: int = 1, app: Client = None):
    """
    Список активных приглашений с пагинацией.

    callback_data: "access_list_invites" или "access_list_invites||page||{num}"
    Источник: 02_menu_navigation.md:265-279

    Args:
        chat_id: Telegram chat_id
        page: Номер страницы (1-based)
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить список всех активных приглашений
        all_invites = auth.storage.list_invitations(active_only=True)

        # Пагинация
        total_invites = len(all_invites)
        total_pages = max(1, (total_invites + INVITES_PER_PAGE - 1) // INVITES_PER_PAGE)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * INVITES_PER_PAGE
        end_idx = start_idx + INVITES_PER_PAGE
        invites_page = all_invites[start_idx:end_idx]

        # Преобразовать в словари для разметки
        invites_dict = []
        for invite in invites_page:
            invites_dict.append({
                "invite_code": invite.invite_code,
                "role": invite.role,
                "expires_at": invite.expires_at,
                "created_by": invite.created_by
            })

        # Формат текста
        text = (
            f"📋 **СПИСОК АКТИВНЫХ ПРИГЛАШЕНИЙ**\n\n"
            f"Всего приглашений: {total_invites}\n"
            f"Страница {page}/{total_pages}\n\n"
            "Выберите приглашение для просмотра деталей:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_invite_list_markup(invites_dict, page, total_pages),
            message_type="menu"
        )

        logger.info(f"Invitation list shown to chat_id={chat_id}, page={page}/{total_pages}")

    except Exception as e:
        logger.error(f"Error in handle_list_invitations: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке списка приглашений.",
            message_type="menu"
        )


async def handle_invitation_details(chat_id: int, invite_code: str, app: Client):
    """
    Детали приглашения с действиями.

    callback_data: "access_invite_details||{invite_code}"
    Источник: 02_menu_navigation.md:267-276

    Args:
        chat_id: Telegram chat_id
        invite_code: Код приглашения
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить приглашение
        invite = auth.storage.get_invitation(invite_code)
        if not invite:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Приглашение с кодом {invite_code[:8]}... не найдено.",
                message_type="menu"
            )
            return

        # Эмодзи для роли
        role_emoji = "⚙️" if invite.role == "admin" else "👤"

        # Статус приглашения
        status_emoji = "✅"
        status_text = "Активно"

        if invite.used:
            status_emoji = "🔒"
            status_text = "Использовано"
        elif not invite.is_active:
            status_emoji = "🚫"
            status_text = "Аннулировано"

        # Дата истечения
        expires_text = "Истек"
        if invite.expires_at:
            try:
                expires = datetime.fromisoformat(invite.expires_at)
                if expires > datetime.now():
                    expires_text = expires.strftime("%d.%m.%Y %H:%M")
                else:
                    status_emoji = "⏰"
                    status_text = "Истек"
            except:
                expires_text = invite.expires_at

        # Создатель
        creator = auth.storage.get_user(invite.created_by)
        creator_name = creator.username if creator else invite.created_by

        # Генерировать ссылку
        bot_username = (await app.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start={invite_code}"

        text = (
            f"📨 **ДЕТАЛИ ПРИГЛАШЕНИЯ**\n\n"
            f"**Роль:** {role_emoji} {invite.role}\n"
            f"**Код:** `{invite_code}`\n"
            f"**Статус:** {status_emoji} {status_text}\n"
            f"**Создатель:** {creator_name}\n"
            f"**Действителен до:** {expires_text}\n"
            f"**Дата создания:** {invite.created_at[:10]}\n\n"
            f"**Ссылка:**\n{invite_link}\n\n"
            "Выберите действие:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_invite_details_markup(invite_code),
            message_type="menu"
        )

        logger.info(f"Invitation details shown: chat_id={chat_id}, invite_code={invite_code}")

    except Exception as e:
        logger.error(f"Error in handle_invitation_details: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке деталей приглашения.",
            message_type="menu"
        )


async def handle_revoke_invitation(chat_id: int, invite_code: str, app: Client):
    """
    Запросить подтверждение аннулирования приглашения (Шаг 1: подтверждение).

    callback_data: "access_revoke_invite||{invite_code}"
    Источник: 02_menu_navigation.md:270-274

    Args:
        chat_id: Telegram chat_id администратора
        invite_code: Код приглашения для аннулирования
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить приглашение
        invite = auth.storage.get_invitation(invite_code)
        if not invite:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ Приглашение с кодом {invite_code[:8]}... не найдено.",
                message_type="menu"
            )
            return

        # Проверка: уже аннулировано
        if not invite.is_active:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="⚠️ Это приглашение уже аннулировано.",
                message_type="status_message"
            )
            await asyncio.sleep(ERROR_DELETE_TIME)
            await handle_invitation_details(chat_id, invite_code, app)
            return

        text = (
            f"🗑 **АННУЛИРОВАНИЕ ПРИГЛАШЕНИЯ**\n\n"
            f"Роль: {invite.role}\n"
            f"Код: `{invite_code[:16]}...`\n\n"
            "⚠️ После аннулирования ссылка перестанет работать.\n"
            "Это действие **НЕОБРАТИМО**.\n\n"
            "**Вы уверены?**"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_confirm_action_markup(
                confirm_callback=f"access_confirm_revoke||{invite_code}",
                cancel_callback=f"access_invite_details||{invite_code}"
            ),
            message_type="confirmation"
        )

        logger.info(f"Revoke invitation confirmation shown: chat_id={chat_id}, invite_code={invite_code}")

    except Exception as e:
        logger.error(f"Error in handle_revoke_invitation: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при запросе аннулирования.",
            message_type="menu"
        )


async def handle_confirm_revoke(chat_id: int, invite_code: str, app: Client):
    """
    Аннулировать приглашение (Шаг 2: аннулирование).

    callback_data: "access_confirm_revoke||{invite_code}"

    Args:
        chat_id: Telegram chat_id администратора
        invite_code: Код приглашения для аннулирования
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить администратора
        admin_user = auth.storage.get_user_by_telegram_id(chat_id)
        if not admin_user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Администратор не найден.",
                message_type="status_message"
            )
            return

        # Деактивировать приглашение через AuthManager
        success = auth.storage.revoke_invitation(invite_code)

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось аннулировать приглашение.",
                message_type="status_message"
            )
            return

        # Audit logging
        auth.storage.log_auth_event(
            event_type="INVITE_REVOKED",
            user_id=admin_user.user_id,
            metadata={
                "invite_code": invite_code,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Уведомление о успехе
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                f"✅ **Приглашение аннулировано**\n\n"
                f"Код: `{invite_code[:16]}...`\n"
                f"Ссылка больше не работает."
            ),
            message_type="status_message"
        )

        # Подождать перед возвратом к списку приглашений
        await asyncio.sleep(NOTIFICATION_DELETE_TIME)
        await handle_list_invitations(chat_id, 1, app)

        logger.info(
            f"Invitation revoked: admin_id={admin_user.user_id}, "
            f"invite_code={invite_code}"
        )

    except Exception as e:
        logger.error(f"Error in handle_confirm_revoke: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при аннулировании приглашения.",
            message_type="status_message"
        )


# ========================================
# 4. БЕЗОПАСНОСТЬ (2 функции)
# ========================================

async def handle_security_menu(chat_id: int, app: Client):
    """
    Меню настроек безопасности.

    callback_data: "access_security_menu"
    Источник: 01_menu_structure.md:400-417

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        text = (
            "🔐 **НАСТРОЙКИ БЕЗОПАСНОСТИ**\n\n"
            "Управление безопасностью системы:\n"
            "- Журнал действий администраторов\n"
            "- Автоочистка сообщений\n"
            "- Политика паролей\n\n"
            "Выберите раздел:"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_security_menu_markup(),
            message_type="menu"
        )

        logger.info(f"Security menu shown to chat_id={chat_id}")

    except Exception as e:
        logger.error(f"Error in handle_security_menu: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке меню безопасности.",
            message_type="menu"
        )


async def handle_audit_log(chat_id: int, page: int = 1, app: Client = None):
    """
    Меню журнала действий (audit log).

    callback_data: "access_audit_log" или "access_audit_log||page||{num}"
    Источник: 02_menu_navigation.md:317-323

    Args:
        chat_id: Telegram chat_id
        page: Номер страницы (1-based)
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить список событий из audit log
        all_events = auth.storage.get_audit_log(limit=1000)  # Последние 1000 событий

        # Пагинация
        total_events = len(all_events)
        total_pages = max(1, (total_events + AUDIT_LOG_PER_PAGE - 1) // AUDIT_LOG_PER_PAGE)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * AUDIT_LOG_PER_PAGE
        end_idx = start_idx + AUDIT_LOG_PER_PAGE
        events_page = all_events[start_idx:end_idx]

        # Форматировать события
        events_text = ""
        for event in events_page:
            # Эмодзи для типа события
            event_emojis = {
                "LOGIN": "🔑",
                "LOGOUT": "🚪",
                "PASSWORD_CHANGED": "🔐",
                "PASSWORD_RESET": "🔄",
                "ROLE_CHANGED": "🎭",
                "USER_BLOCKED": "🚫",
                "USER_UNBLOCKED": "✅",
                "USER_DELETED": "🗑",
                "INVITE_CREATED": "📨",
                "INVITE_REVOKED": "🔒",
                "ACCESS_DENIED": "⛔"
            }
            emoji = event_emojis.get(event.get("event_type", ""), "📝")

            # Формат времени
            timestamp = event.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(timestamp)
                time_str = ts.strftime("%d.%m %H:%M")
            except:
                time_str = timestamp[:16]

            # Информация о пользователе
            user_id = event.get("user_id", "Unknown")
            user = auth.storage.get_user(user_id)
            username = user.username if user else user_id[:8]

            # Тип события
            event_type = event.get("event_type", "UNKNOWN")

            events_text += f"{emoji} `{time_str}` **{username}**: {event_type}\n"

        # Формат текста
        text = (
            f"📜 **ЖУРНАЛ ДЕЙСТВИЙ**\n\n"
            f"Всего событий: {total_events}\n"
            f"Страница {page}/{total_pages}\n\n"
            f"{events_text}\n"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_audit_log_markup(page, total_pages),
            message_type="menu"
        )

        logger.info(f"Audit log shown to chat_id={chat_id}, page={page}/{total_pages}")

    except Exception as e:
        logger.error(f"Error in handle_audit_log: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке журнала действий.",
            message_type="menu"
        )


# ========================================
# 5. FSM СМЕНЫ ПАРОЛЯ (4 функции)
# ========================================

async def handle_change_password_start(chat_id: int, app: Client):
    """
    Запустить FSM смены пароля (Шаг 1: запрос текущего пароля или пропуск).

    Команда: /change_password
    Источник: 02_menu_navigation.md:370-415, architecture_review_report.md:403-434

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        # Получить пользователя
        user = auth.storage.get_user_by_telegram_id(chat_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Пользователь не найден.",
                message_type="menu"
            )
            return

        # Проверить: если временный пароль и must_change_password=True → пропустить Шаг 1
        if user.must_change_password and user.temp_password_expires_at:
            # Пропустить запрос текущего пароля
            user_states[chat_id] = {
                "step": "password_change_new",
                "user_id": user.user_id,
                "skip_current": True
            }

            text = (
                "🔐 **СМЕНА ПАРОЛЯ**\n\n"
                "Вы используете временный пароль.\n"
                "Пожалуйста, установите новый постоянный пароль.\n\n"
                "**Требования к паролю:**\n"
                "- Длина: 5-8 символов\n"
                "- Только буквы и цифры\n"
                "- Не должен совпадать со старым\n\n"
                "Введите новый пароль:"
            )

            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=text,
                reply_markup=access_cancel_markup("menu_main"),
                message_type="input_request"
            )

            logger.info(f"Password change started (skip current): chat_id={chat_id}, user_id={user.user_id}")
        else:
            # Обычный процесс: запросить текущий пароль
            user_states[chat_id] = {
                "step": "password_change_current",
                "user_id": user.user_id,
                "attempts": 0
            }

            text = (
                "🔐 **СМЕНА ПАРОЛЯ**\n\n"
                "Для смены пароля необходимо подтвердить личность.\n\n"
                "Введите ваш **текущий пароль**:"
            )

            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=text,
                reply_markup=access_cancel_markup("menu_main"),
                message_type="input_request"
            )

            logger.info(f"Password change started: chat_id={chat_id}, user_id={user.user_id}")

    except Exception as e:
        logger.error(f"Error in handle_change_password_start: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при запуске смены пароля.",
            message_type="menu"
        )


async def handle_password_change_current_input(chat_id: int, password: str, app: Client):
    """
    Обработать ввод текущего пароля (Шаг 2: валидация).

    FSM step: "password_change_current"
    Источник: architecture_review_report.md:415-433, 02_menu_navigation.md:386-390

    Args:
        chat_id: Telegram chat_id
        password: Введенный текущий пароль
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        state = user_states.get(chat_id, {})
        user_id = state.get("user_id")
        attempts = state.get("attempts", 0)

        if not user_id:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Ошибка состояния. Пожалуйста, начните заново: /change_password",
                message_type="status_message"
            )
            user_states.pop(chat_id, None)
            return

        # Проверить правильность пароля
        user = auth.storage.get_user(user_id)
        if not user:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Пользователь не найден.",
                message_type="status_message"
            )
            user_states.pop(chat_id, None)
            return

        # Валидация пароля через AuthManager
        is_valid = auth.storage.verify_password(user_id, password)

        if is_valid:
            # Пароль верный → перейти к Шагу 3 (новый пароль)
            user_states[chat_id] = {
                "step": "password_change_new",
                "user_id": user_id,
                "old_password": password
            }

            text = (
                "✅ Текущий пароль подтвержден.\n\n"
                "**Требования к новому паролю:**\n"
                "- Длина: 5-8 символов\n"
                "- Только буквы и цифры\n"
                "- Не должен совпадать со старым\n\n"
                "Введите **новый пароль**:"
            )

            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=text,
                reply_markup=access_cancel_markup("menu_main"),
                message_type="input_request"
            )

            logger.info(f"Current password verified: chat_id={chat_id}, user_id={user_id}")
        else:
            # Пароль неверный
            attempts += 1

            if attempts >= 3:
                # Превышено количество попыток
                await track_and_send(
                    chat_id=chat_id,
                    app=app,
                    text=(
                        "❌ **Превышено количество попыток**\n\n"
                        "Вы ввели неверный пароль 3 раза.\n"
                        "Для безопасности процесс смены пароля отменен.\n\n"
                        "Попробуйте снова позже: /change_password"
                    ),
                    message_type="status_message"
                )
                user_states.pop(chat_id, None)

                # Audit logging
                auth.storage.log_auth_event(
                    event_type="PASSWORD_CHANGE_FAILED",
                    user_id=user_id,
                    metadata={
                        "reason": "Too many attempts",
                        "timestamp": datetime.now().isoformat()
                    }
                )

                logger.warning(f"Password change failed (too many attempts): chat_id={chat_id}, user_id={user_id}")
            else:
                # Повторить запрос (max 3 попытки)
                user_states[chat_id]["attempts"] = attempts

                await track_and_send(
                    chat_id=chat_id,
                    app=app,
                    text=(
                        f"❌ Неверный пароль.\n\n"
                        f"Попытка {attempts}/3\n\n"
                        "Введите ваш **текущий пароль**:"
                    ),
                    reply_markup=access_cancel_markup("menu_main"),
                    message_type="input_request"
                )

                logger.info(f"Wrong current password attempt {attempts}: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_password_change_current_input: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при проверке пароля.",
            message_type="status_message"
        )


async def handle_password_change_new_input(chat_id: int, password: str, app: Client):
    """
    Обработать ввод нового пароля (Шаг 3: валидация).

    FSM step: "password_change_new"
    Источник: architecture_review_report.md:792-830, 02_menu_navigation.md:394-414

    Args:
        chat_id: Telegram chat_id
        password: Введенный новый пароль
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        state = user_states.get(chat_id, {})
        user_id = state.get("user_id")
        old_password = state.get("old_password")
        skip_current = state.get("skip_current", False)

        if not user_id:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Ошибка состояния. Пожалуйста, начните заново: /change_password",
                message_type="status_message"
            )
            user_states.pop(chat_id, None)
            return

        # Валидация нового пароля
        import re

        # Длина 5-8 символов
        if len(password) < 5 or len(password) > 8:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=(
                    "❌ **Неверная длина пароля**\n\n"
                    "Пароль должен быть длиной 5-8 символов.\n\n"
                    "Попробуйте снова. Введите **новый пароль**:"
                ),
                reply_markup=access_cancel_markup("menu_main"),
                message_type="input_request"
            )
            logger.info(f"New password invalid (length): chat_id={chat_id}, length={len(password)}")
            return

        # Только буквы и цифры
        if not re.match(r'^[a-zA-Z0-9]+$', password):
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=(
                    "❌ **Недопустимые символы**\n\n"
                    "Пароль должен содержать только буквы и цифры.\n\n"
                    "Попробуйте снова. Введите **новый пароль**:"
                ),
                reply_markup=access_cancel_markup("menu_main"),
                message_type="input_request"
            )
            logger.info(f"New password invalid (chars): chat_id={chat_id}")
            return

        # Не совпадает со старым
        if not skip_current and old_password and password == old_password:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=(
                    "❌ **Пароль совпадает со старым**\n\n"
                    "Новый пароль не должен совпадать со старым.\n\n"
                    "Попробуйте снова. Введите **новый пароль**:"
                ),
                reply_markup=access_cancel_markup("menu_main"),
                message_type="input_request"
            )
            logger.info(f"New password same as old: chat_id={chat_id}, user_id={user_id}")
            return

        # Пароль валиден → перейти к Шагу 4 (подтверждение)
        user_states[chat_id] = {
            "step": "password_change_confirm",
            "user_id": user_id,
            "new_password": password
        }

        text = (
            "✅ Новый пароль принят.\n\n"
            "**Для подтверждения введите новый пароль еще раз:**"
        )

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=access_cancel_markup("menu_main"),
            message_type="input_request"
        )

        logger.info(f"New password validated: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_password_change_new_input: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при валидации пароля.",
            message_type="status_message"
        )


async def handle_password_change_confirm_input(chat_id: int, password: str, app: Client):
    """
    Обработать подтверждение нового пароля (Шаг 4: финализация).

    FSM step: "password_change_confirm"
    Источник: 02_menu_navigation.md:402-410

    Args:
        chat_id: Telegram chat_id
        password: Подтверждение нового пароля
        app: Pyrogram Client
    """
    try:
        auth = get_auth_manager()
        if not auth:
            logger.error("AuthManager не инициализирован!")
            return

        state = user_states.get(chat_id, {})
        user_id = state.get("user_id")
        new_password = state.get("new_password")

        if not user_id or not new_password:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Ошибка состояния. Пожалуйста, начните заново: /change_password",
                message_type="status_message"
            )
            user_states.pop(chat_id, None)
            return

        # Проверка совпадения
        if password != new_password:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=(
                    "❌ **Пароли не совпадают**\n\n"
                    "Подтверждение не совпадает с введенным паролем.\n\n"
                    "Начните заново: /change_password"
                ),
                message_type="status_message"
            )
            user_states.pop(chat_id, None)
            logger.info(f"Password confirmation mismatch: chat_id={chat_id}, user_id={user_id}")
            return

        # Сохранить пароль через AuthManager
        success = auth.storage.update_user_password(
            user_id=user_id,
            new_password=new_password,
            must_change_password=False,  # Снять флаг обязательной смены
            temp_password_expires_at=None  # Очистить срок действия временного пароля
        )

        if not success:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось сохранить новый пароль.",
                message_type="status_message"
            )
            user_states.pop(chat_id, None)
            return

        # Audit logging
        auth.storage.log_auth_event(
            event_type="PASSWORD_CHANGED",
            user_id=user_id,
            metadata={
                "self_changed": True,
                "timestamp": datetime.now().isoformat()
            }
        )

        # Очистить FSM состояние
        user_states.pop(chat_id, None)

        # Уведомление о успехе
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=(
                "✅ **Пароль успешно изменен**\n\n"
                "Ваш новый пароль сохранен.\n"
                "Используйте его для следующего входа.\n\n"
                "Возвращаюсь в главное меню..."
            ),
            message_type="status_message"
        )

        # Подождать перед возвратом к главному меню
        await asyncio.sleep(NOTIFICATION_DELETE_TIME)

        # Импорт главного меню
        from menus import send_main_menu
        await send_main_menu(chat_id, app)

        logger.info(f"Password changed successfully: chat_id={chat_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error in handle_password_change_confirm_input: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при сохранении пароля.",
            message_type="status_message"
        )


# ========================================
# 6. ПОИСК И ФИЛЬТРЫ (4 функции)
# ========================================

async def handle_filter_apply(chat_id: int, role_filter: str, app: Client):
    """
    Применить фильтр по роли к списку пользователей.

    callback_data: "access_filter||{role}"

    Args:
        chat_id: Telegram chat_id
        role_filter: Фильтр роли (all/super_admin/admin/user/guest)
        app: Pyrogram Client
    """
    try:
        # Применить фильтр и показать список пользователей
        await handle_list_users(chat_id, page=1, app=app, role_filter=role_filter)

        logger.info(f"Filter applied: chat_id={chat_id}, role_filter={role_filter}")

    except Exception as e:
        logger.error(f"Error in handle_filter_apply: {e}")
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при применении фильтра.",
            message_type="menu"
        )


async def handle_filter_reset(chat_id: int, app: Client):
    """
    Сбросить фильтр (показать всех пользователей).

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
    """
    try:
        await handle_list_users(chat_id, page=1, app=app, role_filter="all")
        logger.info(f"Filter reset: chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Error in handle_filter_reset: {e}")


# ========================================
# 7. ПАГИНАЦИЯ (2 функции)
# ========================================

async def handle_users_pagination(chat_id: int, page: int, app: Client):
    """
    Пагинация списка пользователей.

    callback_data: "access_list_users||page||{num}"

    Args:
        chat_id: Telegram chat_id
        page: Номер страницы
        app: Pyrogram Client
    """
    try:
        await handle_list_users(chat_id, page=page, app=app)
    except Exception as e:
        logger.error(f"Error in handle_users_pagination: {e}")


async def handle_invitations_pagination(chat_id: int, page: int, app: Client):
    """
    Пагинация списка приглашений.

    callback_data: "access_list_invites||page||{num}"

    Args:
        chat_id: Telegram chat_id
        page: Номер страницы
        app: Pyrogram Client
    """
    try:
        await handle_list_invitations(chat_id, page=page, app=app)
    except Exception as e:
        logger.error(f"Error in handle_invitations_pagination: {e}")


# ========================================
# 8. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (4 функции)
# ========================================

def get_user_role_emoji(role: str) -> str:
    """
    Эмодзи для роли пользователя.

    Args:
        role: Роль пользователя (super_admin/admin/user/guest)

    Returns:
        str: Эмодзи роли
    """
    role_emojis = {
        "super_admin": "👑",
        "admin": "⚙️",
        "user": "👤",
        "guest": "🎭"
    }
    return role_emojis.get(role, "👤")


def get_user_status_emoji(is_active: bool, is_blocked: bool) -> str:
    """
    Эмодзи для статуса пользователя.

    Args:
        is_active: Пользователь активен
        is_blocked: Пользователь заблокирован

    Returns:
        str: Эмодзи статуса
    """
    if is_blocked:
        return "🚫"
    elif is_active:
        return "✅"
    else:
        return "⏸"


def format_user_card(user: Any) -> str:
    """
    Форматирование карточки пользователя.

    Args:
        user: Объект пользователя (User)

    Returns:
        str: Форматированная карточка
    """
    status_emoji = get_user_status_emoji(user.is_active, user.is_blocked)
    role_emoji = get_user_role_emoji(user.role)

    return f"{status_emoji} {role_emoji} {user.username}"


async def send_temp_message(
    chat_id: int,
    app: Client,
    text: str,
    delete_after: int = NOTIFICATION_DELETE_TIME
):
    """
    Отправка временного сообщения с автоудалением.

    Args:
        chat_id: Telegram chat_id
        app: Pyrogram Client
        text: Текст сообщения
        delete_after: Время до удаления (секунды)
    """
    try:
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            message_type="status_message"
        )

        await asyncio.sleep(delete_after)

    except Exception as e:
        logger.error(f"Error in send_temp_message: {e}")


# ========================================
# ЭКСПОРТ
# ========================================

__all__ = [
    # Главное меню
    "handle_access_menu",

    # Управление пользователями (14)
    "handle_users_menu",
    "handle_list_users",
    "handle_user_details",
    "handle_edit_user",
    "handle_change_role",
    "handle_confirm_role_change",
    "handle_reset_password",
    "handle_confirm_reset_password",
    "handle_toggle_block_user",
    "handle_confirm_block",
    "handle_delete_user",
    "handle_confirm_delete",
    "handle_filter_users_by_role",
    "handle_search_user",
    "handle_search_user_input",

    # Приглашения (7)
    "handle_invitations_menu",
    "handle_create_invitation",
    "handle_confirm_create_invite",
    "handle_list_invitations",
    "handle_invitation_details",
    "handle_revoke_invitation",
    "handle_confirm_revoke",

    # Безопасность (2)
    "handle_security_menu",
    "handle_audit_log",

    # FSM смены пароля (4)
    "handle_change_password_start",
    "handle_password_change_current_input",
    "handle_password_change_new_input",
    "handle_password_change_confirm_input",

    # Поиск и фильтры (4)
    "handle_filter_apply",
    "handle_filter_reset",

    # Пагинация (2)
    "handle_users_pagination",
    "handle_invitations_pagination",

    # Вспомогательные (4)
    "get_user_role_emoji",
    "get_user_status_emoji",
    "format_user_card",
    "send_temp_message",
]
