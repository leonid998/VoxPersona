"""
Тестовый скрипт для проверки сохранения и загрузки данных.
Проверяет работу ChatHistoryManager и MDStorageManager.
"""

import sys
import os
from datetime import date
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chat_history import chat_history_manager
from md_storage import md_storage_manager
from config import CHAT_HISTORY_DIR, MD_REPORTS_DIR

def test_chat_history():
    """Тест сохранения и загрузки истории чата."""
    print("\n" + "="*60)
    print("ТЕСТ 1: ChatHistoryManager")
    print("="*60)

    test_user_id = 999999
    test_username = "test_user"

    # Проверяем путь к директории
    print(f"\n📁 Директория истории: {chat_history_manager.history_dir}")
    print(f"   Абсолютный путь: {chat_history_manager.history_dir.absolute()}")
    print(f"   Существует: {chat_history_manager.history_dir.exists()}")

    # Создаем директорию пользователя
    user_dir = chat_history_manager.ensure_user_directory(test_user_id)
    print(f"\n📁 Директория пользователя: {user_dir}")
    print(f"   Абсолютный путь: {user_dir.absolute()}")
    print(f"   Существует: {user_dir.exists()}")

    # Сохраняем тестовое сообщение
    print("\n💾 Сохраняем вопрос пользователя...")
    success1 = chat_history_manager.save_message_to_history(
        user_id=test_user_id,
        username=test_username,
        message_id=1,
        message_type="user_question",
        text="Тестовый вопрос для проверки сохранения"
    )
    print(f"   Результат: {'✅ Успешно' if success1 else '❌ Ошибка'}")

    # Сохраняем ответ бота
    print("\n💾 Сохраняем ответ бота...")
    success2 = chat_history_manager.save_message_to_history(
        user_id=test_user_id,
        username=test_username,
        message_id=2,
        message_type="bot_answer",
        text="Тестовый ответ бота",
        sent_as="message",
        search_type="fast"
    )
    print(f"   Результат: {'✅ Успешно' if success2 else '❌ Ошибка'}")

    # Проверяем файл истории
    today_filename = chat_history_manager.get_today_filename()
    history_file = user_dir / today_filename
    print(f"\n📄 Файл истории: {history_file}")
    print(f"   Существует: {history_file.exists()}")
    if history_file.exists():
        size = history_file.stat().st_size
        print(f"   Размер: {size} байт")

    # Загружаем историю
    print("\n📖 Загружаем историю за сегодня...")
    day_history = chat_history_manager.load_day_history(test_user_id, date.today())

    if day_history:
        print(f"   ✅ История загружена")
        print(f"   Сообщений: {len(day_history.messages)}")
        print(f"   Вопросов: {day_history.stats.total_questions}")
        print(f"   Ответов: {day_history.stats.total_answers}")
    else:
        print(f"   ❌ История НЕ загружена")

    # Получаем статистику
    print("\n📊 Получаем статистику пользователя...")
    stats = chat_history_manager.get_user_stats(test_user_id)
    print(f"   Активных дней: {stats['days_active']}")
    print(f"   Всего вопросов: {stats['total_questions']}")
    print(f"   Всего ответов: {stats['total_answers']}")
    print(f"   Быстрых поисков: {stats['fast_searches']}")

    # Форматируем для отображения
    print("\n📱 Форматированная статистика:")
    formatted = chat_history_manager.format_user_stats_for_display(test_user_id)
    print(formatted)

    return success1 and success2 and day_history is not None


def test_md_reports():
    """Тест сохранения и загрузки MD отчетов."""
    print("\n" + "="*60)
    print("ТЕСТ 2: MDStorageManager")
    print("="*60)

    test_user_id = 999999
    test_username = "test_user"

    # Проверяем путь к директории
    print(f"\n📁 Директория отчетов: {md_storage_manager.reports_dir}")
    print(f"   Абсолютный путь: {md_storage_manager.reports_dir.absolute()}")
    print(f"   Существует: {md_storage_manager.reports_dir.exists()}")

    # Создаем директорию пользователя
    user_dir = md_storage_manager.ensure_user_directory(test_user_id)
    print(f"\n📁 Директория пользователя: {user_dir}")
    print(f"   Абсолютный путь: {user_dir.absolute()}")
    print(f"   Существует: {user_dir.exists()}")

    # Сохраняем тестовый отчет
    print("\n💾 Сохраняем MD отчет...")
    file_path = md_storage_manager.save_md_report(
        content="Тестовый отчет для проверки сохранения",
        user_id=test_user_id,
        username=test_username,
        question="Тестовый вопрос",
        search_type="deep"
    )

    if file_path:
        print(f"   ✅ Отчет сохранен: {file_path}")
        print(f"   Файл существует: {Path(file_path).exists()}")
    else:
        print(f"   ❌ Ошибка сохранения отчета")

    # Загружаем отчеты пользователя
    print("\n📖 Загружаем отчеты пользователя...")
    reports = md_storage_manager.get_user_reports(test_user_id, limit=10)
    print(f"   Найдено отчетов: {len(reports)}")

    for i, report in enumerate(reports, 1):
        print(f"\n   Отчет {i}:")
        print(f"   - Файл: {report.file_path}")
        print(f"   - Вопрос: {report.question}")
        print(f"   - Тип поиска: {report.search_type}")
        print(f"   - Размер: {report.size_bytes} байт")

    # Форматируем для отображения
    if reports:
        print("\n📱 Форматированный список отчетов:")
        formatted = md_storage_manager.format_user_reports_for_display(test_user_id)
        print(formatted)

    return file_path is not None and len(reports) > 0


def main():
    print("\n" + "="*60)
    print("ПРОВЕРКА СОХРАНЕНИЯ И ЗАГРУЗКИ ДАННЫХ")
    print("="*60)

    print(f"\n⚙️  КОНФИГУРАЦИЯ:")
    print(f"   CHAT_HISTORY_DIR: {CHAT_HISTORY_DIR}")
    print(f"   MD_REPORTS_DIR: {MD_REPORTS_DIR}")

    # Запускаем тесты
    test1_passed = test_chat_history()
    test2_passed = test_md_reports()

    # Итоги
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*60)
    print(f"\nТест 1 (ChatHistoryManager): {'✅ ПРОЙДЕН' if test1_passed else '❌ ПРОВАЛЕН'}")
    print(f"Тест 2 (MDStorageManager): {'✅ ПРОЙДЕН' if test2_passed else '❌ ПРОВАЛЕН'}")

    if test1_passed and test2_passed:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("   Данные сохраняются и загружаются корректно.")
    else:
        print("\n❌ ТЕСТЫ ПРОВАЛЕНЫ!")
        print("   Есть проблемы с сохранением или загрузкой данных.")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
