"""
Примеры использования auth_filters в handlers VoxPersona.

Демонстрирует все способы применения Custom Filters для проверки авторизации.

Автор: backend-developer
Дата: 17 октября 2025
Задача: T12 (#00005_20251014_HRYHG)
"""

from pyrogram import Client, filters
from auth_filters import auth_filter, require_role, require_permission


# ========== 1. БАЗОВАЯ АВТОРИЗАЦИЯ ==========

@Client.on_message(filters.audio & auth_filter)
async def handle_audio(client, message):
    """
    Handler аудиосообщений - доступен только авторизованным пользователям.

    Фильтр auth_filter проверяет:
    - Пользователь существует в системе
    - is_active = True
    - is_blocked = False
    - must_change_password = False (блокирует если True)
    """
    await message.reply_text(
        f"✅ Аудиосообщение получено!\n"
        f"Длительность: {message.audio.duration} секунд"
    )


@Client.on_message(filters.document & auth_filter)
async def handle_document(client, message):
    """
    Handler документов - доступен только авторизованным пользователям.
    """
    await message.reply_text(
        f"📄 Документ получен!\n"
        f"Имя файла: {message.document.file_name}\n"
        f"Размер: {message.document.file_size / 1024:.2f} KB"
    )


@Client.on_message(filters.command("start") & auth_filter)
async def handle_start(client, message):
    """
    Handler команды /start - доступен только авторизованным пользователям.
    """
    await message.reply_text(
        "👋 Добро пожаловать в VoxPersona!\n\n"
        "Доступные команды:\n"
        "/help - Справка по командам\n"
        "/profile - Ваш профиль"
    )


# ========== 2. ПРОВЕРКА РОЛЕЙ ==========

@Client.on_message(filters.command("users") & require_role("admin"))
async def list_users(client, message):
    """
    Handler команды /users - доступен только админам и super_admin.

    require_role("admin") проверяет:
    - Роль пользователя >= admin (admin или super_admin)
    - must_change_password = False
    """
    await message.reply_text(
        "👥 **Список пользователей:**\n\n"
        "1. @user1 (user)\n"
        "2. @user2 (admin)\n"
        "3. @user3 (user)\n\n"
        "Всего: 3 пользователя"
    )


@Client.on_message(filters.command("reset_system") & require_role("super_admin"))
async def reset_system(client, message):
    """
    Handler команды /reset_system - доступен только super_admin.

    require_role("super_admin") пропускает только самую высокую роль.
    """
    await message.reply_text(
        "⚠️ **Подтверждение сброса системы**\n\n"
        "Вы уверены, что хотите сбросить систему?\n"
        "Все данные будут удалены!\n\n"
        "Отправьте /confirm_reset для подтверждения"
    )


@Client.on_message(filters.command("invite") & require_role("admin"))
async def create_invite(client, message):
    """
    Handler команды /invite - доступен админам и super_admin.

    Создает новое приглашение для регистрации пользователя.
    """
    await message.reply_text(
        "🎫 **Создание приглашения**\n\n"
        "Выберите роль для нового пользователя:\n"
        "1. user (обычный пользователь)\n"
        "2. admin (администратор)\n\n"
        "Отправьте номер роли (1 или 2)"
    )


# ========== 3. ПРОВЕРКА ПРАВ (RBAC) ==========

@Client.on_message(filters.command("delete_user") & require_permission("users.delete"))
async def delete_user(client, message):
    """
    Handler команды /delete_user - доступен пользователям с правом users.delete.

    require_permission("users.delete") проверяет:
    - У пользователя есть право users.delete в его роли
    - must_change_password = False
    """
    await message.reply_text(
        "🗑️ **Удаление пользователя**\n\n"
        "Отправьте Telegram ID пользователя для удаления:\n"
        "Например: 123456789"
    )


