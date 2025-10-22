#!/usr/bin/env python3
"""
Скрипт для генерации тестовых данных для Menu Crawler
Создает тестовые чаты и отчеты для динамических меню
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Добавляем корневую директорию проекта И src в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

os.environ['ENV'] = 'production'

from conversation_manager import ConversationManager


def create_test_conversations(user_id: str, count: int = 3):
    """
    Создать тестовые чаты для TEST_USER

    Args:
        user_id: ID пользователя
        count: Количество чатов для создания
    """
    print(f"📝 Создание {count} тестовых чатов для user_id: {user_id}...")

    manager = ConversationManager(user_id)

    test_chats = [
        {
            "name": "Тестовый чат 1 - Интервью",
            "mode": "interview",
            "building_type": "hotel"
        },
        {
            "name": "Тестовый чат 2 - Дизайн",
            "mode": "design",
            "building_type": "restaurant"
        },
        {
            "name": "Тестовый чат 3 - Быстрый режим",
            "mode": "fast",
            "building_type": "hotel"
        }
    ]

    created_count = 0

    for i, chat_data in enumerate(test_chats[:count], 1):
        try:
            # Создание чата
            conv_id = manager.create_conversation(
                name=chat_data["name"],
                mode=chat_data.get("mode", "fast")
            )

            # Добавление метаданных
            metadata = {
                "building_type": chat_data.get("building_type", "hotel"),
                "created_by": "menu_crawler_test",
                "created_at": datetime.now().isoformat()
            }

            print(f"  ✅ Создан чат {i}/{count}: {chat_data['name']} (ID: {conv_id[:8]}...)")
            created_count += 1

        except Exception as e:
            print(f"  ❌ Ошибка создания чата {i}: {e}")

    print(f"✅ Создано чатов: {created_count}/{count}")
    return created_count


def create_test_reports(user_id: str, count: int = 2):
    """
    Создать тестовые отчеты для TEST_USER

    Args:
        user_id: ID пользователя
        count: Количество отчетов для создания
    """
    print(f"📄 Создание {count} тестовых отчетов для user_id: {user_id}...")

    # Путь к директории отчетов пользователя
    reports_dir = project_root / "md_reports" / f"user_{user_id}"
    reports_dir.mkdir(parents=True, exist_ok=True)

    test_reports = [
        {
            "filename": "test_report_interview_1.md",
            "title": "Тестовый отчет - Интервью",
            "content": """# Тестовый отчет интервью

## Дата создания
{date}

## Описание
Это тестовый отчет, созданный для проверки Menu Crawler.

## Метаданные
- Тип: Интервью
- Создано: Menu Crawler Test
- Статус: Тестовый
"""
        },
        {
            "filename": "test_report_design_1.md",
            "title": "Тестовый отчет - Дизайн",
            "content": """# Тестовый отчет дизайн-аудита

## Дата создания
{date}

## Описание
Это тестовый отчет дизайн-аудита для проверки Menu Crawler.

## Метаданные
- Тип: Дизайн-аудит
- Создано: Menu Crawler Test
- Статус: Тестовый
"""
        }
    ]

    created_count = 0

    for i, report_data in enumerate(test_reports[:count], 1):
        try:
            report_path = reports_dir / report_data["filename"]

            # Заполнение контента
            content = report_data["content"].format(
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Запись файла
            report_path.write_text(content, encoding='utf-8')

            print(f"  ✅ Создан отчет {i}/{count}: {report_data['filename']}")
            created_count += 1

        except Exception as e:
            print(f"  ❌ Ошибка создания отчета {i}: {e}")

    print(f"✅ Создано отчетов: {created_count}/{count}")
    return created_count


def main():
    """Главная функция генерации тестовых данных"""

    TEST_USER_TELEGRAM_ID = 155894817

    print("=" * 60)
    print("🧪 ГЕНЕРАЦИЯ ТЕСТОВЫХ ДАННЫХ ДЛЯ MENU CRAWLER")
    print("=" * 60)
    print()

    # User ID = telegram_id для тестового пользователя
    user_id = str(TEST_USER_TELEGRAM_ID)

    try:
        # Создание тестовых чатов
        chats_created = create_test_conversations(user_id, count=3)
        print()

        # Создание тестовых отчетов
        reports_created = create_test_reports(user_id, count=2)
        print()

        # Итоговая статистика
        print("=" * 60)
        print("✅ ГЕНЕРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 60)
        print(f"📝 Тестовых чатов создано: {chats_created}")
        print(f"📄 Тестовых отчетов создано: {reports_created}")
        print()
        print("🎯 Ожидаемый эффект:")
        print("   - Доступны dynamic меню: chat_actions||{id}")
        print("   - Доступны отчеты: report_view, report_rename, report_delete")
        print("   - Coverage должен вырасти на ~10-15%")
        print()

        return 0

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
