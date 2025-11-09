# VoxPersona: Полный отчет о структуре проекта

**Дата анализа:** 4 ноября 2025  
**Уровень детализации:** ОЧЕНЬ ТЩАТЕЛЬНЫЙ  
**Проект:** VoxPersona (Telegram бот для интервью и аудитов)

---

## 1. ОБЩАЯ СТРУКТУРА ДИРЕКТОРИЙ

```
C:\Users\l0934\Projects\VoxPersona\
├── src/                              # ✅ Основной код приложения
│   ├── main.py                        # ТОЧКА ВХОДА бота (Pyrogram Client)
│   ├── config.py                      # Конфиг и глобальное состояние
│   ├── constants.py                   # Константы интерфейса
│   ├── bot.py                         # (старый) Pyrogram init
│   │
│   ├── handlers.py                    # 🔥 ШАГ 2: Основные обработчики (callbacks, тексты, аудио)
│   ├── handlers_my_reports_v2.py      # v2 система отчетов
│   ├── conversation_handlers.py       # FSM для мультичатов
│   ├── access_handlers.py             # 🔐 AUTH: Обработчики доступа (управление пользователями)
│   ├── conversation_handler.py        # Старая версия обработчиков
│   │
│   ├── menus.py                       # Генерация клавиатур и меню
│   ├── markups.py                     # Функции для создания разметки Telegram
│   ├── menu_manager.py                # Менеджер меню (интеграция с MessageTracker)
│   │
│   ├── datamodels.py                  # Маппинги (сценарии, здания, отчеты)
│   ├── validators.py                  # Валидация входных данных
│   ├── parser.py                      # Парсинг текста из сообщений
│   │
│   ├── conversation_manager.py        # 🎯 Менеджер мультичатов (KISS pattern)
│   ├── conversations.py               # Модели данных чатов (Pydantic)
│   │
│   ├── auth_manager.py                # 🔐 AUTH: Главный API авторизации (15+ методов)
│   ├── auth_storage.py                # 🔐 AUTH: CRUD операции (JSON файлы)
│   ├── auth_security.py               # 🔐 AUTH: bcrypt + security utils
│   ├── auth_models.py                 # 🔐 AUTH: Pydantic модели (User, Session, etc)
│   ├── auth_filters.py                # 🔐 AUTH: Pyrogram filter для проверки авторизации
│   │
│   ├── storage.py                     # Работа с файлами и БД (FAISS, PostgreSQL)
│   ├── utils.py                       # Утилиты (embedding, text cleaning, UI)
│   ├── analysis.py                    # Анализ аудио/текста (roles assignment)
│   ├── audio_utils.py                 # Утилиты для обработки аудио
│   ├── file_sender.py                 # 🚀 AUTO-SEND: автоматическая отправка файлов
│   ├── message_tracker.py             # 📊 MessageTracker: отслеживание и чистка сообщений
│   ├── run_analysis.py                # Запуск анализа с RAG + spinner
│   ├── rag_persistence.py             # Сохранение/загрузка RAG индексов
│   ├── md_storage.py                  # Управление MD отчетами (файловое хранилище)
│   │
│   ├── minio_manager.py               # 🪣 MinIO: загрузка аудиофайлов в облако
│   │
│   ├── managers/                      # Модульные менеджеры
│   │   ├── __init__.py
│   │   └── base_storage_manager.py    # Базовый класс для менеджеров хранения
│   │
│   ├── db_handler/                    # 🗄️ Database layer (PostgreSQL)
│   │   ├── db.py                      # SQL функции (get_scenario, save_audit, etc)
│   │   ├── fill_prompts_table.py      # Инициализация таблицы промптов
│   │   └── __init__.py
│   │
│   ├── formatters/                    # 📝 Форматирование данных
│   │   ├── base_formatter.py          # Базовый класс форматера
│   │   ├── history_formatter.py       # Форматирование истории чатов
│   │   ├── report_formatter.py        # Форматирование отчетов
│   │   └── __init__.py
│   │
│   ├── auth_data/                     # 🔐 AUTH: Хранилище данных (JSON)
│   │   ├── users/
│   │   ├── sessions/
│   │   ├── invitations/
│   │   ├── roles.json
│   │   └── audit_log.json
│   │
│   ├── migrations/                    # 🔄 Database migrations
│   ├── tests/                         # 🧪 Unit тесты (test_*.py)
│   │
│   ├── __init__.py
│   └── __pycache__/
│
├── tests/                             # 🧪 Integration тесты
│   ├── test_*.py                      # Различные тесты
│   └── __init__.py
│
├── prompts/                           # 📝 Системные промпты
├── prompts-by-scenario/               # 📝 Сценарий-специфичные промпты
│   ├── assign_roles/
│   ├── design/
│   ├── interview/
│   └── sql_prompts/
│
├── menu_crawler/                      # 🤖 Автоматический краулер меню (для тестирования)
│   ├── config/
│   ├── scripts/
│   └── src/
│
├── scripts/                           # 🔧 Вспомогательные скрипты
│   ├── auth_migration.py              # AUTH система миграция
│   └── *.py
│
├── docs/                              # 📚 Документация
├── backups/                           # 💾 Резервные копии
├── chat_history/                      # 💬 История чатов (JSON)
├── conversations/                     # 💬 Мультичаты (JSON структура)
├── md_reports/                        # 📄 Сохраненные MD отчеты
│
├── docker-compose.yml                 # 🐳 Docker compose
├── Dockerfile                         # 🐳 Multi-stage Docker build
├── requirements.txt                   # 📦 Python зависимости
├── .env                               # 🔑 Переменные окружения
├── .env.test                          # 🔑 Test переменные окружения
├── pyrightconfig.json                 # Pyright config
├── README.md                          # Документация
│
└── .git/                              # Git репозиторий
    └── hooks/                         # Git hooks (автодеплой)
```

