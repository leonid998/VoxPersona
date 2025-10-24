# 📦 VoxPersona Automatic Backup System

Система автоматического ежедневного резервного копирования всех критичных данных VoxPersona.

## 🎯 Что бэкапится

### 1. Bind Mount Volumes (директории на хосте)
- `telegram_sessions/` - Telegram сессии ботов
- `auth_data/` - Данные авторизации пользователей
- `rag_indices/` - FAISS индексы RAG системы
- `conversations/` - История диалогов
- `md_reports/` - Markdown отчёты
- `chat_history/` - История чатов
- `logs/` - Логи приложения
- `data/` - Прочие данные

### 2. Docker Named Volumes
- `postgres_data` - База данных PostgreSQL
- `minio_data` - S3-хранилище MinIO
- `minio_certs` - SSL сертификаты MinIO
- `pip_cache` - Кэш pip пакетов
- `huggingface_cache` - Кэш HuggingFace моделей

## ⏰ Расписание

**Запуск:** Каждый день в **2:00 AM**
**Хранение:** 7 дней (всегда остаётся хотя бы 1 последний backup)

## 📂 Структура backup

```
/home/voxpersona_user/backups/
├── persistent_data_backup_20251024_020000.tar.gz  (последний)
├── persistent_data_backup_20251023_020000.tar.gz
├── persistent_data_backup_20251022_020000.tar.gz
├── ...
└── backup.log  (история выполнения)
```

## 🚀 Установка

### 1. Автоматическая установка (через Git)

Скрипт автоматически появится на сервере после push через GitHub Actions:

```bash
# Локально
cd C:/Users/l0934/Projects/VoxPersona
git add scripts/backup_persistent.sh
git commit -m "feat: Add automatic backup system"
git push origin main

# Подождать 5 минут для автоматического деплоя

# На сервере
ssh root@172.237.73.207
cd /home/voxpersona_user/VoxPersona
ls -la scripts/backup_persistent.sh  # Проверка
```

### 2. Установка прав выполнения

```bash
ssh root@172.237.73.207
chmod +x /home/voxpersona_user/VoxPersona/scripts/backup_persistent.sh
```

### 3. Настройка cron

```bash
# Открыть crontab
crontab -e

# Добавить строку (запуск в 2:00 AM каждый день):
0 2 * * * /home/voxpersona_user/VoxPersona/scripts/backup_persistent.sh >> /home/voxpersona_user/backups/cron.log 2>&1

# Сохранить и выйти (:wq в vim)
```

## 🧪 Тестирование

### Запуск вручную

```bash
ssh root@172.237.73.207
cd /home/voxpersona_user/VoxPersona
./scripts/backup_persistent.sh
```

### Проверка результатов

```bash
# Посмотреть созданные backup
ls -lh /home/voxpersona_user/backups/

# Посмотреть лог
tail -50 /home/voxpersona_user/backups/backup.log

# Проверить содержимое архива
tar -tzf /home/voxpersona_user/backups/persistent_data_backup_*.tar.gz | head -20
```

## 🔧 Конфигурация

### Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `BACKUP_RETENTION_DAYS` | 7 | Количество дней хранения backup |

### Пример: Изменить время хранения на 14 дней

```bash
# В crontab
0 2 * * * BACKUP_RETENTION_DAYS=14 /home/voxpersona_user/VoxPersona/scripts/backup_persistent.sh
```

## 📊 Мониторинг

### Проверить последний backup

```bash
ssh root@172.237.73.207
ls -lth /home/voxpersona_user/backups/ | head -5
```

### Проверить логи cron

```bash
cat /home/voxpersona_user/backups/cron.log | tail -50
```

### Проверить логи backup

```bash
cat /home/voxpersona_user/backups/backup.log | tail -100
```

## 🔄 Восстановление из backup

### Полное восстановление

```bash
ssh root@172.237.73.207
cd /home/voxpersona_user/VoxPersona

# Остановить контейнеры
docker-compose down

# Выбрать backup для восстановления
BACKUP_FILE="/home/voxpersona_user/backups/persistent_data_backup_20251024_020000.tar.gz"

# Восстановить bind mounts
tar -xzf "${BACKUP_FILE}" -C /home/voxpersona_user/VoxPersona

# Восстановить Docker volumes (требует ручного восстановления каждого volume)
# См. секцию "Восстановление Docker Volumes" ниже

# Запустить контейнеры
docker-compose up -d
```

