"""
Inline клавиатуры для меню управления доступом.

Разделение ответственности:
- access_handlers.py - бизнес-логика управления доступом
- access_markups.py - UI разметка (InlineKeyboardMarkup)

Автор: VoxPersona Team
Дата: 17 октября 2025
Версия: 1.0
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional, Dict

# === КОНСТАНТЫ ===
BUTTON_BACK = "🔙 Назад"
BUTTON_CANCEL = "« Отмена"
BUTTON_CONFIRM = "✅ Да"
BUTTON_DECLINE = "❌ Нет"

# === ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ ДОСТУПОМ ===

def access_main_menu_markup() -> InlineKeyboardMarkup:
    """
    Главное меню управления доступом.

    Доступ: Только для super_admin
    Путь: Главное меню → Системная → 🔐 Настройки доступа

    Returns:
        InlineKeyboardMarkup с кнопками разделов
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        👥 Управление пользователями        ", callback_data="access_users_menu")],
        [InlineKeyboardButton("        📨 Приглашения        ", callback_data="access_invitations_menu")],
        [InlineKeyboardButton("        🔐 Безопасность        ", callback_data="access_security_menu")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_system")]
    ])

# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===

def access_users_menu_markup() -> InlineKeyboardMarkup:
    """
    Меню управления пользователями.

    Основные действия:
    - Список пользователей с пагинацией
    - Поиск по username/user_id
    - Фильтр по ролям (super_admin, admin, user, guest)

    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        📋 Список пользователей        ", callback_data="access_list_users")],
        [InlineKeyboardButton("        🔍 Поиск пользователя        ", callback_data="access_search_user")],
        [InlineKeyboardButton("        🎭 Фильтр по ролям        ", callback_data="access_filter_roles")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_access")]
    ])

def access_user_list_markup(users: List[Dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Список пользователей с пагинацией (10 на страницу).

    Формат кнопки: [статус] [роль] Username
    - Статус: ✅ активен / 🚫 заблокирован
    - Роль: 👑 super_admin / ⚙️ admin / 👤 user / 🎭 guest

    Args:
        users: Список пользователей для текущей страницы (макс 10)
        page: Текущая страница (1-based)
        total_pages: Всего страниц

    Returns:
        InlineKeyboardMarkup с динамическим списком пользователей
    """
    buttons = []

    # Динамические кнопки пользователей
    for user in users:
        # Эмодзи статуса
        status_emoji = "✅" if user.get("is_active", True) else "🚫"

        # Эмодзи роли
        role_emojis = {
            "super_admin": "👑",
            "admin": "⚙️",
            "user": "👤",
            "guest": "🎭"
        }
        role_emoji = role_emojis.get(user.get("role", "user"), "👤")

        # Формат: [статус] [роль] Username
        username = user.get("username", f"User_{user.get('user_id', 'Unknown')}")
        display_name = f"{status_emoji} {role_emoji} {username}"

        buttons.append([
            InlineKeyboardButton(
                display_name,
                callback_data=f"access_user_details||{user.get('user_id')}"
            )
        ])

    # Навигация пагинации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("  ⬅️ Назад  ", callback_data=f"access_list_users||page||{page-1}"))

    # Индикатор страницы
    nav_buttons.append(InlineKeyboardButton(f"  {page}/{total_pages}  ", callback_data="access_page_info"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("  Вперёд ➡️  ", callback_data=f"access_list_users||page||{page+1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_users_menu")])

    return InlineKeyboardMarkup(buttons)

def access_user_details_markup(user_id: str) -> InlineKeyboardMarkup:
    """
    Детали пользователя с действиями.

    Доступные действия:
    - ✏️ Редактировать (роль, настройки)
    - 🚫 Заблокировать/Разблокировать
    - 🗑 Удалить пользователя

    Args:
        user_id: Telegram user_id пользователя

    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        ✏️ Редактировать        ", callback_data=f"access_edit_user||{user_id}")],
        [InlineKeyboardButton("        🚫 Заблокировать/Разблокировать        ", callback_data=f"access_toggle_block||{user_id}")],
        [InlineKeyboardButton("        🗑 Удалить        ", callback_data=f"access_delete_user_confirm||{user_id}")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_list_users")]
    ])

def access_edit_user_markup(user_id: str) -> InlineKeyboardMarkup:
    """
    Меню редактирования пользователя.

    Доступные изменения:
    - 🎭 Изменить роль (super_admin/admin/user/guest)
    - ⚙️ Изменить настройки (permissions)
    - 🔑 Сбросить пароль

    Args:
        user_id: Telegram user_id пользователя

    Returns:
        InlineKeyboardMarkup с кнопками редактирования
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        🎭 Изменить роль        ", callback_data=f"access_change_role||{user_id}")],
        [InlineKeyboardButton("        ⚙️ Изменить настройки        ", callback_data=f"access_change_settings||{user_id}")],
        [InlineKeyboardButton("        🔑 Сбросить пароль        ", callback_data=f"access_reset_password||{user_id}")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data=f"access_user_details||{user_id}")]
    ])

