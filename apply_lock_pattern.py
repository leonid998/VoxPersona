#!/usr/bin/env python3
"""
Скрипт для автоматического применения Lock + timeout паттерна к критическим функциям.

Применяет изменения к:
1. handle_report_view_input()
2. handle_report_rename_name_input()
3. handle_report_delete_confirm()
"""

import re
from pathlib import Path


def add_lock_wrapper(function_text: str, function_name: str) -> str:
    """
    Добавляет async with get_user_lock(chat_id): wrapper к функции.

    Args:
        function_text: Полный текст функции
        function_name: Имя функции для логирования

    Returns:
        Модифицированный текст функции с Lock wrapper
    """
    lines = function_text.split('\n')

    # Найти начало тела функции (после docstring)
    in_docstring = False
    body_start_idx = None

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # Пропускаем def строку
        if stripped.startswith('async def'):
            continue

        # Отслеживаем docstring
        if '"""' in stripped:
            if not in_docstring:
                in_docstring = True
                # Если это однострочный docstring
                if stripped.count('"""') == 2:
                    body_start_idx = idx + 1
                    break
            else:
                in_docstring = False
                body_start_idx = idx + 1
                break

        # Если нет docstring, тело начинается сразу после def
        if not in_docstring and body_start_idx is None and stripped and not stripped.startswith('"""'):
            body_start_idx = idx
            break

    if body_start_idx is None:
        raise ValueError(f"Не удалось найти начало тела функции {function_name}")

    # Определяем базовую индентацию тела функции
    base_indent = len(lines[body_start_idx]) - len(lines[body_start_idx].lstrip())

    # Формируем новые строки
    new_lines = lines[:body_start_idx]

    # Добавляем Lock wrapper
    new_lines.append(' ' * base_indent + '# 🆕 ФАЗА 1.5: Concurrent control - получаем Lock')
    new_lines.append(' ' * base_indent + 'async with get_user_lock(chat_id):')

    # Добавляем timeout check
    new_lines.append(' ' * (base_indent + 4) + '# 🆕 ФАЗА 1.5: Проверка timeout snapshot')
    new_lines.append(' ' * (base_indent + 4) + 'is_valid, error_msg = _check_snapshot_timeout(chat_id)')
    new_lines.append(' ' * (base_indent + 4) + 'if not is_valid:')
    new_lines.append(' ' * (base_indent + 8) + 'await track_and_send(')
    new_lines.append(' ' * (base_indent + 12) + 'chat_id=chat_id,')
    new_lines.append(' ' * (base_indent + 12) + 'app=app,')
    new_lines.append(' ' * (base_indent + 12) + 'text=error_msg,')
    new_lines.append(' ' * (base_indent + 12) + 'reply_markup=chats_menu_markup_dynamic(chat_id),')
    new_lines.append(' ' * (base_indent + 12) + 'message_type="status_message"')
    new_lines.append(' ' * (base_indent + 8) + ')')
    new_lines.append(' ' * (base_indent + 8) + 'return')
    new_lines.append('')

    # Добавляем остальное тело с дополнительными 4 пробелами
    for line in lines[body_start_idx:]:
        if line.strip():  # Не пустая строка
            new_lines.append(' ' * 4 + line)
        else:
            new_lines.append(line)

    return '\n'.join(new_lines)


def extract_function(content: str, function_name: str) -> tuple[str, int, int]:
    """
    Извлекает текст функции из файла.

    Args:
        content: Содержимое файла
        function_name: Имя функции для поиска

    Returns:
        (текст_функции, начальная_позиция, конечная_позиция)
    """
    # Ищем начало функции
    pattern = rf'^async def {re.escape(function_name)}\('
    lines = content.split('\n')

    start_idx = None
    for idx, line in enumerate(lines):
        if re.match(pattern, line):
            start_idx = idx
            break

    if start_idx is None:
        raise ValueError(f"Функция {function_name} не найдена")

    # Ищем конец функции (следующая функция или конец файла)
    end_idx = len(lines)
    indent_level = len(lines[start_idx]) - len(lines[start_idx].lstrip())

    for idx in range(start_idx + 1, len(lines)):
        line = lines[idx]
        if line.strip():  # Не пустая строка
            current_indent = len(line) - len(line.lstrip())
            # Если встретили функцию на том же уровне вложенности
            if current_indent <= indent_level and (line.strip().startswith('async def ') or line.strip().startswith('def ')):
                end_idx = idx
                break

    function_text = '\n'.join(lines[start_idx:end_idx])
    return function_text, start_idx, end_idx


def apply_lock_to_file(file_path: Path, function_names: list[str]) -> None:
    """
    Применяет Lock паттерн к указанным функциям в файле.

    Args:
        file_path: Путь к файлу
        function_names: Список имен функций для модификации
    """
    print(f"📂 Читаю файл: {file_path}")
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Обрабатываем функции в обратном порядке (с конца файла)
    # чтобы не сбивать индексы строк
    function_names_reversed = sorted(
        function_names,
        key=lambda name: extract_function(content, name)[1],
        reverse=True
    )

    modified_content = content

    for func_name in function_names_reversed:
        print(f"\n🔧 Обрабатываю функцию: {func_name}")

        # Извлекаем функцию
        func_text, start_idx, end_idx = extract_function(modified_content, func_name)
        print(f"   Найдена в строках {start_idx + 1}-{end_idx}")

        # Применяем Lock wrapper
        modified_func = add_lock_wrapper(func_text, func_name)

        # Заменяем в файле
        lines_list = modified_content.split('\n')
        new_lines = lines_list[:start_idx] + modified_func.split('\n') + lines_list[end_idx:]
        modified_content = '\n'.join(new_lines)

        print(f"   ✅ Lock паттерн применен")

    # Создаем backup
    backup_path = file_path.with_suffix('.py.backup')
    print(f"\n💾 Создаю backup: {backup_path}")
    backup_path.write_text(content, encoding='utf-8')

    # Сохраняем изменения
    print(f"💾 Сохраняю изменения: {file_path}")
    file_path.write_text(modified_content, encoding='utf-8')

    print(f"\n✅ Успешно применены изменения!")


def main():
    """Основная функция скрипта."""
    # Путь к файлу
    handlers_file = Path(__file__).parent / 'src' / 'handlers_my_reports_v2.py'

    if not handlers_file.exists():
        print(f"❌ Файл не найден: {handlers_file}")
        return 1

    # Функции для модификации
    target_functions = [
        'handle_report_view_input',
        'handle_report_rename_name_input',
        'handle_report_delete_confirm'
    ]

    print("🚀 Запуск применения Lock паттерна")
    print(f"📁 Целевой файл: {handlers_file}")
    print(f"🎯 Функции для модификации: {', '.join(target_functions)}")
    print()

    try:
        apply_lock_to_file(handlers_file, target_functions)
        return 0
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
