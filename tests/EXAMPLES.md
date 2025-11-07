# Примеры использования тестов User Management

Практические примеры запуска и отладки тестов для разработчиков.

---

## 📖 Базовые примеры

### Пример 1: Запустить все тесты

```bash
cd C:\Users\l0934\Projects\VoxPersona
pytest tests/test_user_management_fixes.py -v
```

**Вывод:**
```
===================== test session starts ======================
collected 20 items

tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_block_user_synchronizes_fields PASSED [  5%]
tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_unblock_user_synchronizes_fields PASSED [ 10%]
...
===================== 20 passed in 2.45s ======================
```

---

### Пример 2: Запустить один конкретный тест

```bash
pytest tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_block_user_synchronizes_fields -v
```

**Когда использовать:**
- Отладка конкретного функционала
- Быстрая проверка одного исправления
- Разработка нового теста

---

### Пример 3: Запустить тесты по маркеру

```bash
# Только тесты блокировки пользователей
pytest tests/test_user_management_fixes.py -v -m blocking

# Только тесты паролей
pytest tests/test_user_management_fixes.py -v -m password

# Только интеграционные тесты
pytest tests/test_user_management_fixes.py -v -m integration
```

**Маркеры:**
- `blocking` - тесты блокировки/разблокировки
- `password` - тесты генерации и валидации паролей
- `status` - тесты отображения статуса
- `integration` - интеграционные тесты

---

## 🐛 Отладка тестов

### Пример 4: Показать детальный traceback

```bash
pytest tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_block_user_synchronizes_fields -vv --tb=long
```

**Вывод при ошибке:**
```
FAILED tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_block_user_synchronizes_fields

________________________________ TRACEBACK _________________________________
    def test_block_user_synchronizes_fields(self, auth_manager, test_user_active):
        ...
        assert blocked_user.is_active is False
>       assert blocked_user.is_blocked is True
E       AssertionError: assert False is True
E        +  where False = <User user_id='...'>is_blocked
```

---

### Пример 5: Показать print() из тестов

```bash
pytest tests/test_user_management_fixes.py -v -s
```

**Когда использовать:**
- Отладка с помощью `print()` в тестах
- Просмотр логов во время выполнения
- Диагностика проблем

---

### Пример 6: Остановиться на первой ошибке

```bash
pytest tests/test_user_management_fixes.py -v -x
```

**Полезно:**
- При разработке нового теста
- Для быстрой диагностики
- Когда один тест блокирует остальные

---

## 📊 Анализ тестов

### Пример 7: Показать покрытие кода

```bash
pip install pytest-cov
pytest tests/test_user_management_fixes.py --cov=src.auth_manager --cov=src.auth_security --cov-report=html
```

**Результат:**
- Консольный отчет о покрытии
- HTML отчет в `htmlcov/index.html`

**Открыть отчет:**
```bash
start htmlcov/index.html  # Windows
```

---

### Пример 8: Показать длительность тестов

```bash
pytest tests/test_user_management_fixes.py -v --durations=10
```

**Вывод:**
```
===================== slowest 10 durations =====================
0.45s call     tests/test_user_management_fixes.py::TestPasswordGeneration::test_reset_password_uses_secrets_module
0.23s call     tests/test_user_management_fixes.py::TestUserManagementIntegration::test_full_user_lifecycle
...
```

**Когда использовать:**
- Оптимизация медленных тестов
- Поиск bottlenecks
- Анализ производительности

---

## 🔧 Продвинутые примеры

### Пример 9: Запустить с профилированием

```bash
pip install pytest-profiling
pytest tests/test_user_management_fixes.py --profile
```

**Результат:**
- Профиль выполнения каждого теста
- Hotspots в коде

---

### Пример 10: Параллельный запуск тестов

```bash
pip install pytest-xdist
pytest tests/test_user_management_fixes.py -v -n 4
```

**Параметры:**
- `-n 4` - использовать 4 процесса
- `-n auto` - автоматически определить количество

**Когда использовать:**
- Большое количество тестов
- CI/CD пайплайн
- Экономия времени

---

### Пример 11: Запустить только упавшие тесты

```bash
# Первый запуск (некоторые тесты упали)
pytest tests/test_user_management_fixes.py -v

# Повторить только упавшие
pytest tests/test_user_management_fixes.py -v --lf
```

**Опции:**
- `--lf` (last-failed) - только упавшие
- `--ff` (failed-first) - сначала упавшие, потом все

---

## 🧩 Примеры для разработки

### Пример 12: Создать новый тест (шаблон)

