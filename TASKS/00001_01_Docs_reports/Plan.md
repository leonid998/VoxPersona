# План реализации: Рефакторинг "Мои отчеты"

**Версия:** 2.1
**Дата создания:** 13.10.2025
**Координатор:** agent-organizer
**Общее время:** 14 часов (1.75 рабочих дня)
**Приоритет:** 🔴 КРИТИЧЕСКИЙ

---

## 1. КОМАНДА

### Координатор
- **agent-organizer** - общая координация, формирование команды, контроль качества и сроков

### Исполнители

#### 1. **python-pro** - Основной разработчик (10 часов)
**Роль:** Реализация критических доработок, интеграция, async унификация
**Зона ответственности:**
- Фаза 1.5: Критические доработки безопасности (timeout, locks, size check)
- Фаза 1: Интеграция handlers_my_reports_v2.py в handlers.py
- Фаза 2: Async унификация handle_report_callback()
- Фаза 3: Cleanup deprecated кода

**Экспертиза:**
- Python 3.11+ async/await
- asyncio.Lock и concurrent control
- FSM state management
- Pyrogram API

#### 2. **test-automator** - Тестирование (2 часа)
**Роль:** Комплексное тестирование всех workflow и edge cases
**Зона ответственности:**
- Фаза 4: Unit и integration тесты
- Smoke тесты всех сценариев
- Тестирование timeout, locks, size check

**Экспертиза:**
- pytest
- async тестирование
- edge cases validation
- test coverage >80%

#### 3. **devops-engineer** - Деплой с откатом (2 часа)
**Роль:** Безопасный деплой с canary стратегией и rollback планом
**Зона ответственности:**
- Фаза 5: Canary deployment
- Rollback стратегия и автоматизация
- Мониторинг на продакшене

**Экспертиза:**
- Docker deployment
- Backup & rollback
- Production monitoring
- SSH remote operations

---

## 2. ПОСЛЕДОВАТЕЛЬНОСТЬ ВЫПОЛНЕНИЯ

### Фаза 1.5: Критические доработки безопасности (2 часа) 🔴 КРИТИЧНО

**Исполнитель:** python-pro
**Приоритет:** 🔴 МАКСИМАЛЬНЫЙ (блокирует все остальное)

#### Задачи:

- [ ] **Шаг 1.5.1: Timeout механизм для snapshot (45 минут)**
  - Добавить импорт `datetime, timedelta` в handlers_my_reports_v2.py
  - Сохранение timestamp при создании snapshot в `handle_my_reports_v2()`
  - Создать helper функцию `_check_snapshot_timeout(chat_id) -> tuple[bool, str]`
  - Добавить проверку timeout в начале каждого `*_input()` handler:
    - `handle_report_view_input()`
    - `handle_report_rename_number_input()`
    - `handle_report_delete_input()`
  - Автоинвалидация snapshot при превышении 5 минут
  - Вывод понятного сообщения пользователю

- [ ] **Шаг 1.5.2: Concurrent control через asyncio.Lock (45 минут)**
  - Добавить в `config.py`:
    ```python
    import asyncio
    from typing import Dict

    user_locks: Dict[int, asyncio.Lock] = {}

    def get_user_lock(chat_id: int) -> asyncio.Lock:
        if chat_id not in user_locks:
            user_locks[chat_id] = asyncio.Lock()
        return user_locks[chat_id]
    ```
  - Импортировать `get_user_lock` в handlers_my_reports_v2.py
  - Обернуть критические секции в `async with get_user_lock(chat_id)`:
    - `handle_report_view_input()` - защита отправки файла
    - `handle_report_rename_name_input()` - защита изменения index.json
    - `handle_report_delete_confirm()` - защита удаления файла

- [ ] **Шаг 1.5.3: Проверка размера файла (30 минут)**
  - Добавить константу `MAX_FILE_SIZE = 10 * 1024 * 1024` (10MB)
  - В `handle_my_reports_v2()` после чтения TXT файла:
    - Проверка `len(content) > MAX_FILE_SIZE`
    - Вывод сообщения с рекомендациями при превышении
    - Логирование размера файла для мониторинга
  - Добавить логирование размера для всех пользователей (info level)

#### Входные данные:
- `C:\Users\l0934\Projects\VoxPersona\src\handlers_my_reports_v2.py` (825 строк)
- `C:\Users\l0934\Projects\VoxPersona\src\config.py` (user_states)