@Client.on_message(filters.command("block_user") & require_permission("users.block"))
async def block_user(client, message):
    """
    Handler команды /block_user - доступен пользователям с правом users.block.
    """
    await message.reply_text(
        "🚫 **Блокировка пользователя**\n\n"
        "Отправьте Telegram ID пользователя для блокировки:\n"
        "Например: 123456789"
    )


@Client.on_message(filters.command("view_audit") & require_permission("audit.read"))
async def view_audit_log(client, message):
    """
    Handler команды /view_audit - доступен пользователям с правом audit.read.

    Право audit.read есть только у super_admin.
    """
    await message.reply_text(
        "📋 **Аудит-лог системы**\n\n"
        "Последние 10 событий:\n"
        "1. LOGIN_SUCCESS - user_123 (2025-10-17 12:00:00)\n"
        "2. PASSWORD_CHANGED - user_456 (2025-10-17 11:30:00)\n"
        "3. USER_BLOCKED - user_789 (2025-10-17 11:00:00)\n"
        "..."
    )


# ========== 4. КОМБИНИРОВАНИЕ ФИЛЬТРОВ ==========

@Client.on_message(
    filters.document
    & auth_filter
    & require_permission("files.upload")
)
async def upload_document_with_permission(client, message):
    """
    Handler документов с проверкой прав на загрузку файлов.

    Комбинирует:
    - filters.document (Pyrogram встроенный фильтр)
    - auth_filter (базовая авторизация)
    - require_permission("files.upload") (проверка прав)

    Все фильтры должны вернуть True для обработки сообщения.
    """
    await message.reply_text(
        f"✅ Документ загружен!\n"
        f"Имя файла: {message.document.file_name}\n"
        f"Размер: {message.document.file_size / 1024:.2f} KB\n\n"
        f"У вас есть право на загрузку файлов (files.upload)"
    )


@Client.on_message(
    filters.audio
    & auth_filter
    & require_role("user")
)
async def handle_audio_with_role(client, message):
    """
    Handler аудио с проверкой роли user (или выше).

    Комбинирует:
    - filters.audio (Pyrogram встроенный фильтр)
    - auth_filter (базовая авторизация)
    - require_role("user") (минимальная роль = user)
    """
    await message.reply_text(
        f"🎵 Аудио получено!\n"
        f"Длительность: {message.audio.duration} секунд\n"
        f"Ваша роль: user (или выше)"
    )


# ========== 5. HANDLER БЕЗ АВТОРИЗАЦИИ (публичный доступ) ==========

@Client.on_message(filters.command("login"))
async def handle_login(client, message):
    """
    Handler команды /login - доступен всем (без auth_filter).

    Используется для аутентификации пользователя.
    """
    await message.reply_text(
        "🔐 **Вход в систему**\n\n"
        "Для входа отправьте ваш пароль в формате:\n"
        "/login your_password\n\n"
        "⚠️ Убедитесь, что чат с ботом приватный!"
    )


@Client.on_message(filters.command("register"))
async def handle_register(client, message):
    """
    Handler команды /register - доступен всем (без auth_filter).

    Используется для регистрации нового пользователя.
    """
    await message.reply_text(
        "📝 **Регистрация**\n\n"
        "Для регистрации вам нужен код приглашения.\n"
        "Отправьте команду в формате:\n"
        "/register invite_code your_username your_password\n\n"
        "Пример:\n"
        "/register ABC123XYZ john abc123"
    )


@Client.on_message(filters.command("help"))
async def handle_help_public(client, message):
    """
    Handler команды /help - доступен всем (публичный).

    Показывает справку для неавторизованных пользователей.
    """
    await message.reply_text(
        "ℹ️ **Справка VoxPersona**\n\n"
        "**Публичные команды:**\n"
        "/login - Вход в систему\n"
        "/register - Регистрация\n"
        "/help - Эта справка\n\n"
        "**Для авторизованных пользователей:**\n"
        "/start - Главное меню\n"
        "/profile - Ваш профиль\n"
        "/change_password - Смена пароля\n\n"
        "**Для администраторов:**\n"
        "/users - Список пользователей\n"
        "/invite - Создать приглашение\n"
        "/block_user - Заблокировать пользователя"
    )


