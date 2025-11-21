#!/usr/bin/env python3
"""
Скрипт для генерации JSON-контейнера с описаниями отчетов.
Запускать из корня проекта: python generate_json_container.py
"""

import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from relevance_evaluator import load_report_descriptions, build_json_container

def main():
    # Загружаем описания
    print("Загружаю описания отчетов...")
    descriptions = load_report_descriptions()
    print(f"Загружено отчетов: {len(descriptions)}")

    # Создаем контейнер
    print("Создаю JSON-контейнер...")
    json_container = build_json_container(descriptions)

    # Создаем папку data если нет
    os.makedirs('data', exist_ok=True)

    # Сохраняем в файл
    output_path = 'data/json_container.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json_container)

    print(f"\nСоздан: {output_path}")
    print(f"Размер: {len(json_container):,} символов")
    print(f"Оценка токенов: ~{len(json_container) // 3:,}")

if __name__ == "__main__":
    main()
