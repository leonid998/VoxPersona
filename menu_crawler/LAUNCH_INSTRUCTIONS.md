# 🚀 Инструкция по запуску Menu Crawler

**Дата создания:** 22 октября 2025
**Версия:** 1.0
**Статус:** Готов к запуску после создания Pyrogram сессии

---

## 📋 Pre-flight Checklist

Перед запуском Menu Crawler убедитесь, что выполнены следующие условия:

### ✅ Локально (C:\Users\l0934\Projects\VoxPersona)

- [x] menu_graph.json создан (101 callback_data, 104 nodes, 123 edges)
- [x] crawler_config.json настроен (21 safe action, 22 forbidden action)
- [x] Код загружен на GitHub (коммит b86fcfc)
- [ ] **Pyrogram User Session создана** (menu_crawler_session.session) ← **КРИТИЧНО!**

### ✅ На сервере (172.237.73.207)

- [x] Код обновлён через GitHub Actions (коммит b86fcfc)
- [x] TEST_USER_ID=155894817 в .env
- [x] API_ID и API_HASH в .env
- [x] structlog==24.1.0 установлен
- [x] Все 14 файлов menu_crawler присутствуют
- [ ] **Pyrogram User Session загружена на сервер** ← **КРИТИЧНО!**

---

## 🔐 Шаг 1: Создание Pyrogram User Session (ЛОКАЛЬНО)

### 1.1. Дождитесь окончания FLOOD_WAIT

**Если получили ошибку FLOOD_WAIT:**
```
Telegram says: [420 FLOOD_WAIT_X] - A wait of 3378 seconds is required
```

**Действие:** Подождите указанное время (обычно ~60 минут)

---

### 1.2. Запустите скрипт создания сессии

Откройте **PowerShell** на вашем компьютере:

```powershell
cd C:\Users\l0934\Projects\VoxPersona
python menu_crawler\scripts\create_user_session.py
```

**Ожидаемый вывод:**
```
============================================================
🔐 СОЗДАНИЕ PYROGRAM USER SESSION
============================================================

✅ API_ID и API_HASH загружены из .env
📁 Проект: C:\Users\l0934\Projects\VoxPersona
📂 Сессия будет создана в: C:\Users\l0934\Projects\VoxPersona\menu_crawler

📱 Номер телефона: +79272491236

🔐 Pyrogram отправит код подтверждения в Telegram
⏳ Подождите SMS или сообщение в Telegram...

Welcome to Pyrogram (version 2.0.106)
The confirmation code has been sent via Telegram app
Enter confirmation code: _
```

### 1.3. Введите код подтверждения

1. Откройте Telegram на телефоне +79272491236
2. Найдите сообщение с кодом (5-6 цифр)
3. Введите код в PowerShell

**Успешный результат:**
```
============================================================
✅ СЕССИЯ УСПЕШНО СОЗДАНА!
============================================================
👤 Пользователь: [Имя] [Фамилия]
🆔 Username: @AsgoldPrime
🔢 Telegram ID: 155894817
📞 Телефон: +79272491236

📁 Файл сессии: C:\Users\l0934\Projects\VoxPersona\menu_crawler\menu_crawler_session.session
```

---

## 📤 Шаг 2: Загрузка сессии на сервер

### 2.1. Загрузить файл сессии через scp

```bash
scp C:\Users\l0934\Projects\VoxPersona\menu_crawler\menu_crawler_session.session root@172.237.73.207:/home/voxpersona_user/VoxPersona/menu_crawler/
```

**Ожидаемый вывод:**
```
menu_crawler_session.session    100%  1024KB   1.0MB/s   00:01
```

### 2.2. Проверить наличие сессии на сервере

```bash
ssh root@172.237.73.207 "ls -lh /home/voxpersona_user/VoxPersona/menu_crawler/*.session"
```

**Ожидаемый вывод:**
```
-rw-r--r-- 1 root root 1.0M Oct 22 16:20 menu_crawler_session.session
```

---

## 🚀 Шаг 3: Запуск Menu Crawler на сервере

### 3.1. SSH на сервер

```bash
ssh root@172.237.73.207
```

### 3.2. Перейти в директорию проекта

```bash
cd /home/voxpersona_user/VoxPersona
```

### 3.3. Запустить Menu Crawler

```bash
python3 -m menu_crawler.src.navigator
```

**ИЛИ (альтернативный способ):**

```bash
cd menu_crawler/src
python3 navigator.py
```

---

## 📊 Шаг 4: Мониторинг выполнения

### 4.1. Ожидаемый вывод в консоли