def access_role_selection_markup(user_id: str) -> InlineKeyboardMarkup:
    """
    Выбор роли для пользователя.

    Доступные роли:
    - 👑 Super Admin (полный доступ)
    - ⚙️ Admin (управление пользователями, просмотр логов)
    - 👤 User (базовый доступ)
    - 🎭 Guest (ограниченный доступ)

    Args:
        user_id: Telegram user_id пользователя

    Returns:
        InlineKeyboardMarkup с выбором роли
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        👑 Super Admin        ", callback_data=f"access_set_role||{user_id}||super_admin")],
        [InlineKeyboardButton("        ⚙️ Admin        ", callback_data=f"access_set_role||{user_id}||admin")],
        [InlineKeyboardButton("        👤 User        ", callback_data=f"access_set_role||{user_id}||user")],
        [InlineKeyboardButton("        🎭 Guest        ", callback_data=f"access_set_role||{user_id}||guest")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data=f"access_edit_user||{user_id}")]
    ])

def access_user_settings_markup(user_id: str) -> InlineKeyboardMarkup:
    """
    Меню изменения настроек пользователя.

    TODO: Реализовать изменение настроек пользователя в следующей версии
    Планируемые опции:
    - 🌐 Изменить язык (access_setting_language)
    - 🕒 Изменить часовой пояс (access_setting_timezone)
    - 🔔 Переключить уведомления (access_setting_notifications)
    - ✅ Переключить статус активности (access_setting_active)

    Args:
        user_id: Telegram user_id пользователя

    Returns:
        InlineKeyboardMarkup с кнопкой "Назад"
    """
    return InlineKeyboardMarkup([
        # TODO: Реализовать изменение настроек пользователя в следующей версии
        # Доступные опции:
        # - 🌐 Изменить язык (access_setting_language)
        # - 🕒 Изменить часовой пояс (access_setting_timezone)
        # - 🔔 Переключить уведомления (access_setting_notifications)
        # - ✅ Переключить статус активности (access_setting_active)
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data=f"access_edit_user||{user_id}")]
    ])

def access_filter_roles_markup() -> InlineKeyboardMarkup:
    """
    Фильтр пользователей по ролям.

    Позволяет отфильтровать список пользователей по роли:
    - 🌐 Все (без фильтра)
    - 👑 Super Admin
    - ⚙️ Admin
    - 👤 User
    - 🎭 Guest

    Returns:
        InlineKeyboardMarkup с кнопками фильтра
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        🌐 Все        ", callback_data="access_filter||all")],
        [InlineKeyboardButton("        👑 Super Admin        ", callback_data="access_filter||super_admin")],
        [InlineKeyboardButton("        ⚙️ Admin        ", callback_data="access_filter||admin")],
        [InlineKeyboardButton("        👤 User        ", callback_data="access_filter||user")],
        [InlineKeyboardButton("        🎭 Guest        ", callback_data="access_filter||guest")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_users_menu")]
    ])

# === ПРИГЛАШЕНИЯ ===

