# VoxPersona Deployment Guide

## 🚀 Automated GitHub Actions Deployment

> **New!** VoxPersona now uses intelligent GitHub Actions for automated deployment with smart restart logic.

### Overview

VoxPersona features an intelligent deployment system that automatically determines the optimal deployment strategy based on file changes:

- **NO_RESTART** (5-10s): Documentation changes only
- **APP_ONLY** (30-60s): Application code changes
- **FULL_RESTART** (2-3min): Infrastructure changes

### Quick Start

1. **Configure GitHub Secrets** (one-time setup):
   ```
   SSH_PRIVATE_KEY - SSH key for server access
   SERVER_IP - Deployment server IP
   SERVER_USER - SSH username
   ```

2. **Push to main branch**:
   ```bash
   git push origin main
   ```
   
3. **Monitor deployment** in GitHub Actions tab

### Manual Deployment Control

For manual deployments:
1. Go to Actions → "Intelligent VoxPersona Deployment"
2. Click "Run workflow"
3. Select deployment type: `auto`, `full`, `app-only`, or `no-restart`

### Detailed Setup

See comprehensive guides:
- [Deployment Setup Guide](.github/DEPLOYMENT_SETUP.md) - SSH keys, secrets, configuration
- [Testing Guide](.github/TESTING_GUIDE.md) - Test scenarios and validation

---

## 📋 Legacy: Manual GitHub Setup

### Step 1: Repository Setup

1. **Create new GitHub repository**:
   - Go to [github.com](https://github.com)
   - Click "New repository"
   - Name: `VoxPersona`
   - Description: "AI-Powered Voice Analysis Platform"
   - Choose Public or Private
   - Don't initialize with README

### Step 2: Initialize Git Repository

```bash
# Navigate to project directory
cd VoxPersona

# Initialize Git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: VoxPersona AI Voice Analysis Platform"

# Add remote repository
git remote add origin https://github.com/yourusername/VoxPersona.git

# Push code to GitHub
git push -u origin main
```

### Step 3: GitHub Secrets Configuration

For automated deployment, configure these secrets in Settings → Secrets and variables → Actions:

**Required for Deployment**:
```
SSH_PRIVATE_KEY - SSH private key content
SERVER_IP - Server IP address
SERVER_USER - SSH username
```

**Application Secrets**:
```
ANTHROPIC_API_KEY
OPENAI_API_KEY
TELEGRAM_BOT_TOKEN
API_ID
API_HASH
DB_PASSWORD
```

### Step 4: Create Release

```bash
# Create version tag
git tag -a v1.0.0 -m "VoxPersona v1.0.0 - Initial release"

# Push tag to GitHub
git push origin v1.0.0
```

On GitHub:
1. Go to Releases
2. Click "Create a new release"
3. Select tag v1.0.0
4. Add release description

## 📋 Чек-лист безопасности

### ✅ Что проверено и безопасно:

- [x] **Секретные данные удалены** - нет реальных API ключей
- [x] **Шаблон конфигурации создан** - .env.template с примерами
- [x] **.gitignore настроен** - исключает .env и другие секретные файлы
- [x] **Документация создана** - README.md и SETUP.md
- [x] **Docker конфигурация очищена** - нет ссылок на backup файлы
- [x] **Исходный код актуален** - взят с рабочего сервера

### ❌ Что НЕ включено (правильно):

- [x] Реальные API ключи
- [x] Пароли базы данных
- [x] Backup файлы с данными
- [x] Логи приложения
- [x] Персональные данные

## 🔧 Настройка для разработчиков

### Клонирование и настройка

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/VoxPersona.git
cd VoxPersona

# Настройка конфигурации
cp .env.template .env
# Отредактируйте .env файл

# Запуск с Docker
docker-compose up -d
```

### Ветвление для разработки

```bash
# Создание ветки для новой функции
git checkout -b feature/new-analysis-type

# Работа с кодом...

# Коммит изменений
git add .
git commit -m "Add new analysis type for retail audits"

# Отправка ветки
git push origin feature/new-analysis-type

# Создание Pull Request на GitHub
```

## 📊 Рекомендуемая структура Issues

### Шаблоны Issues

**Bug Report:**
```markdown
**Описание бага**
Краткое описание проблемы

**Шаги для воспроизведения**
1. Шаг 1
2. Шаг 2
3. Шаг 3

**Ожидаемое поведение**
Что должно происходить

**Фактическое поведение**
Что происходит на самом деле

**Окружение**
- OS: [Ubuntu 22.04]
- Docker: [20.10.21]
- Версия VoxPersona: [v1.0.0]

**Логи**
```
Вставьте логи здесь (без секретных данных)
```
```

**Feature Request:**
```markdown
**Описание функции**
Подробное описание желаемой функции

**Мотивация**
Зачем эта функция нужна

**Предлагаемое решение**
Как это должно работать

**Альтернативы**
Рассматривались ли другие варианты
```

## 🔄 Workflow для обновлений

### Обновление с сервера

```bash
# Получение нового кода с сервера
scp -r user@server:/path/to/app ./server-update

# Сравнение изменений
diff -r src/ server-update/src/

# Применение изменений
cp -r server-update/src/* src/

# Коммит обновлений
git add .
git commit -m "Update from production server - version X.X.X"
git push origin main
```

### Создание нового релиза

```bash
# Обновление версии
git tag -a v1.1.0 -m "VoxPersona v1.1.0 - Added new features"
git push origin v1.1.0

# Создание релиза на GitHub с changelog
```

## 📈 Метрики и аналитика

### GitHub Insights

Отслеживайте:
- Количество клонов
- Количество звезд
- Issues и Pull Requests
- Активность участников

### Рекомендуемые badges для README

```markdown
![GitHub stars](https://img.shields.io/github/stars/yourusername/VoxPersona)
![GitHub forks](https://img.shields.io/github/forks/yourusername/VoxPersona)
![GitHub issues](https://img.shields.io/github/issues/yourusername/VoxPersona)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![License](https://img.shields.io/github/license/yourusername/VoxPersona)
```

## 🤝 Community Guidelines

### Для участников

1. **Следуйте Code of Conduct**
2. **Используйте английский язык** для Issues и PR
3. **Тестируйте изменения** перед отправкой
4. **Документируйте новые функции**
5. **Не включайте секретные данные**

### Для мейнтейнеров

1. **Регулярно обновляйте зависимости**
2. **Отвечайте на Issues в течение 48 часов**
3. **Проводите code review для всех PR**
4. **Поддерживайте актуальную документацию**
5. **Создавайте релизы с changelog**

---

**Готово к размещению на GitHub! 🚀**

Этот проект подготовлен с соблюдением всех лучших практик безопасности и готов для публичного размещения.

