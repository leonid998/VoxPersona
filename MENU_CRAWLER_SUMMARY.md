# 📋 MENU CRAWLER - КРАТКИЙ SUMMARY

**Status**: Comprehensive research completed
**Date**: November 4, 2025

---

## ⚡ QUICK FACTS

**Menu Crawler это NOT restaurant menu parser!**

- **Назначение**: Автоматизированное UI-тестирование навигации Telegram бота
- **Версия**: 1.0 (завершена 22 октября 2025)
- **Локация**: `C:\Users\l0934\Projects\VoxPersona\menu_crawler\`
- **Язык**: Python 3.10.11
- **Тип проекта**: Regression testing tool для VoxPersona

---

## 📁 СТРУКТУРА (5 главных компонентов)

```
menu_crawler/
├── src/
│   ├── main.py                     # Оркестрирует весь цикл
│   ├── navigator.py                # BFS обход меню (главный класс)
│   ├── coverage_verifier.py        # Проверка покрытия меню
│   ├── report_builder.py           # Генерация отчетов
│   └── utils/                      # Checkpoint, cleanup, logging
├── config/
│   ├── menu_graph.json             # Ожидаемая структура (104 nodes, 123 edges)
│   └── crawler_config.json         # Whitelist/blacklist действий
├── scripts/                        # Подготовка (session, data gen)
└── LAUNCH_INSTRUCTIONS.md          # Полная инструкция запуска
```

---

## 🎯 ЧТО ДЕЛАЕТ

```
1. Инициализирует Pyrogram клиент (user session)
   ↓
2. Запускает BFS обход всех 104 узлов меню
   ↓
3. Собирает метрики: посещенные узлы, ошибки, depth
   ↓
4. Генерирует отчеты: JSON + Markdown
   ↓
5. Очищает тестовые данные из БД (cleanup)
```

---

## 🔑 КЛЮЧЕВЫЕ КЛАССЫ

| Класс | Файл | Функция |
|-------|------|---------|
| `MenuNavigator` | navigator.py | BFS обход меню + Pyrogram |
| `CoverageVerifier` | coverage_verifier.py | Верификация покрытия |
| `ReportBuilder` | report_builder.py | JSON + Markdown отчеты |
| `CheckpointManager` | utils/checkpoint_manager.py | Сохранение прогресса |
| `CircuitBreaker` | utils/circuit_breaker.py | Rate limit protection |

---

## 📊 ГРАФ МЕНЮ

**Статистика (из menu_graph.json):**

| Метрика | Значение |
|---------|----------|
| Узлов (nodes) | 104 |
| Связей (edges) | 123 |
| Типы узлов | menu (22), action (66), view (16) |
| Глубина вложенности | 0-7 уровней |
| Динамические узлы | 11 (параметризованные) |
| FSM узлы | 25 (требуют ввода) |
| Условные связи | 62 (для super_admin только) |

**Безопасность:**
- ✅ **Safe**: menu_*, chat_*, send_*, access_*, view||*, select||*
- ❌ **Forbidden**: delete||all, reset_database, dangerous_*

---

## 🚀 ГЛАВНЫЙ WORKFLOW

### Локально (подготовка)

```bash
# 1. Создать Pyrogram session (интерактивно)
python menu_crawler/scripts/create_user_session.py
# → Вводим номер телефона + код подтверждения
# → Создается: menu_crawler/menu_crawler_session.session

# 2. Загрузить на сервер
scp menu_crawler/menu_crawler_session.session root@172.237.73.207:/home/voxpersona_user/VoxPersona/menu_crawler/

# 3. Убедиться TEST_USER_ID совпадает
grep TEST_USER_ID .env  # Должно быть 155894817
```

### На сервере (запуск)

```bash
cd /home/voxpersona_user/VoxPersona
python3 -m menu_crawler.src.main

# ИЛИ альтернативно:
cd menu_crawler/src
python3 navigator.py
```

### Результаты

```
menu_crawler/
├── progress.json                    # Checkpoint (обновляется каждые 10 узлов)
├── reports/
│   ├── report_20251022_163000.json  # JSON метрики
│   └── report_20251022_163000.md    # Markdown отчет
└── actual_callbacks_analysis.json   # Анализ реальных callbacks
```

---

## 🔗 ИНТЕГРАЦИЯ

### С ботом

```
Menu Crawler (user account)
    ↓ (sends callback_query)
Telegram Bot API
    ↓ (processes in handlers)
src/bot.py, src/handlers.py
    ↓ (returns updated menu)
Menu Crawler (receives message)
```

### С БД

```
Menu Crawler (TEST_USER_ID = 155894817)
    ↓ (generates test data)
PostgreSQL
    ↓ (cleanup after test)
DELETE FROM transcription WHERE user_telegram_id = 155894817
```

### С файлами

```
menu_crawler/config/
  ├── menu_graph.json      (ожидаемая структура)
  └── crawler_config.json  (whitelist/blacklist)
          ↓ (processed by)
menu_crawler/src/navigator.py
          ↓ (outputs)
menu_crawler/reports/
  ├── report_*.json
  └── report_*.md