#### Выходные данные:
- Обновленный `handlers_my_reports_v2.py` с timeout и size check
- Обновленный `config.py` с функцией `get_user_lock()`
- Логи с информацией о размере файлов

#### Критерии завершения:
- ✅ Timeout 5 минут работает (snapshot автоматически инвалидируется)
- ✅ asyncio.Lock защищает критические секции от race condition
- ✅ Проверка размера файла блокирует отправку >10MB
- ✅ Логирование размера файла работает
- ✅ Понятные сообщения об ошибках для пользователя
- ✅ Код прошел локальное тестирование

---

### Фаза 1: Интеграция handlers_my_reports_v2 (2 часа) 🔴 КРИТИЧНО

**Исполнитель:** python-pro
**Приоритет:** 🔴 ВЫСОКИЙ

#### Задачи:

- [ ] **Шаг 1.1: Импорт модуля (15 минут)**
  - Файл: `C:\Users\l0934\Projects\VoxPersona\src\handlers.py`
  - После строки 82 добавить импорт:
    ```python
    from handlers_my_reports_v2 import (
        handle_my_reports_v2,
        handle_report_view_request,
        handle_report_view_input,
        handle_report_rename_request,
        handle_report_rename_number_input,
        handle_report_rename_name_input,
        handle_report_delete_request,
        handle_report_delete_input,
        handle_report_delete_confirm
    )
    ```
  - Проверка синтаксиса Python

- [ ] **Шаг 1.2: Callback routing (30 минут)**
  - Файл: `handlers.py`, функция `callback_query_handler` (строка ~1290)
  - Изменить routing для "show_my_reports":
    ```python
    elif data == "show_my_reports":
        await handle_my_reports_v2(c_id, app)  # Новый handler
    ```
  - Добавить новые callback routes:
    ```python
    elif data == "report_view":
        await handle_report_view_request(c_id, app)

    elif data == "report_rename":
        await handle_report_rename_request(c_id, app)

    elif data == "report_delete":
        await handle_report_delete_request(c_id, app)

    elif data.startswith("report_delete_confirm||"):
        await handle_report_delete_confirm(c_id, app)
    ```

- [ ] **Шаг 1.3: FSM обработка в text handler (45 минут)**
  - Файл: `handlers.py`, функция `handle_authorized_text` (после строки 403)
  - Добавить FSM логику:
    ```python
    if c_id in user_states:
        step = user_states[c_id].get("step")

        # View report
        if step == "report_view_ask_number":
            await handle_report_view_input(c_id, text_, app)
            return

        # Rename report - номер
        elif step == "report_rename_ask_number":
            await handle_report_rename_number_input(c_id, text_, app)
            return

        # Rename report - новое имя
        elif step == "report_rename_ask_new_name":
            await handle_report_rename_name_input(c_id, text_, app)
            return

        # Delete report
        elif step == "report_delete_ask_number":
            await handle_report_delete_input(c_id, text_, app)
            return
    ```

- [ ] **Шаг 1.4: Smoke тесты интеграции (30 минут)**
  - Тест 1: Импорт без ошибок
  - Тест 2: Callback routing корректен
  - Тест 3: FSM routing корректен
  - Тест 4: Python синтаксис валиден

#### Входные данные:
- `C:\Users\l0934\Projects\VoxPersona\src\handlers.py` (1370 строк)
- `C:\Users\l0934\Projects\VoxPersona\src\handlers_my_reports_v2.py` (обновленный)

#### Выходные данные:
- Обновленный `handlers.py` с интеграцией v2
- Корректный callback routing
- FSM обработка в text handler

#### Критерии завершения:
- ✅ Импорт handlers_my_reports_v2 работает без ошибок
- ✅ Callback routing направляет на новые handlers
- ✅ FSM состояния обрабатываются корректно
- ✅ Python синтаксис валиден
- ✅ Smoke тесты пройдены

---

### Фаза 2: Async унификация (1 час) 🔴 КРИТИЧНО

**Исполнитель:** python-pro
**Приоритет:** 🔴 ВЫСОКИЙ (блокировка event loop)

#### Задачи:

- [ ] **Шаг 2.1: Исправить handle_report_callback() (45 минут)**
  - Файл: `handlers.py`, строки 329-378
  - Изменить определение функции:
    ```python
    # ❌ ДО:
    def handle_report_callback(callback_query: CallbackQuery, app: Client) -> None:

    # ✅ ПОСЛЕ:
    async def handle_report_callback(callback_query: CallbackQuery, app: Client) -> None:
    ```
  - Добавить `await` для всех Pyrogram методов:
    - `await app.send_document(...)`
    - `await app.answer_callback_query(...)`
    - `await app.edit_message_text(...)`
  - Обновить вызов в callback_query_handler (строка ~1352):
    ```python
    # ❌ ДО:
    handle_report_callback(callback, app)

    # ✅ ПОСЛЕ:
    await handle_report_callback(callback, app)
    ```