---

## 2. ТОЧКИ ВХОДА И ИНИЦИАЛИЗАЦИЯ

### 2.1 Главная точка входа

**Файл:** `src/main.py`

```python
# Структура инициализации:
async def main():
    1. Инициализация AuthManager (src/auth_manager.py)
       └─ Установка в config.auth_manager через set_auth_manager()
    
    2. Инициализация Pyrogram Client
       └─ API_ID, API_HASH из config
       └─ TELEGRAM_BOT_TOKEN
       └─ SESSION_NAME для сохранения сессий
    
    3. Регистрация handlers через handlers.register_handlers(app)
       └─ @app.on_message() - текстовые сообщения
       └─ @app.on_message() - аудиосообщения
       └─ @app.on_callback_query() - callback buttons
    
    4. Асинхронная загрузка RAG моделей
       └─ asyncio.create_task(load_rags())
       └─ Периодическое сохранение (periodic_save_rags)
    
    5. await app.start()
    6. await idle() - ожидание сообщений
```

### 2.2 Инициализация конфигурации

**Файл:** `src/config.py` (475 строк)

**Глобальные переменные:**
```python
# 🔑 API keys
OPENAI_API_KEY = "sk-proj-..."
ANTHROPIC_API_KEY = "sk-ant-..."
API_ID, API_HASH                          # Telegram API
TELEGRAM_BOT_TOKEN                        # Bot token

# 🗄️ Database
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# 🪣 MinIO (облачное хранилище)
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY, MINIO_SECRET_KEY
MINIO_AUDIO_BUCKET_NAME = "voxpersona-audio"

# 💬 Направления хранения
CHAT_HISTORY_DIR = "/home/voxpersona_user/VoxPersona/chat_history"
MD_REPORTS_DIR = "/home/voxpersona_user/VoxPersona/md_reports"
CONVERSATIONS_DIR = "/home/voxpersona_user/VoxPersona/conversations"

# 🌍 Окружение
IS_TESTING = is_testing_environment()    # Определение тестового режима
RUN_MODE = "TEST" | "PROD"

# 🔐 AUTH глобальное состояние
auth_manager: Optional[AuthManager] = None
def set_auth_manager(manager) -> None    # Установить глобальный менеджер
def get_auth_manager()                   # Получить глобальный менеджер

# 💾 Состояние пользователя (FSM)
user_states: dict[int, dict] = {}        # {chat_id: {step, data, mode, ...}}
active_menus: dict[int, list] = {}       # Трекинг активных меню
processed_texts: dict[int, str] = {}     # Обработанные тексты
user_locks: Dict[int, asyncio.Lock] = {} # Race condition защита

# 🎯 RAG модели (глобальные)
rags: dict = {}                          # Загруженные RAG индексы
```

---

## 3. МОДУЛЬНАЯ ОРГАНИЗАЦИЯ И ЗАВИСИМОСТИ

### 3.1 Основной flow обработки (FSM)

