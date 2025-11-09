"""
Простой тест для проверки импорта модуля formatters
"""
import sys
from pathlib import Path

# Добавляем src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Проверка импорта всех классов"""
    print("🔍 Проверка импорта модуля formatters...")

    try:
        from formatters import BaseFormatter, HistoryFormatter, ReportFormatter
        print("✅ Импорт из formatters успешен")
    except ImportError as e:
        print(f"❌ Ошибка импорта из formatters: {e}")
        return False

    try:
        from formatters.base_formatter import BaseFormatter
        print("✅ Импорт BaseFormatter успешен")
    except ImportError as e:
        print(f"❌ Ошибка импорта BaseFormatter: {e}")
        return False

    try:
        from formatters.history_formatter import HistoryFormatter
        print("✅ Импорт HistoryFormatter успешен")
    except ImportError as e:
        print(f"❌ Ошибка импорта HistoryFormatter: {e}")
        return False

    try:
        from formatters.report_formatter import ReportFormatter
        print("✅ Импорт ReportFormatter успешен")
    except ImportError as e:
        print(f"❌ Ошибка импорта ReportFormatter: {e}")
        return False

    return True


def test_inheritance():
    """Проверка наследования классов"""
    print("\n🔍 Проверка наследования классов...")

    from formatters import BaseFormatter, HistoryFormatter, ReportFormatter
    from abc import ABC

    # Проверка BaseFormatter
    if not issubclass(BaseFormatter, ABC):
        print("❌ BaseFormatter не наследуется от ABC")
        return False
    print("✅ BaseFormatter наследуется от ABC")

    # Проверка HistoryFormatter
    if not issubclass(HistoryFormatter, BaseFormatter):
        print("❌ HistoryFormatter не наследуется от BaseFormatter")
        return False
    print("✅ HistoryFormatter наследуется от BaseFormatter")

    # Проверка ReportFormatter
    if not issubclass(ReportFormatter, BaseFormatter):
        print("❌ ReportFormatter не наследуется от BaseFormatter")
        return False
    print("✅ ReportFormatter наследуется от BaseFormatter")

    return True


def test_methods():
    """Проверка наличия методов"""
    print("\n🔍 Проверка наличия методов...")

    from formatters import HistoryFormatter, ReportFormatter

    # Проверка HistoryFormatter
    history = HistoryFormatter()

    required_methods = ['format', 'format_inline_preview', 'format_timestamp', 'truncate_text', 'escape_markdown']
    for method in required_methods:
        if not hasattr(history, method):
            print(f"❌ HistoryFormatter не имеет метода {method}")
            return False
    print("✅ HistoryFormatter имеет все необходимые методы")

    # Проверка ReportFormatter
    report = ReportFormatter()

    required_methods = ['format', 'format_summary', 'format_timestamp', 'truncate_text', 'escape_markdown']
    for method in required_methods:
        if not hasattr(report, method):
            print(f"❌ ReportFormatter не имеет метода {method}")
            return False
    print("✅ ReportFormatter имеет все необходимые методы")

    return True


def test_basic_functionality():
    """Проверка базовой функциональности"""
    print("\n🔍 Проверка базовой функциональности...")

    from formatters import HistoryFormatter

    formatter = HistoryFormatter()

    # Тест format_timestamp
    timestamp = "2025-10-09T14:30:00"
    result = formatter.format_timestamp(timestamp, "full")
    expected = "09.10.2025 в 14:30"
    if result != expected:
        print(f"❌ format_timestamp вернул '{result}', ожидалось '{expected}'")
        return False
    print(f"✅ format_timestamp работает корректно: '{result}'")

    # Тест truncate_text
    text = "Это очень длинный текст который должен быть обрезан по словам для корректного отображения в интерфейсе"
    result = formatter.truncate_text(text, 50)
    if len(result) > 53:  # 50 + "..."
        print(f"❌ truncate_text не обрезал текст: длина {len(result)}")
        return False
    if not result.endswith("..."):
        print(f"❌ truncate_text не добавил '...': '{result}'")
        return False
    print(f"✅ truncate_text работает корректно: '{result}'")

    # Тест escape_markdown
    text = "Текст с *звездочками* и _подчеркиваниями_"
    result = formatter.escape_markdown(text)
    if "*" in result and "\\" not in result:
        print(f"❌ escape_markdown не экранировал спецсимволы: '{result}'")
        return False
    print(f"✅ escape_markdown работает корректно: '{result}'")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ТЕСТ ИМПОРТА И ФУНКЦИОНАЛЬНОСТИ МОДУЛЯ FORMATTERS")
    print("=" * 60)

    all_passed = True

    # Запуск тестов
    all_passed &= test_imports()
    all_passed &= test_inheritance()
    all_passed &= test_methods()
    all_passed &= test_basic_functionality()

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)
