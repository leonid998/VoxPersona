#!/usr/bin/env python3
"""
Миграция: Извлечение реальных вопросов из MD файлов в index.json

Дата: 2025-10-14
Причина: Все 24 отчета имеют question="# Отчет VoxPersona" вместо реального вопроса
"""

import json
import re
from pathlib import Path

REPORTS_DIR = Path("/home/voxpersona_user/VoxPersona/md_reports")
INDEX_FILE = REPORTS_DIR / "index.json"
BACKUP_FILE = REPORTS_DIR / "index.json.backup_before_question_fix"

def extract_question_from_md(md_file_path: Path) -> str:
    """
    Извлекает реальный вопрос пользователя из MD файла.

    MD файлы имеют формат:
    # Отчет VoxPersona
    **Дата:** 14.10.2025 12:00
    **Пользователь:** @username (ID: 12345)
    **Запрос:** РЕАЛЬНЫЙ ВОПРОС ЗДЕСЬ  ← ЭТО НУЖНО
    **Тип поиска:** fast

    Returns:
        Текст вопроса или "# Отчет VoxPersona" если не найден
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Ищем строку **Запрос:**
        match = re.search(r'\*\*Запрос:\*\*\s*(.+?)(?:\n|\r\n)', content)
        if match:
            question = match.group(1).strip()
            return question if question else "# Отчет VoxPersona"

        return "# Отчет VoxPersona"

    except Exception as e:
        print(f"  ⚠️ Ошибка при чтении {md_file_path}: {e}")
        return "# Отчет VoxPersona"

def main():
    print("🔄 МИГРАЦИЯ: Исправление поля question в index.json")
    print(f"📁 Директория: {REPORTS_DIR}")
    print()

    # 1. Создать бэкап
    print("1️⃣ Создание бэкапа...")
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ Бэкап создан: {BACKUP_FILE}")
    print()

    # 2. Обработать каждый отчет
    print("2️⃣ Обновление вопросов...")
    updated_count = 0
    failed_count = 0

    for report in data:
        report_number = report.get("report_number", "?")
        file_path = report.get("file_path")
        old_question = report.get("question", "")

        if not file_path:
            print(f"  ⚠️ Отчет #{report_number}: нет file_path")
            failed_count += 1
            continue

        # Полный путь к MD файлу
        md_file = REPORTS_DIR / file_path

        if not md_file.exists():
            print(f"  ⚠️ Отчет #{report_number}: файл не найден - {file_path}")
            failed_count += 1
            continue

        # Извлечь вопрос
        new_question = extract_question_from_md(md_file)

        # Обновить только если изменился
        if new_question != old_question:
            report["question"] = new_question
            updated_count += 1
            print(f"  ✅ Отчет #{report_number}: обновлен")
            print(f"     Было: {old_question[:60]}...")
            print(f"     Стало: {new_question[:60]}...")
        else:
            print(f"  ➖ Отчет #{report_number}: без изменений")

    print()
    print(f"📊 Результаты:")
    print(f"   Обновлено: {updated_count}")
    print(f"   Без изменений: {len(data) - updated_count - failed_count}")
    print(f"   Ошибок: {failed_count}")
    print()

    # 3. Сохранить обновленный index.json
    if updated_count > 0:
        print("3️⃣ Сохранение изменений...")
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ Изменения сохранены в {INDEX_FILE}")
    else:
        print("3️⃣ Нет изменений для сохранения")

    print()
    print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")

if __name__ == "__main__":
    main()