```
user_states[chat_id] = {
    "step": "dialog_mode" | "ask_employee" | "ask_date" | ... | "confirm_data",
    "mode": "interview" | "design",
    "conversation_id": "uuid",
    "data": {
        "employee": "ФИО",
        "date": "YYYY-MM-DD",
        "place_name": "Название",
        "building_type": "Отель",
        "zone_name": "Зона 1",
        "city": "Москва",
        "client": "ФИО клиента",
        "audio_number": "1",
        "audio_file_name": "file.wav"
    },
    "deep_search": True | False,
    "upload_category": "audio_files" | ...
}
```

### 3.2 Граф зависимостей между модулями

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py (ENTRY)                          │
│ • Инициализирует AuthManager                                     │
│ • Создает Pyrogram Client                                        │
│ • Регистрирует обработчики                                       │
│ • Запускает RAG загрузку                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    config.py         handlers.py      run_analysis.py
    (конфиг)         (обработчики)     (RAG анализ)
        │                  │                 │
        │ глобальные       │ использует      │ использует
        │ состояние        │                 │
        │                  ├─→ menus.py     ├─→ rag_persistence.py
        │                  │    (UI)        ├─→ conversation_manager.py
        │                  │                │
        │                  ├─→ storage.py   │
        │                  │    (файлы)     │
        │                  │                │
        │                  ├─→ utils.py     │
        │                  │    (text)      │
        │                  │                │
        │                  ├─→ validators.py│
        │                  │    (проверки)  │
        │                  │                │
        │                  ├─→ parser.py    │
        │                  │    (парсинг)   │
        │                  │                │
        │                  ├─→ auth_filters.py (🔐 AUTH filter)
        │                  │    │ проверяет get_auth_manager()
        │                  │    └─→ auth_manager.py
        │                  │
        │                  ├─→ conversation_handlers.py
        │                  │    │ работа с мультичатами
        │                  │    └─→ conversation_manager.py
        │                  │         │ CRUD для чатов
        │                  │         └─→ conversations.py (модели)
        │                  │
        │                  ├─→ access_handlers.py (🔐 управление пользователями)
        │                  │    └─→ auth_manager.py
        │                  │         └─→ auth_storage.py
        │                  │
        │                  ├─→ handlers_my_reports_v2.py (отчеты)
        │                  │    └─→ md_storage.py
        │                  │
        │                  ├─→ message_tracker.py (📊 отслеживание)
        │                  │    └─→ menu_manager.py
        │                  │
        │                  ├─→ file_sender.py (🚀 автоотправка)
        │                  │
        │                  ├─→ minio_manager.py (🪣 облачное хранилище)
        │                  │
        │                  └─→ audio_utils.py (обработка аудио)
        │                       └─→ analysis.py (assign_roles)
        │
        ├─→ auth_manager.py (🔐 главный API)
        │    ├─→ auth_storage.py (CRUD в JSON)
        │    │   └─→ auth_data/ (хранилище)
        │    ├─→ auth_security.py (bcrypt)
        │    ├─→ auth_models.py (Pydantic)
        │    └─→ auth_filters.py (Pyrogram filter)
        │
        ├─→ conversation_manager.py (мультичаты)
        │   └─→ conversations.py (модели)
        │
        ├─→ md_storage.py (хранилище отчетов)
        │
        └─→ db_handler/db.py (PostgreSQL)
             └─→ datamodels.py (маппинги)
```

---

## 4. КЛЮЧЕВЫЕ МОДУЛИ И КОМПОНЕНТЫ

### 4.1 🔐 AUTH система (Авторизация)

**Компоненты:**
- `auth_manager.py` - Главный API (15+ методов)
- `auth_storage.py` - CRUD операции (JSON файлы в auth_data/)
- `auth_security.py` - bcrypt хеширование + security utilities
- `auth_models.py` - Pydantic модели (User, Session, Invitation, Role)
- `auth_filters.py` - Pyrogram фильтр для проверки авторизации

**Хранилище:**
```
auth_data/
├── users/
│   └── {user_id}.json          # Данные пользователя
├── sessions/
│   └── {session_id}.json       # Сессии (TTL 24 часа)
├── invitations/
│   └── {invite_code}.json      # Приглашения (TTL 48 часов)
├── roles.json                   # Роли и права
└── audit_log.json              # Log всех действий
```

**Основные методы AuthManager:**
```python
# Аутентификация
async authenticate(telegram_id, password) -> Session
async logout(session_id) -> bool

# Регистрация
async register_user(telegram_id, username, password, invite_code) -> User

# RBAC (Role Based Access Control)
async has_permission(user_id, permission) -> bool
async has_role(user_id, role) -> bool
async get_user_permissions(user_id) -> List[str]

# Управление пользователями
async list_users() -> List[User]
async get_user(user_id) -> User
async block_user(user_id, blocked_by)
async change_role(user_id, new_role, changed_by)
async reset_password(user_id, new_password, reset_by)

