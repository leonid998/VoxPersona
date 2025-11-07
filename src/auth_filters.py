"""
Custom Filters для Pyrogram - проверка авторизации через AuthManager.

Предоставляет 3 фильтра для использования в handlers:
1. auth_filter - базовая проверка авторизации + must_change_password
2. require_role() - фабрика фильтров по ролям (фабричный паттерн)
3. require_permission() - фабрика фильтров по правам (RBAC)

Интеграция с AuthManager:
- Использует get_auth_manager() из config.py (T11)
- Проверяет is_active, is_blocked, must_change_password
- Уведомляет пользователя о необходимости смены пароля
- Уведомляет заблокированного пользователя о причине блокировки (улучшение UX)

Автор: backend-developer, refactoring-specialist
Дата: 17 октября 2025, обновлено 7 ноября 2025
Задача: T12 (#00005_20251014_HRYHG)

Примеры использования:
    from auth_filters import auth_filter, require_role, require_permission

    # Базовая авторизация
    @app.on_message(filters.audio & auth_filter)
    async def handle_audio(client, message):
        pass

    # Проверка роли (admin или выше)
    @app.on_message(filters.command("users") & require_role("admin"))
    async def list_users(client, message):
        pass

    # Проверка прав
    @app.on_message(filters.command("delete") & require_permission("users.delete"))
    async def delete_user(client, message):
        pass
"""

import asyncio
import logging
from pyrogram import filters
from typing import Optional

logger = logging.getLogger(__name__)


# ========== 1. БАЗОВЫЙ ФИЛЬТР АВТОРИЗАЦИИ ==========

async def _is_authorized(flt, client, message):
    """
    Базовая проверка авторизации пользователя.

    КРИТИЧНО:
    - Пропускать команду /change_password (пользователь должен иметь доступ к смене пароля)
    - Проверять must_change_password и блокировать доступ к другим handlers
    - Показывать уведомление пользователю через show_password_change_required()

    Args:
        flt: Фильтр (не используется, но требуется для filters.create())
        client: Pyrogram Client
        message: Pyrogram Message

    Returns:
        bool: True если пользователь авторизован и не требуется смена пароля
    """
    # КРИТИЧНО: Пропускать команду смены пароля (иначе циклическая блокировка)
    if message.text and message.text.startswith("/change_password"):
        logger.debug(
            f"Auth filter: allowing /change_password command "
            f"(telegram_id={message.from_user.id})"
        )
        return True

    # Импорт внутри функции для избежания circular imports
    from config import get_auth_manager

    auth = get_auth_manager()
    if not auth:
        logger.error("Auth filter: auth_manager not initialized!")
        return False

    telegram_id = message.from_user.id
    user = auth.storage.get_user_by_telegram_id(telegram_id)

    # Проверка существования пользователя
    if not user:
        logger.debug(f"Auth filter: user not found (telegram_id={telegram_id})")
        return False

    # Проверка активности
    if not user.is_active:
        logger.debug(
            f"Auth filter: user is inactive (telegram_id={telegram_id}, user_id={user.user_id})"
        )
        return False

    # Проверка блокировки
    if user.is_blocked:
        logger.debug(
            f"Auth filter: user is blocked (telegram_id={telegram_id}, user_id={user.user_id})"
        )
        # Показать уведомление заблокированному пользователю (асинхронно, не блокирует фильтр)
        # Улучшает UX: пользователь понимает, почему бот не отвечает
        asyncio.create_task(show_user_blocked_notification(client, message))
        return False

    # КРИТИЧНО: Проверка активной сессии
    active_session = auth.storage.get_active_session_by_telegram_id(telegram_id)
    if not active_session:
        logger.debug(
            f"Auth filter: no active session (telegram_id={telegram_id}, user_id={user.user_id})"
        )
        return False

    # КРИТИЧНО: Проверка must_change_password
    if user.must_change_password:
        logger.info(
            f"Auth filter: user must change password, blocking access "
            f"(telegram_id={telegram_id}, user_id={user.user_id})"
        )
        # Показать уведомление пользователю (асинхронно, не блокировать фильтр)
        asyncio.create_task(show_password_change_required(client, message))
        return False

    # ✅ Все проверки пройдены
    logger.debug(
        f"Auth filter: access granted (telegram_id={telegram_id}, user_id={user.user_id})"
    )
    return True


# Создать фильтр через filters.create()
auth_filter = filters.create(_is_authorized, name="Authorized")


# ========== 2. ФАБРИКА ФИЛЬТРОВ ПО РОЛЯМ ==========

