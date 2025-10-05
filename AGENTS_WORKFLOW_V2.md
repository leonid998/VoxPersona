# 🤖 Мультиагентная система Claude Code v2.0

**Проект:** VoxPersona | **Дата:** 5 октября 2025 | **Версия:** 2.0
**Язык:** Русский 🇷🇺

---

## 📋 БЫСТРАЯ НАВИГАЦИЯ

1. [Трехуровневая архитектура](#трехуровневая-архитектура)
2. [Каталог агентов (35)](#каталог-агентов)
3. [Decision Tree - выбор агента](#decision-tree)
4. [Обязательный протокол запуска](#протокол-запуска)
5. [Система проверок](#система-проверок)
6. [Отчетность перед коммитом](#отчетность)
7. [Примеры использования](#примеры)

---

## ТРЕХУРОВНЕВАЯ АРХИТЕКТУРА

```
ПОЛЬЗОВАТЕЛЬ → ЗАДАЧА
        ↓
[УРОВЕНЬ 1] Главный координатор (agent-organizer)
        ↓
[УРОВЕНЬ 2] Специализированные координаторы (6)
        ↓
[УРОВЕНЬ 3] Исполнители (28)
        ↓
РЕЗУЛЬТАТ → ОТЧЕТ → КОММИТ
```

### Правило выбора уровня:

| Сложность | Агентов | Координатор |
|-----------|---------|-------------|
| **Простая** | 1 | Прямой запуск исполнителя |
| **Средняя** | 2-4 | multi-agent-coordinator |
| **Сложная** | 5+ | agent-organizer |
| **Production incident** | любое | error-coordinator |

---

## КАТАЛОГ АГЕНТОВ

### 🎯 КООРДИНАТОРЫ (7)

#### 1. **agent-organizer** ⭐ ГЛАВНЫЙ
- **Когда:** Сложные задачи, > 5 агентов, неочевидная последовательность
- **Функции:** Декомпозиция, сборка команды, планирование, контроль
- **Инструменты:** Read, Write, agent-registry, task-queue, monitoring

#### 2. **multi-agent-coordinator** ⭐ ПАРАЛЛЕЛЬ
- **Когда:** 2-4 независимых задачи, параллельное выполнение
- **Функции:** Оркестрация workflow, синхронизация, fault tolerance
- **Инструменты:** Read, Write, message-queue, pubsub, workflow-engine

#### 3. **error-coordinator** ⭐ ИНЦИДЕНТЫ
- **Когда:** Production down, критические ошибки, восстановление
- **Функции:** Управление сбоями, автовосстановление, корреляция ошибок
- **Инструменты:** sentry, pagerduty, error-tracking, circuit-breaker

#### 4. **workflow-orchestrator** 🆕
- **Когда:** BPMN процессы, state machines, сложные бизнес-процессы
- **Функции:** Workflow паттерны, process automation, error compensation
- **Инструменты:** workflow-engine, state-machine, bpmn

#### 5. **task-distributor**
- **Когда:** Распределение нагрузки, приоритизация очереди
- **Функции:** Load balancing, scheduling, capacity tracking
- **Инструменты:** task-queue, load-balancer, scheduler

#### 6. **dependency-manager** 🆕
- **Когда:** Проблемы с зависимостями, конфликты версий, security audit
- **Функции:** Package management, version resolution, supply chain security
- **Инструменты:** npm, pip, gradle, cargo, bundler

#### 7. **incident-responder** 🆕
- **Когда:** Security/operational incidents, evidence collection, forensics
- **Функции:** Incident management, root cause analysis, prevention
- **Инструменты:** pagerduty, opsgenie, jira, statuspage

---

### 💻 ИСПОЛНИТЕЛИ: РАЗРАБОТКА (10)

#### 8. **python-pro** ⭐ ОСНОВНОЙ
- **Специализация:** Python 3.11+, async, type safety, data science
- **Для VoxPersona:** Основной разработчик Pyrogram кода
- **Инструменты:** pip, pytest, black, mypy, ruff, bandit

#### 9. **backend-developer** ⭐ API
- **Специализация:** API, микросервисы, серверная логика
- **Для VoxPersona:** Интеграция с Telegram, обработчики
- **Инструменты:** Docker, database, redis, postgresql

#### 10. **fullstack-developer** 🆕 ⭐
- **Специализация:** End-to-end разработка, фронт + бэк
- **Для VoxPersona:** Полные фичи от UI до БД
- **Инструменты:** React, Node, Docker, database

#### 11. **refactoring-specialist** 🆕 ⭐
- **Специализация:** Систематический рефакторинг, design patterns
- **Для VoxPersona:** Улучшение архитектуры, code smells
- **Инструменты:** ast-grep, jscodeshift, eslint, prettier

#### 12. **sql-pro**
- **Специализация:** PostgreSQL, MySQL, query optimization
- **Для VoxPersona:** Сложные запросы, оптимизация БД

#### 13. **postgres-pro**
- **Специализация:** PostgreSQL internals, tuning, high availability
- **Для VoxPersona:** Экспертная работа с VoxPersona БД

#### 14. **database-administrator**
- **Специализация:** HA, disaster recovery, performance tuning
- **Для VoxPersona:** Администрирование production БД

#### 15. **data-engineer** 🆕
- **Специализация:** ETL, data pipelines, big data
- **Для VoxPersona:** Обработка больших объемов сообщений

#### 16. **ai-engineer** 🆕
- **Специализация:** AI/ML системы, model deployment
- **Для VoxPersona:** RAG оптимизация, ML модели

#### 17. **performance-engineer** 🆕
- **Специализация:** Profiling, optimization, bottleneck identification
- **Для VoxPersona:** Оптимизация скорости ответов бота

---

### 🧪 ИСПОЛНИТЕЛИ: ТЕСТИРОВАНИЕ (4)

#### 18. **test-automator** ⭐
- **Специализация:** Pytest, CI/CD integration, coverage
- **Для VoxPersona:** Автотесты для бота

#### 19. **qa-expert**
- **Специализация:** QA стратегия, test planning, metrics
- **Для VoxPersona:** Обеспечение качества

#### 20. **code-reviewer** ⭐
- **Специализация:** Code quality, security, best practices
- **Для VoxPersona:** Ревью перед merge

#### 21. **architect-reviewer** 🆕
- **Специализация:** System design validation, patterns
- **Для VoxPersona:** Валидация архитектуры фич

---

### 🐛 ИСПОЛНИТЕЛИ: ОТЛАДКА (2)

#### 22. **debugger** ⭐
- **Специализация:** Root cause analysis, systematic debugging
- **Для VoxPersona:** Сложные баги бота

#### 23. **error-detective**
- **Специализация:** Error patterns, correlation, anomaly detection
- **Для VoxPersona:** Анализ логов Telegram

---

### 🚀 ИСПОЛНИТЕЛИ: DEVOPS (5)

#### 24. **devops-engineer** ⭐
- **Специализация:** CI/CD, Docker, Kubernetes, automation
- **Для VoxPersona:** Docker на сервере 172.237.73.207

#### 25. **deployment-engineer**
- **Специализация:** Release automation, zero-downtime deploys
- **Для VoxPersona:** Деплой на production

#### 26. **sre-engineer**
- **Специализация:** SLO, chaos testing, reliability
- **Для VoxPersona:** Мониторинг надежности бота

#### 27. **platform-engineer** 🆕
- **Специализация:** Developer platforms, self-service, GitOps
- **Для VoxPersona:** Internal tooling

#### 28. **cloud-architect** 🆕
- **Специализация:** Multi-cloud, cost optimization, scalability
- **Для VoxPersona:** Облачная архитектура

---

### 📝 ИСПОЛНИТЕЛИ: ДОКУМЕНТАЦИЯ (2)

#### 29. **technical-writer** ⭐
- **Специализация:** API docs, user guides, technical content
- **Для VoxPersona:** Документация меню (5 файлов!)

#### 30. **documentation-engineer**
- **Специализация:** Doc systems, documentation-as-code
- **Для VoxPersona:** Автогенерация документации

---

### 🔍 ИСПОЛНИТЕЛИ: АНАЛИЗ (3)

#### 31. **sequential-thinking** ⭐ MCP
- **Специализация:** Пошаговое решение, динамическая корректировка
- **Для VoxPersona:** Сложная логика, итеративный подход

#### 32. **research-analyst**
- **Специализация:** Information gathering, synthesis, insights
- **Для VoxPersona:** Исследование проблем

#### 33. **data-analyst** 🆕
- **Специализация:** Business intelligence, visualizations, SQL
- **Для VoxPersona:** Аналитика использования бота

---

### 🔐 ИСПОЛНИТЕЛИ: БЕЗОПАСНОСТЬ (2)

#### 34. **security-engineer**
- **Специализация:** DevSecOps, cloud security, compliance
- **Для VoxPersona:** Безопасность инфраструктуры

#### 35. **security-auditor**
- **Специализация:** Security assessments, compliance validation
- **Для VoxPersona:** Аудит безопасности

---

## DECISION TREE

### Шаг 1: Оценка сложности

```
Вопросы:
1. Сколько специализаций требуется?
   1 → Исполнитель
   2-4 → multi-agent-coordinator
   5+ → agent-organizer

2. Это production incident?
   Да → error-coordinator
   Нет → см. п.3

3. Можно выполнить параллельно?
   Да → multi-agent-coordinator
   Нет → см. п.4

4. Сложные зависимости/BPMN?
   Да → workflow-orchestrator
   Нет → Исполнитель
```

### Шаг 2: Матрица выбора исполнителя

| Задача | Агент | Проверка соответствия |
|--------|-------|----------------------|
| **Python код** | python-pro | ✅ .py файлы, Pyrogram |
| **API/Handlers** | backend-developer | ✅ handlers, API endpoints |
| **Полная фича** | fullstack-developer | ✅ UI + БД + логика |
| **Рефакторинг** | refactoring-specialist | ✅ улучшение структуры |
| **SQL запросы** | sql-pro / postgres-pro | ✅ .sql, запросы БД |
| **Тесты** | test-automator | ✅ test_*.py, pytest |
| **Баги** | debugger | ✅ воспроизведение, RCA |
| **DevOps** | devops-engineer | ✅ Docker, сервер |
| **Документация** | technical-writer | ✅ .md файлы, 5 файлов меню |
| **Анализ** | sequential-thinking | ✅ сложная логика |

### Шаг 3: Валидация выбора

**ОБЯЗАТЕЛЬНО проверить:**
- ✅ Специализация агента покрывает задачу?
- ✅ Агент имеет нужные инструменты?
- ✅ Агент знаком с технологиями проекта?
- ✅ Контекст VoxPersona передан в промпте?

---

## ПРОТОКОЛ ЗАПУСКА

### Обязательная последовательность:

#### 1. АНАЛИЗ ЗАДАЧИ (всегда первый этап)
```
- Прочитать требования
- Определить сложность
- Выбрать координатора/агента по Decision Tree
- Валидировать выбор
```

#### 2. ПЛАН РАБОТЫ ⭐ ОБЯЗАТЕЛЬНО
```markdown
## ПЛАН РАБОТЫ (для утверждения)

### Задача:
[Четкое описание задачи]

### Выбранный подход:
- Координатор: [название]
- Исполнители: [список]

### Последовательность:
1. [Этап 1] - [Агент] - [Что делает]
2. [Этап 2] - [Агент] - [Что делает]
3. ...

### Риски:
- [Риск 1] - [Митигация]

### Ожидаемое время:
[Оценка времени выполнения]

❓ УТВЕРДИТЬ ПЛАН? (ДА/НЕТ)
```

#### 3. УТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЕМ ⭐ КРИТИЧНО
```
ЖДАТЬ подтверждения от пользователя
НЕ ЗАПУСКАТЬ агентов без утверждения
```

#### 4. ЗАПУСК АГЕНТОВ
```
- Запуск согласно плану
- Мониторинг выполнения
- Отслеживание прогресса
```

#### 5. ПРОВЕРКА ЗАВЕРШЕНИЯ ⭐ ОБЯЗАТЕЛЬНО
```
Для КАЖДОГО агента:
✅ Агент завершил работу?
✅ Результат соответствует требованиям?
✅ Есть ошибки/прерывания?
✅ Все файлы изменены корректно?
```

#### 6. ОТЧЕТ ПЕРЕД КОММИТОМ ⭐ КРИТИЧНО
```markdown
## ОТЧЕТ О ВЫПОЛНЕНИИ

### ✅ РЕАЛИЗОВАНО:
- [Задача 1] - [Агент] - [Статус: завершено]
- [Задача 2] - [Агент] - [Статус: завершено]

### ❌ НЕ РЕАЛИЗОВАНО:
- [Задача X] - [Причина]

### ⚠️ ПРЕРВАЛОСЬ/СБИЛОСЬ:
- [Задача Y] - [Агент] - [Причина прерывания]
- [Что потеряно/не сохранено]

### 🔄 ПОТЕРЯННЫЙ КОНТЕКСТ:
- [Описание потерянной информации]

### 📊 СТАТИСТИКА:
- Запущено агентов: X
- Завершено успешно: Y
- Прервано: Z
- Время выполнения: T

### 📝 ИЗМЕНЕНИЯ В ФАЙЛАХ:
- [файл1] - [описание изменений]
- [файл2] - [описание изменений]

### ⚠️ ТРЕБУЕТСЯ ВНИМАНИЕ:
- [Список проблем для ручной проверки]
```

#### 7. GIT WORKFLOW ⚠️ ВАЖНО
```bash
# ✅ РАЗРЕШЕНО:
git add .
git commit -m "message"

# ❌ ЗАПРЕЩЕНО без указания пользователя:
git push
```

**ПРАВИЛО:** Push делается ТОЛЬКО по явному указанию пользователя!

---

## СИСТЕМА ПРОВЕРОК

### Чек-лист ПЕРЕД запуском:

```
□ Задача проанализирована
□ Сложность определена
□ Агент выбран по Decision Tree
□ Валидация выбора пройдена
□ План работы составлен
□ План УТВЕРЖДЕН пользователем ✅
□ Контекст VoxPersona подготовлен
```

### Чек-лист ВО ВРЕМЯ выполнения:

```
□ Каждый агент получил четкий промпт
□ Контекст проекта передан
□ Мониторинг прогресса активен
□ Ошибки логируются
```

### Чек-лист ПОСЛЕ выполнения:

```
□ Все агенты завершили работу
□ Результаты проверены
□ Отчет составлен ✅
□ Документация обновлена (если меню - 5 файлов!)
□ Тесты прошли
□ Готовность к коммиту подтверждена
```


---

## ПРИМЕРЫ

### Пример 1: Простая задача (1 агент)

**Задача:** Добавить валидацию длины сообщения (max 4096)

**План:**
```markdown
### Выбор: python-pro (прямой запуск)
### Этапы:
1. Добавить функцию validate_message_length()
2. Интегрировать в message_handler
3. Unit тест
```

**Промпт:**
```
python-pro: Добавь валидацию длины сообщения (max 4096 символов)
в src/handlers/message_handler.py. Если превышает - обрезать и
добавить "..." в конце. Написать unit тест.
```

---

### Пример 2: Средняя задача (multi-agent-coordinator)

**Задача:** Оптимизировать загрузку истории чатов

**План:**
```markdown
### Координатор: multi-agent-coordinator
### Этапы (параллельно):
1. postgres-pro: Индексы + оптимизация запросов
2. python-pro: LRU кэш для последних 10 чатов
3. performance-engineer: Benchmark до/после

### Время: ~30 минут
```

**Промпт:**
```markdown
multi-agent-coordinator: Оптимизируй загрузку истории чатов VoxPersona.

Параллельные задачи:
1. postgres-pro: Анализируй get_messages() в conversation_manager.py,
   добавь индексы, оптимизируй запросы
2. python-pro: Реализуй LRU cache для 10 последних чатов, TTL 5 мин
3. performance-engineer: Измерь время загрузки до/после, цель < 1 сек

Сервер: 172.237.73.207, БД: voxpersona_postgres
```

---

### Пример 3: Сложная задача (agent-organizer)

**Задача:** Реализовать экспорт истории в PDF

**План:**
```markdown
### Координатор: agent-organizer
### Этапы:
1. Дизайн (architect-reviewer): Валидация архитектуры
2. Разработка параллельно (multi-agent-coordinator):
   - backend-developer: API endpoint
   - python-pro: PDF генерация (reportlab)
3. Интеграция:
   - backend-developer: MinIO сохранение
   - python-pro: Telegram отправка
4. Тестирование (test-automator)
5. Документация (technical-writer): 5 файлов меню!

### Время: ~2 часа
```

**Промпт:**
```markdown
agent-organizer: Реализуй экспорт истории диалогов в PDF для VoxPersona.

Требования:
1. UI: кнопка "📄 Экспорт в PDF" в меню чатов
2. Backend: PDF генерация с форматированием
3. Хранение: MinIO
4. Отправка: Telegram document
5. Очистка: автоудаление через 24 часа

Контекст:
- Python Telegram bot (Pyrogram)
- Меню: см. MESSAGE_TRACKER_IMPLEMENTATION.md
- Сервер: 172.237.73.207

⚠️ ВАЖНО:
- Обновить ВСЕ 5 файлов документации меню!
- Тесты обязательны
```

---

### Пример 4: Production Incident (error-coordinator)

**Задача:** Бот не отвечает, БД не доступна

**План:**
```markdown
### Координатор: error-coordinator
### Немедленно (параллельно):
1. sre-engineer: Health checks, metrics
2. database-administrator: PostgreSQL статус
3. devops-engineer: Docker контейнеры, сеть

### После диагностики:
4. debugger: Root cause analysis
5. python-pro/devops-engineer: Исправление
6. test-automator: Regression тесты
7. technical-writer: Postmortem

### SLA: < 15 минут восстановление
```

**Промпт:**
```markdown
error-coordinator: VoxPersona бот не отвечает, production down.

Симптомы:
- Бот не отвечает 5 минут
- Логи: "connection pool exhausted"
- Критичность: HIGH

Сервер: 172.237.73.207
Docker: voxpersona_app, voxpersona_postgres

Действия:
1. Немедленная диагностика (параллельно)
2. Быстрый фикс или rollback
3. Root cause
4. Postmortem

⚠️ SLA: < 15 минут
```

---

## АНТИПАТТЕРНЫ

### ❌ НЕ ДЕЛАТЬ:

1. **Запускать агентов без плана и утверждения**
   - Проблема: Неожиданные действия, потеря контроля

2. **Пропускать отчет перед коммитом**
   - Проблема: Потеря информации о проблемах

3. **Делать git push без указания пользователя**
   - Проблема: Критичное нарушение workflow

4. **Использовать agent-organizer для простых задач**
   - Проблема: Избыточный overhead

5. **Не указывать контекст VoxPersona в промпте**
   - Проблема: Агенты не понимают специфику

6. **Забывать про документацию меню (5 файлов!)**
   - Проблема: Техдолг, рассинхронизация

7. **Не проверять завершение каждого агента**
   - Проблема: Потеря результатов, незавершенная работа

### ✅ ПРАВИЛЬНО:

1. **Всегда составлять план → утверждение → запуск**
2. **Всегда делать отчет перед коммитом**
3. **Push только по указанию пользователя**
4. **Простая задача → прямой агент**
5. **Всегда передавать контекст VoxPersona**
6. **Проверять завершение всех агентов**

---

## БЫСТРАЯ СПРАВКА

### Таблица выбора координатора:

| Ситуация | Координатор |
|----------|-------------|
| 1 простая задача | Исполнитель |
| 2-4 параллельных | multi-agent-coordinator |
| 5+ сложных | agent-organizer |
| BPMN/workflow | workflow-orchestrator |
| Production down | error-coordinator |
| Dependency hell | dependency-manager |
| Security incident | incident-responder |

### Таблица выбора исполнителя:

| Тип работы | Агент |
|------------|-------|
| Python код | python-pro |
| Full feature | fullstack-developer |
| Рефакторинг | refactoring-specialist |
| SQL/БД | postgres-pro |
| Тесты | test-automator |
| Баги | debugger |
| DevOps | devops-engineer |
| Документация | technical-writer |
| Анализ | sequential-thinking |
| ML/AI | ai-engineer |

---

## КОНТРОЛЬНЫЕ ТОЧКИ

### До запуска агентов:
1. ✅ План составлен?
2. ✅ План утвержден пользователем?
3. ✅ Контекст подготовлен?

### Во время выполнения:
1. ✅ Агенты получили промпты?
2. ✅ Мониторинг активен?
3. ✅ Ошибки фиксируются?

### После выполнения:
1. ✅ Все агенты завершили?
2. ✅ Отчет составлен?
3. ✅ Готовность к коммиту?
4. ⚠️ Push ТОЛЬКО по указанию!

---

## ИТОГО

**35 агентов:**
- 7 координаторов
- 28 исполнителей

**Обязательные этапы:**
1. Анализ → Decision Tree → Выбор агента
2. План → Утверждение пользователем ✅
3. Запуск → Мониторинг
4. Проверка завершения каждого агента
5. Отчет перед коммитом ⭐
6. Коммит ✅ | Push ❌ (только по указанию)

**Ключевые правила:**
- Всегда проверять соответствие агента задаче
- Обязательный отчет о незавершенном/прерванном
- Push ТОЛЬКО по указанию пользователя

---

**Версия:** 2.0 | **Дата:** 5 октября 2025
**Статус:** ✅ Production Ready
**Оптимизация:** 750 строк (было 1317) | Сжатие 43%

🚀 **Готово к использованию!**