- [ ] **Шаг 2.2: Проверка всех async вызовов (15 минут)**
  - Сканирование handlers.py на паттерн `app.send_*` без await
  - Поиск `app.edit_*` без await
  - Поиск `app.answer_*` без await
  - Исправление найденных проблем

#### Входные данные:
- `C:\Users\l0934\Projects\VoxPersona\src\handlers.py` (обновленный)

#### Выходные данные:
- Полностью async совместимый `handle_report_callback()`
- Нет блокирующих sync вызовов

#### Критерии завершения:
- ✅ `handle_report_callback()` объявлен как async
- ✅ Все Pyrogram методы вызываются с await
- ✅ Вызов в routing с await
- ✅ Нет блокировки event loop
- ✅ Python синтаксис валиден

---

### Фаза 3: Cleanup deprecated кода (1 час) 🟡 ВЫСОКО

**Исполнитель:** python-pro
**Приоритет:** 🟡 СРЕДНИЙ

#### Задачи:

- [ ] **Шаг 3.1: Закомментировать старый код (30 минут)**
  - Файл: `handlers.py`, строки 589-632
  - Закомментировать функцию `handle_show_my_reports()`:
    ```python
    # ============================================================================
    # DEPRECATED - Заменено на handlers_my_reports_v2.py (13.10.2025)
    # ============================================================================
    # async def handle_show_my_reports(chat_id: int, app: Client):
    #     ...весь старый код...
    ```
  - Добавить комментарий с причиной и датой

- [ ] **Шаг 3.2: Удалить старые callback routes (15 минут)**
  - Закомментировать или удалить старый routing для:
    - `send_report||` (если не используется)
    - `show_all_reports` (если не используется)
  - Оставить резервную копию в комментариях

- [ ] **Шаг 3.3: Обновить комментарии (15 минут)**
  - Добавить комментарий в начале handlers.py:
    ```python
    # "Мои отчеты" v2 - см. handlers_my_reports_v2.py (13.10.2025)
    # Старая реализация закомментирована (строки 589-632)
    ```
  - Обновить inline комментарии

#### Входные данные:
- `C:\Users\l0934\Projects\VoxPersona\src\handlers.py` (обновленный)

#### Выходные данные:
- Чистый код без deprecated функций
- Понятные комментарии
- Резервная копия старого кода в комментариях

#### Критерии завершения:
- ✅ Старая функция `handle_show_my_reports()` закомментирована
- ✅ Старые callback routes очищены
- ✅ Комментарии обновлены
- ✅ Резервная копия сохранена в комментариях
- ✅ Код читаем и структурирован

---

### Фаза 4: Тестирование (4 часа) 🟡 ВЫСОКО

**Исполнитель:** test-automator
**Приоритет:** 🟡 ВЫСОКИЙ

#### Задачи:

- [ ] **Шаг 4.1: Unit тесты (2 часа)**
  - Создать файл: `tests/test_my_reports_v2.py`
  - Тест-кейсы:
    1. `test_handle_my_reports_v2_no_reports()` - нет отчетов
    2. `test_handle_my_reports_v2_with_reports()` - есть отчеты
    3. `test_validate_report_index()` - валидация номера
    4. `test_snapshot_race_condition()` - snapshot предотвращает race
    5. `test_snapshot_timeout()` 🆕 - timeout инвалидирует snapshot
    6. `test_concurrent_operations()` 🆕 - Lock предотвращает race
    7. `test_file_size_limit()` 🆕 - проверка лимита 10MB
    8. `test_view_workflow()` - просмотр отчета
    9. `test_rename_workflow()` - переименование отчета
    10. `test_delete_workflow()` - удаление отчета
    11. `test_invalid_number_input()` - некорректный номер
    12. `test_report_not_found()` - отчет не найден
    13. `test_file_not_found()` - файл отчета не найден

- [ ] **Шаг 4.2: Integration тесты (1 час)**
  - Тест полного workflow View (от кнопки до файла)
  - Тест полного workflow Rename (номер → новое имя)
  - Тест полного workflow Delete (номер → подтверждение)
  - Тест отмены действия на каждом шаге
  - Тест timeout после 5 минут бездействия 🆕
  - Тест одновременных операций (concurrent) 🆕

