# Руководство по миграции пользователей VoxPersona

## Обзор

Данное руководство описывает процесс миграции существующих пользователей из старой системы авторизации (`config.authorized_users`) в новую auth систему на базе AuthManager.

## Подготовка к миграции

### 1. Проверка текущих пользователей

```bash
cd C:\Users\l0934\Projects\VoxPersona
python -c "from src.config import authorized_users; print(f'Пользователей для миграции: {len(authorized_users)}'); print(authorized_users)"
```

### 2. Создание резервной копии (опционально)

```bash
# Бэкап текущих данных auth_data (если есть)
tar -czf auth_data_backup_$(date +%Y%m%d_%H%M%S).tar.gz src/auth_data/
```

## Запуск миграции

### Тестовая миграция (рекомендуется)

Сначала протестируйте процесс миграции с mock данными:

```bash
python scripts/test_migrate_users.py
```

Проверьте созданные файлы:
- `src/auth_data/test_migration_report.json` - отчет о миграции
- `src/auth_data/user_{user_id}/user.json` - данные пользователей

### Реальная миграция

**ВАЖНО:** Убедитесь, что Pyrogram Client авторизован (наличие .session файла).

```bash
python scripts/migrate_users.py
```

## Что происходит во время миграции

Для каждого `telegram_id` из `config.authorized_users`:

1. **Генерация пароля**: Создается случайный пароль (16 символов)
2. **Получение username**: Запрос к Telegram API для получения имени пользователя
3. **Создание пользователя**: Запись в auth систему с параметрами:
   - `role`: "user" (обычный пользователь)
   - `must_change_password`: True (требуется смена пароля)
   - `temp_password_expires_at`: now + 3 дня (TTL временного пароля)
   - `is_active`: True
   - `is_blocked`: False
4. **Сохранение пароля**: Запись в `migration_report.json` для отправки

## Результаты миграции

### Отчет о миграции

После завершения создается файл `src/auth_data/migration_report.json`:

```json
{
  "migration_date": "2025-10-20T12:00:00",
  "total_users": 5,
  "migrated": [
    {
      "telegram_id": 123456789,
      "username": "Иван Петров",
      "temp_password": "abc123xyz456def",
      "role": "user",
      "user_id": "uuid-here",
      "success": true
    }
  ],
  "failed": []
}
```

### Структура данных пользователя

Каждый пользователь сохраняется в `auth_data/user_{user_id}/user.json`:

```json
{
  "user_id": "uuid",
  "telegram_id": 123456789,
  "username": "Иван Петров",
  "password_hash": "sha256-hash",
  "role": "user",
  "must_change_password": true,
  "temp_password_expires_at": "2025-10-23T12:00:00",
  "is_active": true,
  "is_blocked": false,
  "created_at": "2025-10-20T12:00:00",
  "metadata": {
    "registration_source": "migration",
    "invite_code_used": "MIGRATION",
    "notes": "Migrated from config.authorized_users"
  }
}
```

## Проверка результатов

### 1. Просмотр отчета

```bash
cat src/auth_data/migration_report.json
```

### 2. Проверка созданных пользователей

```bash
ls -la src/auth_data/user_*/
```

### 3. Программная проверка

```python
from pathlib import Path
from src.auth_manager import AuthManager

auth_manager = AuthManager(Path("src/auth_data"))

# Проверить пользователя по telegram_id
user = auth_manager.storage.get_user_by_telegram_id(123456789)
print(f"User: {user.username}, must_change_password: {user.must_change_password}")
```

## Следующие шаги

После успешной миграции:

### 1. Отправка паролей пользователям (T19)

Используйте скрипт `scripts/send_passwords.py` (будет создан в T19) для отправки временных паролей:

```bash
python scripts/send_passwords.py --input src/auth_data/migration_report.json
```

### 2. Безопасное хранение паролей

**КРИТИЧНО:** После отправки паролей:

```bash
# Переместить отчет в безопасное место
mv src/auth_data/migration_report.json ~/secure_backup/migration_report_$(date +%Y%m%d).json

# Или зашифровать
gpg -c src/auth_data/migration_report.json
rm src/auth_data/migration_report.json
```

### 3. Очистка старой системы

После подтверждения успешной работы новой auth системы:

```python
# В config.py - очистить authorized_users (когда все переключатся)
# authorized_users: Set[int] = set()
```

## Устранение проблем

### Ошибка: "Failed to retrieve username"

**Причина:** Pyrogram Client не может получить информацию о пользователе.

**Решение:**
- Проверьте авторизацию Pyrogram Client
- Убедитесь, что пользователь существует в Telegram
- Скрипт автоматически использует fallback: `User{telegram_id}`

### Ошибка: "User already exists"

**Причина:** Пользователь уже был мигрирован ранее.

**Решение:**
- Это нормальное поведение (идемпотентность)
- Скрипт пропускает уже мигрированных пользователей
- Проверьте отчет на наличие повторных запусков

### Ошибка: "Failed to create user in storage"

**Причина:** Ошибка записи в файловую систему.

**Решение:**
- Проверьте права доступа к `auth_data/`
- Проверьте наличие свободного места на диске
- Проверьте логи для деталей ошибки

## Безопасность

### Защита паролей

- ✅ Пароли хешируются через SHA256 (временно, в T09 будет bcrypt)
- ✅ Временные пароли имеют TTL = 3 дня
- ✅ Требуется обязательная смена пароля при первом входе
- ⚠️ `migration_report.json` содержит открытые пароли - защитите его!

### Рекомендации

1. Запускайте миграцию в нерабочее время
2. Сохраняйте `migration_report.json` в безопасном месте
3. Отправьте пароли пользователям как можно быстрее
4. Удалите/зашифруйте отчет после отправки паролей
5. Мониторьте логи на наличие неудачных попыток входа

## Контакты

При возникновении проблем обращайтесь к:
- **backend-developer** (создатель системы)
- Документация: `TASKS/00005_20251014_HRYHG/`

---

**Версия:** 1.0
**Дата:** 20 октября 2025
**Задача:** T18 (#00005_20251014_HRYHG)
