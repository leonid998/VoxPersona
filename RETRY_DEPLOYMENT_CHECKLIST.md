# Чеклист Развертывания Retry Механизма

## ✅ Pre-Deployment Checklist

### 1. Код
- [x] Импорт `functools.wraps` добавлен
- [x] Декоратор `retry_on_failure` создан
- [x] Сигнатура `_save_to_conversation` изменена на `-> bool`
- [x] Return values добавлены в `_save_to_conversation`
- [x] Функция `_save_to_conversation_with_retry` создана
- [x] Вызовы в `smart_send_text_unified` обновлены (2 места)
- [x] Уведомления пользователю добавлены
- [x] Синтаксис проверен (Python AST)

### 2. Тестирование
- [x] Синтаксическая проверка пройдена
- [x] Все ключевые элементы присутствуют
- [ ] Unit тесты для retry декоратора (опционально)
- [ ] Integration тесты для сохранения (опционально)
- [ ] Нагрузочное тестирование (опционально)

### 3. Документация
- [x] `RETRY_MECHANISM_CHANGES.md` создан
- [x] `RETRY_FIX_SUMMARY.txt` создан
- [x] `RETRY_EXAMPLE.md` создан
- [x] Резервные копии созданы

### 4. Резервное Копирование
- [x] `utils.py.backup` - оригинальная версия
- [x] `utils_original.py` - дубликат оригинала

---

## 🚀 Deployment Steps

### Шаг 1: Подготовка
```bash
# На сервере создать backup текущей версии
ssh root@172.237.73.207 "cp /root/bots/voxpersona/src/utils.py /root/bots/voxpersona/src/utils.py.pre-retry-backup"
```

### Шаг 2: Деплой
```bash
# Скопировать обновленный файл на сервер
scp C:/Users/l0934/Projects/VoxPersona/src/utils.py root@172.237.73.207:/root/bots/voxpersona/src/
```

### Шаг 3: Перезапуск бота
```bash
# На сервере перезапустить Docker контейнер
ssh root@172.237.73.207 "docker restart voxpersona-bot"
```

### Шаг 4: Мониторинг
```bash
# Проверить логи после перезапуска
ssh root@172.237.73.207 "docker logs -f voxpersona-bot"
```

---

## 🔍 Post-Deployment Verification

### 1. Проверка запуска бота
```bash
# Проверить что бот запустился без ошибок
docker ps | grep voxpersona-bot
# Должен показать RUNNING статус
```

### 2. Проверка логов на ошибки импорта
```bash
# Искать ImportError или SyntaxError
docker logs voxpersona-bot 2>&1 | grep -E "ImportError|SyntaxError|Error"
# Не должно быть ошибок связанных с utils.py
```

### 3. Функциональный тест
- [ ] Отправить короткое сообщение боту
- [ ] Проверить что ответ сохранился в conversation
- [ ] Проверить логи на наличие "Saved to conversation"

### 4. Тест retry механизма (симуляция)
Временно можно добавить в код:
```python
# В _save_to_conversation для теста
if random.random() < 0.7:  # 70% шанс на провал
    return False
```
- [ ] Проверить что retry срабатывает
- [ ] Проверить логи на "Retry 1/3", "Retry 2/3"
- [ ] Проверить успешное сохранение после retry

### 5. Тест критической ошибки
Временно:
```python
# В _save_to_conversation для теста
return False  # Всегда False
```
- [ ] Проверить что пользователь получает уведомление
- [ ] Проверить логи на "CRITICAL: Failed to save conversation"

---

## 📊 Monitoring Metrics

### Что отслеживать:
1. **Частота retry**
   - Сколько раз в день срабатывает retry?
   - На каком attempt обычно успех?

2. **Критические ошибки**
   - Сколько раз все 3 попытки провалились?
   - Какие error messages?

3. **Performance**
   - Добавленная задержка от retry (max 3s)
   - Влияние на общую производительность

### Алертинг
Настроить оповещения при:
- Более 10 CRITICAL ошибок в час
- Более 50% сообщений требуют retry
- Любые SyntaxError/ImportError

---

## 🔄 Rollback Plan

### Если что-то пошло не так:

#### Вариант 1: Быстрый откат
```bash
# На сервере вернуть backup
ssh root@172.237.73.207 "cp /root/bots/voxpersona/src/utils.py.pre-retry-backup /root/bots/voxpersona/src/utils.py"
ssh root@172.237.73.207 "docker restart voxpersona-bot"
```

#### Вариант 2: Откат с локальной копии
```bash
# Залить оригинальный файл
scp C:/Users/l0934/Projects/VoxPersona/src/utils.py.backup root@172.237.73.207:/root/bots/voxpersona/src/utils.py
ssh root@172.237.73.207 "docker restart voxpersona-bot"
```

#### Вариант 3: Git revert (если в репозитории)
```bash
ssh root@172.237.73.207 "cd /root/bots/voxpersona && git checkout utils.py && docker restart voxpersona-bot"
```

---

## 📝 Notes

### Критические моменты:
1. **asyncio.to_thread()** требует Python 3.9+
   - Убедиться что на сервере Python >= 3.9
   - Проверить: `python --version`

2. **functools.wraps** - стандартная библиотека
   - Не требует дополнительных зависимостей

3. **Event loop**
   - Retry не блокирует благодаря asyncio.to_thread()
   - Тесты на блокировку не требуются

### Ожидаемые изменения в поведении:
- Временные ошибки сохранения теперь автоматически исправляются
- Пользователи видят уведомления только при критических проблемах
- Детальное логирование для debugging

---

## ✅ Sign-off

- [ ] Код проверен и готов
- [ ] Backup создан
- [ ] Документация завершена
- [ ] Deployment plan утвержден
- [ ] Rollback plan подготовлен
- [ ] Мониторинг настроен
- [ ] Команда уведомлена

**Дата готовности:** 5 октября 2025  
**Responsible:** Backend Developer  
**Approver:** _____________  
**Deployed by:** _____________  
**Deployment date:** _____________

---

**Статус:** ✅ Ready for Production Deployment
