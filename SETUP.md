# Подробное руководство по установке VoxPersona

## 📋 Предварительные требования

### Системные требования

- **Операционная система**: Linux (Ubuntu 20.04+), macOS (10.15+), Windows 10/11
- **RAM**: Минимум 4GB, рекомендуется 8GB+ для стабильной работы
- **CPU**: Многоядерный процессор, рекомендуется 4+ ядра
- **Свободное место**: 10GB+ (включая Docker образы и данные)
- **Интернет**: Стабильное подключение для API вызовов

### Программное обеспечение

- **Docker**: версия 20.10 или выше
- **Docker Compose**: версия 2.0 или выше
- **Git**: для клонирования репозитория

## 🔑 Получение API ключей

### 1. Anthropic Claude API

1. Перейдите на [console.anthropic.com](https://console.anthropic.com)
2. Зарегистрируйтесь или войдите в аккаунт
3. Перейдите в раздел "API Keys"
4. Нажмите "Create Key"
5. Скопируйте ключ (начинается с `sk-ant-`)

**Важно**: Для стабильной работы рекомендуется получить несколько ключей для балансировки нагрузки.

### 2. OpenAI API

1. Перейдите на [platform.openai.com](https://platform.openai.com)
2. Зарегистрируйтесь или войдите в аккаунт
3. Перейдите в "API keys"
4. Нажмите "Create new secret key"
5. Скопируйте ключ (начинается с `sk-`)

### 3. Telegram Bot

1. Найдите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Получите токен (формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Настройте описание и команды бота через BotFather

### 4. Telegram API

1. Перейдите на [my.telegram.org](https://my.telegram.org)
2. Войдите с помощью номера телефона
3. Перейдите в "API development tools"
4. Создайте новое приложение
5. Получите `API ID` (число) и `API Hash` (строка)

## 🛠️ Пошаговая установка

### Шаг 1: Клонирование репозитория

```bash
# Клонируйте репозиторий
git clone https://github.com/yourusername/VoxPersona.git

# Перейдите в директорию проекта
cd VoxPersona
```

### Шаг 2: Настройка конфигурации

```bash
# Создайте файл конфигурации
cp .env.template .env

# Откройте файл для редактирования
nano .env  # или используйте любой текстовый редактор
```

### Шаг 3: Заполнение .env файла

Откройте файл `.env` и заполните следующие обязательные поля:

```env
# Database Configuration
DB_NAME=bot_db
DB_USER=voxpersona_user
DB_PASSWORD=your_secure_password_here

# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-your_anthropic_key_here
OPENAI_API_KEY=sk-your_openai_key_here
TELEGRAM_BOT_TOKEN=123456789:your_telegram_bot_token_here

# Telegram API
API_ID=your_telegram_api_id_here
API_HASH=your_telegram_api_hash_here

# Bot Configuration
PASSWORD=your_bot_access_password_here
```

**Опционально** (для улучшенной производительности):
```env
# Дополнительные Anthropic ключи для балансировки нагрузки
ANTHROPIC_API_KEY_2=sk-ant-api03-second_key_here
ANTHROPIC_API_KEY_3=sk-ant-api03-third_key_here
# ... до ANTHROPIC_API_KEY_7
```

### Шаг 4: Инициализация базы данных (опционально)

Если у вас есть SQL файл для инициализации:

```bash
# Поместите ваш SQL файл в корень проекта
cp your_database_dump.sql init.sql

# Раскомментируйте строку в docker-compose.yml
sed -i 's/# - \.\/init\.sql/- \.\/init\.sql/' docker-compose.yml
```

### Шаг 5: Запуск системы

```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Проверка статуса контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f voxpersona
```

### Шаг 6: Проверка работоспособности

1. **Проверьте логи приложения**:
   ```bash
   docker-compose logs voxpersona | grep -i "started\|ready\|error"
   ```

2. **Проверьте подключение к базе данных**:
   ```bash
   docker exec voxpersona_postgres pg_isready -U voxpersona_user -d bot_db
   ```

3. **Протестируйте Telegram бота**:
   - Найдите вашего бота в Telegram
   - Отправьте команду `/start`
   - Убедитесь, что бот отвечает

## 🔧 Устранение неполадок

### Проблема: Контейнер не запускается

```bash
# Проверьте логи для выявления ошибок
docker-compose logs voxpersona

# Проверьте конфигурацию
docker-compose config

# Пересоберите образ
docker-compose build --no-cache voxpersona
```

### Проблема: Ошибки API ключей

```bash
# Проверьте переменные окружения в контейнере
docker exec voxpersona_app env | grep -E "(ANTHROPIC|OPENAI|TELEGRAM)"

# Убедитесь, что ключи корректны и активны
```

### Проблема: База данных недоступна

```bash
# Проверьте статус PostgreSQL
docker-compose ps postgres

# Проверьте логи базы данных
docker-compose logs postgres

# Перезапустите базу данных
docker-compose restart postgres
```

### Проблема: Недостаточно памяти

```bash
# Проверьте использование ресурсов
docker stats

# Уменьшите лимит памяти в docker-compose.yml
# Измените: memory: 10G на memory: 4G
```

## 📊 Мониторинг

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Только приложение
docker-compose logs -f voxpersona

# Только база данных
docker-compose logs -f postgres

# Последние 100 строк
docker-compose logs --tail=100 voxpersona
```

### Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Использование диска
docker system df

# Информация о контейнерах
docker-compose ps
```

## 🔄 Обновление

### Обновление кода

```bash
# Получите последние изменения
git pull origin main

# Пересоберите образ
docker-compose build voxpersona

# Перезапустите сервисы
docker-compose up -d
```

### Резервное копирование

```bash
# Создание backup базы данных
docker exec voxpersona_postgres pg_dump -U voxpersona_user -d bot_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup конфигурации
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
```

## 🚀 Оптимизация производительности

### Для продакшен-среды

1. **Увеличьте количество Anthropic ключей** для балансировки нагрузки
2. **Настройте логирование** на внешний том
3. **Используйте внешнюю базу данных** для масштабируемости
4. **Настройте мониторинг** (Prometheus, Grafana)
5. **Используйте reverse proxy** (nginx, Traefik)

### Настройка лимитов

```yaml
# В docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G      # Уменьшите при необходимости
      cpus: '4.0'     # Ограничьте CPU
    reservations:
      memory: 2G
      cpus: '1.0'
```

## 📞 Получение помощи

Если у вас возникли проблемы:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в корректности .env файла
3. Проверьте доступность API сервисов
4. Создайте Issue в GitHub с подробным описанием проблемы

---

**Успешной установки! 🚀**