def require_role(min_role: str):
    """
    Фабрика фильтров для проверки роли пользователя.

    Иерархия ролей (от низшей к высшей):
    - guest (0)
    - user (1)
    - admin (2)
    - super_admin (3)

    КРИТИЧНО:
    - Проверяет must_change_password ПЕРЕД проверкой роли
    - Блокирует доступ если must_change_password=True
    - Показывает уведомление пользователю

    Args:
        min_role: Минимальная роль для доступа (guest, user, admin, super_admin)

    Returns:
        filters.Filter: Pyrogram фильтр для использования в @app.on_message()

    Examples:
        # Только админы и выше
        @app.on_message(filters.command("users") & require_role("admin"))
        async def list_users(client, message):
            pass

        # Только super_admin
        @app.on_message(filters.command("reset") & require_role("super_admin"))
        async def reset_system(client, message):
            pass
    """
    async def _check_role(flt, client, message):
        """
        Проверяет роль пользователя.

        Args:
            flt: Фильтр (содержит min_role через замыкание)
            client: Pyrogram Client
            message: Pyrogram Message

        Returns:
            bool: True если роль пользователя >= min_role
        """
        # Импорт внутри функции для избежания circular imports
        from config import get_auth_manager

        auth = get_auth_manager()
        if not auth:
            logger.error("Role filter: auth_manager not initialized!")
            return False

        telegram_id = message.from_user.id
        user = auth.storage.get_user_by_telegram_id(telegram_id)

        # Проверка существования пользователя
        if not user:
            logger.debug(f"Role filter: user not found (telegram_id={telegram_id})")
            return False

        # Проверка активности и блокировки
        if not user.is_active or user.is_blocked:
            logger.debug(
                f"Role filter: user is inactive or blocked "
                f"(telegram_id={telegram_id}, user_id={user.user_id})"
            )
            return False

        # КРИТИЧНО: Проверка must_change_password
        if user.must_change_password:
            logger.info(
                f"Role filter: user must change password, blocking access "
                f"(telegram_id={telegram_id}, user_id={user.user_id})"
            )
            # Показать уведомление пользователю (асинхронно)
            asyncio.create_task(show_password_change_required(client, message))
            return False

        # Иерархия ролей
        role_hierarchy = {
            "guest": 0,
            "user": 1,
            "admin": 2,
            "super_admin": 3
        }

        user_level = role_hierarchy.get(user.role, -1)
        required_level = role_hierarchy.get(flt.min_role, 999)  # Невалидная роль = недоступно

        has_access = user_level >= required_level

        logger.debug(
            f"Role filter: telegram_id={telegram_id}, user_id={user.user_id}, "
            f"user_role={user.role} (level={user_level}), "
            f"required_role={flt.min_role} (level={required_level}), "
            f"result={has_access}"
        )

        return has_access

    # Создать фильтр через filters.create() с передачей min_role
    return filters.create(_check_role, name=f"Role≥{min_role}", min_role=min_role)


# ========== 3. ФАБРИКА ФИЛЬТРОВ ПО ПРАВАМ (RBAC) ==========