```
🔐 Инициализация Menu Navigator...
✅ menu_graph.json загружен (104 nodes, 123 edges)
✅ crawler_config.json загружен
✅ Pyrogram клиент инициализирован

🚀 Начало обхода меню...
⏳ Обработка узла: menu_main
✅ Посещено: menu_main → menu_chats
⏳ Обработка узла: menu_chats
✅ Посещено: menu_chats → chat_actions
...
[~5-10 минут обхода]
...
✅ Обход завершен. Посещено рёбер: 123
```

### 4.2. Логи (structured JSON)

Логи будут выводиться в формате JSON:

```json
{"event": "crawler_started", "level": "info", "timestamp": "2025-10-22T16:20:00Z"}
{"event": "node_visited", "level": "info", "from": "menu_main", "to": "menu_chats", "timestamp": "..."}
{"event": "checkpoint_saved", "level": "info", "visited_edges": 50, "timestamp": "..."}
{"event": "crawler_finished", "level": "info", "visited_edges": 123, "timestamp": "..."}
```

### 4.3. Checkpoint файл (прогресс)

Автоматически создаётся файл прогресса:

```bash
ls -lh menu_crawler/progress.json
```

Содержит:
```json
{
  "timestamp": "2025-10-22T16:25:00",
  "visited_edges": [
    ["menu_main", "menu_chats"],
    ["menu_chats", "chat_actions"]
  ],
  "queue": [
    ["menu_main", "menu_system"]
  ]
}
```

---

## 📁 Шаг 5: Проверка отчётов

### 5.1. JSON отчёт

```bash
cd /home/voxpersona_user/VoxPersona
cat menu_crawler/reports/report_*.json | jq '.'
```

**Ожидаемая структура:**
```json
{
  "timestamp": "2025-10-22T16:30:00",
  "session_id": "test_20251022_163000",
  "status": "PASS",
  "coverage": {
    "total_expected": 104,
    "total_visited": 104,
    "coverage_percent": 100.0
  },
  "issues": {
    "critical": [],
    "warnings": [],
    "info": []
  },
  "ux_metrics": {
    "max_depth": 4,
    "deep_nodes_count": 0,
    "nodes_without_back_count": 2
  }
}
```

### 5.2. Markdown отчёт

```bash
cat menu_crawler/reports/report_*.md
```

**Формат отчёта:**
```markdown
# 📊 Отчёт Menu Crawler

**Дата:** 22 октября 2025, 16:30
**Статус:** ✅ PASS
**Session ID:** test_20251022_163000

## 📈 Покрытие меню

| Метрика | Значение |
|---------|----------|
| Ожидалось узлов | 104 |
| Посещено узлов | 104 |
| Покрытие | 100.0% |

## 📐 UX Метрики

- **Максимальная глубина:** 4 клика
- **Узлов глубже 4 кликов:** 0
- **Узлов без кнопки "Назад":** 2
```

---

## 🧪 Шаг 6: Тестирование cleanup БД

### 6.1. Подключиться к PostgreSQL

```bash
docker exec -it voxpersona_postgres psql -U voxpersona_user -d bot_db
```

### 6.2. Проверить отсутствие тестовых данных

```sql
-- Проверка по TEST_USER_ID
SELECT COUNT(*) FROM transcription WHERE user_telegram_id = 155894817;
```

**Ожидаемый результат:** `0` (все тестовые данные удалены)

### 6.3. Выход из psql

```sql
\q
```

---

## ⚠️ Troubleshooting

### Ошибка: "menu_crawler_session.session not found"

**Причина:** Файл сессии не загружен на сервер

**Решение:**
```bash
scp C:\Users\l0934\Projects\VoxPersona\menu_crawler\menu_crawler_session.session root@172.237.73.207:/home/voxpersona_user/VoxPersona/menu_crawler/
```

---

### Ошибка: "FLOOD_WAIT_X"

**Причина:** Telegram API rate limit

**Решение:** Подождите указанное время (обычно 30-60 минут)

---

### Ошибка: "Unauthorized"

**Причина:** Сессия устарела или невалидна

**Решение:**
1. Удалите старую сессию: `rm menu_crawler/menu_crawler_session.session`
2. Создайте новую сессию (Шаг 1)
3. Загрузите на сервер (Шаг 2)

---

### Ошибка: "TEST_USER_ID protection triggered"

**Причина:** TEST_USER_ID в .env не совпадает с Telegram ID в сессии

**Решение:**
```bash
# Проверить TEST_USER_ID в .env
grep TEST_USER_ID .env

# Должно быть: TEST_USER_ID=155894817
```

---

## 📞 Контакты

**Разработчик:** Claude Code + Agent Team
**Дата:** 22 октября 2025
**Проект:** VoxPersona Menu Crawler MVP
