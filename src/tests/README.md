# Инструкции по запуску тестов

**Задача ID:** 00001_20251007_T3H8K9
**Фаза:** 5 (Testing)
**Агент:** test-automator

---

## 🧪 Запуск всех тестов

```bash
cd C:/Users/l0934/Projects/VoxPersona
pytest src/tests/test_file_sender.py -v
```

---

## 📊 Запуск с покрытием кода

```bash
# Терминальный отчет + HTML
pytest src/tests/test_file_sender.py --cov=src.file_sender --cov-report=html --cov-report=term

# Открыть HTML отчет (Windows)
start htmlcov/index.html
```

---

## 🎯 Запуск конкретных групп тестов

### Unit-тесты только

```bash
pytest src/tests/test_file_sender.py -v -k "not asyncio"
```

### Integration-тесты только

```bash
pytest src/tests/test_file_sender.py -v -k "asyncio"
```

### Тесты форматирования

```bash
pytest src/tests/test_file_sender.py::TestFormatHistoryForFile -v
pytest src/tests/test_file_sender.py::TestFormatReportsForFile -v
```

### Тесты throttling

```bash
pytest src/tests/test_file_sender.py::TestThrottling -v
```

### Integration-тесты

```bash
pytest src/tests/test_file_sender.py::TestAutoSendHistoryFile -v
pytest src/tests/test_file_sender.py::TestAutoSendReportsFile -v
```

---

## 🔍 Запуск конкретного теста

```bash
pytest src/tests/test_file_sender.py::TestFormatHistoryForFile::test_empty_history -v
```

---

## 🚀 Быстрый запуск (без verbose)

```bash
pytest src/tests/test_file_sender.py
```

---

## 📈 Статистика покрытия

После запуска с `--cov-report=html` откройте `htmlcov/index.html` для детального анализа.

**Целевое покрытие:** > 85%

---

## 🎭 E2E-тесты (Manual)

E2E-тесты необходимо выполнить вручную с реальным Telegram ботом.

См. инструкции в конце файла `test_file_sender.py` (комментарий).

### Быстрый чеклист E2E:

- [ ] **Сценарий 1:** Новый пользователь → /start → файлы НЕ отправляются
- [ ] **Сценарий 2:** Существующий пользователь → /start → два файла отправляются
- [ ] **Сценарий 3:** Повторный /start → throttling работает (файлы НЕ отправляются)
- [ ] **Сценарий 4:** /history и /reports работают как раньше (обратная совместимость)

---

## 🐛 Troubleshooting

### ModuleNotFoundError

Если получаете `ModuleNotFoundError: No module named 'file_sender'`:

```bash
# Добавьте src в PYTHONPATH
set PYTHONPATH=C:\Users\l0934\Projects\VoxPersona\src;%PYTHONPATH%

# Или используйте editable install
pip install -e .
```

### pytest not found

```bash
pip install pytest pytest-asyncio pytest-cov
```

---

## 📝 Результаты тестирования

После выполнения всех тестов заполните:

### Unit-тесты

- **Всего тестов:** ___
- **Успешно:** ___
- **Провалено:** ___
- **Покрытие:** ___%

### Integration-тесты

- **Всего тестов:** ___
- **Успешно:** ___
- **Провалено:** ___

### E2E-тесты (Manual)

- **Сценарий 1:** ✅/❌
- **Сценарий 2:** ✅/❌
- **Сценарий 3:** ✅/❌
- **Сценарий 4:** ✅/❌

---

## 🎯 Критерии готовности

- [ ] Все unit-тесты проходят
- [ ] Все integration-тесты проходят
- [ ] Покрытие > 85%
- [ ] Все 4 E2E-сценария выполнены
- [ ] Нет критических багов
- [ ] Нет регрессий в существующих командах

---

**Следующий агент:** documentation-engineer (Фаза 6)
