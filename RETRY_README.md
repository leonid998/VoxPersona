# Retry Механизм для VoxPersona Bot

> Автоматическая обработка ошибок сохранения с exponential backoff

## 📋 Краткое Описание

Добавлен robust retry механизм для обработки временных ошибок при сохранении сообщений в conversation history. Теперь система автоматически повторяет неудачные попытки сохранения, предотвращая потерю данных.

## 🎯 Проблема

**Было:**
- Функция `_save_to_conversation()` возвращала `None` вместо `bool`
- Ошибки сохранения игнорировались
- Данные терялись молча
- Пользователь не получал уведомления о проблемах

**Стало:**
- Корректные return values (`True`/`False`)
- Автоматический retry с exponential backoff (3 попытки)
- Уведомления пользователю при критических ошибках
- Подробное логирование всех попыток

## 🔧 Технические Детали

### Retry Декоратор

```python
@retry_on_failure(max_attempts=3, backoff_factor=2)
def _save_to_conversation_with_retry(...) -> bool:
    return _save_to_conversation(...)
```

**Параметры:**
- `max_attempts=3` - максимум 3 попытки
- `backoff_factor=2` - экспоненциальное увеличение задержки (1s, 2s, 4s)

### Exponential Backoff

| Попытка | Задержка перед следующей | Общее время |
|---------|-------------------------|-------------|
| 1       | 1s                      | 1s          |
| 2       | 2s                      | 3s          |
| 3       | -                       | 3s          |

### Async/Await Integration

```python
success = await asyncio.to_thread(
    _save_to_conversation_with_retry,
    chat_id, conversation_id, ...
)
```

**Почему `asyncio.to_thread()`?**
- Retry механизм использует `time.sleep()` (синхронный)
- `asyncio.to_thread()` запускает в отдельном потоке
- Event loop НЕ блокируется

## 📊 Сценарии Работы

### ✅ Успешное сохранение (1 попытка)

```
INFO: Saved to conversation: conv_123 (user_id=456, message_id=789)
```

### ⚠️ Временная ошибка (retry успешен)

```
WARNING: Retry 1/3 for _save_to_conversation_with_retry after 1s
INFO: Success on attempt 2/3
INFO: Saved to conversation: conv_123 (user_id=456, message_id=789)
```

### ❌ Критическая ошибка (все попытки провалились)

```
WARNING: Retry 1/3 for _save_to_conversation_with_retry after 1s
WARNING: Retry 2/3 for _save_to_conversation_with_retry after 2s
ERROR: Failed after 3 attempts
ERROR: CRITICAL: Failed to save conversation: conv_123
```

**Telegram уведомление пользователю:**
```
⚠️ Не удалось сохранить ответ в историю мультичата. Попробуйте позже.
```

## 📁 Структура Файлов

```
VoxPersona/
├── src/
│   ├── utils.py                         # ОБНОВЛЕН (20KB)
│   ├── utils.py.backup                  # Резервная копия (16KB)
│   └── utils.py.bak                     # Другая резервная копия
├── RETRY_README.md                      # Этот файл
├── RETRY_MECHANISM_CHANGES.md           # Подробная документация изменений
├── RETRY_FIX_SUMMARY.txt                # Краткая сводка
├── RETRY_EXAMPLE.md                     # 5 практических примеров
└── RETRY_DEPLOYMENT_CHECKLIST.md        # Чеклист деплоя
```

## 🚀 Deployment

### Шаг 1: Backup на сервере

```bash
ssh root@172.237.73.207 "cp /root/bots/voxpersona/src/utils.py /root/bots/voxpersona/src/utils.py.pre-retry-backup"
```

### Шаг 2: Деплой

```bash
scp C:/Users/l0934/Projects/VoxPersona/src/utils.py root@172.237.73.207:/root/bots/voxpersona/src/
```

### Шаг 3: Перезапуск

```bash
ssh root@172.237.73.207 "docker restart voxpersona-bot"
```

### Шаг 4: Проверка

```bash
ssh root@172.237.73.207 "docker logs -f voxpersona-bot"
```

## 🔍 Мониторинг

### Ключевые метрики:

1. **Частота retry** - как часто срабатывает retry
2. **Успешность retry** - на какой попытке обычно успех
3. **Критические ошибки** - сколько раз все 3 попытки провалились
4. **Performance** - задержка от retry (max 3s)

### Алертинг:

Настроить оповещения при:
- Более 10 CRITICAL ошибок в час
- Более 50% сообщений требуют retry
- Любые ImportError/SyntaxError

### Grep команды для логов:

```bash
# Успешные retry
docker logs voxpersona-bot | grep "Success on attempt"

# Критические ошибки
docker logs voxpersona-bot | grep "CRITICAL: Failed to save"

# Все retry попытки
docker logs voxpersona-bot | grep "Retry.*for _save_to_conversation"
```

## 🔄 Rollback

### Быстрый откат:

```bash
ssh root@172.237.73.207 "cp /root/bots/voxpersona/src/utils.py.pre-retry-backup /root/bots/voxpersona/src/utils.py && docker restart voxpersona-bot"
```

### Откат с локальной копии:

```bash
scp C:/Users/l0934/Projects/VoxPersona/src/utils.py.backup root@172.237.73.207:/root/bots/voxpersona/src/utils.py
ssh root@172.237.73.207 "docker restart voxpersona-bot"
```

## 📚 Дополнительная Документация

- **RETRY_MECHANISM_CHANGES.md** - Полное описание изменений в коде
- **RETRY_EXAMPLE.md** - 5 детальных примеров работы
- **RETRY_FIX_SUMMARY.txt** - Краткая сводка в текстовом формате
- **RETRY_DEPLOYMENT_CHECKLIST.md** - Чеклист развертывания

## ⚙️ Требования

- Python >= 3.9 (для `asyncio.to_thread()`)
- functools (стандартная библиотека)
- Существующие зависимости проекта

## 🧪 Тестирование

### Синтаксис:
```bash
python -m py_compile src/utils.py
# ✅ Успешно
```

### Функциональный тест:
1. Отправить сообщение боту
2. Проверить логи на "Saved to conversation"
3. Проверить conversation history

### Тест retry:
Временно добавить в `_save_to_conversation`:
```python
import random
if random.random() < 0.7:  # 70% шанс провала
    return False
```

## ❓ FAQ

**Q: Блокирует ли retry event loop?**  
A: Нет, используется `asyncio.to_thread()` для запуска в отдельном потоке.

**Q: Что происходит при критической ошибке?**  
A: Пользователь получает уведомление, сообщение доставлено, но не сохранено в истории.

**Q: Можно ли настроить количество попыток?**  
A: Да, изменить параметр `max_attempts` в декораторе `@retry_on_failure`.

**Q: Как долго может длиться retry?**  
A: Максимум 3 секунды (1s + 2s между попытками).

## 👤 Автор

Backend Developer  
Дата: 5 октября 2025

## 📝 Changelog

### [1.0.0] - 2025-10-05
#### Added
- Retry декоратор с exponential backoff
- `_save_to_conversation_with_retry` функция
- Уведомления пользователю при критических ошибках
- Подробное логирование

#### Changed
- `_save_to_conversation` signature: `-> None` на `-> bool`
- Добавлены return values в `_save_to_conversation`

#### Fixed
- Ошибки сохранения теперь не игнорируются
- Данные не теряются при временных сбоях

---

**Статус:** ✅ Ready for Production
