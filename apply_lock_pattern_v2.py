#!/usr/bin/env python3
"""
Улучшенный скрипт для применения Lock + timeout паттерна.
Версия 2: работает с "чистой" версией файла (без предыдущих Lock wrapper).
"""

import re
from pathlib import Path


def wrap_function_body_with_lock(lines: list[str], start_idx: int) -> list[str]:
    """
    Оборачивает тело функции в async with get_user_lock().

    Args:
        lines: Список строк файла
        start_idx: Индекс строки с def функции

    Returns:
        Новый список строк с примененным Lock паттерном
    """
    # Найти конец docstring и начало тела функции
    in_docstring = False
    body_start = None

    for idx in range(start_idx + 1, len(lines)):
        line = lines[idx]
        stripped = line.strip()

        if '"""' in stripped:
            if not in_docstring:
                in_docstring = True
                # Однострочный docstring?
                if stripped.count('"""') == 2:
                    body_start = idx + 1
                    break
            else:
                in_docstring = False
                body_start = idx + 1
                break

        # Нет docstring - тело начинается сразу
        if not in_docstring and stripped and not stripped.startswith('"""'):
            body_start = idx
            break

    if body_start is None:
        raise ValueError(f"Cannot find function body start at line {start_idx}")

    # Определить базовую индентацию тела функции
    base_indent = len(lines[body_start]) - len(lines[body_start].lstrip())

    # Формируем новый список строк
    result = []

    # Строки до тела функции (включая def и docstring)
    result.extend(lines[:body_start])

    # Добавляем Lock wrapper
    result.append(' ' * base_indent + '# 🆕 ФАЗА 1.5: Concurrent control - получаем Lock')
    result.append(' ' * base_indent + 'async with get_user_lock(chat_id):')

    # Добавляем timeout check
    result.append(' ' * (base_indent + 4) + '# 🆕 ФАЗА 1.5: Проверка timeout snapshot')
    result.append(' ' * (base_indent + 4) + 'is_valid, error_msg = _check_snapshot_timeout(chat_id)')
    result.append(' ' * (base_indent + 4) + 'if not is_valid:')
    result.append(' ' * (base_indent + 8) + 'await track_and_send(')
    result.append(' ' * (base_indent + 12) + 'chat_id=chat_id,')
    result.append(' ' * (base_indent + 12) + 'app=app,')
    result.append(' ' * (base_indent + 12) + 'text=error_msg,')
    result.append(' ' * (base_indent + 12) + 'reply_markup=chats_menu_markup_dynamic(chat_id),')
    result.append(' ' * (base_indent + 12) + 'message_type="status_message"')
    result.append(' ' * (base_indent + 8) + ')')
    result.append(' ' * (base_indent + 8) + 'return')
    result.append('')

    # Находим конец текущей функции
    func_end = None
    for idx in range(body_start, len(lines)):
        line = lines[idx]
        stripped = line.strip()

        # Конец функции - следующая функция на том же уровне или конец файла
        if stripped and not line.startswith(' ') and idx > body_start:
            func_end = idx
            break

        # Другая функция на том же уровне вложенности
        current_indent = len(line) - len(line.lstrip()) if line.strip() else 999
        if current_indent <= base_indent - 4 and (stripped.startswith('async def ') or stripped.startswith('def ')) and idx > body_start:
            func_end = idx
            break

    if func_end is None:
        func_end = len(lines)

    # Добавляем тело функции с дополнительными 4 пробелами
    for line in lines[body_start:func_end]:
        if line.strip():  # Не пустая строка - добавляем indent
            result.append(' ' * 4 + line)
        else:  # Пустая строка - оставляем как есть
            result.append(line)

    # Добавляем остальное содержимое файла
    result.extend(lines[func_end:])

    return result


def apply_lock_to_function(content: str, function_name: str) -> str:
    """
    Применяет Lock паттерн к одной функции.

    Args:
        content: Содержимое файла
        function_name: Имя функции

    Returns:
        Модифицированное содержимое файла
    """
    lines = content.split('\n')

    # Найти начало функции
    pattern = rf'^async def {re.escape(function_name)}\('
    func_start = None

    for idx, line in enumerate(lines):
        if re.match(pattern, line):
            func_start = idx
            break

    if func_start is None:
        raise ValueError(f"Function {function_name} not found")

    print(f"   Найдена в строке {func_start + 1}")

    # Применяем Lock wrapper
    new_lines = wrap_function_body_with_lock(lines, func_start)

    return '\n'.join(new_lines)


def main():
    """Основная функция."""
    handlers_file = Path(__file__).parent / 'src' / 'handlers_my_reports_v2.py'

    if not handlers_file.exists():
        print(f"❌ Файл не найден: {handlers_file}")
        return 1

    # Функции для модификации (в порядке от конца файла к началу)
    target_functions = [
        'handle_report_delete_confirm',
        'handle_report_rename_name_input',
        'handle_report_view_input'
    ]

    print("🚀 Запуск применения Lock паттерна v2")
    print(f"📁 Файл: {handlers_file}")
    print(f"🎯 Функции: {', '.join(target_functions)}\n")

    try:
        # Создаем backup
        backup_path = handlers_file.with_suffix('.py.backup2')
        print(f"💾 Создаю backup: {backup_path}")
        content = handlers_file.read_text(encoding='utf-8')
        backup_path.write_text(content, encoding='utf-8')

        # Применяем к каждой функции
        for func_name in target_functions:
            print(f"\n🔧 Обрабатываю функцию: {func_name}")
            content = apply_lock_to_function(content, func_name)
            print(f"   ✅ Lock паттерн применен")

        # Сохраняем изменения
        print(f"\n💾 Сохраняю изменения: {handlers_file}")
        handlers_file.write_text(content, encoding='utf-8')

        print("\n✅ Успешно применены изменения!")
        return 0

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