# ========== 6. HANDLER СМЕНЫ ПАРОЛЯ (ВСЕГДА ДОСТУПЕН) ==========

@Client.on_message(filters.command("change_password"))
async def handle_change_password(client, message):
    """
    Handler команды /change_password - доступен ВСЕМ (включая must_change_password=True).

    КРИТИЧНО:
    - Этот handler НЕ использует auth_filter!
    - auth_filter специально пропускает команду /change_password
    - Позволяет пользователям с must_change_password=True сменить пароль
    """
    await message.reply_text(
        "🔑 **Смена пароля**\n\n"
        "Для смены пароля отправьте команду в формате:\n"
        "/change_password old_password new_password\n\n"
        "Пример:\n"
        "/change_password abc123 xyz789\n\n"
        "⚠️ **Требования к паролю:**\n"
        "- Длина: 5-8 символов\n"
        "- Обязательна хотя бы одна буква\n"
        "- Обязательна хотя бы одна цифра"
    )


# ========== 7. ОБРАБОТКА ОШИБОК (NO MATCH) ==========

@Client.on_message(filters.text & ~auth_filter)
async def handle_unauthorized_access(client, message):
    """
    Handler для неавторизованных пользователей (auth_filter вернул False).

    Показывает сообщение об ошибке доступа.

    NOTE: Этот handler имеет низкий приоритет и срабатывает только если
          сообщение не обработано другими handlers.
    """
    await message.reply_text(
        "🚫 **Доступ запрещен**\n\n"
        "Для использования бота необходимо войти в систему.\n"
        "Используйте команду /login для входа.\n\n"
        "Если у вас нет аккаунта, запросите код приглашения у администратора."
    )


# ========== ИТОГОВАЯ СТАТИСТИКА ФИЛЬТРОВ ==========

"""
📊 **Статистика использования фильтров в примерах:**

**auth_filter** - 8 handlers
    - Базовая авторизация для всех защищенных команд
    - Проверяет must_change_password
    - Показывает уведомление о смене пароля

**require_role()** - 5 handlers
    - require_role("user") - 1 handler
    - require_role("admin") - 3 handlers
    - require_role("super_admin") - 1 handler

**require_permission()** - 4 handlers
    - require_permission("users.delete") - 1 handler
    - require_permission("users.block") - 1 handler
    - require_permission("audit.read") - 1 handler
    - require_permission("files.upload") - 1 handler

**Комбинированные фильтры** - 2 handlers
    - filters.document & auth_filter & require_permission()
    - filters.audio & auth_filter & require_role()

**Публичные handlers (без фильтров)** - 3 handlers
    - /login, /register, /help

**CRITICAL handler (без auth_filter)** - 1 handler
    - /change_password (доступен пользователям с must_change_password=True)

📝 **Важные замечания:**

1. **Пропуск команды /change_password в auth_filter:**
   - auth_filter специально пропускает команду /change_password
   - Это позволяет пользователям с must_change_password=True сменить пароль
   - Без этого пользователь попадает в циклическую блокировку

2. **Порядок фильтров имеет значение:**
   - Pyrogram применяет фильтры слева направо через оператор &
   - Рекомендуется: filters.builtin & auth_filter & require_role/permission
   - Сначала проверяются встроенные фильтры (быстрее), затем кастомные

3. **Асинхронное уведомление:**
   - show_password_change_required() вызывается через asyncio.create_task()
   - Не блокирует фильтр, возвращает False сразу
   - Уведомление показывается пользователю независимо

4. **RBAC vs Role-based filtering:**
   - require_role() - простая иерархия ролей (guest < user < admin < super_admin)
   - require_permission() - детальная проверка прав через RBAC
   - Используйте require_permission() для точного контроля доступа
"""
