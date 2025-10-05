# Примеры Работы Retry Механизма

## Пример 1: Успешное сохранение с первой попытки

### Вызов:
\`\`\`python
await smart_send_text_unified(
    text="Короткий ответ",
    chat_id=123456,
    app=app,
    conversation_id="conv_789"
)
\`\`\`

### Логи:
\`\`\`
INFO: Saved to conversation: conv_789 (user_id=123456, message_id=12345)
INFO: Message sent to 123456, length: 15 chars
\`\`\`

### Результат:
- ✅ Сообщение отправлено
- ✅ Сохранено в conversation с первой попытки
- ✅ return True

---

## Пример 2: Успешное сохранение со второй попытки

### Вызов:
\`\`\`python
await smart_send_text_unified(
    text="Важный ответ",
    chat_id=123456,
    app=app,
    conversation_id="conv_789"
)
\`\`\`

### Логи:
\`\`\`
WARNING: Retry 1/3 for _save_to_conversation_with_retry after 1s (result was False)
INFO: Success on attempt 2/3
INFO: Saved to conversation: conv_789 (user_id=123456, message_id=12346)
INFO: Message sent to 123456, length: 13 chars
\`\`\`

### Результат:
- ⚠️ Первая попытка провалилась (wait 1s)
- ✅ Вторая попытка успешна
- ✅ return True
- Пользователь не получил уведомление об ошибке (проблема решена автоматически)

---

## Пример 3: Критическая ошибка (все попытки провалились)

### Вызов:
\`\`\`python
await smart_send_text_unified(
    text="Критический ответ",
    chat_id=123456,
    app=app,
    conversation_id="conv_789"
)
\`\`\`

### Логи:
\`\`\`
WARNING: Retry 1/3 for _save_to_conversation_with_retry after 1s (result was False)
WARNING: Retry 2/3 for _save_to_conversation_with_retry after 2s (result was False)
ERROR: Failed after 3 attempts
ERROR: CRITICAL: Failed to save conversation after all retries: user_id=123456, conversation_id=conv_789
INFO: Message sent to 123456, length: 18 chars
\`\`\`

### Telegram для пользователя:
\`\`\`
[Бот отправил ответ]
⚠️ Не удалось сохранить ответ в историю мультичата. Попробуйте позже.
\`\`\`

### Результат:
- ❌ Попытка 1 провалилась (wait 1s)
- ❌ Попытка 2 провалилась (wait 2s)
- ❌ Попытка 3 провалилась
- ⚠️ Пользователь уведомлен о проблеме
- ✅ Сообщение все равно доставлено (просто не сохранено в истории)

---

## Пример 4: Обработка исключений

### Сценарий:
База данных временно недоступна (exception)

### Логи:
\`\`\`
ERROR: Attempt 1/3 for _save_to_conversation_with_retry raised exception: Database connection failed
WARNING: ⏳ Waiting 1s before retry...
ERROR: Attempt 2/3 for _save_to_conversation_with_retry raised exception: Database connection failed
WARNING: ⏳ Waiting 2s before retry...
INFO: Success on attempt 3/3
INFO: Saved to conversation: conv_789 (user_id=123456, message_id=12347)
\`\`\`

### Результат:
- ❌ Попытка 1: Exception (wait 1s)
- ❌ Попытка 2: Exception (wait 2s)
- ✅ Попытка 3: Успех (БД восстановилась)
- ✅ return True
- Пользователь не получил уведомление (проблема решена)

---

## Пример 5: Длинный ответ (отправка файлом)

### Вызов:
\`\`\`python
await smart_send_text_unified(
    text="Очень длинный ответ..." * 1000,  # >4096 символов
    chat_id=123456,
    app=app,
    conversation_id="conv_789"
)
\`\`\`

### Процесс:
1. Отправлено превью сообщения
2. Создан MD файл
3. Отправлен файл с caption
4. Попытка сохранения в conversation с retry
5. При неудаче - уведомление пользователю

### Результат:
- ✅ Файл отправлен
- ✅ Сохранено в conversation (с retry если нужно)
- ✅ return True

---

## Технические Детали

### Exponential Backoff Timing:
- Попытка 1 → Failed
- Wait: 2^(1-1) = 2^0 = **1 секунда**
- Попытка 2 → Failed
- Wait: 2^(2-1) = 2^1 = **2 секунды**
- Попытка 3 → Failed/Success
- Total max wait: **3 секунды**

### Почему не блокирует event loop?
\`\`\`python
# Синхронная retry функция запускается в отдельном потоке
success = await asyncio.to_thread(
    _save_to_conversation_with_retry,  # Синхронная функция с time.sleep()
    chat_id, conversation_id, ...
)
\`\`\`

### Когда пользователь получает уведомление?
**ТОЛЬКО** когда все 3 попытки провалились:
\`\`\`python
if not success:  # После retry
    await app.send_message(
        chat_id,
        "⚠️ Не удалось сохранить ответ в историю мультичата. Попробуйте позже."
    )
\`\`\`

---

## Best Practices

1. **Мониторинг логов**: Следите за WARNING и ERROR логами для выявления проблем
2. **Алертинг**: Настройте оповещения при частых CRITICAL ошибках
3. **Тюнинг параметров**: При необходимости измените max_attempts или backoff_factor
4. **Дашборд**: Отслеживайте метрики retry (сколько раз срабатывает, успешность)

---

**Статус:** ✅ Механизм работает и протестирован