def access_invitations_menu_markup() -> InlineKeyboardMarkup:
    """
    Меню управления приглашениями.

    Функции:
    - Создать приглашения для Admin/User
    - Список активных приглашений
    - Аннулирование приглашений

    Returns:
        InlineKeyboardMarkup с кнопками управления приглашениями
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        ➕ Создать приглашение (Admin)        ", callback_data="access_create_invite||admin")],
        [InlineKeyboardButton("        ➕ Создать приглашение (User)        ", callback_data="access_create_invite||user")],
        [InlineKeyboardButton("        📋 Список приглашений        ", callback_data="access_list_invites")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_access")]
    ])

def access_invite_list_markup(invites: List[Dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Список приглашений с пагинацией (10 на страницу).

    Формат кнопки: [роль] Code... (до YYYY-MM-DD)

    Args:
        invites: Список приглашений для текущей страницы
        page: Текущая страница (1-based)
        total_pages: Всего страниц

    Returns:
        InlineKeyboardMarkup с динамическим списком приглашений
    """
    buttons = []

    # Динамические кнопки приглашений
    for invite in invites:
        # Эмодзи роли
        role_emojis = {
            "admin": "⚙️",
            "user": "👤",
            "guest": "🎭"
        }
        role_emoji = role_emojis.get(invite.get("role", "user"), "👤")

        # Формат даты (YYYY-MM-DD)
        expires_at = invite.get("expires_at", "N/A")
        if expires_at and expires_at != "N/A":
            try:
                # Если datetime, извлечь дату
                expires_at = expires_at.split()[0] if " " in str(expires_at) else expires_at
            except:
                expires_at = "N/A"

        # Короткий код приглашения (первые 8 символов)
        invite_code = invite.get("invite_code", "Unknown")
        short_code = invite_code[:8] + "..." if len(invite_code) > 8 else invite_code

        # Формат: [роль] Code... (до YYYY-MM-DD)
        display_name = f"{role_emoji} {short_code} (до {expires_at})"

        buttons.append([
            InlineKeyboardButton(
                display_name,
                callback_data=f"access_invite_details||{invite_code}"
            )
        ])

    # Навигация пагинации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("  ⬅️ Назад  ", callback_data=f"access_list_invites||page||{page-1}"))

    # Индикатор страницы
    nav_buttons.append(InlineKeyboardButton(f"  {page}/{total_pages}  ", callback_data="access_page_info"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("  Вперёд ➡️  ", callback_data=f"access_list_invites||page||{page+1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_invitations_menu")])

    return InlineKeyboardMarkup(buttons)

def access_invite_details_markup(invite_code: str) -> InlineKeyboardMarkup:
    """
    Детали приглашения с действиями.

    Доступные действия:
    - 🗑 Аннулировать приглашение

    Args:
        invite_code: Код приглашения

    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        🗑 Аннулировать        ", callback_data=f"access_revoke_invite||{invite_code}")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_list_invites")]
    ])

def access_invite_type_markup() -> InlineKeyboardMarkup:
    """
    Выбор типа приглашения (для создания).

    Типы приглашений:
    - ⚙️ Admin (управление пользователями, просмотр логов)
    - 👤 User (базовый доступ к функциям)

    Returns:
        InlineKeyboardMarkup с выбором типа
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        ⚙️ Приглашение для Admin        ", callback_data="access_create_invite||admin")],
        [InlineKeyboardButton("        👤 Приглашение для User        ", callback_data="access_create_invite||user")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_invitations_menu")]
    ])

# === БЕЗОПАСНОСТЬ ===

def access_security_menu_markup() -> InlineKeyboardMarkup:
    """
    Меню настроек безопасности.

    Функции:
    - 📜 Журнал действий (audit log)
    - 🕒 Автоочистка сообщений
    - 🔐 Политика паролей

    Returns:
        InlineKeyboardMarkup с кнопками безопасности
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        📜 Журнал действий        ", callback_data="access_audit_log")],
        [InlineKeyboardButton("        🕒 Автоочистка сообщений        ", callback_data="access_cleanup_settings")],
        [InlineKeyboardButton("        🔐 Политика паролей        ", callback_data="access_password_policy")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_access")]
    ])
def access_password_policy_markup() -> InlineKeyboardMarkup:
    """
    Меню просмотра политики паролей.

    Отображает текущие требования к паролям в системе:
    - Минимальная и максимальная длина
    - Обязательные символы (буквы, цифры)

    Returns:
        InlineKeyboardMarkup с кнопкой "Назад"
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_security_menu")]
    ])


def access_audit_log_markup(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Журнал действий с пагинацией (20 записей на страницу).

    Отображает последние действия администраторов:
    - Изменение ролей
    - Блокировка/разблокировка
    - Удаление пользователей
    - Создание приглашений

    Args:
        page: Текущая страница (1-based)
        total_pages: Всего страниц

    Returns:
        InlineKeyboardMarkup с навигацией
    """
    buttons = []

    # Навигация пагинации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("  ⬅️ Назад  ", callback_data=f"access_audit_log||page||{page-1}"))

    # Индикатор страницы
    nav_buttons.append(InlineKeyboardButton(f"  {page}/{total_pages}  ", callback_data="access_page_info"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("  Вперёд ➡️  ", callback_data=f"access_audit_log||page||{page+1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_security_menu")])

    return InlineKeyboardMarkup(buttons)

# === УНИВЕРСАЛЬНЫЕ РАЗМЕТКИ ===

def access_confirm_action_markup(confirm_callback: str, cancel_callback: str = "menu_access") -> InlineKeyboardMarkup:
    """
    Универсальная разметка подтверждения действия.

    Используется для подтверждения критичных операций:
    - Удаление пользователя
    - Аннулирование приглашения
    - Блокировка пользователя
    - Сброс пароля

    Args:
        confirm_callback: callback_data для кнопки "Да"
        cancel_callback: callback_data для кнопки "Отмена" (default: menu_access)

    Returns:
        InlineKeyboardMarkup с кнопками подтверждения/отмены
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"    {BUTTON_CONFIRM}    ", callback_data=confirm_callback),
            InlineKeyboardButton(f"    {BUTTON_DECLINE}    ", callback_data=cancel_callback)
        ]
    ])