- [ ] **Шаг 4.3: Edge cases тесты (30 минут)**
  - Ввод текста вместо номера
  - Ввод 0, -1, 999 (невалидные номера)
  - Удаление отчета между запросом и действием
  - Отсутствие файла отчета
  - Список отчетов >10MB 🆕
  - Snapshot устарел (>5 минут) 🆕

- [ ] **Шаг 4.4: Smoke тесты локально (30 минут)**
  - Тест 1: "Мои отчеты" → TXT файл отправлен
  - Тест 2: Просмотр отчета №5
  - Тест 3: Переименование отчета №3
  - Тест 4: Удаление отчета №10
  - Тест 5: Отмена действия
  - Тест 6: Timeout после 5 минут 🆕
  - Тест 7: Быстрые повторные нажатия (Lock) 🆕

#### Входные данные:
- Все файлы проекта после Фазы 3
- Тестовые данные (mock отчеты)

#### Выходные данные:
- `tests/test_my_reports_v2.py` (13 тест-кейсов)
- Test coverage report (>80%)
- Список найденных багов (если есть)

#### Критерии завершения:
- ✅ 13 unit тестов пройдены
- ✅ Integration тесты пройдены
- ✅ Edge cases обработаны корректно
- ✅ Test coverage >80%
- ✅ Smoke тесты пройдены локально
- ✅ Нет критических багов
- ✅ Timeout механизм работает
- ✅ Lock механизм работает
- ✅ Size check работает

---

### Фаза 5: Деплой с rollback стратегией (4 часа) 🟢 СРЕДНЕ

**Исполнитель:** devops-engineer
**Приоритет:** 🟢 СРЕДНИЙ

#### Задачи:

- [ ] **Шаг 5.1: Подготовка rollback плана (30 минут)**
  - Создать rollback скрипт: `rollback_my_reports_v2.sh`
  - Содержание:
    ```bash
    #!/bin/bash
    # Rollback script для handlers_my_reports_v2
    cd /home/voxpersona_user/VoxPersona
    LAST_BACKUP=$(ls -t src/handlers.py.backup_* | head -1)
    BACKUP_SUFFIX=$(echo $LAST_BACKUP | sed 's/.*backup_//')
    cp src/handlers.py.backup_$BACKUP_SUFFIX src/handlers.py
    cp src/config.py.backup_$BACKUP_SUFFIX src/config.py
    cp src/handlers_my_reports_v2.py.backup_$BACKUP_SUFFIX src/handlers_my_reports_v2.py
    docker restart voxpersona
    ```
  - Сделать скрипт исполняемым: `chmod +x rollback_my_reports_v2.sh`
  - Протестировать локально (dry-run)

- [ ] **Шаг 5.2: Backup текущей версии (30 минут)**
  - SSH: `ssh root@172.237.73.207`
  - Создать backup:
    ```bash
    cd /home/voxpersona_user/VoxPersona
    BACKUP_SUFFIX=$(date +%Y%m%d_%H%M%S)
    cp src/handlers.py src/handlers.py.backup_$BACKUP_SUFFIX
    cp src/config.py src/config.py.backup_$BACKUP_SUFFIX
    cp src/handlers_my_reports_v2.py src/handlers_my_reports_v2.py.backup_$BACKUP_SUFFIX
    ls -la src/*.backup_$BACKUP_SUFFIX > rollback_manifest_$BACKUP_SUFFIX.txt
    echo "Backup created: $BACKUP_SUFFIX"
    ```
  - Сохранить BACKUP_SUFFIX для rollback

- [ ] **Шаг 5.3: Canary deployment (1 час)**
  - Копирование файлов на сервер:
    - `handlers_my_reports_v2.py` (обновленный)
    - `config.py` (с get_user_lock)
    - `handlers.py` (с интеграцией v2)
  - Проверка синтаксиса Python:
    ```bash
    docker exec voxpersona python -m py_compile /app/src/handlers.py
    docker exec voxpersona python -m py_compile /app/src/handlers_my_reports_v2.py
    docker exec voxpersona python -m py_compile /app/src/config.py
    ```
  - Graceful restart:
    ```bash
    docker exec voxpersona pkill -USR1 python || docker restart voxpersona
    ```
  - Мониторинг первые 5 минут (КРИТИЧНО!):
    ```bash
    docker logs -f voxpersona --tail 200 | grep -i "error\|exception\|report\|started"
    ```