```python
# tests/test_user_management_fixes.py

@pytest.mark.asyncio
@pytest.mark.blocking
async def test_my_new_feature(self, auth_manager, test_user_active):
    """
    Тест: описание нового функционала.

    ОЖИДАЕМОЕ ПОВЕДЕНИЕ:
    - Шаг 1: что происходит
    - Шаг 2: что проверяется
    """
    # Arrange: Подготовка данных
    user = test_user_active

    # Act: Выполнение действия
    result = await auth_manager.some_new_method(user.user_id)

    # Assert: Проверка результата
    assert result is True, "Новый метод должен вернуть True"

    # Assert: Проверка побочных эффектов
    updated_user = await auth_manager.get_user(user.user_id)
    assert updated_user.some_field == "expected_value"
```

**Запустить новый тест:**
```bash
pytest tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_my_new_feature -v
```

---

### Пример 13: Отладка с breakpoint

```python
# В тесте
@pytest.mark.asyncio
async def test_with_debugging(self, auth_manager):
    user = await auth_manager.create_user(...)

    # Остановиться здесь для инспекции
    import pdb; pdb.set_trace()

    result = await auth_manager.block_user(user.user_id)
    assert result is True
```

**Запустить:**
```bash
pytest tests/test_user_management_fixes.py::test_with_debugging -v -s
```

**Команды pdb:**
- `n` - next line
- `c` - continue
- `p variable` - print variable
- `l` - list code
- `q` - quit

---

### Пример 14: Использовать фикстуру в тесте

```python
# Использование существующих фикстур
def test_using_fixtures(auth_manager, test_user_active, password_samples):
    """Тест с использованием нескольких фикстур."""
    # auth_manager - готовый AuthManager
    # test_user_active - тестовый активный пользователь
    # password_samples - примеры паролей

    for pwd in password_samples['valid']:
        is_valid, _ = auth_manager.security.validate_password(pwd)
        assert is_valid is True
```

---

## 🎯 Практические сценарии

### Сценарий 1: Проверить исправление бага

```bash
# 1. Создать тест, воспроизводящий баг
# 2. Убедиться, что тест падает (баг воспроизведен)
pytest tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_block_user_synchronizes_fields -v

# 3. Исправить баг в коде (auth_manager.py)
# 4. Запустить тест снова
pytest tests/test_user_management_fixes.py::TestUserBlockingAndStatus::test_block_user_synchronizes_fields -v

# 5. Тест прошел ✅ - баг исправлен
```

---

### Сценарий 2: Разработка нового функционала (TDD)

```bash
# 1. Написать тест для нового функционала (тест падает - функционал не реализован)
pytest tests/test_user_management_fixes.py::test_new_feature -v

# 2. Реализовать минимальный функционал (тест проходит)
pytest tests/test_user_management_fixes.py::test_new_feature -v

# 3. Рефакторинг (тест продолжает проходить)
pytest tests/test_user_management_fixes.py::test_new_feature -v

# 4. Запустить все тесты для проверки регрессии
pytest tests/test_user_management_fixes.py -v
```

---

### Сценарий 3: Регрессионное тестирование

```bash
# Запустить все тесты перед commit
pytest tests/test_user_management_fixes.py -v --tb=short

# Если упали - исправить
# Если прошли - commit
git add .
git commit -m "feat: добавлен новый функционал"
```

---

## 📝 Полезные команды

### Показать список всех тестов (без запуска)

```bash
pytest tests/test_user_management_fixes.py --collect-only
```

---

### Запустить тесты с timeout

```bash
pip install pytest-timeout
pytest tests/test_user_management_fixes.py -v --timeout=5
```

---

### Генерировать JUnit XML отчет (для CI)

```bash
pytest tests/test_user_management_fixes.py -v --junitxml=test-results.xml
```

---

### Запустить с разными уровнями verbose

```bash
# Минимальный вывод
pytest tests/test_user_management_fixes.py -q

# Обычный вывод
pytest tests/test_user_management_fixes.py -v

# Максимальный вывод
pytest tests/test_user_management_fixes.py -vv
```

---

## 🚀 Интеграция в workflow

### Pre-commit hook

Создать `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "Running User Management tests..."
pytest tests/test_user_management_fixes.py -v --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Commit aborted."
    exit 1
fi

echo "✅ All tests passed. Proceeding with commit."
exit 0
```

**Активировать:**
```bash
chmod +x .git/hooks/pre-commit
```

---

### VS Code tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run User Management Tests",
      "type": "shell",
      "command": "pytest",
      "args": [
        "tests/test_user_management_fixes.py",
        "-v"
      ],
      "group": {
        "kind": "test",
        "isDefault": true
      }
    }
  ]
}
```

**Запустить:** `Ctrl+Shift+B` в VS Code

---

## 📚 Дополнительные ресурсы

- [Полная документация тестов](README_TESTS.md)
- [Конфигурация pytest](../pytest.ini)
- [Фикстуры](conftest.py)

---

**Последнее обновление:** 7 ноября 2025
