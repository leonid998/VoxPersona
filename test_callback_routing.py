"""
Тестирование callback роутинга для Phase 2 Authorization System.

Проверяет:
1. Все кнопки из access_markups.py имеют обработчики в handlers.py
2. Все обработчики из handlers.py имеют соответствующие кнопки
3. Строит граф навигации меню
4. Находит мёртвые кнопки (callback без handler)

Автор: VoxPersona Team
Дата: 17 октября 2025
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict


@dataclass
class CallbackButton:
    """Кнопка с callback_data."""
    callback_data: str
    source_function: str  # Функция в access_markups.py
    is_dynamic: bool  # Параметризованная кнопка (содержит ||)
    pattern: str  # Паттерн для сопоставления


@dataclass
class CallbackHandler:
    """Обработчик callback в handlers.py."""
    callback_pattern: str
    handler_function: str
    line_number: int
    is_dynamic: bool


@dataclass
class RoutingIssue:
    """Проблема роутинга."""
    issue_type: str  # "dead_button", "unused_handler", "mismatch"
    callback_data: str
    details: str


class CallbackRoutingTester:
    """Тестер роутинга callback."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.markups_file = project_root / "src" / "access_markups.py"
        self.handlers_file = project_root / "src" / "handlers.py"

        # Хранилище данных
        self.buttons: List[CallbackButton] = []
        self.handlers: List[CallbackHandler] = []
        self.issues: List[RoutingIssue] = []
        self.navigation_graph: Dict[str, List[str]] = {}

    def extract_buttons_from_markups(self) -> List[CallbackButton]:
        """Извлекает все callback_data из access_markups.py."""
        print("📋 Извлечение кнопок из access_markups.py...")

        content = self.markups_file.read_text(encoding="utf-8")

        # Регулярка для InlineKeyboardButton с callback_data
        pattern = r'InlineKeyboardButton\([^)]*callback_data=["\'](.*?)["\']'
        matches = re.findall(pattern, content)

        # Также ищем функции, где эти кнопки определены
        function_pattern = r'def (\w+)\([^)]*\):'
        functions = re.findall(function_pattern, content)

        buttons = []
        current_function = None

        for line_num, line in enumerate(content.split("\n"), 1):
            # Определяем текущую функцию
            func_match = re.search(r'def (\w+)\(', line)
            if func_match:
                current_function = func_match.group(1)

            # Ищем callback_data в строке
            callback_match = re.search(r'callback_data=["\'](.*?)["\']', line)
            if callback_match and current_function:
                callback_data = callback_match.group(1)

                # Определяем паттерн (заменяем переменные на *)
                is_dynamic = "||" in callback_data or "{" in callback_data
                pattern = self._normalize_callback_pattern(callback_data)

                buttons.append(CallbackButton(
                    callback_data=callback_data,
                    source_function=current_function,
                    is_dynamic=is_dynamic,
                    pattern=pattern
                ))

        print(f"✅ Найдено {len(buttons)} кнопок")
        return buttons

    def extract_handlers_from_handlers_py(self) -> List[CallbackHandler]:
        """Извлекает обработчики callback из handlers.py (lines 1363-1469)."""
        print("📋 Извлечение обработчиков из handlers.py...")

        content = self.handlers_file.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Интересует блок 1363-1469 (Auth callback routing)
        auth_block = lines[1362:1469]  # Python 0-indexed

        handlers = []

        for i, line in enumerate(auth_block, start=1363):
            line_stripped = line.strip()

            # Простой callback: elif data == "menu_access":
            simple_match = re.search(r'elif data == ["\'](.*?)["\']:', line_stripped)
            if simple_match:
                callback = simple_match.group(1)
                handler_match = re.search(r'await (\w+)\(', line_stripped)
                handler_func = handler_match.group(1) if handler_match else "Unknown"

                handlers.append(CallbackHandler(
                    callback_pattern=callback,
                    handler_function=handler_func,
                    line_number=i,
                    is_dynamic=False
                ))

            # Динамический callback: elif data.startswith("access_user_details||"):
            dynamic_match = re.search(r'elif data\.startswith\(["\'](.*?)["\']', line_stripped)
            if dynamic_match:
                callback_prefix = dynamic_match.group(1)
                handler_match = re.search(r'await (\w+)\(', line_stripped)
                handler_func = handler_match.group(1) if handler_match else "Unknown"

                handlers.append(CallbackHandler(
                    callback_pattern=callback_prefix,
                    handler_function=handler_func,
                    line_number=i,
                    is_dynamic=True
                ))

        print(f"✅ Найдено {len(handlers)} обработчиков")
        return handlers

    def _normalize_callback_pattern(self, callback: str) -> str:
        """
        Нормализует callback для сопоставления.

        Примеры:
        - "access_user_details||{user_id}" → "access_user_details||"
        - f"access_filter||{role}" → "access_filter||"
        """
        # Заменяем f-string переменные
        pattern = re.sub(r'\{[^}]+\}', '*', callback)

        # Заменяем динамические части
        if "||" in pattern:
            pattern = pattern.split("||")[0] + "||"

        return pattern

    def check_routing(self):
        """Проверяет соответствие кнопок и обработчиков."""
        print("\n🔍 Проверка соответствия callback роутинга...")

        # 1. Проверка: есть ли обработчики для всех кнопок
        for button in self.buttons:
            # Пропускаем информационные кнопки
            if button.callback_data in ["access_page_info"]:
                continue

            # Ищем соответствующий обработчик
            found = False
            for handler in self.handlers:
                if self._match_callback(button, handler):
                    found = True
                    break

            if not found:
                self.issues.append(RoutingIssue(
                    issue_type="dead_button",
                    callback_data=button.callback_data,
                    details=f"Кнопка в {button.source_function}, но нет обработчика в handlers.py"
                ))

        # 2. Проверка: есть ли кнопки для всех обработчиков
        for handler in self.handlers:
            found = False
            for button in self.buttons:
                if self._match_callback(button, handler):
                    found = True
                    break

            if not found:
                self.issues.append(RoutingIssue(
                    issue_type="unused_handler",
                    callback_data=handler.callback_pattern,
                    details=f"Обработчик {handler.handler_function} (line {handler.line_number}), но нет кнопки"
                ))

        print(f"✅ Проверка завершена: найдено {len(self.issues)} проблем")

    def _match_callback(self, button: CallbackButton, handler: CallbackHandler) -> bool:
        """Проверяет соответствие кнопки и обработчика."""
        if not button.is_dynamic and not handler.is_dynamic:
            # Простое сопоставление
            return button.callback_data == handler.callback_pattern

        if button.is_dynamic and handler.is_dynamic:
            # Динамическое сопоставление
            button_prefix = button.callback_data.split("||")[0] + "||"
            handler_prefix = handler.callback_pattern

            # Убираем trailing || из handler если есть
            if handler_prefix.endswith("||"):
                handler_prefix = handler_prefix[:-2] + "||"

            return button_prefix == handler_prefix

        if button.is_dynamic and not handler.is_dynamic:
            # Кнопка динамическая, обработчик простой - не совпадает
            return False

        if not button.is_dynamic and handler.is_dynamic:
            # Кнопка простая, обработчик динамический - проверяем prefix
            return button.callback_data.startswith(handler.callback_pattern.rstrip("||"))

        return False

    def build_navigation_graph(self):
        """Строит граф навигации меню."""
        print("\n🗺️ Построение графа навигации...")

        # Группируем кнопки по функциям (меню)
        for button in self.buttons:
            menu = button.source_function
            callback = button.callback_data

            if menu not in self.navigation_graph:
                self.navigation_graph[menu] = []

            self.navigation_graph[menu].append(callback)

        print(f"✅ Построено {len(self.navigation_graph)} меню")

    def generate_report(self) -> Dict:
        """Генерирует JSON отчёт."""
        print("\n📄 Генерация отчёта...")

        # Группировка проблем по типам
        dead_buttons = [issue for issue in self.issues if issue.issue_type == "dead_button"]
        unused_handlers = [issue for issue in self.issues if issue.issue_type == "unused_handler"]

        report = {
            "test_info": {
                "project": "VoxPersona Phase 2 Authorization",
                "test_type": "Callback Routing Validation",
                "markups_file": str(self.markups_file),
                "handlers_file": str(self.handlers_file),
            },
            "statistics": {
                "total_buttons": len(self.buttons),
                "total_handlers": len(self.handlers),
                "total_issues": len(self.issues),
                "dead_buttons_count": len(dead_buttons),
                "unused_handlers_count": len(unused_handlers),
            },
            "issues": {
                "dead_buttons": [asdict(issue) for issue in dead_buttons],
                "unused_handlers": [asdict(issue) for issue in unused_handlers],
            },
            "navigation_graph": self.navigation_graph,
            "buttons": [asdict(btn) for btn in self.buttons],
            "handlers": [asdict(h) for h in self.handlers],
        }

        return report

    def run(self) -> Dict:
        """Запускает полный цикл тестирования."""
        print("=" * 60)
        print(" 🧪 Тестирование Callback Роутинга")
        print("=" * 60)
        print()

        # 1. Извлечение кнопок
        self.buttons = self.extract_buttons_from_markups()

        # 2. Извлечение обработчиков
        self.handlers = self.extract_handlers_from_handlers_py()

        # 3. Проверка соответствия
        self.check_routing()

        # 4. Построение графа
        self.build_navigation_graph()

        # 5. Генерация отчёта
        report = self.generate_report()

        return report