def access_back_markup(return_to: str = "menu_access") -> InlineKeyboardMarkup:
    """
    Простая кнопка "Назад".

    Используется для возврата из информационных экранов.

    Args:
        return_to: callback_data для возврата (default: menu_access)

    Returns:
        InlineKeyboardMarkup с одной кнопкой "Назад"
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data=return_to)]
    ])

def access_cancel_markup(cancel_callback: str) -> InlineKeyboardMarkup:
    """
    Кнопка отмены для FSM процессов.

    Используется во время ввода данных:
    - Создание приглашения
    - Поиск пользователя
    - Изменение настроек

    Args:
        cancel_callback: callback_data для возврата

    Returns:
        InlineKeyboardMarkup с кнопкой отмены
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"    {BUTTON_CANCEL}    ", callback_data=cancel_callback)]
    ])

def access_pagination_markup(page: int, total_pages: int, prefix: str, back_to: str) -> InlineKeyboardMarkup:
    """
    Универсальная пагинация для любых списков.

    Создает навигацию:
    - [⬅️ Назад] [X/Y] [Вперёд ➡️]
    - [🔙 Назад]

    Args:
        page: Текущая страница (1-based)
        total_pages: Всего страниц
        prefix: Префикс callback_data (например, "access_list_users")
        back_to: callback_data для кнопки "Назад в меню"

    Returns:
        InlineKeyboardMarkup с навигацией
    """
    buttons = []

    # Навигация пагинации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("  ⬅️ Назад  ", callback_data=f"{prefix}||page||{page-1}"))

    # Индикатор страницы (неактивная кнопка)
    nav_buttons.append(InlineKeyboardButton(f"  {page}/{total_pages}  ", callback_data="access_page_info"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("  Вперёд ➡️  ", callback_data=f"{prefix}||page||{page+1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    # Кнопка "Назад в меню"
    buttons.append([InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data=back_to)])

    return InlineKeyboardMarkup(buttons)

# === ДОПОЛНИТЕЛЬНЫЕ РАЗМЕТКИ ===

def access_search_result_markup(found_users: List[Dict]) -> InlineKeyboardMarkup:
    """
    Результаты поиска пользователя.

    Отображает найденных пользователей (максимум 10):
    - [статус] [роль] Username

    Args:
        found_users: Список найденных пользователей

    Returns:
        InlineKeyboardMarkup с результатами поиска
    """
    buttons = []

    # Ограничение 10 результатов
    for user in found_users[:10]:
        # Эмодзи статуса
        status_emoji = "✅" if user.get("is_active", True) else "🚫"

        # Эмодзи роли
        role_emojis = {
            "super_admin": "👑",
            "admin": "⚙️",
            "user": "👤",
            "guest": "🎭"
        }
        role_emoji = role_emojis.get(user.get("role", "user"), "👤")

        # Формат: [статус] [роль] Username
        username = user.get("username", f"User_{user.get('user_id', 'Unknown')}")
        display_name = f"{status_emoji} {role_emoji} {username}"

        buttons.append([
            InlineKeyboardButton(
                display_name,
                callback_data=f"access_user_details||{user.get('user_id')}"
            )
        ])

    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_users_menu")])

    return InlineKeyboardMarkup(buttons)

def access_cleanup_settings_markup() -> InlineKeyboardMarkup:
    """
    Настройки автоочистки сообщений.

    Функции:
    - Установить время (1-48 часов)
    - Настройка для пользователей
    - Просмотр расписания

    Returns:
        InlineKeyboardMarkup с настройками автоочистки
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        ⏱ Установить время (1-48 ч)        ", callback_data="access_set_cleanup_hours")],
        [InlineKeyboardButton("        👥 Настройка для пользователей        ", callback_data="access_cleanup_per_user")],
        [InlineKeyboardButton("        📅 Просмотр расписания        ", callback_data="access_view_cleanup_schedule")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="access_security_menu")]
    ])