# Управление приглашениями
async create_invitation(invite_type, created_by, target_role) -> Invitation
async validate_invitation(invite_code) -> bool
```

### 4.2 💬 Мультичаты (Conversation Manager)

**Компоненты:**
- `conversation_manager.py` - Менеджер чатов (singleton)
- `conversations.py` - Pydantic модели
- `conversation_handlers.py` - FSM обработчики для мультичатов

**Хранилище:**
```
conversations/
└── user_{user_id}/
    ├── index.json              # Список всех чатов пользователя
    ├── {conversation_id}.json  # Чат 1 (все сообщения + метаданные)
    ├── {conversation_id}.json  # Чат 2
    └── ...
```

**Основные методы:**
```python
create_conversation(user_id, username, first_question) -> str
load_conversation(user_id, conversation_id) -> Conversation
save_conversation(conversation) -> bool
delete_conversation(user_id, conversation_id) -> bool

get_active_conversation_id(user_id) -> str
set_active_conversation(user_id, conversation_id) -> bool

add_message(user_id, conversation_id, message) -> bool
get_messages(user_id, conversation_id, limit=20) -> List[Message]

get_user_stats(user_id, days_back=30) -> dict
format_user_stats_for_display(user_id) -> str
```

### 4.3 📊 Message Tracker (Отслеживание сообщений)

**Файл:** `src/message_tracker.py`

**Функция:**
```python
async track_and_send(
    chat_id: int,
    app: Client,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    message_type: str = "default"  # status_message, input_request, menu, info
) -> Message
```

**Назначение:**
- Отслеживание ID отправленных сообщений
- Автоматическая очистка временных сообщений
- Предотвращение spam эффектов

### 4.4 🚀 Auto-Send система (Автоматическая отправка файлов)

**Файл:** `src/file_sender.py`

**Функции:**
```python
auto_send_history_file(chat_id, conversation_id, app)  # Отправка истории
auto_send_reports_file(chat_id, app)                   # Отправка отчетов
send_history_on_demand(chat_id, conversation_id, app)  # Ручная отправка
```

**Механизм:**
- Автоматическое разделение больших сообщений
- Отправка как файл (TXT) если > 1200 символов
- Throttling для соблюдения лимитов Telegram

### 4.5 🪣 MinIO Manager (Облачное хранилище)

**Файл:** `src/minio_manager.py`

**Функции:**
```python
upload_audio_file(file_path, object_name, metadata)  # Загрузка аудио
download_audio_file(object_name, file_path)          # Скачивание
delete_audio_file(object_name)                        # Удаление
list_audio_files(prefix)                              # Список файлов
```

**Bucket:** `voxpersona-audio`

---

## 5. КОНФИГУРАЦИОННЫЕ ФАЙЛЫ

### 5.1 Переменные окружения (`.env`)

```bash
# 🔑 API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
API_ID=21738379
API_HASH=e7e76e237d77713b4dec8e5869f49552
TELEGRAM_BOT_TOKEN=7368149804:AAELma-...
SESSION_BOT_NAME=market_res_bot

# 🗄️ Database
DB_NAME=voxpersona
DB_USER=voxpersona_user
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432

# 🪣 MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_AUDIO_BUCKET_NAME=voxpersona-audio

# 📝 Модели
REPORT_MODEL_NAME=gpt-4o-mini
TRANSCRIBATION_MODEL_NAME=whisper-1

# 📊 Smart Send
TELEGRAM_MESSAGE_THRESHOLD=1200
CHAT_HISTORY_DIR=/home/voxpersona_user/VoxPersona/chat_history
MD_REPORTS_DIR=/home/voxpersona_user/VoxPersona/md_reports
CONVERSATIONS_DIR=/home/voxpersona_user/VoxPersona/conversations

# 🧪 Testing
IS_TESTING=false
TEST_USER_ID=123456789
```

### 5.2 Docker

**Dockerfile:** Multi-stage build
```dockerfile
Stage 1: system-base (ffmpeg, build tools)
Stage 2: python-deps (requirements.txt)
Stage 3: pytorch-stage (torch, sentence-transformers)
Stage 4: models-stage (pre-load embedding models)
Stage 5: final (app code)
```

---

## 6. ОСНОВНЫЕ ЗАВИСИМОСТИ

### 6.1 Python пакеты (requirements.txt - 100+ пакетов)

**Ключевые:**
```
# Framework & Bot
pyrogram==2.0.106           # Telegram Bot Framework
asyncio                     # Асинхронность