- [ ] **Шаг 5.4: Smoke тесты на сервере (1 час)**
  - Тестовый пользователь → "Мои отчеты"
  - Проверки:
    1. ✅ Бот запустился без ошибок
    2. ✅ Кнопка "Мои отчеты" работает
    3. ✅ TXT файл отправляется
    4. ✅ Меню с кнопками отображается
    5. ✅ Просмотр отчета работает
    6. ✅ Переименование работает
    7. ✅ Удаление работает
    8. ✅ Подтверждения запрашиваются
    9. ✅ MessageTracker очистка работает
    10. 🆕 ✅ Timeout срабатывает (ждать >5 минут)
    11. 🆕 ✅ Lock работает (быстрые повторные нажатия)
    12. 🆕 ✅ Size check работает (пользователь с >10MB)

- [ ] **Шаг 5.5: Мониторинг и готовность к rollback (1 час)**
  - Мониторинг логов первые 24 часа:
    ```bash
    docker logs voxpersona --tail 100 -f | grep -i "error\|exception\|report"
    ```
  - Триггеры для rollback:
    1. 🔴 Бот не запускается (>30 секунд downtime)
    2. 🔴 Exception в handle_my_reports_v2
    3. 🔴 Пользователи не могут получить список отчетов
    4. 🔴 Удаление отчетов некорректно
    5. 🟡 Timeout не работает
    6. 🟡 Lock не работает
  - Процедура rollback (5 минут):
    ```bash
    ssh root@172.237.73.207
    cd /home/voxpersona_user/VoxPersona
    ./rollback_my_reports_v2.sh
    # Проверка восстановления
    docker logs -f voxpersona --tail 50
    ```
  - Post-rollback анализ:
    ```bash
    docker logs voxpersona > rollback_error_$(date +%Y%m%d_%H%M%S).log
    # Анализ причины, исправление в dev, повторный деплой через 24ч
    ```

#### Входные данные:
- Все файлы после Фазы 4 (протестированные)
- SSH доступ к серверу 172.237.73.207
- Docker контейнер voxpersona

#### Выходные данные:
- Деплой на продакшене
- Backup файлы с timestamp
- Rollback скрипт (готов к использованию)
- Логи деплоя и мониторинга

#### Критерии завершения:
- ✅ Backup создан и проверен
- ✅ Rollback скрипт протестирован
- ✅ Файлы скопированы на сервер
- ✅ Python синтаксис валиден
- ✅ Бот перезапущен без ошибок
- ✅ Мониторинг первые 5 минут пройден
- ✅ 12 smoke тестов на сервере пройдены
- ✅ Готовность к rollback в любой момент
- ✅ Логи мониторятся 24 часа

---

## 3. ЗАВИСИМОСТИ

```
Фаза 1.5 (Критические доработки)
        ↓
Фаза 1 (Интеграция) ← БЛОКИРУЕТ Фазу 2
        ↓
Фаза 2 (Async унификация)
        ↓
Фаза 3 (Cleanup) ← БЛОКИРУЕТ Фазу 4
        ↓
Фаза 4 (Тестирование) ← БЛОКИРУЕТ Фазу 5
        ↓
Фаза 5 (Деплой)
```

**Критические зависимости:**
- Фаза 1.5 ОБЯЗАТЕЛЬНО перед Фазой 1 (без timeout/locks нельзя интегрировать)
- Фаза 1 ОБЯЗАТЕЛЬНО перед Фазой 2 (нужен импорт для async унификации)
- Фаза 3 ОБЯЗАТЕЛЬНО перед Фазой 4 (чистый код для тестирования)
- Фаза 4 ОБЯЗАТЕЛЬНО перед Фазой 5 (только протестированный код на продакшен)

---

## 4. ЧТО МОЖНО ЗАПУСКАТЬ ПАРАЛЛЕЛЬНО

### Возможности параллельной работы:

**НЕТ параллельных задач** - все фазы последовательны из-за зависимостей.

**Единственная возможность оптимизации:**
- Шаг 5.1 (Подготовка rollback плана) можно начать параллельно с Фазой 4 (Тестирование)
- Экономия: ~30 минут

**Почему нельзя распараллелить больше:**
- Фаза 1.5 изменяет handlers_my_reports_v2.py → блокирует Фазу 1
- Фаза 1 изменяет handlers.py → блокирует Фазу 2
- Фаза 2 изменяет handlers.py → блокирует Фазу 3
- Фаза 3 финализирует код → блокирует Фазу 4
- Фаза 4 валидирует код → блокирует Фазу 5