### Восстановление Docker Volumes

```bash
# Пример: Восстановление postgres_data
tar -xzf "${BACKUP_FILE}" postgres_data.tar -O | \
  docker run --rm -i \
    -v voxpersona_postgres_data:/volume \
    alpine \
    sh -c "cd /volume && tar -xf -"

# Аналогично для minio_data, minio_certs и других volumes
```

### Выборочное восстановление

```bash
# Восстановить только telegram_sessions
tar -xzf "${BACKUP_FILE}" telegram_sessions/ -C /home/voxpersona_user/VoxPersona

# Восстановить только auth_data
tar -xzf "${BACKUP_FILE}" auth_data/ -C /home/voxpersona_user/VoxPersona
```

## ⚙️ Принцип работы

1. **Сбор bind mounts** - Архивирование директорий на хосте
2. **Экспорт Docker volumes** - Извлечение данных из Docker volumes во временные tar файлы
3. **Создание единого архива** - Объединение всех данных в один .tar.gz
4. **Проверка целостности** - Верификация созданного архива
5. **Очистка старых backup** - Удаление backup старше 7 дней (всегда оставляет последний)
6. **Очистка временных файлов** - Удаление промежуточных файлов экспорта

## 🛡️ Безопасность

- ✅ Всегда оставляет хотя бы один backup (даже если старше 7 дней)
- ✅ Автоматическая очистка временных файлов при ошибках
- ✅ Проверка целостности созданных архивов
- ✅ Проверка доступного места на диске (минимум 5GB)
- ✅ Детальное логирование всех операций

## 📈 Оценка размеров

| Компонент | Примерный размер |
|-----------|------------------|
| telegram_sessions | 56 KB |
| auth_data | 32 KB |
| rag_indices | 156 MB |
| conversations | 140 KB |
| md_reports | 396 KB |
| postgres_data | ~50-100 MB |
| minio_data | ~500 MB - 2 GB |
| **Итоговый backup** | ~1-2.5 GB |

**Требуется места для 7 дней:** ~10-20 GB

## 🆘 Решение проблем

### Backup не запускается по cron

```bash
# Проверить cron задачу
crontab -l

# Проверить права на скрипт
ls -la /home/voxpersona_user/VoxPersona/scripts/backup_persistent.sh

# Проверить логи cron
cat /home/voxpersona_user/backups/cron.log
```

### Ошибка "Недостаточно места на диске"

```bash
# Проверить доступное место
df -h /home/voxpersona_user/backups

# Очистить старые backup вручную
cd /home/voxpersona_user/backups
rm -f persistent_data_backup_2025*.tar.gz  # Осторожно!
```

### Docker volume не экспортируется

```bash
# Проверить существование volume
docker volume ls | grep voxpersona

# Проверить права Docker
docker ps
```

## 📝 Логи

### Формат логов

```
[2025-10-24 02:00:00] 🤖 Запуск автоматического backup VoxPersona
[2025-10-24 02:00:01] 📁 Сбор bind mount директорий...
[2025-10-24 02:00:01]   ✓ telegram_sessions (56K)
[2025-10-24 02:00:01]   ✓ auth_data (32K)
...
[2025-10-24 02:05:30] ✅ Backup успешно завершен!
```

## 🔗 Связанные документы

- [docker-compose.yml](../docker-compose.yml) - Конфигурация Docker volumes
- [TASKS/00006_20251015_URYFB/exec_log.md](../TASKS/00006_20251015_URYFB/exec_log.md) - Журнал восстановления системы
- [TASKS/00006_20251015_URYFB/research/ARCHITECTURE_ANALYSIS.md](../TASKS/00006_20251015_URYFB/research/ARCHITECTURE_ANALYSIS.md) - Анализ архитектуры защиты данных

---

**Дата создания:** 2025-10-24
**Версия:** 1.0.0
**Автор:** VoxPersona Team