# LLM & RAG
anthropic==0.49.0          # Claude API
openai==1.77.0             # OpenAI API
langchain==0.3.25          # LLM orchestration
langchain-core==0.3.58
langchain-openai==0.3.16
langchain-community==0.3.23

# Векторная БД
faiss-cpu==1.11.0          # FAISS (CPU)
sentence-transformers==4.1.0  # Embedding модели
transformers==4.51.3       # HuggingFace

# БД
psycopg2-binary==2.9.10    # PostgreSQL
asyncpg==0.30.0            # Async PostgreSQL

# Облако & Хранилище
minio==7.2.15              # MinIO client

# Обработка данных
pydantic==2.10.6           # Data validation
pandas==2.2.3              # Data manipulation
numpy==2.2.4               # Numerical computing

# Audio
pydub==0.25.1              # Audio processing
librosa                    # Music analysis (implicit)

# Security & Crypto
bcrypt>=4.0.0              # Password hashing
cryptography               # Encryption
pycryptodome==3.22.0       # Additional crypto

# Utils
python-dotenv==1.0.1       # .env loading
requests==2.32.3           # HTTP
aiohttp==3.11.14           # Async HTTP
structlog==24.1.0          # Logging

# Text Processing
pymorphy2==0.9.1           # Russian morphology
regex==2024.11.6           # Advanced regex
```

### 6.2 Системные зависимости (Dockerfile)

```bash
build-essential             # Компилятор для C extensions
ffmpeg                      # Audio/Video processing
libpq-dev                   # PostgreSQL development
g++, gcc                    # C/C++ compilers
pkg-config                  # Package configuration
```

---

## 7. ГРАФ ИМПОРТОВ И ЗАВИСИМОСТИ

### 7.1 handlers.py (главный обработчик)

```python
import:
├─ pyrogram (filters, Client, Message, CallbackQuery)
├─ config (все глобальные переменные и функции)
├─ handlers_my_reports_v2 (v2 отчеты)
├─ conversation_handlers (мультичаты FSM)
├─ conversation_manager (CRUD чатов)
├─ access_handlers (🔐 управление пользователями)
├─ access_markups (🔐 клавиатуры доступа)
├─ auth_filters (🔐 авторизация filter)
├─ menus (генерация меню)
├─ menu_manager (управление меню)
├─ message_tracker (отслеживание сообщений)
├─ file_sender (автоотправка файлов)
├─ minio_manager (облачное хранилище)
├─ storage (работа с файлами/БД)
├─ validators (валидация)
├─ parser (парсинг текста)
├─ analysis (assign_roles)
├─ audio_utils (обработка аудио)
├─ run_analysis (RAG анализ)
├─ md_storage (хранилище отчетов)
└─ datamodels (маппинги)
```

### 7.2 auth_manager.py (главный API авторизации)

```python
import:
├─ auth_storage (CRUD операции)
├─ auth_security (bcrypt)
├─ auth_models (Pydantic модели)
└─ uuid, hashlib, secrets, datetime
```

### 7.3 conversation_manager.py (менеджер мультичатов)

```python
import:
├─ conversations (Pydantic модели)
├─ config.CONVERSATIONS_DIR (путь)
└─ json, pathlib, uuid, datetime
```

---

## 8. ТОЧКИ ВХОДА ДЛЯ КРИТИЧЕСКИХ ОПЕРАЦИЙ

### 8.1 Авторизация

```
/start (неавторизованный пользователь)
    ↓
cmd_start_login()
    ↓
Проверка существования пользователя в auth_storage
    ↓
Запрос пароля (FSM: "awaiting_password")
    ↓
handle_password_input()
    ↓
auth_manager.authenticate(telegram_id, password)
    ↓
Создание сессии + Audit log
    ↓
✅ Отправка главного меню
```

### 8.2 Обработка текстового сообщения

```
@app.on_message(filters.text & auth_filter)
    ↓
handle_auth_text()
    ↓
handle_authorized_text()  [основная логика]
    ↓
Проверка FSM step пользователя:
    ├─ "dialog_mode"      → run_dialog_mode() + RAG анализ
    ├─ "ask_employee"     → ask_employee() → FSM "ask_date"
    ├─ "ask_date"         → ask_date() → FSM "ask_employee"
    ├─ "confirm_data"     → show_confirmation_menu()
    ├─ "edit_*"           → обновление данных
    └─ "renaming_chat"    → handle_rename_chat_input()
```

### 8.3 Обработка callback

```
@app.on_callback_query()
    ↓
