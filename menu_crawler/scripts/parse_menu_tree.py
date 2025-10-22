#!/usr/bin/env python3
"""
Автоматический парсер COMPLETE_MENU_TREE.md → menu_graph.json
Извлекает узлы и связи для menu_crawler
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


class MenuTreeParser:
    """Парсер дерева меню из Markdown в JSON граф"""

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: List[dict] = []
        self.callback_patterns: Set[str] = set()

    def parse_markdown(self, md_content: str) -> Tuple[Dict, List]:
        """Парсинг Markdown контента"""

        # Регулярные выражения для извлечения данных
        callback_pattern = r'►\s*([a-z_]+(?:\|\|[a-z_{}]+)?)'
        menu_section_pattern = r'^##\s+(.+)$'
        button_pattern = r'([📱⚙️❓📁🔐👥🎫⚙️🆕📊📄✏️🚫🗑️➕📜🕒💡🛠️📝🔙🏠🏨🍽️🏢⚡🔬✅❌ℹ️📁🎵👁️]+)\s+(.+?)\s+[─►]+\s*([a-z_]+(?:\|\|[^│\n\s]+)?)'

        lines = md_content.split('\n')
        current_section = None
        current_parent = None
        depth_stack = []  # Стек глубины вложенности

        # Предопределенные узлы
        self._add_node("menu_main", "menu", 0, "Главное меню")

        for i, line in enumerate(lines):
            line = line.strip()

            # Определение секции
            section_match = re.match(menu_section_pattern, line)
            if section_match:
                current_section = section_match.group(1)
                continue

            # Поиск callback_data паттернов
            callback_matches = re.findall(callback_pattern, line)
            for callback in callback_matches:
                # Очистка от динамических параметров
                clean_callback = self._clean_callback(callback)
                self.callback_patterns.add(clean_callback)

                # Определение типа узла
                node_type = self._determine_node_type(clean_callback)
                depth = self._calculate_depth(line)
                description = self._extract_description(line, callback)

                # Добавление узла
                self._add_node(clean_callback, node_type, depth, description)

            # Поиск кнопок с переходами
            button_matches = re.findall(button_pattern, line)
            for emoji, button_text, callback_data in button_matches:
                clean_callback = self._clean_callback(callback_data)
                full_button_text = f"{emoji} {button_text}".strip()

                # Определение родительского узла
                parent_node = self._determine_parent(line, current_section, depth_stack)

                # Добавление связи
                if parent_node:
                    condition = self._check_condition(current_section, clean_callback)
                    self._add_edge(parent_node, clean_callback, callback_data, full_button_text, condition)

        return self.nodes, self.edges

    def _add_node(self, node_id: str, node_type: str, depth: int, description: str):
        """Добавление узла в граф"""
        if node_id not in self.nodes:
            node = {
                "type": node_type,
                "depth": depth,
                "description": description
            }

            # Динамические узлы
            if "||" in node_id and "{" not in node_id:
                node["dynamic"] = True

            # FSM узлы
            if node_id in ["new_chat", "rename_chat", "report_rename", "edit_audio_number",
                          "edit_date", "edit_employee", "edit_place_name", "edit_city",
                          "edit_zone_name", "edit_client", "access_search_user",
                          "invite_password_input", "change_password_current"]:
                node["fsm"] = True

            self.nodes[node_id] = node

    def _add_edge(self, from_node: str, to_node: str, callback_data: str, button_text: str, condition: str = None):
        """Добавление связи между узлами"""
        edge = {
            "from": from_node,
            "to": to_node,
            "callback_data": callback_data,
            "button_text": button_text
        }

        if condition:
            edge["condition"] = condition

        # Проверка на дубликаты
        if not any(e["from"] == from_node and e["to"] == to_node and e["callback_data"] == callback_data
                  for e in self.edges):
            self.edges.append(edge)

    def _clean_callback(self, callback: str) -> str:
        """Очистка callback_data от динамических параметров"""
        # Удаление {id}, {user_id}, {conversation_id} и т.д.
        callback = re.sub(r'\{[^}]+\}', '', callback)
        # Удаление ||page||{n}
        callback = re.sub(r'\|\|page\|\|\d+', '', callback)
        # Удаление trailing ||
        callback = callback.rstrip('|')
        return callback

    def _determine_node_type(self, callback: str) -> str:
        """Определение типа узла по callback_data"""
        if callback.startswith("menu_"):
            return "menu"
        elif callback.startswith("view") or callback.startswith("show"):
            return "view"
        elif callback.startswith("access_user_details") or callback.startswith("access_invite_details"):
            return "view"
        elif "actions" in callback or "confirm" in callback or "delete" in callback:
            return "action"
        elif callback.startswith("edit_") or callback.startswith("rename_"):
            return "action"
        elif callback.startswith("help_"):
            return "view"
        else:
            return "action"

    def _calculate_depth(self, line: str) -> int:
        """Расчет глубины вложенности по отступам"""
        indent = len(line) - len(line.lstrip('│├└─ '))
        return min(indent // 4, 6)  # Максимум 6 уровней

    def _extract_description(self, line: str, callback: str) -> str:
        """Извлечение описания узла"""
        # Удаление символов дерева и callback
        clean_line = re.sub(r'[│├└─►\s]+', ' ', line)
        clean_line = clean_line.replace(callback, '').strip()

        # Удаление emoji
        clean_line = re.sub(r'[\U0001F300-\U0001F9FF]+', '', clean_line).strip()

        return clean_line or callback.replace('_', ' ').title()

    def _determine_parent(self, line: str, section: str, depth_stack: List) -> str:
        """Определение родительского узла"""
        # Логика определения родителя на основе секции и контекста
        if "Главное меню" in section or not section:
            return "menu_main"
        elif "ЧАТЫ" in section.upper():
            return "menu_chats"
        elif "СИСТЕМНАЯ" in section.upper():
            return "menu_system"
        elif "НАСТРОЙКИ ДОСТУПА" in section.upper():
            return "menu_access"
        elif "ПОМОЩЬ" in section.upper():
            return "menu_help"
        else:
            return "menu_main"

    def _check_condition(self, section: str, callback: str) -> str:
        """Проверка условной видимости (super_admin)"""
        if "ДОСТУПА" in section.upper() or callback.startswith("access_"):
            return "user_role == super_admin"
        return None

    def build_graph_structure(self):
        """Построение полной структуры графа с правильными связями"""

        # Основные меню от menu_main
        main_children = {
            "menu_chats": "📱 Чаты/Диалоги",
            "menu_system": "⚙️ Системная",
            "menu_help": "❓ Помощь"
        }

        for child, button_text in main_children.items():
            self._add_node(child, "menu", 1, button_text.split()[-1])
            self._add_edge("menu_main", child, child, button_text)

        # Меню чатов
        chats_children = {
            "new_chat": "🆕 Новый чат",
            "show_stats": "📊 Статистика",
            "show_my_reports": "📄 Мои отчеты"
        }

        for child, button_text in chats_children.items():
            node_type = "action" if child == "new_chat" else "view"
            self._add_node(child, node_type, 2, button_text.split(maxsplit=1)[-1])
            self._add_edge("menu_chats", child, child, button_text)

        # Динамические чаты
        self._add_node("chat_actions", "action", 2, "Действия с чатом", )
        self.nodes["chat_actions"]["dynamic"] = True
        self._add_edge("menu_chats", "chat_actions", "chat_actions||{conversation_id}", "📝 [Название чата]")

        # Действия с чатом
        chat_actions_children = {
            "confirm_switch": "В Чат",
            "rename_chat": "✏️ Переименовать",
            "delete_chat": "🗑️ Удалить"
        }

        for child, button_text in chat_actions_children.items():
            self._add_node(child, "action", 3, button_text)
            if "||" in child:
                callback = f"{child}||{{id}}"
            else:
                callback = child
            self._add_edge("chat_actions", child, callback, button_text)

        # Отчеты
        self._add_node("send_report", "action", 3, "Отправить отчет")
        self.nodes["send_report"]["dynamic"] = True
        self._add_edge("show_my_reports", "send_report", "send_report||{report_id}", "📄 [Название отчета]")

        # Действия с отчетом
        report_actions = {
            "report_view": "👁️ Просмотр",
            "report_rename": "✏️ Переименовать",
            "report_delete": "🗑️ Удалить"
        }

        for child, button_text in report_actions.items():
            self._add_node(child, "action", 4, button_text)
            self._add_edge("send_report", child, child, button_text)

        # Системная
        system_children = {
            "menu_storage": "📁 Хранилище",
            "menu_access": "🔐 Настройки доступа"
        }

        for child, button_text in system_children.items():
            self._add_node(child, "menu", 2, button_text.split()[-1])
            condition = "user_role == super_admin" if child == "menu_access" else None
            self._add_edge("menu_system", child, child, button_text, condition)

        # Хранилище
        self._add_node("view||audio", "view", 3, "Аудио файлы")
        self._add_edge("menu_storage", "view||audio", "view||audio", "📁 Аудио файлы")

        # Настройки доступа (super_admin only)
        access_children = {
            "access_users_menu": "👥 Управление пользователями",
            "access_invitations_menu": "🎫 Приглашения",
            "access_security_menu": "⚙️ Настройки безопасности"
        }

        for child, button_text in access_children.items():
            self._add_node(child, "menu", 3, button_text.split(maxsplit=1)[-1])
            self._add_edge("menu_access", child, child, button_text, "user_role == super_admin")

        # Управление пользователями
        users_children = {
            "access_list_users": "📊 Список пользователей",
            "access_edit_user_select": "✏️ Редактировать пользователя",
            "access_block_user_select": "🚫 Заблокировать/Разблокировать",
            "access_delete_user_select": "🗑️ Удалить пользователя"
        }

        for child, button_text in users_children.items():
            self._add_node(child, "view" if "list" in child else "action", 4, button_text.split(maxsplit=1)[-1])
            self._add_edge("access_users_menu", child, child, button_text, "user_role == super_admin")

        # Динамические пользователи
        self._add_node("access_user_details", "view", 5, "Детали пользователя")
        self.nodes["access_user_details"]["dynamic"] = True
        self._add_edge("access_list_users", "access_user_details", "access_user_details||{user_id}",
                      "✅ [Username]", "user_role == super_admin")

        # Приглашения
        invitations_children = {
            "access_create_invite_admin": "➕ Создать приглашение администратора",
            "access_create_invite_user": "➕ Создать приглашение пользователя",
            "access_list_invites": "📜 Активные приглашения"
        }

        for child, button_text in invitations_children.items():
            self._add_node(child, "action" if "create" in child else "view", 4, button_text.split(maxsplit=1)[-1])
            self._add_edge("access_invitations_menu", child, child, button_text, "user_role == super_admin")

        # Динамические приглашения
        self._add_node("access_invite_details", "view", 5, "Детали приглашения")
        self.nodes["access_invite_details"]["dynamic"] = True
        self._add_edge("access_list_invites", "access_invite_details", "access_invite_details||{invite_code}",
                      "🎫 [CODE]", "user_role == super_admin")

        # Безопасность
        security_children = {
            "access_cleanup_settings": "🕒 Автоочистка сообщений",
            "access_password_policy": "🔐 Политика паролей",
            "access_audit_log": "📝 Журнал действий"
        }

        for child, button_text in security_children.items():
            self._add_node(child, "menu", 4, button_text.split(maxsplit=1)[-1])
            self._add_edge("access_security_menu", child, child, button_text, "user_role == super_admin")

        # Помощь
        help_children = {
            "help_about": "📱 О боте",
            "help_functions": "🛠️ Функции",
            "help_stats": "📊 Статистика",
            "help_tips": "💡 Советы"
        }

        for child, button_text in help_children.items():
            self._add_node(child, "view", 2, button_text.split(maxsplit=1)[-1])
            self._add_edge("menu_help", child, child, button_text)

        # Кнопки "Назад"
        back_buttons = [
            ("menu_chats", "menu_main", "🔙 Назад"),
            ("menu_system", "menu_main", "🔙 Назад"),
            ("menu_help", "menu_main", "🔙 Назад"),
            ("menu_storage", "menu_system", "🔙 Назад"),
            ("menu_access", "menu_system", "🔙 Назад"),
            ("chat_actions", "menu_chats", "🔙 Назад"),
            ("show_my_reports", "menu_chats", "🔙 Назад"),
            ("access_users_menu", "menu_access", "🔙 Назад"),
            ("access_invitations_menu", "menu_access", "🔙 Назад"),
            ("access_security_menu", "menu_access", "🔙 Назад"),
        ]

        for from_node, to_node, button_text in back_buttons:
            condition = "user_role == super_admin" if from_node.startswith("access_") else None
            self._add_edge(from_node, to_node, to_node, button_text, condition)

    def generate_json(self) -> dict:
        """Генерация финального JSON"""
        return {
            "nodes": self.nodes,
            "edges": self.edges
        }

    def validate_graph(self) -> Tuple[bool, List[str]]:
        """Валидация графа"""
        errors = []

        # Проверка связности
        reachable = set()
        stack = ["menu_main"]

        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)

            # Найти всех детей
            for edge in self.edges:
                if edge["from"] == node and edge["to"] not in reachable:
                    stack.append(edge["to"])

        # Изолированные узлы
        all_nodes = set(self.nodes.keys())
        isolated = all_nodes - reachable

        if isolated:
            errors.append(f"Изолированные узлы (недостижимы от menu_main): {isolated}")

        # Проверка существования узлов в edges
        for edge in self.edges:
            if edge["from"] not in self.nodes:
                errors.append(f"Узел '{edge['from']}' в edge не существует в nodes")
            if edge["to"] not in self.nodes:
                errors.append(f"Узел '{edge['to']}' в edge не существует в nodes")

        return len(errors) == 0, errors


def main():
    """Главная функция"""

    # Пути к файлам
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    md_file = project_root / "TASKS" / "00005_20251014_HRYHG" / "Implemt" / "menu_crawler" / "COMPLETE_MENU_TREE.md"
    output_file = project_root / "menu_crawler" / "config" / "menu_graph.json"

    print("🌳 ПАРСЕР ДЕРЕВА МЕНЮ VOXPERSONA")
    print("=" * 60)

    # Чтение Markdown файла
    print(f"\n📖 Чтение: {md_file}")
    if not md_file.exists():
        print(f"❌ ОШИБКА: Файл не найден: {md_file}")
        return

    md_content = md_file.read_text(encoding='utf-8')
    print(f"✅ Прочитано {len(md_content)} символов, {len(md_content.splitlines())} строк")

    # Парсинг
    print("\n🔍 Парсинг структуры меню...")
    parser = MenuTreeParser()
    parser.parse_markdown(md_content)
    parser.build_graph_structure()

    # Статистика
    print(f"\n📊 СТАТИСТИКА:")
    print(f"   Узлов (nodes): {len(parser.nodes)}")
    print(f"   Связей (edges): {len(parser.edges)}")
    print(f"   Уникальных callback_data: {len(parser.callback_patterns)}")

    # Разбивка по типам узлов
    node_types = {}
    for node in parser.nodes.values():
        node_type = node["type"]
        node_types[node_type] = node_types.get(node_type, 0) + 1

    print(f"\n   По типам узлов:")
    for node_type, count in sorted(node_types.items()):
        print(f"      {node_type}: {count}")

    # Динамические узлы
    dynamic_count = sum(1 for node in parser.nodes.values() if node.get("dynamic"))
    fsm_count = sum(1 for node in parser.nodes.values() if node.get("fsm"))
    print(f"\n   Динамические узлы: {dynamic_count}")
    print(f"   FSM узлы: {fsm_count}")

    # Валидация
    print("\n🔍 Валидация графа...")
    is_valid, errors = parser.validate_graph()

    if is_valid:
        print("✅ Граф валиден!")
    else:
        print("⚠️ Обнаружены проблемы:")
        for error in errors:
            print(f"   - {error}")

    # Генерация JSON
    print(f"\n💾 Генерация JSON...")
    graph_data = parser.generate_json()

    # Создание директории если не существует
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Сохранение
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Сохранено: {output_file}")
    print(f"   Размер: {output_file.stat().st_size / 1024:.2f} KB")

    # Примеры узлов
    print(f"\n📋 ПРИМЕРЫ УЗЛОВ:")
    example_nodes = ["menu_main", "menu_chats", "chat_actions", "access_user_details", "send_report"]
    for node_id in example_nodes:
        if node_id in parser.nodes:
            node = parser.nodes[node_id]
            print(f"\n   {node_id}:")
            print(f"      type: {node['type']}")
            print(f"      depth: {node['depth']}")
            print(f"      description: {node['description']}")
            if node.get("dynamic"):
                print(f"      dynamic: True")
            if node.get("fsm"):
                print(f"      fsm: True")

    # Примеры связей
    print(f"\n🔗 ПРИМЕРЫ СВЯЗЕЙ:")
    for i, edge in enumerate(parser.edges[:10]):
        condition_str = f" [CONDITION: {edge['condition']}]" if edge.get("condition") else ""
        print(f"   {edge['from']} → {edge['to']}{condition_str}")
        print(f"      callback: {edge['callback_data']}")
        print(f"      button: {edge['button_text']}")

    print("\n" + "=" * 60)
    print("✅ ГОТОВО! menu_graph.json создан успешно.")
    print("\n📌 ИТОГОВЫЕ МЕТРИКИ:")
    print(f"   ✅ Узлов: {len(parser.nodes)}")
    print(f"   ✅ Связей: {len(parser.edges)}")
    print(f"   ✅ Callback паттернов: {len(parser.callback_patterns)}")
    print(f"   ✅ Граф связен: {is_valid}")


if __name__ == "__main__":
    main()