def require_permission(permission: str):
    """
    Фабрика фильтров для проверки прав доступа (RBAC).

    Использует AuthManager.has_permission() для проверки прав через роль пользователя.

    Доступные права (примеры):
    - users.* (create, read, update, delete, block, unblock, change_role, etc.)
    - invitations.* (create_admin, create_user, read, revoke, list)
    - files.* (upload, download, delete, read)
    - conversations.* (create, read, update, delete)
    - reports.* (create, read, update, delete)

    КРИТИЧНО:
    - Проверяет must_change_password ПЕРЕД проверкой прав
    - Блокирует доступ если must_change_password=True
    - Показывает уведомление пользователю

    Args:
        permission: Право доступа в формате "resource.action" (например, "users.delete")

    Returns:
        filters.Filter: Pyrogram фильтр для использования в @app.on_message()

    Examples:
        # Проверка права на загрузку файлов
        @app.on_message(filters.document & require_permission("files.upload"))
        async def handle_document(client, message):
            pass

        # Проверка права на удаление пользователей
        @app.on_message(filters.command("delete_user") & require_permission("users.delete"))
        async def delete_user(client, message):
            pass
    """
    async def _check_permission(flt, client, message):
        """
        Проверяет права доступа пользователя.

        Args:
            flt: Фильтр (содержит permission через замыкание)
            client: Pyrogram Client
            message: Pyrogram Message

        Returns:
            bool: True если у пользователя есть право доступа
        """
        # Импорт внутри функции для избежания circular imports
        from config import get_auth_manager

        auth = get_auth_manager()
        if not auth:
            logger.error("Permission filter: auth_manager not initialized!")
            return False

        telegram_id = message.from_user.id
        user = auth.storage.get_user_by_telegram_id(telegram_id)

        # Проверка существования пользователя
        if not user:
            logger.debug(f"Permission filter: user not found (telegram_id={telegram_id})")
            return False

        # Проверка активности и блокировки
        if not user.is_active or user.is_blocked:
            logger.debug(
                f"Permission filter: user is inactive or blocked "
                f"(telegram_id={telegram_id}, user_id={user.user_id})"
            )
            return False

        # КРИТИЧНО: Проверка must_change_password
        if user.must_change_password:
            logger.info(
                f"Permission filter: user must change password, blocking access "
                f"(telegram_id={telegram_id}, user_id={user.user_id})"
            )
            # Показать уведомление пользователю (асинхронно)
            asyncio.create_task(show_password_change_required(client, message))
            return False

        # Проверка прав через AuthManager
        has_perm = await auth.has_permission(user.user_id, flt.permission)

        logger.debug(
            f"Permission filter: telegram_id={telegram_id}, user_id={user.user_id}, "
            f"permission={flt.permission}, result={has_perm}"
        )

        return has_perm

    # Создать фильтр через filters.create() с передачей permission
    return filters.create(_check_permission, name=f"Permission:{permission}", permission=permission)


# ========== 4. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ УВЕДОМЛЕНИЯ ==========

async def show_password_change_required(client, message):
    """
    Показывает уведомление пользователю о необходимости смены пароля.

    КРИТИЧНО:
    - Вызывается асинхронно через asyncio.create_task() (не блокирует фильтр)
    - Показывается каждый раз при попытке доступа к защищенному handler
    - Содержит инструкции по смене пароля

    Args:
        client: Pyrogram Client
        message: Pyrogram Message (для определения chat_id)

    Example:
        # Вызывается автоматически из фильтров при must_change_password=True
        asyncio.create_task(show_password_change_required(client, message))
    """
    try:
        notification = (
            "🔒 **Требуется смена пароля**\n\n"
            "Вы используете временный пароль, который необходимо сменить.\n"
            "Пожалуйста, смените пароль для продолжения работы с ботом.\n\n"
            "📝 **Команда для смены пароля:**\n"
            "/change_password\n\n"
            "⏳ **Срок действия временного пароля:**\n"
            "3 дня с момента выдачи\n\n"
            "⚠️ До смены пароля доступ к функциям бота ограничен."
        )

        await client.send_message(message.chat.id, notification)

        logger.info(
            f"Password change notification sent "
            f"(telegram_id={message.from_user.id}, chat_id={message.chat.id})"
        )

    except Exception as e:
        logger.error(
            f"Failed to send password change notification: {e} "
            f"(telegram_id={message.from_user.id}, chat_id={message.chat.id})"
        )


async def show_user_blocked_notification(client, message):
    """
    Показывает уведомление заблокированному пользователю.

    КРИТИЧНО:
    - Вызывается асинхронно через asyncio.create_task() (не блокирует фильтр)
    - Показывается при каждой попытке доступа заблокированного пользователя
    - Содержит информацию о причине блокировки и действиях для разблокировки
    - Улучшает UX: пользователь понимает, почему бот не отвечает

    Args:
        client: Pyrogram Client
        message: Pyrogram Message (для определения chat_id)

    Example:
        # Вызывается автоматически из фильтров при is_blocked=True
        asyncio.create_task(show_user_blocked_notification(client, message))
    """
    try:
        notification = (
            "🚫 **Доступ заблокирован**\n\n"
            "Ваш аккаунт был заблокирован администратором.\n\n"
            "Для получения дополнительной информации и восстановления доступа "
            "обратитесь к администратору системы.\n\n"
            "⚠️ Все функции бота недоступны до разблокировки аккаунта."
        )

        await client.send_message(message.chat.id, notification)

        logger.info(
            f"Block notification sent "
            f"(telegram_id={message.from_user.id}, chat_id={message.chat.id})"
        )

    except Exception as e:
        logger.error(
            f"Failed to send block notification: {e} "
            f"(telegram_id={message.from_user.id}, chat_id={message.chat.id})"
        )


# ========== ЭКСПОРТ ==========

__all__ = [
    "auth_filter",
    "require_role",
    "require_permission",
    "show_password_change_required",
    "show_user_blocked_notification"
]