callback_query_handler()
    ↓
Проверка TEST_USER_ID (Menu Crawler protection)
    ↓
Роутинг по callback_data:
    ├─ Мультичаты         → handle_new_chat, handle_switch_chat, etc
    ├─ 🔐 AUTH           → handle_access_menu, handle_users_menu, etc
    ├─ Отчеты             → handle_report, handle_my_reports_v2
    ├─ Меню               → handle_menu_* функции
    ├─ Редактирование     → handle_edit_field, handle_back_to_confirm
    └─ Файловые операции  → handle_file_selection, handle_file_deletion
```

### 8.4 Обработка аудиосообщения

```
@app.on_message((filters.voice | filters.audio) & auth_filter)
    ↓
handle_audio_msg()
    ↓
1. Проверка размера файла (до 2GB)
2. Скачивание во временную директорию
3. Загрузка в MinIO (metadata: user_id, timestamp, status)
4. Транскрибация (OpenAI Whisper)
5. Если mode="interview" → assign_roles()
6. Автопарсинг из caption (если есть)
7. FSM "inputing_fields" для сбора данных
    ↓
✅ Готово к анализу
```

---

## 9. ХРАНИЛИЩА ДАННЫХ

### 9.1 Файловое хранилище (JSON)

**Директории:**
```
chat_history/                          # История переговоров
md_reports/                            # MD отчеты (Markdown)
conversations/                         # Мультичаты (JSON)
auth_data/                            # 🔐 AUTH система
├── users/
├── sessions/
├── invitations/
├── roles.json
└── audit_log.json
```

### 9.2 Облачное хранилище (MinIO)

**Bucket:** `voxpersona-audio`
```
s3://voxpersona-audio/
└── {user_id}/
    └── {timestamp}_{filename}         # Аудиофайлы пользователя
```

### 9.3 Реляционная БД (PostgreSQL)

**Основные таблицы:**
```
audit                    # Основные аудиты
transcription           # Транскрипты аудио
scenario                # Типы сценариев
report_type             # Типы отчетов
employee                # ФИО сотрудников
client                  # ФИО клиентов
place                   # Названия заведений
zone                    # Зоны в заведениях
city                    # Города
building                # Типы зданий
user_road              # Цепочка (audit, scenario, report_type, building)
```

---

## 10. ОСНОВНЫЕ МОДЕЛИ ДАННЫХ

### 10.1 User State (FSM)

```python
user_states[chat_id] = {
    "step": str,                    # Текущий шаг FSM
    "mode": "interview" | "design", # Сценарий
    "conversation_id": str,         # UUID чата
    "deep_search": bool,            # Режим поиска
    "data": {                       # Собираемые данные
        "employee": str,
        "date": "YYYY-MM-DD",
        "place_name": str,
        "building_type": str,
        "zone_name": str,
        "city": str,
        "client": str,
        "audio_number": str,
        "audio_file_name": str
    }
}
```

### 10.2 Conversation (из conversations.py)

```python
class ConversationMessage(BaseModel):
    message_id: str                  # UUID
    type: "user_question" | "bot_answer"
    text: str
    timestamp: str                   # ISO format
    tokens: int
    sent_as: "text" | "file"
    search_type: "fast" | "deep"
    file_path: Optional[str]         # Путь к MD файлу

class ConversationMetadata(BaseModel):
    conversation_id: str             # UUID
    user_id: int                     # Telegram ID
    username: str
    title: str                       # Название чата
    created_at: str                  # ISO format
    updated_at: str
    is_active: bool
    message_count: int
    total_tokens: int
    chat_number: int                 # Постоянный номер (auto-increment)

class Conversation(BaseModel):
    metadata: ConversationMetadata
    messages: List[ConversationMessage]
```

### 10.3 User (из auth_models.py)

```python
class User(BaseModel):
    user_id: str                     # UUID
    telegram_id: int
    username: str
    password_hash: str               # SHA256 (временно, позже bcrypt)
    role: str                        # super_admin, admin, user, guest
    is_active: bool
    is_blocked: bool
    must_change_password: bool       # Флаг принудительной смены
    temp_password_expires_at: Optional[datetime]  # TTL 3 дня
    created_at: datetime
    updated_at: datetime
    created_by_user_id: Optional[str]
    last_login: Optional[datetime]
    login_count: int
    failed_login_attempts: int
    last_failed_login: Optional[datetime]
    password_changed_at: Optional[datetime]
    settings: UserSettings
    metadata: UserMetadata
