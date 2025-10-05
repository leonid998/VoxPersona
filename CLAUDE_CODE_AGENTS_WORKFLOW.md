# 🤖 Мультиагентная архитектура Claude Code для VoxPersona

**Дата создания:** 5 октября 2025
**Версия:** 1.0
**Проект:** VoxPersona Telegram Bot
**Назначение:** Инструкция по организации работы с субагентами Claude Code

---

## 📋 ОГЛАВЛЕНИЕ

1. [Введение](#введение)
2. [Анализ доступных субагентов](#анализ-доступных-субагентов)
3. [Субагенты для VoxPersona](#субагенты-для-voxpersona)
4. [Трехуровневая модель организации](#трехуровневая-модель-организации)
5. [Workflow-паттерны](#workflow-паттерны)
6. [Практические примеры](#практические-примеры)
7. [Инструкция для Claude Code](#инструкция-для-claude-code)

---

## ВВЕДЕНИЕ

### Проблема
VoxPersona — это сложный Python-проект с:
- Telegram ботом на Pyrogram
- RAG-системой с векторным поиском
- Мультичат функционалом
- PostgreSQL базой данных
- MinIO хранилищем
- Docker инфраструктурой на удаленном сервере

Классический подход "один Claude на всё" приводит к:
- ❌ Потере фокуса на задаче
- ❌ Неоптимальному использованию специализации
- ❌ Медленному выполнению параллельных задач
- ❌ Сложности отладки при ошибках

### Решение
**Мультиагентная архитектура** с использованием специализированных субагентов Claude Code:
- ✅ Разделение ответственности
- ✅ Параллельное выполнение независимых задач
- ✅ Использование экспертизы специализированных агентов
- ✅ Четкая координация и управление

---

## АНАЛИЗ ДОСТУПНЫХ СУБАГЕНТОВ

### Классификация по функциям

#### 🎯 КООРДИНАТОРЫ (Организация работы)

**1. agent-organizer** ⭐ КЛЮЧЕВОЙ
- Специализация: сборка команды агентов, декомпозиция задач, оптимизация ресурсов
- Использование: главный координатор для сложных задач
- Инструменты: Read, Write, agent-registry, task-queue, monitoring

**2. multi-agent-coordinator** ⭐ КЛЮЧЕВОЙ
- Специализация: оркестрация workflow, межагентная коммуникация, fault tolerance
- Использование: управление параллельными агентами
- Инструменты: Read, Write, message-queue, pubsub, workflow-engine

**3. task-distributor**
- Специализация: распределение нагрузки, приоритизация, балансировка
- Использование: управление очередью задач
- Инструменты: Read, Write, task-queue, load-balancer, scheduler

**4. error-coordinator**
- Специализация: распределенная обработка ошибок, восстановление, resilience
- Использование: управление сбоями в мультиагентной системе
- Инструменты: Read, Write, MultiEdit, Bash, sentry, pagerduty, error-tracking, circuit-breaker

#### 💻 ИСПОЛНИТЕЛИ: Разработка

**5. python-pro** ⭐ КЛЮЧЕВОЙ
- Специализация: Python 3.11+, type safety, async, data science, web frameworks
- Использование: основной разработчик Python кода
- Инструменты: Read, Write, MultiEdit, Bash, pip, pytest, black, mypy, poetry, ruff, bandit

**6. backend-developer** ⭐ ВАЖНЫЙ
- Специализация: API, микросервисы, production
- Использование: разработка серверной части
- Инструменты: Read, Write, MultiEdit, Bash, Docker, database, redis, postgresql

**7. sql-pro**
- Специализация: PostgreSQL, MySQL, SQL Server, Oracle, оптимизация запросов
- Использование: работа с базами данных
- Инструменты: Read, Write, MultiEdit, Bash, psql, mysql, sqlite3, explain, analyze

**8. database-administrator**
- Специализация: high-availability, performance tuning, disaster recovery
- Использование: администрирование БД
- Инструменты: Read, Write, MultiEdit, Bash, psql, mysql, mongosh, redis-cli, pg_dump

**9. postgres-pro**
- Специализация: PostgreSQL internals, оптимизация, высокая доступность
- Использование: экспертная работа с PostgreSQL
- Инструменты: psql, pg_dump, pgbench, pg_stat_statements, pgbadger

#### 🧪 ИСПОЛНИТЕЛИ: Тестирование и качество

**10. test-automator** ⭐ ВАЖНЫЙ
- Специализация: test frameworks, CI/CD интеграция, comprehensive coverage
- Использование: создание и запуск тестов
- Инструменты: Read, Write, selenium, cypress, playwright, pytest, jest, appium, k6, jenkins

**11. qa-expert**
- Специализация: QA стратегия, test planning, quality metrics
- Использование: обеспечение качества
- Инструменты: Read, Grep, selenium, cypress, playwright, postman, jira, testrail, browserstack

**12. code-reviewer** ⭐ ВАЖНЫЙ
- Специализация: code quality, security, best practices
- Использование: ревью кода
- Инструменты: Read, Grep, Glob, git, eslint, sonarqube, semgrep

#### 🐛 ИСПОЛНИТЕЛИ: Отладка

**13. debugger** ⭐ ВАЖНЫЙ
- Специализация: root cause analysis, систематическое решение проблем
- Использование: сложная отладка
- Инструменты: Read, Grep, Glob, gdb, lldb, chrome-devtools, vscode-debugger, strace, tcpdump

**14. error-detective**
- Специализация: паттерны ошибок, корреляция, anomaly detection
- Использование: анализ распределенных ошибок
- Инструменты: Read, Grep, Glob, elasticsearch, datadog, sentry, loggly, splunk

#### 🚀 ИСПОЛНИТЕЛИ: DevOps и инфраструктура

**15. devops-engineer** ⭐ КЛЮЧЕВОЙ
- Специализация: CI/CD, контейнеризация, облачные платформы
- Использование: DevOps автоматизация
- Инструменты: Read, Write, MultiEdit, Bash, docker, kubernetes, terraform, ansible, prometheus, jenkins

**16. sre-engineer**
- Специализация: SLO, chaos testing, toil reduction
- Использование: надежность систем
- Инструменты: Read, Write, MultiEdit, Bash, prometheus, grafana, terraform, kubectl, python, go, pagerduty

**17. deployment-engineer**
- Специализация: CI/CD pipelines, release automation, zero-downtime
- Использование: развертывание
- Инструменты: Read, Write, MultiEdit, Bash, ansible, jenkins, gitlab-ci, github-actions, argocd, spinnaker

**18. docker-specialist** (кастомный - создать при необходимости)
- Специализация: Docker, docker-compose, multi-stage builds
- Использование: контейнеризация

#### 🏗️ ИСПОЛНИТЕЛИ: Архитектура

**19. architect-reviewer**
- Специализация: system design validation, architectural patterns
- Использование: валидация архитектуры
- Инструменты: Read, plantuml, structurizr, archunit, sonarqube

**20. api-designer**
- Специализация: REST, GraphQL API design
- Использование: проектирование API
- Инструменты: Read, Write, MultiEdit, Bash, openapi-generator, graphql-codegen, postman, swagger-ui

#### 📝 ИСПОЛНИТЕЛИ: Документация

**21. technical-writer** ⭐ ВАЖНЫЙ
- Специализация: API docs, user guides, technical content
- Использование: создание документации
- Инструменты: markdown, asciidoc, confluence, gitbook, mkdocs

**22. documentation-engineer**
- Специализация: doc systems, documentation-as-code
- Использование: системы документации
- Инструменты: Read, Write, MultiEdit, Bash, markdown, asciidoc, sphinx, mkdocs, docusaurus, swagger

#### 🔍 ИСПОЛНИТЕЛИ: Исследование

**23. search-specialist**
- Специализация: information retrieval, query optimization
- Использование: поиск информации в коде
- Инструменты: Read, Write, WebSearch, Grep, elasticsearch, google-scholar

**24. research-analyst**
- Специализация: information gathering, synthesis, insights
- Использование: исследование и анализ
- Инструменты: Read, Write, WebSearch, WebFetch, Grep

**25. data-researcher**
- Специализация: data mining, statistical analysis, pattern recognition
- Использование: исследование данных
- Инструменты: Read, Write, sql, python, pandas, WebSearch, api-tools

#### 🔐 ИСПОЛНИТЕЛИ: Безопасность

**26. security-engineer**
- Специализация: DevSecOps, cloud security, compliance
- Использование: безопасность инфраструктуры
- Инструменты: Read, Write, MultiEdit, Bash, nmap, metasploit, burp, vault, trivy, falco, terraform

**27. security-auditor**
- Специализация: security assessments, compliance validation
- Использование: аудит безопасности
- Инструменты: Read, Grep, nessus, qualys, openvas, prowler, scout, suite, compliance, checker

#### 🧠 ИСПОЛНИТЕЛИ: Специальные

**28. sequential-thinking** ⭐ КЛЮЧЕВОЙ
- Специализация: пошаговое решение сложных задач с динамической корректировкой
- Использование: сложная логика, требующая итеративного подхода
- Доступен через: MCP server (уже установлен)

**29. context-manager**
- Специализация: state management, синхронизация между агентами
- Использование: управление контекстом в мультиагентных системах
- Инструменты: Read, Write, redis, elasticsearch, vector-db

**30. performance-monitor**
- Специализация: метрики, аномалии, observability
- Использование: мониторинг производительности агентов
- Инструменты: Read, Write, MultiEdit, Bash, prometheus, grafana, datadog, elasticsearch, statsd

---

## СУБАГЕНТЫ ДЛЯ VOXPERSONA

### Отобранные агенты по категориям

#### 🎯 УРОВЕНЬ 1: ГЛАВНЫЙ КООРДИНАТОР
1. **agent-organizer** - декомпозиция сложных задач, сборка команды агентов

#### 🎯 УРОВЕНЬ 2: СПЕЦИАЛИЗИРОВАННЫЕ КООРДИНАТОРЫ
2. **multi-agent-coordinator** - оркестрация параллельных задач
3. **error-coordinator** - управление ошибками и восстановлением

#### 💻 УРОВЕНЬ 3: ИСПОЛНИТЕЛИ

**Разработка Python:**
4. **python-pro** - основной разработчик Python кода
5. **backend-developer** - API и серверная логика

**База данных:**
6. **postgres-pro** - экспертная работа с PostgreSQL
7. **database-administrator** - администрирование БД

**Тестирование:**
8. **test-automator** - автоматизация тестов (pytest)
9. **code-reviewer** - ревью кода и качество

**Отладка:**
10. **debugger** - сложная отладка
11. **error-detective** - анализ ошибок

**DevOps:**
12. **devops-engineer** - CI/CD, Docker, мониторинг
13. **deployment-engineer** - развертывание на сервер

**Документация:**
14. **technical-writer** - создание документации
15. **documentation-engineer** - системы документации

**Анализ:**
16. **sequential-thinking** - сложные логические задачи (MCP)
17. **research-analyst** - исследование и анализ

**Безопасность:**
18. **security-engineer** - безопасность инфраструктуры

---

## ТРЕХУРОВНЕВАЯ МОДЕЛЬ ОРГАНИЗАЦИИ

### Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     ПОЛЬЗОВАТЕЛЬ (User)                         │
│                    Постановка задачи                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  УРОВЕНЬ 1: ГЛАВНЫЙ КООРДИНАТОР                 │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              🎯 agent-organizer                           │ │
│  │                                                           │ │
│  │  • Анализирует сложную задачу                            │ │
│  │  • Декомпозирует на подзадачи                            │ │
│  │  • Определяет необходимых агентов                        │ │
│  │  • Планирует последовательность выполнения               │ │
│  │  • Контролирует общий прогресс                           │ │
│  │  • Собирает финальный результат                          │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              УРОВЕНЬ 2: СПЕЦИАЛИЗИРОВАННЫЕ КООРДИНАТОРЫ         │
│                                                                 │
│  ┌─────────────────────────┐   ┌──────────────────────────────┐│
│  │ 🔄 multi-agent-         │   │ 🔧 error-coordinator         ││
│  │    coordinator          │   │                              ││
│  │                         │   │                              ││
│  │ • Параллельное          │   │ • Мониторинг ошибок          ││
│  │   выполнение            │   │ • Fault tolerance            ││
│  │ • Синхронизация         │   │ • Автовосстановление         ││
│  │ • Управление очередями  │   │ • Cascade prevention         ││
│  └─────────────────────────┘   └──────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ↓                   ↓
┌──────────────────────────────────────────────────────────────────┐
│                 УРОВЕНЬ 3: АГЕНТЫ-ИСПОЛНИТЕЛИ                    │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ 💻 РАЗРАБОТКА   │  │ 🧪 ТЕСТИРОВАНИЕ │  │ 🚀 DEVOPS       │ │
│  │                 │  │                 │  │                 │ │
│  │ python-pro      │  │ test-automator  │  │ devops-engineer │ │
│  │ backend-dev     │  │ code-reviewer   │  │ deployment-eng  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ 🗄️ БАЗА ДАННЫХ  │  │ 🐛 ОТЛАДКА      │  │ 📝 ДОКУМЕНТАЦИЯ │ │
│  │                 │  │                 │  │                 │ │
│  │ postgres-pro    │  │ debugger        │  │ technical-writer│ │
│  │ database-admin  │  │ error-detective │  │ doc-engineer    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ 🔐 БЕЗОПАСНОСТЬ │  │ 🧠 АНАЛИЗ       │  │ 🔍 ИССЛЕДОВАНИЕ │ │
│  │                 │  │                 │  │                 │ │
│  │ security-eng    │  │ sequential-     │  │ research-analyst│ │
│  │                 │  │ thinking (MCP)  │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Принципы взаимодействия

#### 1. Иерархическая координация
```
agent-organizer
    ├─> multi-agent-coordinator
    │       ├─> python-pro + backend-developer (параллельно)
    │       └─> test-automator (после разработки)
    │
    └─> error-coordinator
            └─> debugger (при ошибках)
```

#### 2. Параллельное выполнение
```python
# Пример: одновременная работа нескольких агентов
multi-agent-coordinator:
    - python-pro: рефакторинг handlers.py
    - backend-developer: оптимизация API
    - postgres-pro: оптимизация запросов БД
    # Все выполняются параллельно
```

#### 3. Sequential dependency
```python
# Пример: последовательная зависимость
agent-organizer:
    1. python-pro: написать новую функцию
    2. test-automator: создать тесты
    3. code-reviewer: провести ревью
    4. deployment-engineer: развернуть на сервер
```

#### 4. Error handling cascade
```python
# Пример: каскадная обработка ошибок
error-coordinator:
    1. Обнаружена ошибка при деплое
    2. ↓ Запускает debugger
    3. ↓ Если нужен код-анализ → запускает error-detective
    4. ↓ Если нужно исправление → делегирует python-pro
    5. ↓ После исправления → запускает test-automator
```

### Правила распределения

#### Когда использовать agent-organizer:
- ✅ Задача требует > 3 разных специализаций
- ✅ Неочевидна последовательность выполнения
- ✅ Высокая сложность и риск ошибок
- ✅ Требуется оптимизация ресурсов

#### Когда использовать multi-agent-coordinator:
- ✅ Несколько независимых подзадач можно выполнить параллельно
- ✅ Требуется синхронизация результатов
- ✅ Управление message queue между агентами

#### Когда использовать error-coordinator:
- ✅ Распределенная система с множеством точек отказа
- ✅ Требуется автоматическое восстановление
- ✅ Нужна корреляция ошибок между компонентами

#### Когда использовать специализированных исполнителей:
- ✅ Задача четко вписывается в одну специализацию
- ✅ Не требуется сложная координация
- ✅ Простая линейная последовательность

---

## WORKFLOW-ПАТТЕРНЫ

### Паттерн 1: Новая фича (Feature Development)

**Задача:** Добавить функцию экспорта истории чатов в PDF

```
agent-organizer:
    Анализ → Планирование → Сборка команды
    ↓
    multi-agent-coordinator:
        ┌─> python-pro: реализация export_to_pdf()
        ├─> backend-developer: интеграция с handlers
        └─> postgres-pro: оптимизация запроса истории
        # Параллельное выполнение
    ↓
    test-automator:
        - Написать unit тесты
        - Написать интеграционные тесты
    ↓
    code-reviewer:
        - Проверка качества кода
        - Security check
    ↓
    documentation-engineer:
        - Обновить документацию API
        - Добавить примеры использования
    ↓
    deployment-engineer:
        - Развернуть на тестовый сервер
        - Валидация
        - Развернуть на production
```

### Паттерн 2: Отладка бага (Bug Fix)

**Задача:** Исправить ошибку "memory leak в long-running conversations"

```
error-coordinator:
    Обнаружение → Анализ → Восстановление
    ↓
    debugger:
        - Воспроизведение бага
        - Анализ памяти
        - Идентификация root cause
    ↓
    error-detective:
        - Корреляция с логами
        - Анализ паттернов ошибок
        - Поиск похожих багов
    ↓
    python-pro:
        - Исправление кода
        - Оптимизация управления памятью
    ↓
    test-automator:
        - Regression тесты
        - Memory leak тесты
    ↓
    devops-engineer:
        - Мониторинг памяти в production
        - Настройка алертов
```

### Паттерн 3: Рефакторинг (Code Refactoring)

**Задача:** Рефакторинг message_tracker.py для улучшения производительности

```
agent-organizer:
    ↓
    sequential-thinking (MCP):
        - Анализ текущей архитектуры
        - Определение bottlenecks
        - Планирование рефакторинга
    ↓
    code-reviewer:
        - Анализ code smells
        - Определение patterns для применения
    ↓
    multi-agent-coordinator:
        ┌─> python-pro: рефакторинг кода
        └─> test-automator: обновление тестов
        # Параллельно
    ↓
    performance-monitor:
        - Benchmark до/после
        - Анализ улучшений
    ↓
    technical-writer:
        - Обновление документации
```

### Паттерн 4: Database Migration

**Задача:** Миграция с JSON файлов на PostgreSQL

```
agent-organizer:
    ↓
    architect-reviewer:
        - Валидация плана миграции
        - Оценка рисков
    ↓
    multi-agent-coordinator:
        ┌─> postgres-pro: дизайн схемы БД
        ├─> database-administrator: настройка репликации
        └─> backend-developer: адаптер для совместимости
        # Параллельно
    ↓
    python-pro:
        - Реализация миграционных скриптов
        - Data validation
    ↓
    test-automator:
        - Тесты миграции
        - Rollback тесты
    ↓
    deployment-engineer:
        - Staged rollout
        - Мониторинг
```

### Паттерн 5: DevOps Pipeline

**Задача:** Настроить CI/CD для автоматического деплоя

```
agent-organizer:
    ↓
    devops-engineer:
        - Дизайн CI/CD pipeline
        - Выбор инструментов (GitHub Actions)
    ↓
    multi-agent-coordinator:
        ┌─> deployment-engineer: конфигурация деплоя
        ├─> test-automator: интеграция тестов в CI
        ├─> security-engineer: security scanning
        └─> sre-engineer: мониторинг и алерты
        # Параллельно
    ↓
    documentation-engineer:
        - Документация pipeline
        - Runbooks
```

### Паттерн 6: Исследование проблемы (Investigation)

**Задача:** Понять почему RAG поиск медленный на больших документах

```
agent-organizer:
    ↓
    research-analyst:
        - Анализ текущей реализации
        - Поиск best practices
        - Сравнение подходов
    ↓
    sequential-thinking (MCP):
        - Гипотезы о причинах
        - Итеративная проверка гипотез
    ↓
    multi-agent-coordinator:
        ┌─> performance-engineer: профилирование кода
        ├─> database-administrator: анализ запросов
        └─> data-researcher: анализ векторных индексов
        # Параллельно
    ↓
    technical-writer:
        - Отчет с findings
        - Рекомендации
```

---

## ПРАКТИЧЕСКИЕ ПРИМЕРЫ

### Пример 1: Простая задача (один исполнитель)

**Задача:** Добавить валидацию email в user input

```markdown
## Решение без координатора (прямое использование)

Использую: python-pro

Task:
- Добавить функцию validate_email() в validators.py
- Использовать regex для валидации
- Добавить в обработчик user input
- Написать unit тест

Результат: быстрое решение без overhead координации
```

### Пример 2: Средняя задача (2-3 агента с координатором)

**Задача:** Оптимизировать загрузку истории чатов

```markdown
## Решение с multi-agent-coordinator

Промпт для multi-agent-coordinator:
"Оптимизируй загрузку истории чатов в VoxPersona. Текущая проблема: загрузка 100+ сообщений занимает > 5 секунд."

multi-agent-coordinator запускает параллельно:
1. postgres-pro:
   - Анализ запросов
   - Создание индексов
   - Query optimization

2. python-pro:
   - Кэширование результатов
   - Lazy loading реализация

3. performance-monitor:
   - Benchmark до/после
   - Метрики производительности

Результат: координация параллельной работы, быстрое выполнение
```

### Пример 3: Сложная задача (5+ агентов, требуется организация)

**Задача:** Реализовать систему автоматической генерации аналитических отчетов из диалогов

```markdown
## Решение с agent-organizer

Промпт для agent-organizer:
"Реализуй систему автоматической генерации аналитических отчетов из диалогов пользователей VoxPersona.
Требования:
- Анализ тональности
- Выделение ключевых тем
- Генерация PDF отчета
- Автоматическая отправка раз в неделю
- Хранение в MinIO"

agent-organizer декомпозирует:

Этап 1 (Дизайн):
- architect-reviewer: валидация архитектуры
- api-designer: дизайн API для отчетов

Этап 2 (Разработка) - Параллельно через multi-agent-coordinator:
- python-pro: sentiment analysis модуль
- backend-developer: API endpoints
- postgres-pro: агрегирующие запросы

Этап 3 (Интеграция):
- python-pro: PDF generation (reportlab)
- backend-developer: MinIO интеграция
- devops-engineer: cron job настройка

Этап 4 (Тестирование):
- test-automator: unit + integration тесты
- qa-expert: тест-план и валидация

Этап 5 (Документация и деплой):
- technical-writer: документация API
- deployment-engineer: деплой на production
- sre-engineer: мониторинг

Результат: полная оркестрация сложного проекта
```

### Пример 4: Кризисная ситуация (error handling)

**Задача:** Production down - Telegram бот не отвечает

```markdown
## Решение с error-coordinator

Промпт для error-coordinator:
"VoxPersona бот в production перестал отвечать. Последние логи показывают ошибки подключения к PostgreSQL."

error-coordinator координирует:

Немедленно (Параллельно):
1. sre-engineer:
   - Проверка health checks
   - Анализ метрик Prometheus
   - Rollback если нужно

2. database-administrator:
   - Проверка статуса PostgreSQL
   - Анализ connection pool
   - Проверка репликации

3. devops-engineer:
   - Проверка Docker контейнеров
   - Логи инфраструктуры
   - Сетевая connectivity

После диагностики:
4. debugger:
   - Root cause analysis
   - Воспроизведение проблемы

Исправление:
5. python-pro:
   - Патч connection retry logic
   - Graceful degradation

Постморtem:
6. technical-writer:
   - Incident report
   - Lessons learned

Результат: быстрое восстановление с полной координацией
```

---

## ИНСТРУКЦИЯ ДЛЯ CLAUDE CODE

### 📋 Общие принципы

#### 1. Оценка сложности задачи

Перед началом работы определи уровень сложности:

```
ПРОСТАЯ (1 агент):
- Четкая задача в одной области
- Не требует координации
- Пример: "исправь опечатку в docstring"
→ Используй специализированного агента напрямую

СРЕДНЯЯ (2-4 агента):
- Требует 2-4 специализации
- Возможно параллельное выполнение
- Пример: "оптимизируй медленный API endpoint"
→ Используй multi-agent-coordinator

СЛОЖНАЯ (5+ агентов):
- Множество специализаций
- Сложные зависимости
- Пример: "реализуй новую подсистему"
→ Используй agent-organizer
```

#### 2. Выбор координатора

```python
if задача_сложная and агентов > 5:
    используй: agent-organizer

elif задача_параллельная and агентов 2-4:
    используй: multi-agent-coordinator

elif задача_с_ошибками or production_incident:
    используй: error-coordinator

else:
    используй: специализированного агента напрямую
```

#### 3. Формулирование промптов

**Для координаторов:**
```markdown
Формат промпта для agent-organizer:

"[Описание задачи]

Проект: VoxPersona Telegram Bot (Python, Pyrogram, PostgreSQL)
Требования:
- [требование 1]
- [требование 2]

Контекст:
- [важный контекст о проекте]

Ожидаемый результат:
- [что должно быть на выходе]"
```

**Для исполнителей:**
```markdown
Формат промпта для специализированного агента:

"[Конкретная задача]

Файлы: [список файлов]
Текущая проблема: [описание]

Требования:
- [технические требования]

⚠️ ВАЖНО:
- [специфичные для VoxPersona ограничения]
- Обязательно обновить документацию в [файлы]
"
```

### 📋 Workflow для разных сценариев

#### Сценарий A: Разработка новой функции

```markdown
1. Анализ требований:
   Агент: research-analyst
   Задача: "Изучи текущую архитектуру [модуль] и предложи подход к [фича]"

2. Декомпозиция (если сложная):
   Агент: agent-organizer
   Задача: "Разбей реализацию [фича] на независимые задачи для VoxPersona"

3. Разработка (параллельно):
   Координатор: multi-agent-coordinator
   Агенты:
   - python-pro: основная логика
   - backend-developer: API интеграция
   - postgres-pro: изменения БД (если нужно)

4. Тестирование:
   Агент: test-automator
   Задача: "Создай тесты для [фича], покрытие > 80%"

5. Ревью:
   Агент: code-reviewer
   Задача: "Ревью кода [фича], проверь security и best practices"

6. Документация:
   Агент: technical-writer
   Задача: "Обнови документацию для [фича]"
   ⚠️ ВАЖНО: Обновить ВСЕ 5 файлов документации меню!

7. Деплой:
   Агент: deployment-engineer
   Задача: "Разверни [фича] на сервер 172.237.73.207"
```

#### Сценарий B: Исправление бага

```markdown
1. Репродукция:
   Агент: debugger
   Задача: "Воспроизведи баг [описание] в VoxPersona"

2. Анализ (если сложный):
   Агент: error-detective
   Задача: "Проанализируй логи и найди корреляции с [баг]"

3. Исправление:
   Агент: python-pro
   Задача: "Исправь [баг] в [файл]"

4. Regression тесты:
   Агент: test-automator
   Задача: "Добавь regression тест для [баг]"

5. Проверка не сломалось:
   Агент: qa-expert
   Задача: "Валидируй что исправление [баг] не сломало [связанную функциональность]"
```

#### Сценарий C: Оптимизация производительности

```markdown
1. Профилирование:
   Координатор: multi-agent-coordinator
   Агенты параллельно:
   - performance-monitor: метрики системы
   - postgres-pro: анализ медленных запросов
   - python-pro: профилирование кода

2. Анализ:
   Агент: sequential-thinking (MCP)
   Задача: "Проанализируй bottlenecks в [компонент] VoxPersona"

3. Оптимизация:
   Координатор: multi-agent-coordinator
   Агенты параллельно:
   - python-pro: оптимизация кода
   - postgres-pro: оптимизация запросов
   - devops-engineer: оптимизация инфраструктуры

4. Бенчмаркинг:
   Агент: performance-monitor
   Задача: "Сравни производительность до/после оптимизации"
```

#### Сценарий D: Production Incident

```markdown
1. Координация восстановления:
   Координатор: error-coordinator

2. Диагностика (параллельно):
   Агенты:
   - sre-engineer: проверка метрик и health
   - database-administrator: состояние БД
   - devops-engineer: инфраструктура Docker/сервер

3. Быстрый фикс:
   Агент: по результатам диагностики (python-pro/devops-engineer/etc)

4. Rollback если нужно:
   Агент: deployment-engineer

5. Root Cause:
   Агент: debugger

6. Постморtem:
   Агент: technical-writer
```

### 📋 Шаблоны промптов

#### Шаблон 1: Запуск agent-organizer

```markdown
Используя agent-organizer, выполни следующую задачу для проекта VoxPersona:

Задача: [детальное описание]

Контекст проекта:
- Технологии: Python 3.11, Pyrogram, PostgreSQL, Docker
- Архитектура: [релевантная информация]
- Текущее состояние: [что уже есть]

Требования:
1. [требование 1]
2. [требование 2]
3. [требование 3]

Ограничения:
- [ограничение 1]
- [ограничение 2]

⚠️ ВАЖНО:
- При изменении меню бота - обновить ВСЕ 5 файлов документации
- При изменении истории чатов - обновить CONVERSATION_HISTORY_FLOW_REPORT.md
- Все изменения через SSH на сервере 172.237.73.207
- Тесты должны пройти перед деплоем

Ожидаемый результат:
[что должно быть на выходе]
```

#### Шаблон 2: Запуск multi-agent-coordinator

```markdown
Используя multi-agent-coordinator, координируй следующие параллельные задачи для VoxPersona:

Задачи для параллельного выполнения:

1. [Агент 1]: python-pro
   Задача: [описание]
   Файлы: [список]

2. [Агент 2]: postgres-pro
   Задача: [описание]
   База: [детали]

3. [Агент 3]: test-automator
   Задача: [описание]
   Coverage: > 80%

Синхронизация:
- [как агенты должны координироваться]

После завершения всех:
- [финальный шаг]
```

#### Шаблон 3: Запуск специализированного агента

```markdown
Используя [имя агента], выполни:

Задача: [конкретная задача]

Файлы: [список файлов]
Контекст: [минимально необходимый контекст]

Требования:
- [требование 1]
- [требование 2]

⚠️ ВАЖНО:
- [специфичные для VoxPersona моменты]

Результат:
- [что ожидается]
```

### 📋 Чеклист перед запуском агентов

#### Перед любой задачей:
- [ ] Определил сложность (простая/средняя/сложная)
- [ ] Выбрал правильного координатора или агента
- [ ] Проверил доступность нужных файлов
- [ ] Понял зависимости между подзадачами

#### Для VoxPersona специфично:
- [ ] Если меню - готов обновить 5 файлов документации
- [ ] Если история чатов - готов обновить CONVERSATION_HISTORY_FLOW_REPORT.md
- [ ] Если БД - проверил доступ к PostgreSQL на сервере
- [ ] Если деплой - проверил SSH доступ к 172.237.73.207
- [ ] Если тесты - указал где их запускать (локально/сервер)

#### После выполнения:
- [ ] Все агенты завершили работу
- [ ] Результаты синхронизированы (если параллельные задачи)
- [ ] Тесты прошли
- [ ] Документация обновлена
- [ ] Изменения задеплоены (если требуется)

### 📋 Антипаттерны (чего НЕ делать)

#### ❌ Плохо:
```markdown
"Сделай всё сам без агентов"
→ Проблема: теряется специализация, медленно, высокий риск ошибок

"Запусти всех агентов сразу на всё"
→ Проблема: избыточная координация, waste ресурсов

"Используй agent-organizer для простой задачи"
→ Проблема: overhead координации не оправдан

"Не указывай контекст VoxPersona в промпте"
→ Проблема: агенты не понимают специфику проекта

"Забыть про документацию"
→ Проблема: код без документации = технический долг
```

#### ✅ Хорошо:
```markdown
"Простая задача → специализированный агент напрямую"
"Средняя задача с параллелизмом → multi-agent-coordinator"
"Сложная задача → agent-organizer для планирования"
"Всегда указывай контекст VoxPersona"
"Всегда обновляй документацию"
"Используй error-coordinator для production incidents"
```

### 📋 Примеры реальных команд

#### Пример 1: Простая задача
```markdown
Используя python-pro, добавь валидацию длины названия чата (max 50 символов) в conversation_handlers.py, функция handle_rename_chat_request().

Требования:
- Проверка перед сохранением
- Сообщение пользователю если превышает
- Обрезка с "..." если нужно

Файл: /home/voxpersona_user/VoxPersona/src/conversation_handlers.py (на сервере 172.237.73.207)
```

#### Пример 2: Средняя задача
```markdown
Используя multi-agent-coordinator, оптимизируй загрузку истории диалогов в VoxPersona.

Параллельные задачи:

1. postgres-pro:
   Проанализируй и оптимизируй запросы в conversation_manager.py:
   - get_messages()
   - load_conversation()
   Добавь индексы если нужно.

2. python-pro:
   Реализуй кэширование в chat_history.py:
   - LRU cache для последних 10 чатов
   - TTL 5 минут

3. performance-monitor:
   Измерь время загрузки до/после оптимизации
   Цель: < 1 секунда для 100 сообщений

Сервер: 172.237.73.207
БД: PostgreSQL в Docker (voxpersona_postgres)
```

#### Пример 3: Сложная задача
```markdown
Используя agent-organizer, реализуй систему экспорта истории диалогов в PDF для VoxPersona.

Требования:
1. UI: кнопка "📄 Экспорт в PDF" в меню чатов
2. Backend: генерация PDF с форматированием (reportlab)
3. Хранение: сохранение в MinIO
4. Отправка: через Telegram document
5. Очистка: автоудаление PDF через 24 часа

Контекст:
- Проект: Python Telegram bot на Pyrogram
- Текущее меню: см. MESSAGE_TRACKER_IMPLEMENTATION.md
- История: см. CONVERSATION_HISTORY_FLOW_REPORT.md
- Сервер: 172.237.73.207, Docker инфраструктура

⚠️ ВАЖНО:
- Обновить ВСЕ 5 файлов документации меню!
- Добавить в CONVERSATION_HISTORY_FLOW_REPORT.md раздел про PDF экспорт
- Тесты для генерации PDF и отправки
- MinIO credentials из config.py

Ожидаемый результат:
- Полностью рабочая фича
- Задеплоено на production
- Документация обновлена
- Тесты прошли
```

#### Пример 4: Production incident
```markdown
Используя error-coordinator, восстанови VoxPersona бот - не отвечает в production.

Симптомы:
- Бот не отвечает на сообщения
- Последние логи: "connection pool exhausted"
- Время: 5 минут назад
- Критичность: HIGH

Сервер: 172.237.73.207
Docker: voxpersona_app, voxpersona_postgres

Действия:
1. Немедленная диагностика (параллельно)
2. Быстрый фикс или rollback
3. Root cause analysis
4. Постморtem документ

⚠️ SLA: восстановить за < 15 минут
```

---

## 📊 МЕТРИКИ ЭФФЕКТИВНОСТИ

### Измеряемые показатели

#### 1. Время выполнения
```
Без мультиагентов:
- Простая задача: T
- Средняя задача: 3T
- Сложная задача: 10T

С мультиагентами:
- Простая задача: T (без overhead)
- Средняя задача: T (параллелизм)
- Сложная задача: 3T (координация + параллелизм)

Ускорение: до 3x на сложных задачах
```

#### 2. Качество кода
```
С использованием code-reviewer:
- Меньше багов в production
- Соблюдение best practices
- Consistency в кодовой базе
```

#### 3. Полнота решения
```
С agent-organizer:
- Учтены все edge cases
- Документация обновлена
- Тесты покрывают функционал
```

### Когда НЕ использовать мультиагентов

❌ Избегай в этих случаях:
- Очень простая задача (< 5 минут работы)
- Исследовательская задача (читать код, понять логику)
- Прототипирование / proof of concept
- Быстрый эксперимент

✅ Используй мультиагентов когда:
- Production-ready код
- Критичная функциональность
- Требуется высокое качество
- Сложная координация нужна
- Параллелизм возможен

---

## 🎯 ЗАКЛЮЧЕНИЕ

### Ключевые выводы

1. **Трехуровневая иерархия** обеспечивает гибкость и эффективность
2. **agent-organizer** - для сложных задач с декомпозицией
3. **multi-agent-coordinator** - для параллельных задач
4. **error-coordinator** - для управления ошибками и incidents
5. **Специализированные агенты** - для целевых задач

### Быстрая шпаргалка

| Задача | Агент | Когда |
|--------|-------|-------|
| **Новая фича** | agent-organizer | Сложная, много специализаций |
| **Оптимизация** | multi-agent-coordinator | Параллельные улучшения |
| **Баг фикс** | debugger → python-pro | Воспроизведение → исправление |
| **Рефакторинг** | sequential-thinking → python-pro | Анализ → рефакторинг |
| **DB работа** | postgres-pro | Запросы, схема, оптимизация |
| **Тестирование** | test-automator | Автотесты, CI/CD |
| **Ревью кода** | code-reviewer | Качество, security |
| **Документация** | technical-writer | API docs, guides |
| **Деплой** | deployment-engineer | Production release |
| **Incident** | error-coordinator | Production down |

### Следующие шаги

1. **Начни с простого**: используй специализированных агентов для текущих задач
2. **Добавь координацию**: когда задачи усложнятся - используй multi-agent-coordinator
3. **Масштабируй**: для больших фич используй agent-organizer
4. **Мониторь**: отслеживай эффективность мультиагентного подхода
5. **Итерируй**: корректируй workflow на основе опыта

---

**Автор:** Claude Code (Sonnet 4.5)
**Дата:** 5 октября 2025
**Версия:** 1.0
**Статус:** ✅ Готово к использованию

---

## 📎 ПРИЛОЖЕНИЯ

### Приложение A: Полный список агентов

#### Координаторы (4)
1. agent-organizer
2. multi-agent-coordinator
3. task-distributor
4. error-coordinator

#### Разработка (9)
5. python-pro
6. backend-developer
7. fullstack-developer
8. frontend-developer
9. typescript-pro
10. javascript-pro
11. sql-pro
12. postgres-pro
13. database-administrator

#### Тестирование (3)
14. test-automator
15. qa-expert
16. code-reviewer

#### Отладка (2)
17. debugger
18. error-detective

#### DevOps (5)
19. devops-engineer
20. sre-engineer
21. deployment-engineer
22. platform-engineer
23. terraform-engineer

#### Архитектура (3)
24. architect-reviewer
25. api-designer
26. microservices-architect

#### Документация (2)
27. technical-writer
28. documentation-engineer

#### Анализ (3)
29. sequential-thinking (MCP)
30. research-analyst
31. data-researcher

#### Безопасность (2)
32. security-engineer
33. security-auditor

#### Специальные (3)
34. context-manager
35. performance-monitor
36. knowledge-synthesizer

**Итого: 36 субагентов доступно**

### Приложение B: Инструменты агентов

#### Основные инструменты
- Read, Write, Edit, MultiEdit - файловые операции
- Bash - выполнение команд
- Glob, Grep - поиск
- Docker - контейнеризация
- Task - запуск субагентов

#### Специализированные инструменты
- pytest, jest, cypress - тестирование
- psql, mysql, mongodb - базы данных
- terraform, ansible, kubernetes - инфраструктура
- prometheus, grafana, datadog - мониторинг
- git, github-cli - версионный контроль


*Этот документ является живым руководством и должен обновляться по мере развития практик работы с мультиагентной системой.*
