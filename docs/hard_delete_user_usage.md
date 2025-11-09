# Использование метода `hard_delete_user()`

## Описание
Метод `hard_delete_user()` выполняет **физическое удаление** пользователя из системы VoxPersona.

В отличие от `delete_user()` (который делает soft delete, устанавливая `is_active=False`), этот метод:
- Удаляет файл `user.json`
- Удаляет файл `sessions.json`
- Удаляет файл `audit_log.json` (если существует)
- **Полностью удаляет директорию** `user_{user_id}/`

## Когда использовать
- Когда нужно окончательно удалить пользователя без возможности восстановления
- При очистке тестовых данных
- При выполнении GDPR-запросов на удаление персональных данных

## Сигнатура
```python
def hard_delete_user(self, user_id: str) -> bool
```

## Параметры
- `user_id` (str): ID пользователя для удаления

## Возвращаемое значение
- `True`: Удаление успешно
- `False`: Ошибка при удалении (пользователь не существует или нет прав доступа)

## Примеры использования

### Базовый пример
```python
from pathlib import Path
from auth_storage import AuthStorageManager

# Инициализация
storage = AuthStorageManager(Path("auth_data"))

# Физическое удаление пользователя
success = storage.hard_delete_user(user_id="12345")

if success:
    print("Пользователь полностью удален")
else:
    print("Ошибка при удалении")
```

### Использование в обработчике Telegram бота
```python
from pyrogram import Client, filters
from auth_storage import AuthStorageManager

@Client.on_message(filters.command("delete_account"))
async def delete_account_handler(client, message):
    user_id = str(message.from_user.id)
    
    # Подтверждение удаления
    await message.reply("Вы уверены? Это действие необратимо. Ответьте 'ДА' для подтверждения.")
    
    # ... код ожидания подтверждения ...
    
    # Физическое удаление
    success = storage.hard_delete_user(user_id)
    
    if success:
        await message.reply("Ваш аккаунт полностью удален. До свидания!")
    else:
        await message.reply("Ошибка при удалении аккаунта.")
```

## Thread-Safety
Метод является **thread-safe** благодаря использованию per-user locks:
```python
lock = self._get_user_lock(user_id)
with lock:
    # Удаление происходит под lock
    shutil.rmtree(user_dir)
```

Это означает, что можно безопасно вызывать метод из нескольких Pyrogram workers одновременно.

## Обработка ошибок

### PermissionError
```python
try:
    success = storage.hard_delete_user(user_id)
except Exception as e:
    logger.error(f"Failed to delete user: {e}")
```

Метод внутренне обрабатывает `PermissionError` и логирует ошибку:
```
ERROR: Permission denied to hard delete user 12345: [Errno 13] Permission denied
```

### Пользователь не существует
```python
success = storage.hard_delete_user("nonexistent_user")
# Вернет False и залогирует предупреждение:
# WARNING: Cannot hard delete non-existent user: nonexistent_user
```

## Сравнение с `delete_user()`

| Характеристика | `delete_user()` | `hard_delete_user()` |
|---------------|-----------------|---------------------|
| Тип удаления | Soft delete | Hard delete (физическое) |
| Директория | Остается | Удаляется полностью |
| Файлы | Остаются | Удаляются все |
| Восстановление | Возможно (через `is_active=True`) | Невозможно |
| Использование | Временная блокировка | Окончательное удаление |

## Best Practices

1. **Всегда делайте backup перед физическим удалением**:
```python
# Создать backup перед удалением
backup_path = storage.backup_user(user_id)
success = storage.hard_delete_user(user_id)
```

2. **Запрашивайте подтверждение от пользователя**:
```python
# Двойное подтверждение для критических операций
if user_confirmed and user_reconfirmed:
    storage.hard_delete_user(user_id)
```

3. **Логируйте события удаления**:
```python
from auth_models import AuthAuditEvent

# Залогировать событие перед удалением
event = AuthAuditEvent(
    event_type="user_hard_deleted",
    user_id=user_id,
    details={"deleted_by": "admin"}
)
storage.log_auth_event(event)

# Физическое удаление
storage.hard_delete_user(user_id)
```

## Тестирование

Пример unit теста:
```python
import tempfile
from pathlib import Path
from auth_storage import AuthStorageManager
from auth_models import User

def test_hard_delete_user():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AuthStorageManager(Path(tmpdir))
        
        # Создать пользователя
        user = User(
            user_id="test_123",
            telegram_id=123,
            username="testuser",
            password_hash="hash"
        )
        storage.create_user(user)
        
        # Проверить что директория существует
        user_dir = Path(tmpdir) / "user_test_123"
        assert user_dir.exists()
        
        # Физическое удаление
        success = storage.hard_delete_user("test_123")
        assert success == True
        
        # Проверить что директория удалена
        assert not user_dir.exists()
```

## Автор
- **backend-developer**
- Дата: 2025-11-07
- Задача: #00007_20251105_YEIJEG/08_del_user

## Связанные методы
- `delete_user()` - Soft delete (установка `is_active=False`)
- `create_user()` - Создание нового пользователя
- `get_user()` - Получение данных пользователя