---

## 5. РИСКИ И МИТИГАЦИЯ

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Устаревший snapshot (>5 мин)** | Средняя | Среднее | Timeout механизм + автоинвалидация (Фаза 1.5) |
| **Одновременные операции (concurrent)** | Средняя | Высокое | asyncio.Lock для критических секций (Фаза 1.5) |
| **Список >10MB не отправляется** | Низкая | Среднее | Проверка размера + рекомендации (Фаза 1.5) |
| **Критичная ошибка на продакшене** | Низкая | Критично | Canary deployment + быстрый rollback 5 мин (Фаза 5) |
| **Баг при race condition** | Низкая | Среднее | Snapshot механизм + Lock (Фаза 1.5) |
| **Блокировка event loop** | Низкая | Высокое | Async унификация (Фаза 2) + asyncio.to_thread() |
| **Потеря данных при удалении** | Низкая | Высокое | Подтверждение + логирование (уже реализовано) |
| **Проблемы с интеграцией** | Средняя | Среднее | Поэтапная интеграция + smoke тесты (Фаза 1) |
| **Недостаточное тестирование** | Низкая | Высокое | 13 тест-кейсов + >80% coverage (Фаза 4) |
| **Деплой без возможности отката** | Низкая | Критично | Backup + rollback скрипт (Фаза 5) |

---

## 6. ВРЕМЕННАЯ ОЦЕНКА

| Фаза | Часы | Агент | Приоритет |
|------|------|-------|-----------|
| Фаза 1.5: Критические доработки | 2 | python-pro | 🔴 МАКСИМАЛЬНЫЙ |
| Фаза 1: Интеграция | 2 | python-pro | 🔴 ВЫСОКИЙ |
| Фаза 2: Async унификация | 1 | python-pro | 🔴 ВЫСОКИЙ |
| Фаза 3: Cleanup | 1 | python-pro | 🟡 СРЕДНИЙ |
| Фаза 4: Тестирование | 4 | test-automator | 🟡 ВЫСОКИЙ |
| Фаза 5: Деплой | 4 | devops-engineer | 🟢 СРЕДНИЙ |
| **ИТОГО** | **14** | | **1.75 рабочих дня** |

**Распределение нагрузки:**
- python-pro: 6 часов (43%)
- test-automator: 4 часа (29%)
- devops-engineer: 4 часа (28%)

---

## 7. ОСОБЫЕ ТРЕБОВАНИЯ

### Критические дополнения (от архитектора):

#### 1. Таймаут снимка - 5 минут ⏱️
- **Проблема:** Snapshot может устареть, если пользователь долго не вводит номер
- **Решение:** Автоматическая инвалидация snapshot через 5 минут
- **Реализация:** Фаза 1.5, Шаг 1.5.1
- **Где применять:** Все `*_input()` handlers

#### 2. asyncio.Lock для конкурентности 🔒
- **Проблема:** Одновременные операции могут вызвать race condition
- **Решение:** asyncio.Lock для защиты критических секций
- **Реализация:** Фаза 1.5, Шаг 1.5.2
- **Критические секции:**
  - `handle_report_view_input()` - отправка файла
  - `handle_report_rename_name_input()` - изменение index.json
  - `handle_report_delete_confirm()` - удаление файла

#### 3. Проверка размера файла - 10MB лимит 📦
- **Проблема:** Telegram имеет лимит на размер файлов
- **Решение:** Проверка размера TXT файла перед отправкой
- **Реализация:** Фаза 1.5, Шаг 1.5.3
- **Лимит:** 10MB (10 * 1024 * 1024 байт)
- **Действие:** Вывод рекомендаций пользователю + логирование

#### 4. Стратегия отката при деплое 🔄
- **Проблема:** Нет четкого плана отката при критических ошибках
- **Решение:** Canary deployment + детальный rollback план
- **Реализация:** Фаза 5, Шаги 5.1-5.5
- **Триггеры для rollback:**
  - Бот не запускается (>30 секунд downtime)
  - Exception в handle_my_reports_v2
  - Пользователи не могут получить список отчетов
  - Удаление отчетов работает некорректно
- **Время rollback:** 5 минут

### Технологический стек:
- **Python:** 3.11+
- **Async framework:** asyncio, Pyrogram
- **FSM:** user_states (config.py)
- **Concurrent control:** asyncio.Lock
- **File handling:** BytesIO
- **Storage:** MDStorageManager (md_storage.py)
- **Message tracking:** MessageTracker (message_tracker.py)

