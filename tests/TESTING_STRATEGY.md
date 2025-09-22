# Testing Strategy for VoxPersona

## Test Categories

### 🟢 CI-Compatible Tests
**Файлы:** `test_ci_compatible.py`
**Окружение:** GitHub Actions, локальная разработка
**Зависимости:** Только стандартные Python библиотеки

- ✅ Проверка версии Python
- ✅ Структура проекта
- ✅ Базовые импорты
- ✅ Конфигурация без внешних сервисов
- ✅ Утилиты и модели данных

### 🟡 Local-Only Tests
**Файлы:** `test_minio_manager.py`, `test_integration.py`, и др.
**Окружение:** Только локальная разработка
**Зависимости:** MinIO, torch, внешние сервисы

- ❌ Тесты MinIO интеграции
- ❌ Тесты torch/ML моделей
- ❌ Интеграционные тесты с сервисами
- ❌ Тесты имитации ошибок

## Команды для запуска

### В CI (GitHub Actions):
```bash
# Автоматически запускаются только CI-совместимые тесты
pytest tests/test_ci_compatible.py -v
```

### Локально (полные тесты):
```bash
# Запуск всех тестов
python tests/run_tests.py

# Запуск только unit тестов
python tests/run_tests.py --unit

# Запуск только интеграционных тестов  
python tests/run_tests.py --integration

# Запуск comprehensive тестов
python tests/run_tests.py --comprehensive
```

### Локально (только CI-совместимые):
```bash
# Эмуляция CI окружения
export CI=true
export SKIP_MINIO_TESTS=true
export SKIP_TORCH_TESTS=true
pytest tests/test_ci_compatible.py -v
```

## Переменные окружения

### CI Environment Detection:
- `CI=true` - Общий индикатор CI
- `GITHUB_ACTIONS=true` - Специфично для GitHub Actions
- `SKIP_MINIO_TESTS=true` - Пропустить MinIO тесты
- `SKIP_TORCH_TESTS=true` - Пропустить torch тесты

### Test Mode:
- `RUN_MODE=TEST` - Режим тестирования

## Ожидаемые результаты

### В GitHub Actions:
```
✅ 4-6 тестов пройдены (базовая функциональность)
⏭️  MinIO тесты пропущены
⏭️  Torch тесты пропущены
⏭️  Интеграционные тесты пропущены
```

### Локально:
```
✅ 15+ тестов пройдены (полная функциональность)
❌ 6 могут не пройти (MinIO недоступен локально)
❌ 9 могут не пройти (torch/внешние сервисы)
```

## Troubleshooting

### Если CI тесты падают:
1. Проверьте Python версию (должна быть 3.10.11)
2. Проверьте базовые импорты в `src/`
3. Убедитесь, что структура проекта корректна

### Если локальные тесты падают:
1. Установите все зависимости: `pip install -r requirements.txt`
2. Запустите MinIO локально (если нужно)
3. Проверьте файл `.env` конфигурации