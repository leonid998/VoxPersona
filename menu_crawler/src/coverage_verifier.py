"""
Coverage verifier для проверки полноты обхода меню VoxPersona.

Сравнивает ожидаемый граф меню (menu_graph.json) с фактически собранным графом
и вычисляет метрики покрытия и UX качества навигации.
"""

from collections import deque
from typing import Any

import structlog

logger = structlog.get_logger()


class CoverageVerifier:
    """
    Проверяет покрытие меню сравнением expected_graph и actual_graph.

    Вычисляет метрики покрытия:
    - Процент посещенных узлов
    - Недостижимые узлы
    - Недокументированные узлы

    Метрики UX:
    - Максимальная глубина навигации
    - Узлы на глубине > 4
    - Узлы без кнопки "Назад"
    """

    def __init__(self, expected_graph: dict[str, Any], actual_graph: dict[str, Any]) -> None:
        """
        Инициализация верификатора.

        Args:
            expected_graph: Ожидаемый граф из menu_graph.json
            actual_graph: Фактически собранный граф от navigator
        """
        self.expected_graph = expected_graph
        self.actual_graph = actual_graph

        logger.info(
            "coverage_verifier_initialized",
            expected_nodes=len(expected_graph.get("nodes", {})),
            actual_nodes=len(actual_graph.get("nodes", {}))
        )

    def verify(self) -> dict[str, Any]:
        """
        Выполняет полную верификацию покрытия меню.

        Returns:
            dict: Результаты верификации с метриками покрытия и UX
        """
        logger.info("coverage_verification_started")

        expected_nodes = set(self.expected_graph.get("nodes", {}).keys())
        actual_nodes = set(self.actual_graph.get("nodes", {}).keys())

        total_expected = len(expected_nodes)
        total_visited = len(actual_nodes)

        # Базовые метрики покрытия
        coverage_percent = (total_visited / total_expected * 100) if total_expected > 0 else 0.0
        unreachable_nodes = sorted(list(expected_nodes - actual_nodes))
        undocumented_nodes = sorted(list(actual_nodes - expected_nodes))

        logger.info(
            "coverage_calculated",
            coverage_percent=coverage_percent,
            total_expected=total_expected,
            total_visited=total_visited
        )

        if unreachable_nodes:
            logger.warning(
                "unreachable_nodes_found",
                count=len(unreachable_nodes),
                nodes=unreachable_nodes
            )

        # UX метрики
        max_depth = self._calculate_max_depth()
        deep_nodes = self._find_nodes_over_depth(threshold=4)
        nodes_without_back = self._find_nodes_without_back()

        # Определение статуса
        if coverage_percent == 100.0 and len(unreachable_nodes) == 0:
            status = "PASS"
        elif coverage_percent >= 90.0 and len(unreachable_nodes) == 0:
            status = "PARTIAL"
        else:
            status = "FAIL"

        result = {
            "total_expected": total_expected,
            "total_visited": total_visited,
            "coverage_percent": round(coverage_percent, 2),
            "unreachable_nodes": unreachable_nodes,
            "undocumented_nodes": undocumented_nodes,
            "max_depth": max_depth,
            "deep_nodes": deep_nodes,
            "nodes_without_back_button": nodes_without_back,
            "status": status
        }

        logger.info(
            "coverage_verification_completed",
            status=status,
            coverage_percent=result["coverage_percent"],
            max_depth=max_depth,
            deep_nodes_count=len(deep_nodes),
            nodes_without_back_count=len(nodes_without_back)
        )

        return result

    def _calculate_max_depth(self) -> int:
        """
        Вычисляет максимальную глубину навигации от menu_main.

        Использует BFS обход actual_graph начиная с menu_main.

        Returns:
            int: Максимальная найденная глубина
        """
        nodes = self.actual_graph.get("nodes", {})
        edges = self.actual_graph.get("edges", [])

        if "menu_main" not in nodes:
            logger.warning("max_depth_calculation_failed", reason="menu_main not found")
            return 0

        # Построение adjacency list
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            from_node = edge.get("from")
            to_node = edge.get("to")
            if from_node and to_node:
                adjacency.setdefault(from_node, []).append(to_node)

        # BFS с подсчетом глубины
        queue: deque[tuple[str, int]] = deque([("menu_main", 0)])
        visited: set[str] = {"menu_main"}
        max_depth = 0

        while queue:
            current_node, depth = queue.popleft()
            max_depth = max(max_depth, depth)

            for neighbor in adjacency.get(current_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return max_depth

    def _find_nodes_over_depth(self, threshold: int = 4) -> list[list[Any]]:
        """
        Находит узлы глубже заданного порога.

        Args:
            threshold: Пороговая глубина (по умолчанию 4)

        Returns:
            list: Список [node_id, depth] отсортированный по глубине DESC
        """
        nodes = self.actual_graph.get("nodes", {})
        edges = self.actual_graph.get("edges", [])

        if "menu_main" not in nodes:
            return []

        # Построение adjacency list
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            from_node = edge.get("from")
            to_node = edge.get("to")
            if from_node and to_node:
                adjacency.setdefault(from_node, []).append(to_node)

        # BFS с подсчетом глубины для всех узлов
        queue: deque[tuple[str, int]] = deque([("menu_main", 0)])
        visited: set[str] = {"menu_main"}
        node_depths: dict[str, int] = {"menu_main": 0}

        while queue:
            current_node, depth = queue.popleft()

            for neighbor in adjacency.get(current_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    node_depths[neighbor] = depth + 1
                    queue.append((neighbor, depth + 1))

        # Фильтрация узлов глубже threshold
        deep_nodes = [
            [node_id, depth]
            for node_id, depth in node_depths.items()
            if depth > threshold
        ]

        # Сортировка по глубине DESC
        deep_nodes.sort(key=lambda x: x[1], reverse=True)

        return deep_nodes

    def _find_nodes_without_back(self) -> list[str]:
        """
        Находит узлы без кнопки "Назад".

        Кнопка "Назад" определяется как ребро к узлу с меньшей глубиной.
        menu_main исключается из проверки.

        Returns:
            list: Список node_id узлов без кнопки "Назад"
        """
        nodes = self.actual_graph.get("nodes", {})
        edges = self.actual_graph.get("edges", [])

        if "menu_main" not in nodes:
            return []

        # Построение adjacency list и вычисление глубин
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            from_node = edge.get("from")
            to_node = edge.get("to")
            if from_node and to_node:
                adjacency.setdefault(from_node, []).append(to_node)

        # BFS для вычисления глубин
        queue: deque[tuple[str, int]] = deque([("menu_main", 0)])
        visited: set[str] = {"menu_main"}
        node_depths: dict[str, int] = {"menu_main": 0}

        while queue:
            current_node, depth = queue.popleft()

            for neighbor in adjacency.get(current_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    node_depths[neighbor] = depth + 1
                    queue.append((neighbor, depth + 1))

        # Проверка наличия кнопки "Назад" для каждого узла
        nodes_without_back: list[str] = []

        for node_id in nodes:
            if node_id == "menu_main":
                continue  # menu_main не требует кнопки "Назад"

            current_depth = node_depths.get(node_id, float('inf'))
            neighbors = adjacency.get(node_id, [])

            # Проверка: есть ли хотя бы одно ребро к узлу с меньшей глубиной
            has_back_button = any(
                node_depths.get(neighbor, float('inf')) < current_depth
                for neighbor in neighbors
            )

            if not has_back_button:
                nodes_without_back.append(node_id)

        return sorted(nodes_without_back)


# Пример использования
if __name__ == "__main__":
    # Пример expected_graph
    expected_graph = {
        "nodes": {
            "menu_main": {"type": "menu", "depth": 0, "description": "Главное меню"},
            "menu_chats": {"type": "menu", "depth": 1, "description": "Чаты/Диалоги"},
            "menu_settings": {"type": "menu", "depth": 1, "description": "Настройки"},
        },
        "edges": [
            {"from": "menu_main", "to": "menu_chats", "callback_data": "menu_chats", "button_text": "📱 Чаты"},
            {"from": "menu_main", "to": "menu_settings", "callback_data": "menu_settings", "button_text": "⚙️ Настройки"},
            {"from": "menu_chats", "to": "menu_main", "callback_data": "menu_main", "button_text": "🔙 Назад"},
        ]
    }

    # Пример actual_graph (неполное покрытие)
    actual_graph = {
        "nodes": {
            "menu_main": {"type": "menu", "depth": 0, "description": "Главное меню"},
            "menu_chats": {"type": "menu", "depth": 1, "description": "Чаты/Диалоги"},
        },
        "edges": [
            {"from": "menu_main", "to": "menu_chats", "callback_data": "menu_chats", "button_text": "📱 Чаты"},
            {"from": "menu_chats", "to": "menu_main", "callback_data": "menu_main", "button_text": "🔙 Назад"},
        ]
    }

    # Инициализация и верификация
    verifier = CoverageVerifier(expected_graph, actual_graph)
    result = verifier.verify()

    # Вывод результатов
    print("\n=== Coverage Verification Results ===")
    print(f"Status: {result['status']}")
    print(f"Coverage: {result['coverage_percent']}% ({result['total_visited']}/{result['total_expected']})")
    print(f"Unreachable nodes: {result['unreachable_nodes']}")
    print(f"Undocumented nodes: {result['undocumented_nodes']}")
    print(f"Max depth: {result['max_depth']}")
    print(f"Deep nodes (>4): {result['deep_nodes']}")
    print(f"Nodes without back button: {result['nodes_without_back_button']}")
