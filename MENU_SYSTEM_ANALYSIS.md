# 🎯 СИСТЕМА МЕНЮ TELEGRAM БОТА VoxPersona
## ОЧЕНЬ ТЩАТЕЛЬНОЕ ИССЛЕДОВАНИЕ (Very Thorough Analysis)

**Дата анализа**: 4 ноября 2025  
**Статус**: ПОЛНЫЙ АНАЛИЗ - все компоненты системы меню  
**Язык**: Python 3.10+ (Pyrogram 2.0)

---

## 📋 СОДЕРЖАНИЕ

1. [Архитектура системы меню](#архитектура)
2. [Все файлы связанные с меню](#файлы)
3. [Структура классов и функций](#классы)
4. [Список ВСЕХ callback_data](#callbacks)
5. [FSM состояния](#fsm-states)
6. [Keyboard разметки](#keyboards)
7. [Навигация и связи](#навигация)
8. [Точки для изменений](#точки-для-изменений)

---

## 🏗️ АРХИТЕКТУРА

###层级 ИЕРАРХИЯ МЕНЮ

```
┌─────────────────────────────────────────────────────────────────┐
│                    🏠 ГЛАВНОЕ МЕНЮ (main_menu)                  │
│         [📱 Чаты/Диалоги]  [⚙️ Системная]  [❓ Помощь]          │
└────┬──────────────────────┬─────────────────────────┬───────────┘
     │                      │                         │
     ▼                      ▼                         ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  МЕНЮ ЧАТОВ      │  │ СИСТЕМНОЕ МЕНЮ   │  │  ПОМОЩЬ          │
│ (chats_menu)     │  │ (system_menu)    │  │ (help_menu)      │
│                  │  │                  │  │                  │
│ [🆕 Новый]       │  │ [📁 Хранилище]   │  │ [Информация]     │
│ [📊 Статистика]  │  │ [🔐 Доступ]*     │  │ [🔙 Назад]      │
│ [📄 Отчеты]      │  │ [🔙 Назад]      │  │                  │
│ [💬 Чаты...]     │  │                  │  │ *super_admin     │
│ [🔙 Назад]      │  │ *super_admin:    │  │                  │
│                  │  │  меню_access     │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
     │                      │
     ├──────────────────┤   └─────────────────────┐
     │                                            │
     ▼                                            ▼
┌──────────────────┐          ┌──────────────────────────────────┐
│ МЕНЮ ДЕЙСТВИЙ    │          │  МЕНЮ ХРАНИЛИЩА & АНАЛИЗА        │
│ С ЧАТОМ          │          │  (storage_menu)                  │
│ (chat_actions)   │          │                                  │
│                  │          │ [🎬 Интервью/Дизайн]             │
│ [В Чат] [✏️] [🗑️] │          │ [📁 Аудио] [📄 Отчеты]          │
│ [Назад]          │          │ [Типы/Города/Зоны]              │
└──────────────────┘          │ [🔙 Назад]                      │
                              └──────────────────────────────────┘
```

### ТЕХНОЛОГИЧЕСКИЙ СТЕК

```
┌─────────────────────────────────────────────────────┐
│ Pyrogram 2.0 (Telegram Bot API)                     │
├─────────────────────────────────────────────────────┤
│ InlineKeyboardMarkup (кнопки с callback_data)       │
│ ReplyKeyboardMarkup (стандартные кнопки)           │
│ CallbackQuery (нажатие на inline кнопку)           │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ MESSAGE TRACKER (message_tracker.py)                │
│ - Отслеживание интерактивных элементов             │
│ - Автоматическая очистка старых меню              │
│ - Типы: menu, input_request, confirmation, status  │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ FSM (Finite State Machine)                          │
│ - Управляется через user_states[chat_id]           │
│ - Шаги: dialog_mode, inputing_fields, и т.д.       │
├─────────────────────────────────────────────────────┤
│ CALLBACK HANDLERS (обработчики нажатий кнопок)    │
│ - register_handlers() в handlers.py                │
│ - app.on_callback_query() декоратор                │
└─────────────────────────────────────────────────────┘
```

---

## 📁 ВСЕ ФАЙЛЫ СВЯЗАННЫЕ С МЕНЮ

### ОСНОВНЫЕ ФАЙЛЫ МЕНЮ

| Файл | Размер | Назначение | Тип |
|------|--------|-----------|------|
| **markups.py** | ~400 строк | ГЛАВНЫЙ файл - все InlineKeyboardMarkup для меню | Keyboards |
| **menus.py** | ~100 строк | Вспомогательные функции для отправки меню | Helpers |
| **menu_manager.py** | ~80 строк | ⚠️ УСТАРЕЛ - теперь использует MessageTracker | Legacy |
| **message_tracker.py** | ~300 строк | 🆕 Интеллектуальное отслеживание и очистка | Core |

### HANDLERS (Обработчики callback_data)

| Файл | Функций | Назначение |
|------|---------|-----------|
| **handlers.py** | 50+ | ГЛАВНЫЙ router - callback_query_handler(), меню, отчеты |
| **conversation_handlers.py** | 10 | Мультичаты - новый/удалить/переименовать чат |
| **handlers_my_reports_v2.py** | 15 | Операции с отчетами (view/rename/delete) - async |
| **access_handlers.py** | 40+ | Управление доступом (только super_admin) |
| **auth_filters.py** | 1 | auth_filter - проверка авторизации перед меню |

### РАЗМЕТКИ (Keyboards)

| Файл | Функций | Назначение |
|------|---------|-----------|
| **markups.py** | 20+ | Все InlineKeyboardMarkup для основного меню |
| **access_markups.py** | 15+ | Все InlineKeyboardMarkup для меню доступа |

### КОНФИГУРАЦИЯ И ВСПОМОГАТЕЛЬНЫЕ

| Файл | Назначение |
|------|-----------|
| **bot.py** | Регистрация хендлеров, основной loop (СТАРАЯ система) |
| **config.py** | Глобальные переменные (processed_texts, user_states, STORAGE_DIRS) |
| **datamodels.py** | Маппинги (REPORT_MAPPING, mapping_scenario_names, mapping_building_names) |
| **constants.py** | BUTTON_BACK, BUTTON_BACK_WITH_ARROW, COMMAND_HISTORY и т.д. |

---

## 🏛️ СТРУКТУРА КЛАССОВ И ОСНОВНЫЕ ФУНКЦИИ

### CLASS: MessageTracker (message_tracker.py)

**Назначение**: Единая система отслеживания и умной очистки интерактивных элементов

```python
class MessageTracker:
    # Структура: {chat_id: [TrackedMessage, ...]}
    _tracked_messages: dict[int, List[TrackedMessage]]
    
    @classmethod
    async def track_and_send(
        cls,
        chat_id: int,
        app: Client,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        message_type: MessageType = "menu"
    ) -> Message
    
    @classmethod
    async def _cleanup_by_type(cls, chat_id: int, app: Client, message_type: MessageType)
    
    @classmethod
    def clear_tracked_messages(cls, chat_id: int) -> None
```

**Типы сообщений (MessageType)**:
- `"menu"` - Обычное меню с кнопками (очищает все предыдущие меню + input + confirmation)
- `"input_request"` - Запрос ввода текста (очищает предыдущие input_request)
- `"confirmation"` - Подтверждающий диалог (очищает предыдущие confirmation)
- `"status_message"` - Системное сообщение-статус (очищает предыдущие status)
- `"info_message"` - Информационное сообщение (НЕ очищается автоматически)

---

## 📊 ВСЕ CALLBACK_DATA И HANDLERS

### ГЛАВНОЕ МЕНЮ И НАВИГАЦИЯ

```python
# Главное меню
"menu_main"              → handle_main_menu()
"menu_help"              → handle_help_menu()
"menu_system"            → handle_menu_system()
"menu_chats"             → handle_menu_chats()
"menu_storage"           → handle_menu_storage()
"menu_dialog"            → handle_menu_dialog()
"menu_access"            → handle_access_menu() [только super_admin]
```

**ФУНКЦИИ**:
```python
async def handle_main_menu(chat_id: int, app: Client)
async def handle_help_menu(chat_id: int, app: Client)
async def handle_menu_system(chat_id: int, app: Client)
async def handle_menu_chats(chat_id: int, app: Client)
async def handle_menu_storage(chat_id: int, app: Client)
async def handle_menu_dialog(chat_id: int, app: Client)
```

### МУЛЬТИЧАТЫ (conversation_handlers.py)

```python
# Callback handlers
"new_chat"                      → handle_new_chat(chat_id, app)
"chat_actions||{conversation_id}" → handle_chat_actions(chat_id, conv_id, app)
"switch_chat||{conversation_id}"  → handle_switch_chat_request(...)
"confirm_switch||{conversation_id}" → handle_switch_chat_confirm(...)
"rename_chat||{conversation_id}"  → handle_rename_chat_request(...)
"delete_chat||{conversation_id}"  → handle_delete_chat_request(...)
"confirm_delete||{conversation_id}" → handle_delete_chat_confirm(...)

# FSM State
step: "renaming_chat" → handle_rename_chat_input(chat_id, text, app)
```

### РЕЖИМЫ ПОИСКА И ДИАЛОГ

```python
# Выбор режима поиска
"mode_fast"    → handle_mode_fast(callback, app)      # ⚡ Быстрый
"mode_deep"    → handle_mode_deep(callback, app)      # 🔬 Глубокий

# Выбор сценария анализа
"mode_interview"  → handle_mode_selection(chat_id, "mode_interview", app)
"mode_design"     → handle_mode_selection(chat_id, "mode_design", app)
```

### ХРАНИЛИЩЕ И ФАЙЛЫ

```python
# Просмотр файлов
"view||{category}"        → handle_view_files(chat_id, data, app)
"select||{cat}||{file}"   → handle_file_selection(chat_id, data, app)
"delete||{cat}||{file}"   → handle_file_deletion(chat_id, data, app)
"upload||{category}"      → file_upload_handler(chat_id, data, app)

# Категории: "audio", "text_without_roles", "text_with_roles"
```

### ОТЧЕТЫ И АНАЛИЗ

```python
# INTERVIEW отчеты
"report_int_methodology"  → handle_report(chat_id, data, app)
"report_int_links"        → handle_report(chat_id, data, app)
"report_int_general"      → handle_report(chat_id, data, app)
"report_int_specific"     → handle_report(chat_id, data, app)
"report_int_employee"     → handle_report(chat_id, data, app)

# DESIGN отчеты
"report_design_audit_methodology" → handle_report(chat_id, data, app)
"report_design_compliance"        → handle_report(chat_id, data, app)
"report_design_structured"        → handle_report(chat_id, data, app)

# Мои отчеты v2
"report_view"      → handle_report_view_request(chat_id, app)
"report_rename"    → handle_report_rename_request(chat_id, app)
"report_delete"    → handle_report_delete_request(chat_id, app)
"report_delete_confirm||{index}" → handle_report_delete_confirm(chat_id, app)

# Отправка отчета
"send_report||{file_path}"  → handle_report_callback(callback, app)
"show_all_reports"          → handle_report_callback(callback, app)
"send_history_manual"       → send_history_on_demand(chat_id, conv_id, app)
```

### ПОДТВЕРЖДЕНИЕ И РЕДАКТИРОВАНИЕ

```python
# Подтверждение собранных данных
"confirm_data"  → handle_confirm_data(chat_id, app)
"edit_data"     → show_edit_menu(chat_id, state, app)

# Редактирование полей
"edit_audio_number"    → handle_edit_field(chat_id, "audio_number", app)
"edit_date"            → handle_edit_field(chat_id, "date", app)
"edit_employee"        → handle_edit_field(chat_id, "employee", app)
"edit_place_name"      → handle_edit_field(chat_id, "place_name", app)
"edit_building_type"   → handle_edit_field(chat_id, "building_type", app)
"edit_zone_name"       → handle_edit_field(chat_id, "zone_name", app)
"edit_city"            → handle_edit_field(chat_id, "city", app)
"edit_client"          → handle_edit_field(chat_id, "client", app)

# Навигация при редактировании
"back_to_confirm"  → handle_back_to_confirm(chat_id, app)

# Выбор типа здания
"choose_building||{type}"  → handle_choose_building(chat_id, data, app)
  # type: "hotel", "restaurant", "spa"
```

### СТАТИСТИКА И ОТЧЕТЫ

```python
"show_stats"       → handle_show_stats(chat_id, app)
"show_my_reports"  → handle_show_my_reports(chat_id, app)
```

### УПРАВЛЕНИЕ ДОСТУПОМ (ACCESS) - SUPER_ADMIN ONLY

#### ПОЛЬЗОВАТЕЛИ
```python
"access_users_menu"            → handle_users_menu(chat_id, app)
"access_list_users"            → handle_list_users(chat_id, 1, app)
"access_list_users||page||{n}" → handle_users_pagination(chat_id, page, app)
"access_user_details||{user_id}" → handle_user_details(chat_id, user_id, app)
"access_edit_user||{user_id}"  → handle_edit_user(chat_id, user_id, app)
"access_change_role||{user_id}" → handle_change_role(chat_id, user_id, app)
"access_set_role||{user_id}||{role}" → handle_confirm_role_change(...)
"access_reset_password||{user_id}" → handle_reset_password(...)
"access_confirm_reset||{user_id}" → handle_confirm_reset_password(...)
"access_toggle_block||{user_id}" → handle_toggle_block_user(...)
"access_confirm_block||{user_id}" → handle_confirm_block(...)
"access_delete_user||{user_id}" → handle_delete_user(...)
"access_confirm_delete||{user_id}" → handle_confirm_delete(...)
"access_search_user"           → handle_search_user(chat_id, app)
"access_filter_roles"          → handle_filter_users_by_role(chat_id, app)
"access_filter||{role}"        → handle_filter_apply(chat_id, role, app)
"access_filter_reset"          → handle_filter_reset(chat_id, app)
```

#### ПРИГЛАШЕНИЯ
```python
"access_invitations_menu"              → handle_invitations_menu(chat_id, app)
"access_create_invite||{role}"         → handle_create_invitation(...)
"access_confirm_invite||{role}"        → handle_confirm_create_invite(...)
"access_list_invites"                  → handle_list_invitations(chat_id, 1, app)
"access_list_invites||page||{n}"       → handle_invitations_pagination(...)
"access_invite_details||{invite_code}" → handle_invitation_details(...)
"access_revoke_invite||{invite_code}"  → handle_revoke_invitation(...)
"access_confirm_revoke||{invite_code}" → handle_confirm_revoke(...)
```

#### БЕЗОПАСНОСТЬ
```python
"access_security_menu"         → handle_security_menu(chat_id, app)
"access_audit_log"             → handle_audit_log(chat_id, 1, app)
"access_audit_log||page||{n}"  → handle_audit_log(chat_id, page, app)
"access_page_info"             → Информационный callback (без действия)
"access_cleanup_settings"      → Меню автоочистки
"access_password_policy"       → Политика паролей
```

---

## 🔄 FSM СОСТОЯНИЯ (user_states[chat_id])

### СТРУКТУРА СОСТОЯНИЯ

```python
user_states[chat_id] = {
    # === ОСНОВНЫЕ ===
    "conversation_id": str,      # ID текущего чата
    "step": str,                 # Текущий шаг FSM
    "deep_search": bool,         # Режим поиска (True=глубокий, False=быстрый)
    
    # === МУЛЬТИЧАТЫ ===
    "renaming_chat": bool,       # Флаг переименования чата
    
    # === ИНТЕРВЬЮ/ДИЗАЙН ===
    "mode": "interview" | "design",  # Выбранный сценарий
    "data": {                    # Собранные данные
        "audio_number": int,
        "date": "YYYY-MM-DD",
        "employee": str,
        "place_name": str,
        "building_type": str,
        "zone_name": str,
        "city": str,              # Только для design
        "client": str,            # Только для interview
        "audio_file_name": str,
        "type_of_location": str
    },
    "data_collected": bool,      # Флаг что данные собраны
    "pending_report": str,       # Ожидающийся отчет (callback_data)
    
    # === МУЛЬТИЧАТЫ ===
    "step": "renaming_chat",     # Переименование чата
    "conversation_id": str,      # ID чата для переименования
    
    # === МОИ ОТЧЕТЫ V2 ===
    "step": "report_view_ask_number" | "report_rename_ask_number" | 
            "report_rename_ask_new_name" | "report_delete_ask_number",
    "reports_snapshot": [Report, ...],   # Кэш списка отчетов
    "reports_timestamp": datetime,       # Время загрузки кэша (timeout 5 мин)
    "reports_message_id": int,          # ID сообщения с TXT списком
    "selected_report_index": int,       # Выбранный индекс при операции
    
    # === AUTH ДОСТУП ===
    "step": "password_change_current" | "password_change_new" | 
            "password_change_confirm" | "access_search_user_input",
    "new_password": str,                # Новый пароль (для смены)
    "upload_category": str,             # Категория при загрузке файла
    
    # === AUTH LOGIN (для неавторизованных) ===
    "step": "awaiting_password",
    "user_id": int,
    "telegram_id": int,
    "attempts": int,
    "expires_at": datetime              # Timeout 5 минут
}
```

### ВСЕ ЗНАЧЕНИЯ STEP

| step | Фаза | Описание | Обработчик |
|------|------|---------|-----------|
| `"dialog_mode"` | Диалог | Пользователь может писать вопросы | handle_authorized_text() |
| `"inputing_fields"` | Сбор | Вводит номер файла аудио | ask_audio_number() |
| `"ask_audio_number"` | Сбор | Ввод номера файла | ask_audio_number() |
| `"ask_date"` | Сбор | Ввод даты (YYYY-MM-DD) | ask_date() |
| `"ask_employee"` | Сбор | Ввод ФИО сотрудника | ask_employee() |
| `"ask_place_name"` | Сбор | Ввод названия заведения | ask_place_name() |
| `"ask_building_type"` | Сбор | Ввод типа здания | ask_building_type() |
| `"ask_zone"` | Сбор | Ввод зоны | ask_zone() |
| `"ask_city"` | Сбор | Ввод города (DESIGN только) | ask_city() |
| `"ask_client"` | Сбор | Ввод ФИО клиента (INTERVIEW только) | ask_client() |
| `"confirm_data"` | Подтв. | Подтверждение собранных данных | show_confirmation_menu() |
| `"edit_{field}"` | Редакт. | Редактирование поля | handle_edit_field() |
| `"renaming_chat"` | Мультич. | Переименование чата | handle_rename_chat_input() |
| `"report_view_ask_number"` | Отчеты | Ввод номера отчета для просмотра | handle_report_view_input() |
| `"report_rename_ask_number"` | Отчеты | Ввод номера отчета для переименования | handle_report_rename_number_input() |
| `"report_rename_ask_new_name"` | Отчеты | Ввод нового названия отчета | handle_report_rename_name_input() |
| `"report_delete_ask_number"` | Отчеты | Ввод номера отчета для удаления | handle_report_delete_input() |
| `"password_change_current"` | AUTH | Ввод текущего пароля | handle_password_change_current_input() |
| `"password_change_new"` | AUTH | Ввод нового пароля | handle_password_change_new_input() |
| `"password_change_confirm"` | AUTH | Подтверждение нового пароля | handle_password_change_confirm_input() |
| `"access_search_user_input"` | AUTH | Ввод поиска пользователя | handle_search_user_input() |
| `"awaiting_password"` | LOGIN | Ввод пароля при входе | handle_password_input() |

---

## ⌨️ KEYBOARD РАЗМЕТКИ

### ФАЙЛ: markups.py (420 строк)

**ГЛАВНЫЕ МЕНЮ**:
```python
def main_menu_markup() -> InlineKeyboardMarkup
    # [📱 Чаты/Диалоги] [⚙️ Системная] [❓ Помощь]

def system_menu_markup(user_role: str = "user") -> InlineKeyboardMarkup
    # [📁 Хранилище] [🔐 Доступ]* [🔙 Назад]
    # *только super_admin

def chats_menu_markup_dynamic(user_id: int) -> InlineKeyboardMarkup
    # [🆕 Новый чат] [🔙 Назад]
    # [📊 Статистика] [📄 Мои отчеты]
    # [Активный чат] + список неактивных

def storage_menu_markup() -> InlineKeyboardMarkup
    # [📁 Аудио файлы] [🔙 Назад]

def help_menu_markup() -> tuple[InlineKeyboardMarkup, str]
    # [🔙 Назад] + справочный текст
```

**ЧАТЫ**:
```python
def chat_actions_menu_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup
    # [В Чат] [✏️] [🗑️] [Назад]

def switch_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup
    # [✅ Да] [❌ Отмена]

def delete_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup
    # [🗑️ Удалить] [❌ Отмена]

def create_chat_button_row(conv: ConversationMetadata, ...) -> list
    # Одна кнопка чата (📝 или 💬) с названием на всю ширину
```

**РЕЖИМЫ ПОИСКА И АНАЛИЗ**:
```python
def make_dialog_markup() -> InlineKeyboardMarkup
    # [⚡ Быстрый поиск] [🔬 Глубокое исследование]
    # [📜 История] [📱 Чаты]

def interview_or_design_menu() -> InlineKeyboardMarkup
    # [ИНТЕРВЬЮ] [ДИЗАЙН] [🔙 Назад]

def interview_menu_markup() -> InlineKeyboardMarkup
    # [1) Методология] [2) Связки] [3) Общие факторы]
    # [4) Факторы в заведении] [5) Сотрудник] [🔙 Назад]

def design_menu_markup() -> InlineKeyboardMarkup
    # [1) Методология] [2) Соответствие] [3) Структурированный] [🔙 Назад]

def building_type_menu_markup() -> InlineKeyboardMarkup
    # [Отель] [Ресторан] [Центр здоровья]
```

**ДАННЫЕ И РЕДАКТИРОВАНИЕ**:
```python
def confirm_menu_markup(mode: str, ...) -> tuple[InlineKeyboardMarkup, str]
    # [✅ Подтвердить] [✏️ Изменить]

def edit_menu_markup(mode: str) -> InlineKeyboardMarkup
    # [Номер файла] [Дата] [Сотрудник] [Заведение]
    # [Тип здания] [Зона] [Город/Клиент] [« Назад]
```

### ФАЙЛ: access_markups.py (550+ строк)

**ГЛАВНОЕ МЕНЮ ДОСТУПА**:
```python
def access_main_menu_markup() -> InlineKeyboardMarkup
    # [👥 Пользователи] [📨 Приглашения]
    # [🔐 Безопасность] [🔙 Назад]

def access_users_menu_markup() -> InlineKeyboardMarkup
    # [📋 Список] [🔍 Поиск] [🎭 Фильтр] [🔙 Назад]

def access_invitations_menu_markup() -> InlineKeyboardMarkup
    # [➕ Админ] [➕ Юзер] [📋 Список] [🔙 Назад]

def access_security_menu_markup() -> InlineKeyboardMarkup
    # [📜 Журнал] [🕒 Автоочистка] [🔐 Политика] [🔙 Назад]
```

**ПОЛЬЗОВАТЕЛИ И РОЛИ**:
```python
def access_user_list_markup(users: List[Dict], page: int, total: int) -> InlineKeyboardMarkup
    # Динамический список пользователей с пагинацией

def access_user_details_markup(user_id: str) -> InlineKeyboardMarkup
    # [✏️ Редактировать] [🚫 Заблокировать] [🗑 Удалить] [🔙 Назад]

def access_edit_user_markup(user_id: str) -> InlineKeyboardMarkup
    # [🎭 Роль] [⚙️ Настройки] [🔑 Пароль] [🔙 Назад]

def access_change_role_markup(user_id: str) -> InlineKeyboardMarkup
    # [👑 Super Admin] [⚙️ Admin] [👤 User] [🎭 Guest] [🔙 Назад]

def access_filter_roles_markup() -> InlineKeyboardMarkup
    # [🌐 Все] [👑 Super Admin] [⚙️ Admin] [👤 User] [🎭 Guest]
```

---

## 🗺️ НАВИГАЦИЯ И СВЯЗИ МЕЖДУ МЕНЮ

### ГРАФ ПЕРЕХОДОВ

```
                          ┌─────────────────────┐
                          │  /START или         │
                          │  menu_main Callback │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │ 🏠 ГЛАВНОЕ МЕНЮ     │
                          │ main_menu_markup()  │
                          └──────┬──────────────┘
                    ┌─────────────┼─────────────┐
                    │             │             │
              ┌─────▼─┐      ┌────▼────┐   ┌──▼────┐
              │📱 Чаты │      │⚙️ Система│   │❓ Помощь│
              │"menu_  │      │"menu_   │   │"menu_ │
              │chats"  │      │system"  │   │help"  │
              └─────┬──┘      └────┬────┘   └───┬───┘
                    │             │            │
            ┌───────┼──┬──────────┼─────┐      │
            │       │  │          │     │      │
     ┌──────▼──┐   │  │    ┌─────▼─┐   │      │
     │ Список  │   │  │    │📁 Хран.│   │      │
     │ чатов   │   │  │    │"menu_  │   │      │
     │chats_   │   │  │    │storage" │  │  [Инфо]
     │dynamic()│   │  │    └────┬───┘   │      │
     └──────┬──┘   │  │         │       │      │
            │      │  │    ┌────▼──┐    │      │
     ┌──────▼──┐   │  │    │Интервью│   │      │
     │Действия │   │  │    │/Дизайн │   │      │
     │с чатом  │   │  │    └────┬──┘    │      │
     │chat_    │   │  │         │       │      │
     │actions()│   │  │    ┌────▼──┐    │      │
     └────┬────┘   │  │    │Отчеты  │   │      │
          │        │  │    └────────┘    │      │
     [Переключ]    │  │                  │      │
     [Переименов]  │  │    ┌──────────┐  │      │
     [Удалить]     │  │    │🔐 ДОСТУП │  │      │
     [Назад]       │  │    │"menu_    │  │      │
                   │  │    │access"   │  │      │
                   │  │    └──────────┘  │      │
                   │  │                  │      │
                   └──┴──────────────────┘      │
                          ↓                     │
                    [подменю...]         [Назад]
```

### КЛЮЧЕВЫЕ ПЕРЕХОДЫ

1. **Главное меню → Чаты**
   - `menu_main` → `menu_chats`
   - Показывает динамический список с кнопками операций

2. **Чаты → Действия**
   - `chat_actions||{conv_id}`
   - Меню: Переключить | Переименовать | Удалить | Назад

3. **Главное меню → Системное**
   - `menu_main` → `menu_system`
   - Для super_admin: показывает `menu_access`

4. **Системное → Доступ** (super_admin только!)
   - `menu_system` → `menu_access`
   - Доступ к управлению пользователями и приглашениями

5. **Главное меню → Хранилище → Анализ**
   - `menu_main` → `menu_storage`
   - Выбор типа анализа (интервью/дизайн)
   - Выбор отчетов по типу

6. **Циклические переходы**
   - Каждое меню имеет кнопку `🔙 Назад` с `callback_data="menu_*"`
   - Автоматическое возвращение в главное меню

---

## 🔧 ТОЧКИ ДЛЯ ВНЕСЕНИЯ ИЗМЕНЕНИЙ

### 1. ДОБАВЛЕНИЕ НОВОГО CALLBACK

**ШАГ 1: Создать функцию в markups.py**
```python
def new_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Вариант 1", callback_data="new_action_1")],
        [InlineKeyboardButton("Вариант 2", callback_data="new_action_2")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
    ])
```

**ШАГ 2: Создать handler в handlers.py**
```python
async def handle_new_action_1(chat_id: int, app: Client):
    # Логика
    await send_menu(
        chat_id=chat_id,
        app=app,
        text="Результат действия",
        reply_markup=new_menu_markup()
    )
```

**ШАГ 3: Зарегистрировать в callback_query_handler**
```python
@app.on_callback_query()
async def callback_query_handler(client: Client, callback: CallbackQuery):
    # ...
    elif data == "new_action_1":
        await handle_new_action_1(c_id, app)
```

### 2. ДОБАВЛЕНИЕ НОВОГО FSM СОСТОЯНИЯ

**ШАГ 1: Добавить обработчик текста в handle_authorized_text()**
```python
if c_id in user_states:
    step = user_states[c_id].get("step")
    
    if step == "new_step_name":
        await handle_new_step_input(c_id, text_, app)
        return
```

**ШАГ 2: Создать функцию обработки**
```python
async def handle_new_step_input(chat_id: int, text: str, app: Client):
    st = user_states.get(chat_id, {})
    st["data"]["new_field"] = text
    st["step"] = "next_step"
    
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text="Введите следующее значение:",
        message_type="input_request"
    )
```

### 3. ИЗМЕНЕНИЕ СУЩЕСТВУЮЩЕГО МЕНЮ

**Минимально инвазивный способ**:
```python
# В markups.py - модифицировать функцию
def main_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Чаты/Диалоги", callback_data="menu_chats"),
            InlineKeyboardButton("🆕 НОВАЯ КНОПКА", callback_data="menu_new"),  # ← ДОБАВЛЕНО
            InlineKeyboardButton("⚙️ Системная", callback_data="menu_system"),
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
        ]
    ])

# В handlers.py - добавить handler
elif data == "menu_new":
    await handle_new_menu(c_id, app)
```

### 4. ОЧИСТКА И ПЕРЕИНИЦИАЛИЗАЦИЯ МЕНЮ

**Правильный способ с MessageTracker**:
```python
# Старый способ (❌ НЕПРАВИЛЬНО)
app.delete_messages(chat_id, old_message_ids)
app.send_message(chat_id, "Новое меню", reply_markup=markup)

# Новый способ (✅ ПРАВИЛЬНО)
await track_and_send(
    chat_id=chat_id,
    app=app,
    text="Новое меню",
    reply_markup=markup,
    message_type="menu"  # Автоматически очистит старые меню
)
```

### 5. ДОБАВЛЕНИЕ НОВОГО CALLBACK С ПАРАМЕТРАМИ

**Шаблон**:
```python
# В меню: callback_data="action||param1||param2"
InlineKeyboardButton("Кнопка", callback_data=f"delete_item||{item_id}||{item_name}")

# В handler:
elif data.startswith("delete_item||"):
    parts = data.split("||")
    item_id = parts[1]
    item_name = parts[2]
    await handle_delete_item(c_id, item_id, item_name, app)
```

### 6. ИНТЕГРАЦИЯ С AUTH_FILTER

**Для защищенных меню**:
```python
# В bot.py - apply filter при регистрации
@app.on_message(filters.command("new_command") & auth_filter)
async def cmd_new_command(client: Client, message: Message):
    c_id = message.chat.id
    # Пользователь уже авторизован благодаря auth_filter
    await send_menu(c_id, app, "Ваше меню", markup)
```

---

## 📊 СВОДНАЯ ТАБЛИЦА ВСЕХ КОМПОНЕНТОВ

### РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ

| Месторасположение | Способ регистрации | Применяется к |
|------------------|-------------------|--------------|
| **bot.py** | `@app.on_callback_query()` | Все callback_data |
| **bot.py** | `@app.on_message(filters.command("start"))` | Команда /start |
| **bot.py** | `@app.on_message(filters.text & auth_filter)` | Текст от авторизованных |
| **bot.py** | `@app.on_message(filters.voice \| filters.audio)` | Голос/аудио |
| **bot.py** | `@app.on_message(filters.document)` | Документы |

### ФУНКЦИИ В handlers.py

| Функция | Тип | Async | Назначение |
|---------|-----|-------|-----------|
| `handle_main_menu()` | Menu | ✅ | Главное меню |
| `handle_menu_chats()` | Menu | ✅ | Список чатов |
| `handle_menu_system()` | Menu | ✅ | Системное меню |
| `handle_new_chat()` | Action | ✅ | Создание чата |
| `handle_chat_actions()` | Menu | ✅ | Меню чата |
| `handle_show_stats()` | Info | ✅ | Статистика |
| `handle_confirm_data()` | Action | ❌ | Подтверждение |
| `handle_authorized_text()` | FSM | ✅ | Главный обработчик текста |
| `handle_report()` | Analysis | ✅ | Генерация отчета |
| `handle_edit_field()` | FSM | ✅ | Редактирование поля |

### ФУНКЦИИ В conversation_handlers.py

| Функция | Назначение | Async |
|---------|-----------|-------|
| `ensure_active_conversation()` | Проверка/создание активного чата | ❌ |
| `handle_new_chat()` | Создание нового чата | ✅ |
| `handle_chat_actions()` | Меню действий с чатом | ✅ |
| `handle_switch_chat_confirm()` | Переключение чата | ✅ |
| `handle_rename_chat_request()` | Запрос переименования | ✅ |
| `handle_rename_chat_input()` | Применение нового имени | ✅ |
| `handle_delete_chat_confirm()` | Удаление чата | ✅ |

### ФУНКЦИИ В handlers_my_reports_v2.py

| Функция | Назначение | Async |
|---------|-----------|-------|
| `handle_my_reports_v2()` | Основная функция отчетов | ✅ |
| `handle_report_view_request()` | Запрос просмотра отчета | ✅ |
| `handle_report_view_input()` | Ввод номера отчета | ✅ |
| `handle_report_rename_request()` | Запрос переименования | ✅ |
| `handle_report_delete_request()` | Запрос удаления | ✅ |
| `handle_report_delete_confirm()` | Подтверждение удаления | ✅ |

---

## ⚡ КРИТИЧНЫЕ ДЕТАЛИ

### ИСПОЛЬЗОВАНИЕ MESSAGETRACKER (ОБЯЗАТЕЛЬНО!)

**❌ НЕПРАВИЛЬНО**:
```python
app.send_message(chat_id, "меню 1", reply_markup=markup)
app.send_message(chat_id, "меню 2", reply_markup=markup)  # Два меню в чате!
```

**✅ ПРАВИЛЬНО**:
```python
await track_and_send(
    chat_id=chat_id,
    app=app,
    text="меню 1",
    reply_markup=markup,
    message_type="menu"
)
await track_and_send(
    chat_id=chat_id,
    app=app,
    text="меню 2",
    reply_markup=markup,
    message_type="menu"  # Автоматически удалит старое меню!
)
```

### FSM УПРАВЛЕНИЕ СОСТОЯНИЕМ

**Правильное сохранение**:
```python
st = user_states.get(chat_id, {})
st["data"]["field"] = value
st["step"] = "next_step"
user_states[chat_id] = st  # ✅ ВАЖНО: переприсвоить!
```

### CALLBACK_DATA ПАРАМЕТРЫ

**Максимум 3 параметра с ||**:
```python
"action||param1||param2"     # ✅ OK
"action||p1||p2||p3||p4"     # ❌ Сложнее, лучше как-то иначе
```

---

## 📝 ЗАКЛЮЧЕНИЕ

Система меню VoxPersona состоит из:

1. **520+ строк** кода для разметок (markups.py + access_markups.py)
2. **50+ функций** для обработки callbacks
3. **15+ FSM состояний** для управления пользовательским взаимодействием
4. **100+ callback_data** патернов для навигации
5. **3 основных слоя**:
   - **UI слой** (markups.py) - дизайн кнопок и меню
   - **Logic слой** (handlers.py) - обработка действий
   - **Tracking слой** (message_tracker.py) - умная очистка

**Главный вывод**: Система правильно организована с разделением ответственности, использует правильные паттерны (MessageTracker для очистки, FSM для состояний, auth_filter для безопасности).