def main():
    """Главная функция."""
    project_root = Path(__file__).parent

    tester = CallbackRoutingTester(project_root)
    report = tester.run()

    # Сохранение отчёта
    output_file = project_root / "callback_routing_test_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📄 Отчёт сохранён: {output_file}")
    print()
    print("=" * 60)
    print(" 📊 Результаты тестирования")
    print("=" * 60)
    print(f"✅ Всего кнопок: {report['statistics']['total_buttons']}")
    print(f"✅ Всего обработчиков: {report['statistics']['total_handlers']}")
    print(f"❌ Всего проблем: {report['statistics']['total_issues']}")
    print()

    if report['statistics']['dead_buttons_count'] > 0:
        print(f"🔴 Мёртвые кнопки (без обработчиков): {report['statistics']['dead_buttons_count']}")
        for issue in report['issues']['dead_buttons'][:5]:  # Показываем первые 5
            print(f"   - {issue['callback_data']}")
            print(f"     {issue['details']}")
        print()

    if report['statistics']['unused_handlers_count'] > 0:
        print(f"🟡 Неиспользуемые обработчики (без кнопок): {report['statistics']['unused_handlers_count']}")
        for issue in report['issues']['unused_handlers'][:5]:
            print(f"   - {issue['callback_data']}")
            print(f"     {issue['details']}")
        print()

    if report['statistics']['total_issues'] == 0:
        print("🎉 Все callback правильно роутятся! Проблем не найдено.")
    else:
        print(f"⚠️ Обнаружено {report['statistics']['total_issues']} проблем роутинга.")
        print("   Смотрите полный отчёт в callback_routing_test_report.json")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