### Ограничения:
1. ⚠️ **Все изменения ТОЛЬКО ЛОКАЛЬНО** (не на сервере до Фазы 5)
2. ✅ **Интеграция с handlers_my_reports_v2.py** (825 строк готового кода)
3. ✅ **Использование существующих механизмов очистки** (MessageTracker)
4. ✅ **100% async реализация** (нет блокировки event loop)
5. ✅ **Безопасные callback_data** (индексы вместо file_path)
6. 🆕 **Timeout 5 минут** (автоинвалидация snapshot)
7. 🆕 **asyncio.Lock** (защита критических секций)
8. 🆕 **Size check 10MB** (проверка перед отправкой)
9. 🆕 **Rollback готовность** (backup + скрипт отката)

---

## 8. КРИТЕРИИ ПРИЕМКИ (CHECKLIST)

### Обязательные критерии (MUST HAVE):

#### Функциональные:
- [ ] ✅ При нажатии "Мои отчеты" отправляется TXT файл с полным списком
- [ ] ✅ TXT файл содержит пронумерованный список (1, 2, 3...)
- [ ] ✅ Меню содержит кнопки [Посмотреть] [Переименовать] [Удалить] [Назад]
- [ ] ✅ Пользователь вводит номер отчета для действий
- [ ] ✅ Перед КАЖДЫМ действием запрашивается подтверждение
- [ ] ✅ Просмотр: отправляется файл отчета
- [ ] ✅ Переименование: изменяется название в index.json
- [ ] ✅ Удаление: удаляется файл + запись из индекса
- [ ] ✅ MessageTracker автоочистка работает

#### Технические:
- [ ] ✅ 100% async реализация (нет блокировки event loop)
- [ ] 🆕 ✅ **Timeout для snapshot (5 минут)** - автоинвалидация устаревших списков
- [ ] 🆕 ✅ **Concurrent control (asyncio.Lock)** - защита от race condition
- [ ] 🆕 ✅ **Проверка размера файла (10MB)** - предотвращение отправки больших файлов

### Дополнительные критерии (SHOULD HAVE):

- [ ] ✅ Показываются ВСЕ отчеты (не ограничение 5-10)
- [ ] ✅ Snapshot механизм (нет race condition)
- [ ] ✅ Валидация номера отчета (1 до N)
- [ ] ✅ Обработка ошибок (файл не найден, неверный номер)
- [ ] ✅ Логирование всех действий
- [ ] ✅ BytesIO для оптимизации памяти
- [ ] ✅ Очистка состояния после действий
- [ ] 🆕 ✅ **Rollback стратегия** - быстрый откат при критических ошибках
- [ ] 🆕 ✅ **Canary deployment** - поэтапный деплой с мониторингом

### Критерии качества (NICE TO HAVE):

- [ ] Unit тесты (покрытие > 80%)
- [ ] Integration тесты
- [ ] 🆕 ✅ **Логирование размера файла** - для мониторинга нагрузки
- [ ] Документация для пользователей
- [ ] Счетчик попыток ввода (максимум 3)

---

## 9. КОММУНИКАЦИЯ И ОТЧЕТНОСТЬ

### Ежедневные stand-up (15 минут):
- **Время:** Начало каждой фазы
- **Формат:**
  - Что сделано вчера
  - Что планируется сегодня
  - Какие блокеры

### Отчеты по фазам:
- **После Фазы 1.5:** Отчет о критических доработках (timeout, locks, size check)
- **После Фазы 1:** Отчет об интеграции (импорты, routing, FSM)
- **После Фазы 2:** Отчет об async унификации
- **После Фазы 3:** Отчет о cleanup
- **После Фазы 4:** Test coverage report + список багов
- **После Фазы 5:** Deployment report + мониторинг логов

### Эскалация проблем:
- **Критичные баги:** Немедленно agent-organizer
- **Блокеры:** В течение 1 часа agent-organizer
- **Технические вопросы:** В slack канал команды

---

## 10. ПОСТ-ДЕПЛОЙ МОНИТОРИНГ

### Метрики для отслеживания:

#### Функциональные метрики:
- Количество вызовов "Мои отчеты" в день
- Количество View/Rename/Delete операций
- Количество успешных/неуспешных операций
- Среднее время выполнения операций