```

---

## 11. СПЕЦИАЛЬНЫЕ ПАТТЕРНЫ И МЕХАНИЗМЫ

### 11.1 Race Condition Protection

```python
# В config.py
user_locks: Dict[int, asyncio.Lock] = {}

def get_user_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in user_locks:
        user_locks[chat_id] = asyncio.Lock()
    return user_locks[chat_id]

# Использование в handlers:
async with get_user_lock(chat_id):
    # Критическая секция (view report, rename, delete)
```

**Назначение:** Защита от одновременных операций с одним пользователем

### 11.2 Testing Environment Detection

```python
# В config.py
def is_testing_environment() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True
    if "pytest" in sys.modules:
        return True
    if os.getenv("IS_TESTING", "false").lower() == "true":
        return True
    if os.getenv("RUN_MODE", "").upper() == "TEST":
        return True
    return False
```

### 11.3 Atomic File Operations

```python
# В conversation_manager.py
# Двухфазный commit для гарантии атомарности:

1. Запись во временный файл: {conversation_id}.json.tmp
2. Атомарное переименование: .tmp → .json
3. При ошибке: откат (удаление .tmp файлов)
```

### 11.4 Transactional Message Addition

```python
def add_message(user_id, conversation_id, message):
    try:
        # Подготовка обоих файлов:
        with open(conv_temp, 'w'): json.dump(conversation_data)
        with open(index_temp, 'w'): json.dump(index_data)
        
        # АТОМАРНОЕ переименование ВСЕх файлов:
        conv_temp.replace(conversation_file)
        index_temp.replace(index_file)
        
        return True
    except Exception as e:
        # Откат всех временных файлов
        cleanup_temp_files([conv_temp, index_temp])
        return False
```

---

## 12. БЕЗОПАСНОСТЬ И АУДИТ

### 12.1 Авторизация и RBAC

- Пароли хешируются через SHA256 (TODO: bcrypt в T09)
- Сессии имеют TTL 24 часа
- Приглашения имеют TTL 48 часов
- Все действия логируются в `audit_log.json`

### 12.2 Roles & Permissions

**Роли:**
- `super_admin` - полный доступ
- `admin` - управление пользователями
- `user` - базовый доступ
- `guest` - только чтение

**Права** (формат: `resource.action`):
- `users.*` (create, read, update, delete, block, unblock, change_role)
- `files.*` (upload, download, delete, read)
- `conversations.*` (create, read, update, delete)
- `invitations.*` (create_admin, create_user, read, revoke, list)
- `audit.*` (read)

### 12.3 Menu Crawler Protection

```python
# Для TEST_USER_ID отключены опасные операции:
TEST_USER_ID = int(os.getenv('TEST_USER_ID', 0))

if TEST_USER_ID and callback.from_user.id == TEST_USER_ID:
    # Загрузить config из menu_crawler/config/crawler_config.json
    safe_navigation = ["menu_main", "menu_chats", "menu_system", ...]
    forbidden_actions = ["delete_", "confirm_delete", "upload_", ...]
    
    # Проверить приоритеты: whitelist > blacklist
```

---

## 13. ГЛАВНЫЕ ТИПЫ ОПЕРАЦИЙ

### 13.1 Интервью (Interview Flow)

```
1. Выбор сценария "Интервью"
2. Загрузка аудиофайла
3. Транскрибация + assign_roles
4. Сбор данных:
   - Номер файла (audio_number)
   - Дата (date)
   - ФИО сотрудника (employee)
   - Название заведения (place_name)
   - Тип заведения (building_type)
   - Зона (zone_name)
   - ФИО клиента (client) [только для интервью]
5. Выбор отчета:
   - Методология интервью
   - Связки
   - Общие факторы
   - Факторы в этом заведении
6. Анализ через RAG + Claude
7. Сохранение отчета в MD
```

### 13.2 Дизайн (Design Flow)

```
Аналогично, но без "ФИО клиента" и с дополнительным полем "Город"
Отчеты:
- Методология аудита
- Соответствие программе аудита
- Структурированный отчет аудита
```

### 13.3 Мультичаты (Multi-Chat Flow)

```
1. Нажать "📱 Чаты"
2. "Новый чат" или выбрать существующий
3. Выбрать режим поиска (⚡ быстрый или 🔬 глубокий)
4. Задать вопрос (текстом)
5. RAG анализ + Claude
6. Ответ отправляется:
   - Текстом (если < 1200 символов)
   - Файлом (если > 1200 символов)
