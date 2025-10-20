# VoxPersona Scripts

Служебные скрипты для управления и обслуживания VoxPersona.

## Скрипты миграции

### migrate_users.py

Скрипт миграции пользователей из старой системы авторизации (`config.authorized_users`) в новую auth систему.

#### Что делает скрипт:

1. Читает список пользователей из `config.authorized_users`
2. Для каждого пользователя:
   - Генерирует случайный временный пароль (16 символов)
   - Получает username через Telegram API
   - Создает пользователя в новой auth системе
   - Устанавливает `must_change_password=True`
   - Устанавливает TTL временного пароля = 3 дня
3. Сохраняет отчет о миграции в `auth_data/migration_report.json`

#### Использование:

```bash
# Запуск из корневой директории проекта
cd C:\Users\l0934\Projects\VoxPersona
python scripts/migrate_users.py
```

#### Требования:

- Pyrogram Client должен быть авторизован (наличие .session файла)
- Переменные окружения: `API_ID`, `API_HASH`, `SESSION_NAME`
- Доступ к Telegram API для получения информации о пользователях

#### Результаты:

После выполнения создается файл `src/auth_data/migration_report.json`:

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
  "failed": [
    {
      "telegram_id": 987654321,
      "username": "UNKNOWN",
      "role": "user",
      "success": false,
      "error": "Failed to retrieve user info from Telegram"
    }
  ]
}
```

#### Важные замечания:

- **Пароли в отчете**: Временные пароли сохраняются в `migration_report.json` для последующей отправки пользователям
- **Безопасность**: После отправки паролей пользователям, удалите или переместите `migration_report.json` в безопасное место
- **Идемпотентность**: Повторный запуск пропустит уже мигрированных пользователей
- **Error handling**: Скрипт продолжает работу при ошибке миграции отдельного пользователя

#### Логирование:

Скрипт выводит подробные логи в stdout:

```
[2025-10-20 12:00:00] INFO: === VoxPersona User Migration Script ===
[2025-10-20 12:00:00] INFO: Authorized users to migrate: 5
[2025-10-20 12:00:00] INFO: Pyrogram Client connected
[2025-10-20 12:00:01] INFO: User migrated successfully: telegram_id=123456789, user_id=..., username=Иван Петров
[2025-10-20 12:00:05] INFO: Migration completed: 4 migrated, 1 failed
[2025-10-20 12:00:05] INFO: === Migration Summary ===
[2025-10-20 12:00:05] INFO: Total users: 5
[2025-10-20 12:00:05] INFO: Successfully migrated: 4
[2025-10-20 12:00:05] INFO: Failed: 1
```

#### Следующие шаги:

После успешной миграции:

1. Проверьте `migration_report.json` на наличие ошибок
2. Используйте T19 (скрипт отправки паролей) для отправки временных паролей пользователям
3. Удалите или переместите `migration_report.json` в безопасное место
4. Обновите документацию для пользователей о новой системе авторизации

---

**Автор:** backend-developer
**Дата:** 20 октября 2025
**Задача:** T18 (#00005_20251014_HRYHG)