#### Технические метрики:
- 🆕 Количество timeout событий (>5 минут)
- 🆕 Количество concurrent операций (Lock срабатывания)
- 🆕 Размер отправляемых файлов (средний, максимальный)
- 🆕 Количество отказов из-за size check (>10MB)
- Количество ошибок в логах
- Event loop lag
- Memory usage
- CPU usage

#### Пользовательские метрики:
- Количество отмен операций
- Количество некорректных вводов
- Время от запроса до действия
- Обратная связь от пользователей

### Логирование:

```python
# Примеры логирования (уже реализовано в handlers_my_reports_v2.py)
logger.info(f"[MyReportsV2] User {chat_id} opened reports menu v2")
logger.info(f"[ReportView] User {chat_id} viewed report #{index}")
logger.info(f"[ReportRename] User {chat_id} renamed report #{index}")
logger.info(f"[ReportDelete] User {chat_id} deleted report #{index}")

# Новые логи (добавить в Фазе 1.5)
logger.info(f"Reports list size for user {chat_id}: {file_size_mb:.2f} MB ({len(reports)} reports)")
logger.warning(f"Reports list too large for user {chat_id}: {file_size_mb:.2f} MB")
logger.warning(f"Snapshot timeout for user {chat_id}: {elapsed_time} seconds")
logger.debug(f"Lock acquired for user {chat_id}: {operation}")
```

---

## 11. СЛЕДУЮЩИЕ ШАГИ ПОСЛЕ ЗАВЕРШЕНИЯ

### Краткосрочные (1 неделя):
1. Сбор обратной связи от пользователей
2. Анализ метрик (timeout, locks, size check)
3. Исправление minor багов (если найдены)
4. Обновление документации

### Среднесрочные (1 месяц):
1. Оптимизация производительности на основе метрик
2. Добавление счетчика попыток ввода (максимум 3)
3. Улучшение UX на основе обратной связи
4. Расширение тестового покрытия до >90%

### Долгосрочные (3 месяца):
1. Фильтры для списка отчетов (по дате, по названию)
2. Пагинация для очень больших списков (>100 отчетов)
3. Экспорт списка в разных форматах (CSV, JSON)
4. Статистика по отчетам (графики, тренды)

---

## 12. КОНТАКТНАЯ ИНФОРМАЦИЯ

### Команда:

**agent-organizer** (Координатор)
- Роль: Общая координация, контроль качества
- Ответственность: Все фазы

**python-pro** (Основной разработчик)
- Роль: Критические доработки, интеграция, async унификация
- Ответственность: Фазы 1.5, 1, 2, 3

**test-automator** (Тестирование)
- Роль: Unit, integration, edge cases тесты
- Ответственность: Фаза 4

**devops-engineer** (Деплой)
- Роль: Canary deployment, rollback, мониторинг
- Ответственность: Фаза 5

---

## 13. ВЕРСИОНИРОВАНИЕ

**Версия плана:** 2.1
**Дата создания:** 13.10.2025
**Последнее обновление:** 13.10.2025

**История изменений:**
- v2.1 (13.10.2025): Добавлена Фаза 1.5 (критические доработки безопасности)
- v2.0 (13.10.2025): Добавлены требования от архитектора (timeout, locks, size check, rollback)
- v1.0 (10.10.2025): Первая версия плана (без критических доработок)

---

## 14. ЗАКЛЮЧЕНИЕ

План реализации рефакторинга "Мои отчеты" разработан с учетом всех критических требований:

✅ **Критические доработки безопасности (Фаза 1.5):**
- Timeout 5 минут для snapshot
- asyncio.Lock для concurrent control
- Проверка размера файла 10MB
- Rollback стратегия

✅ **Поэтапная реализация:**
- Фаза 1.5: Критические доработки (2 часа)
- Фаза 1: Интеграция (2 часа)
- Фаза 2: Async унификация (1 час)
- Фаза 3: Cleanup (1 час)
- Фаза 4: Тестирование (4 часа)
- Фаза 5: Деплой с rollback (4 часа)

✅ **Команда из 3 агентов:**
- python-pro (10 часов) - основная разработка
- test-automator (4 часа) - тестирование
- devops-engineer (4 часа) - деплой

✅ **Оценка времени:** 14 часов (1.75 рабочих дня)

✅ **Риски минимизированы:** Через timeout, locks, size check, rollback стратегию

**Рекомендация:** 🚀 **НАЧАТЬ РЕАЛИЗАЦИЮ С ФАЗЫ 1.5 (КРИТИЧНЫЕ ДОРАБОТКИ)**

---

*Конец плана реализации*
