# VoxPersona - AI-Powered Voice Analysis Platform

VoxPersona - это интеллектуальная платформа для анализа голосовых записей с использованием передовых технологий искусственного интеллекта. Система предоставляет автоматическую транскрипцию, анализ содержания и генерацию детальных отчетов на основе аудиоданных.

## 🚀 Основные возможности

- **Автоматическая транскрипция** - Преобразование речи в текст с использованием OpenAI Whisper
- **Интеллектуальный анализ** - Глубокий анализ содержания с помощью Claude 3.5 Sonnet
- **RAG система** - Поиск и извлечение релевантной информации из базы знаний
- **Telegram интеграция** - Удобный интерфейс через Telegram бота
- **Многосценарный анализ** - Поддержка различных типов аудитов и отчетов
- **Векторный поиск** - Семантический поиск с использованием FAISS и SentenceTransformers

## 🏗️ Архитектура

### Технологический стек

- **Backend**: Python 3.10+
- **AI/ML**: OpenAI GPT, Anthropic Claude, SentenceTransformers
- **База данных**: PostgreSQL 14
- **Векторный поиск**: FAISS (CPU-оптимизированная версия)
- **Контейнеризация**: Docker & Docker Compose
- **Интерфейс**: Telegram Bot API

### Компоненты системы

```
VoxPersona/
├── src/                    # Основной код приложения
│   ├── main.py            # Точка входа
│   ├── bot.py             # Telegram бот
│   ├── handlers.py        # Обработчики сообщений
│   ├── analysis.py        # Анализ данных
│   ├── storage.py         # RAG и работа с БД
│   └── ...
├── prompts/               # Системные промпты
├── prompts-by-scenario/   # Промпты по сценариям
├── sql_scripts/          # Схема базы данных
├── Dockerfile            # Конфигурация контейнера
└── docker-compose.yml    # Оркестрация сервисов
```

## 📋 Требования

### Системные требования

- **RAM**: Минимум 4GB, рекомендуется 8GB+
- **CPU**: Многоядерный процессор (рекомендуется 4+ ядра)
- **Диск**: 10GB+ свободного места
- **ОС**: Linux, macOS, Windows (с Docker)

### Зависимости

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.10+ (для разработки)

## 🛠️ Установка и настройка

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/VoxPersona.git
cd VoxPersona
```

### 2. Настройка конфигурации

```bash
# Создайте файл конфигурации на основе шаблона
cp .env.template .env

# Отредактируйте .env файл, заполнив необходимые значения
nano .env
```

### 3. Получение API ключей

#### Anthropic Claude API
1. Зарегистрируйтесь на [console.anthropic.com](https://console.anthropic.com)
2. Создайте API ключ
3. Добавьте в `.env`: `ANTHROPIC_API_KEY=your_key_here`

#### OpenAI API
1. Зарегистрируйтесь на [platform.openai.com](https://platform.openai.com)
2. Создайте API ключ
3. Добавьте в `.env`: `OPENAI_API_KEY=your_key_here`

#### Telegram Bot
1. Создайте бота через [@BotFather](https://t.me/botfather)
2. Получите токен бота
3. Добавьте в `.env`: `TELEGRAM_BOT_TOKEN=your_token_here`

#### Telegram API
1. Зарегистрируйтесь на [my.telegram.org](https://my.telegram.org)
2. Создайте приложение
3. Добавьте в `.env`: `API_ID` и `API_HASH`

### 4. Запуск с Docker

```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f voxpersona

# Остановка сервисов
docker-compose down
```

### 5. Инициализация базы данных

```bash
# Если у вас есть SQL файл для инициализации
# Раскомментируйте соответствующую строку в docker-compose.yml
# и поместите ваш init.sql в корень проекта

# Или выполните SQL скрипты вручную
docker exec -i voxpersona_postgres psql -U voxpersona_user -d bot_db < sql_scripts/create_tables.sql
```

## 🔧 Разработка

### Локальная разработка

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
python src/main.py
```

### Структура базы данных

Система использует PostgreSQL с следующими основными таблицами:

- `audit` - Записи аудитов
- `transcription` - Транскрипции аудио
- `prompts` - Системные промпты
- `client` - Информация о клиентах
- `employee` - Данные сотрудников
- `buildings` - Типы зданий
- `scenario` - Сценарии анализа

Полная схема доступна в `sql_scripts/create_tables.sql`.

## 🤖 Использование

### Telegram интерфейс

1. Найдите вашего бота в Telegram
2. Отправьте `/start` для начала работы
3. Загрузите аудиофайл для анализа
4. Выберите тип анализа/сценарий
5. Получите детальный отчет

### Поддерживаемые форматы

- **Аудио**: MP3, WAV, M4A, OGG
- **Максимальный размер**: 50MB
- **Длительность**: До 2 часов

## 📊 Мониторинг и логи

```bash
# Просмотр логов приложения
docker-compose logs -f voxpersona

# Просмотр логов базы данных
docker-compose logs -f postgres

# Мониторинг ресурсов
docker stats
```

## 🔒 Безопасность

- Все API ключи хранятся в переменных окружения
- База данных изолирована в Docker сети
- Логи не содержат чувствительной информации
- Регулярно обновляйте зависимости

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 🆘 Поддержка

Если у вас возникли вопросы или проблемы:

1. Проверьте [Issues](https://github.com/yourusername/VoxPersona/issues)
2. Создайте новый Issue с подробным описанием
3. Приложите логи и конфигурацию (без секретных данных)

## 🔄 Обновления

Следите за обновлениями в разделе [Releases](https://github.com/yourusername/VoxPersona/releases).

---

**VoxPersona** - Превращаем голос в инсайты с помощью ИИ 🎙️🤖

# Test deployment with new RSA key
# Test deployment with PEM format key
# Test with original ED25519 OpenSSH format key
# Webhook Auto Deploy Test - Tue Aug 26 08:52:27 EDT 2025