7. История сохраняется в conversations/{user_id}/{conversation_id}.json
```

---

## 14. ВСПОМОГАТЕЛЬНЫЕ СКРИПТЫ И УТИЛИТЫ

### 14.1 Скрипты в `/scripts`

- `auth_migration.py` - Миграция AUTH системы
- Другие вспомогательные скрипты

### 14.2 Menu Crawler (для автоматического тестирования)

**Путь:** `menu_crawler/`

**Назначение:** Автоматический краулер меню для тестирования UI

**Конфиг:** `menu_crawler/config/crawler_config.json`
```json
{
  "safe_navigation": ["menu_main", "menu_chats", ...],
  "forbidden_actions": ["delete_", "confirm_delete", ...]
}
```

---

## 15. ГЛАВНЫЕ ОТЛИЧИЯ И ОСОБЕННОСТИ

### 15.1 ✅ Завершено

- ✅ Двухуровневая авторизация (пароль + сессия)
- ✅ RBAC с 4 ролями
- ✅ Мультичаты с JSON хранилищем
- ✅ RAG система с 9 индексами
- ✅ Auto-send для файлов > 1200 символов
- ✅ Message Tracker для очистки сообщений
- ✅ MinIO интеграция для аудиофайлов
- ✅ Atomic file operations с двухфазный commit
- ✅ Race condition protection через asyncio.Lock
- ✅ Auth audit log

### 15.2 🔄 В разработке / TODO

- 🔄 Замена SHA256 на bcrypt в T09
- 🔄 Интеграция SMTP для отправки приглашений
- 🔄 Web UI для администратора
- 🔄 Метрики и мониторинг
- 🔄 Rate limiting по пользователям

### 15.3 📊 Архитектурные решения

| Решение | Выбор | Почему |
|---------|-------|--------|
| Хранилище чатов | JSON | KISS, простота, нет зависимостей от БД |
| Авторизация | JSON файлы | Простота, независимость от БД |
| Состояние пользователя | В памяти (config.py) | Скорость, простота для FSM |
|报告хранилище | Markdown + JSON индекс | Читаемо, версионируемо, просто |
| Синхронизация | Атомарные операции | Надежность, отсутствие корруптов |

---

## 16. БЫСТРАЯ НАВИГАЦИЯ ПО ФАЙЛАМ

```
Нужно найти...                              Ищите в...
─────────────────────────────────────────────────────────────
Главная логика обработки сообщений        src/handlers.py
Авторизация пользователя                   src/auth_manager.py
Проверка прав доступа в handler'е          src/auth_filters.py
Менеджер мультичатов                       src/conversation_manager.py
Работа с отчетами (v2)                     src/handlers_my_reports_v2.py
Форматирование UI                          src/menus.py + src/markups.py
Работа с аудиофайлами                      src/audio_utils.py
Облачное хранилище                         src/minio_manager.py
Отслеживание сообщений                     src/message_tracker.py
Валидация входных данных                   src/validators.py
Конфиг и глобальное состояние              src/config.py
PostgreSQL операции                        src/db_handler/db.py
RAG индексы (загрузка/сохранение)          src/rag_persistence.py
Маппинги (сценарии, типы отчетов)          src/datamodels.py
Модели чатов (Pydantic)                    src/conversations.py
Модели авторизации (Pydantic)              src/auth_models.py
CRUD авторизации                           src/auth_storage.py
Security функции                           src/auth_security.py
Системные константы                        src/constants.py
```

---

## 17. РЕЗЮМЕ

**Тип проекта:** Telegram Bot для проведения интервью и аудитов  
**Архитектура:** FSM (Finite State Machine) + RAG (Retrieval Augmented Generation)  
**БД:** PostgreSQL + JSON файлы + MinIO S3  
**Язык:** Python 3.10.11  
**Framework:** Pyrogram (Telegram), LangChain (RAG), Pydantic (validation)  

**Ключевые компоненты:**
1. ✅ Двухуровневая авторизация (AUTH система)
2. ✅ RBAC с 4 ролями и детальными правами
3. ✅ Мультичаты с JSON хранилищем
4. ✅ RAG система с 9 индексами
5. ✅ MinIO интеграция для аудиофайлов
6. ✅ Message Tracker для управления сообщениями
7. ✅ Atomic file operations для надежности
8. ✅ Race condition protection
9. ✅ Полный audit log всех действий

**Специальные паттерны:**
- FSM для управления состоянием пользователя
- Singleton pattern для менеджеров (conversation_manager, etc)
- Atomic operations для целостности данных
- Async/await для асинхронной обработки

---

**Отчет создан:** 4 ноября 2025  
**Статус:** ✅ READY FOR PRODUCTION (с некоторыми TODO)