```

---

## ⚙️ КОНФИГУРАЦИЯ

### crawler_config.json (Whitelist/Blacklist)

```json
{
  "safe_navigation": ["menu_", "chat_", "access_", "view||", "select||"],
  "forbidden_actions": ["delete||all", "reset_database"],
  "throttle_delay": 2.0,           // Пауза между запросами
  "callback_timeout": 10            // Timeout на ответ
}
```

**Логика:**
1. Если в safe_navigation → ✅ разрешено
2. Если в forbidden_actions → ❌ запрещено
3. Если начинается с safe prefix → ✅ разрешено
4. Иначе → ❌ запрещено

### menu_graph.json (Ожидаемая структура)

```json
{
  "nodes": {
    "menu_main": {"type": "menu", "depth": 0},
    "chat_actions||{id}": {"type": "action", "depth": 4, "dynamic": true}
  },
  "edges": [
    {"from": "menu_main", "to": "menu_chats", "callback_data": "menu_chats", "button_text": "💬 Чаты"}
  ]
}
```

---

## 📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### Coverage report

```
Status: PASS
Coverage: 100.0%
  - Total expected: 104 nodes
  - Total visited: 104 nodes
  - Missing: 0

UX Metrics:
  - Max depth: 4 clicks
  - Deep nodes (>4): 0
  - Nodes without back button: 2
```

### Logs (structured JSON)

```json
{"event": "crawler_started", "level": "info", "timestamp": "2025-10-22T16:20:00Z"}
{"event": "node_visited", "level": "info", "from": "menu_main", "to": "menu_chats"}
{"event": "checkpoint_saved", "level": "info", "visited_edges": 50}
{"event": "crawler_finished", "level": "info", "visited_edges": 123}
```

---

## 🛡️ БЕЗОПАСНОСТЬ

### Test isolation

```env
TEST_USER_ID=155894817  # Отделение тестовых данных
```

### Cleanup

```python
# После каждого запуска:
DELETE FROM transcription WHERE user_telegram_id = 155894817;
DELETE FROM reports WHERE user_telegram_id = 155894817;
```

### Rate limit protection

```python
# Circuit Breaker pattern:
CLOSED → normal
OPEN → wait (too many errors)
HALF_OPEN → test recovery

# Throttling:
await asyncio.sleep(2.0)  # Between callbacks
```

---

## 🔧 ТОЧКИ ДЛЯ ИЗМЕНЕНИЯ

| Задача | Файл | Действие |
|--------|------|---------|
| Добавить узел меню | COMPLETE_MENU_TREE.md | Добавить в markdown |
| | `build_menu_graph_v3.py` | Запустить генерацию |
| Изменить safe/forbidden | crawler_config.json | Edit JSON |
| Изменить throttle/timeout | crawler_config.json | Edit JSON |
| Добавить FSM узел | `fsm_handler.py` | Добавить обработчик |
| Изменить cleanup логику | `cleanup.py` | Edit функцию |

---

## 📊 ФАЙЛЫ ПО ФУНКЦИЯМ

### Основной код

- **navigator.py** (400+ строк): BFS обход, Pyrogram интеграция
- **main.py** (100 строк): Оркестрация workflow
- **coverage_verifier.py** (150 строк): Верификация покрытия
- **report_builder.py** (200+ строк): Генерация отчетов

### Утилиты

- **checkpoint_manager.py**: Сохранение/восстановление прогресса
- **circuit_breaker.py**: Rate limit protection
- **cleanup.py**: Удаление тестовых данных
- **fsm_handler.py**: Обработка FSM узлов
- **logging_config.py**: Structured JSON logging

### Скрипты

- **create_user_session.py**: Создание Pyrogram session
- **build_menu_graph_v3.py**: Генерация меню графа
- **generate_test_data.py**: Тестовые данные в БД
- **set_test_user_super_admin.py**: Admin прав для тестового юзера

---

## 🎓 ПРИМЕРЫ

### Запуск на сервере

```bash
ssh root@172.237.73.207
cd /home/voxpersona_user/VoxPersona
python3 -m menu_crawler.src.main

# Ожидаемый вывод: 5-10 минут обхода
# Результат: 123 edge visited, 104 nodes covered
```

### Проверка результата

```bash
cat menu_crawler/reports/report_*.json | jq '.coverage'

# {
#   "total_expected": 104,
#   "total_visited": 104,
#   "coverage_percent": 100.0
# }
```

### Проверка cleanup

```bash
# На DB:
SELECT COUNT(*) FROM transcription WHERE user_telegram_id = 155894817;
# Ожидаемо: 0 (все удалено)
```

---

## ❓ FAQ

**Q: Зачем Menu Crawler если есть другие тесты?**  
A: Это end-to-end UI тест, проверяет что ВСЕ кнопки и меню работают в реальном боте.

**Q: Почему нужна Pyrogram session?**  
A: Чтобы эмулировать реального пользователя (отправлять callback_query от user account).

**Q: Как часто нужно запускать?**  
A: После каждого обновления меню/навигации (обычно раз в неделю).

**Q: Что если Menu Crawler упадет?**  
A: Есть checkpoint система - можно восстановиться с того же места.

**Q: Какие данные остаются в БД?**  
A: Никакие! Все тестовые данные автоматически удаляются после теста.

---

## 🎯 ИТОГ

| Вопрос | Ответ |
|--------|-------|
| Что это? | UI-тестер Telegram бота (не парсер ресторанов) |
| Что проверяет? | Навигацию: 104 узла, 123 связи, 0-7 глубина |
| Где запускается? | На сервере (Linux) через Python 3 |
| Как часто? | Раз в неделю после обновлений меню |
| Что выдает? | JSON + Markdown отчеты с метриками |
| Безопасность? | Whitelist/blacklist, test isolation, cleanup |
| Скорость? | 5-10 минут на полный обход |
| Статус? | ✅ Готов к использованию |

---

**MENU CRAWLER = Инструмент регрессионного тестирования UI Telegram бота**

*Research date: November 4, 2025*  
*Files analyzed: 20+*  
*Code lines: 2000+*  
*Thoroughness: VERY THOROUGH* ✅
