# CHANGELOG: MD Cleanup Implementation

## [1.1.0] - 2025-10-05

### Added

#### conversation_manager.py
- **MD файлы теперь автоматически удаляются** при удалении чата
- Метод `delete_conversation()` обновлен для cleanup связанных MD отчетов
- Добавлено логирование статистики удаленных MD файлов
- Обработка ошибок для каждого удаляемого файла

#### md_storage.py
- **Новый метод:** `find_orphaned_reports(user_id: int) -> List[str]`
  - Находит MD отчеты не связанные ни с одним чатом
  - Сравнивает все MD файлы со ссылками в conversations
  
- **Новый метод:** `cleanup_orphaned_reports(user_id: int) -> int`
  - Удаляет осиротевшие MD файлы
  - Обновляет index.json
  - Возвращает количество удаленных файлов
  
- **Новый метод:** `_remove_from_index(file_paths: List[str])`
  - Приватный метод для обновления MD индекса
  - Удаляет записи об удаленных файлах
  
- **Обновлен метод:** `get_user_reports(user_id: int, limit: Optional[int] = 10)`
  - Добавлена поддержка `limit=None` для получения всех отчетов
  - Используется в `find_orphaned_reports()`

#### Новые файлы
- `src/test_md_cleanup.py` - Тестовый скрипт для проверки cleanup механизма
- `MD_CLEANUP_IMPLEMENTATION.md` - Полная документация реализации

### Changed

#### Логика удаления чата
**До:**
```python
def delete_conversation(self, user_id: int, conversation_id: str) -> bool:
    # Сразу удаляет JSON файл чата
    conversation_file.unlink()
    # MD файлы остаются "осиротевшими"
```

**После:**
```python
def delete_conversation(self, user_id: int, conversation_id: str) -> bool:
    # 1. СНАЧАЛА загружает чат
    conversation = self.load_conversation(user_id, conversation_id)
    
    # 2. Собирает MD файлы
    md_files_to_delete = [
        msg.file_path for msg in conversation.messages
        if msg.file_path and msg.sent_as == "file"
    ]
    
    # 3. Удаляет MD файлы с логированием
    for file_path in md_files_to_delete:
        Path(file_path).unlink()
        logger.info(f"Deleted MD file: {file_path}")
    
    # 4. ПОТОМ удаляет JSON чата
    conversation_file.unlink()
```

### Fixed
- **Проблема:** MD файлы оставались после удаления чатов
- **Решение:** Автоматический cleanup при удалении + метод поиска orphaned

### Security
- Все операции удаления обернуты в `try-except`
- Проверка существования файлов перед удалением
- Невозможно удалить "живые" файлы (связанные с чатами)
- Атомарное обновление index.json

### Performance
- Минимальное влияние: удаление файлов выполняется последовательно
- Метод `find_orphaned_reports()` оптимизирован с использованием set

## Migration Guide

### Для существующих данных

Если у вас уже есть orphaned MD файлы, выполните cleanup:

```python
from md_storage import md_storage_manager

# Для конкретного пользователя
deleted = md_storage_manager.cleanup_orphaned_reports(user_id=123456)
print(f"Удалено orphaned файлов: {deleted}")

# Или найти без удаления
orphaned = md_storage_manager.find_orphaned_reports(user_id=123456)
print(f"Найдено orphaned файлов: {len(orphaned)}")
```

### API изменения

#### Новые публичные методы:
- `MDStorageManager.find_orphaned_reports(user_id: int) -> List[str]`
- `MDStorageManager.cleanup_orphaned_reports(user_id: int) -> int`

#### Обновленные методы:
- `MDStorageManager.get_user_reports(user_id: int, limit: Optional[int] = 10)`
  - Теперь поддерживает `limit=None` для получения всех отчетов

#### Без изменений:
- `ConversationManager.delete_conversation()` - сигнатура не изменилась
- Все остальные публичные API сохранены

## Testing

Запустить тесты:
```bash
cd /home/voxpersona_user/VoxPersona/src
python test_md_cleanup.py
```

Проверить в production:
1. Создать чат с длинным ответом (создастся MD файл)
2. Удалить чат через меню
3. Проверить что MD файл также удален

## Rollback

Если нужен откат к предыдущей версии:
```bash
# Восстановить из backup
cp src/conversation_manager.py.backup src/conversation_manager.py

# Перезапустить бота
docker-compose restart voxpersona-bot
```

---

**Автор:** Python Pro Agent  
**Дата:** 5 октября 2025  
**Версия:** 1.1.0  
**Статус:** ✅ Протестировано и готово к production
