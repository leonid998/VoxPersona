"""
Checkpoint Manager для сохранения и восстановления прогресса crawler.

Позволяет возобновить обход меню после сбоя или остановки.
Сохраняет visited_edges и queue в JSON формате.
"""

import json
import structlog
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Set, Tuple, Any

# Получить structured logger
logger = structlog.get_logger(__name__)


class CheckpointManager:
    """
    Менеджер checkpoint'ов для сохранения прогресса crawler.

    Сохраняет состояние обхода (visited_edges, queue) в JSON файл.
    Позволяет восстановить прогресс при повторном запуске.

    Attributes:
        checkpoint_path (Path): Путь к файлу checkpoint
    """

    def __init__(self, checkpoint_path: Path = Path("progress.json")):
        """
        Инициализация CheckpointManager.

        Args:
            checkpoint_path: Путь к файлу checkpoint (default: progress.json)
        """
        self.checkpoint_path = checkpoint_path

        logger.info(
            "checkpoint_manager_initialized",
            checkpoint_path=str(checkpoint_path)
        )

    def save(self, state: Dict[str, Any]) -> bool:
        """
        Сохранить состояние crawler в checkpoint файл.

        Args:
            state: Словарь с состоянием:
                - visited_edges: set[(from, to)] - посещённые рёбра
                - queue: deque[(parent, callback_data)] - очередь для обхода
                - actual_graph: dict - собранный граф (опционально)

        Returns:
            True если сохранение успешно, False иначе

        Example:
            >>> manager = CheckpointManager()
            >>> state = {
            ...     "visited_edges": {(None, "menu_main"), ("menu_main", "menu_chats")},
            ...     "queue": deque([("menu_main", "menu_system")])
            ... }
            >>> manager.save(state)
            True
        """
        try:
            # Сериализация: set → list, deque → list
            serialized_state = {
                "timestamp": datetime.utcnow().isoformat(),
                "visited_edges": list(state.get("visited_edges", set())),
                "queue": list(state.get("queue", deque())),
                "actual_graph": state.get("actual_graph", {"nodes": {}, "edges": []})
            }

            # Сохранить в файл с красивым форматированием
            with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(serialized_state, f, indent=2, ensure_ascii=False)

            logger.info(
                "checkpoint_saved",
                checkpoint_path=str(self.checkpoint_path),
                visited_edges=len(serialized_state["visited_edges"]),
                queue_size=len(serialized_state["queue"]),
                nodes=len(serialized_state["actual_graph"]["nodes"]),
                edges=len(serialized_state["actual_graph"]["edges"])
            )

            return True

        except Exception as e:
            logger.error(
                "checkpoint_save_failed",
                checkpoint_path=str(self.checkpoint_path),
                error=str(e)
            )
            return False

    def load(self) -> Optional[Dict[str, Any]]:
        """
        Загрузить checkpoint из файла.

        Returns:
            Словарь с состоянием crawler или None если checkpoint не найден

        Example:
            >>> manager = CheckpointManager()
            >>> state = manager.load()
            >>> if state:
            ...     print(f"Загружено {len(state['visited_edges'])} рёбер")
        """
        # Проверить существование файла
        if not self.checkpoint_path.exists():
            logger.info(
                "checkpoint_not_found",
                checkpoint_path=str(self.checkpoint_path)
            )
            return None

        try:
            # Загрузить из файла
            with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                serialized_state = json.load(f)

            # Десериализация: list → set, list → deque
            # Важно: кортежи (from, to) нужно восстановить из вложенных списков
            visited_edges_list = serialized_state.get("visited_edges", [])
            visited_edges = set(
                tuple(edge) if isinstance(edge, list) else edge
                for edge in visited_edges_list
            )

            queue_list = serialized_state.get("queue", [])
            queue = deque(
                tuple(item) if isinstance(item, list) else item
                for item in queue_list
            )

            state = {
                "timestamp": serialized_state.get("timestamp"),
                "visited_edges": visited_edges,
                "queue": queue,
                "actual_graph": serialized_state.get("actual_graph", {"nodes": {}, "edges": []})
            }

            logger.info(
                "checkpoint_loaded",
                checkpoint_path=str(self.checkpoint_path),
                timestamp=state["timestamp"],
                visited_edges=len(state["visited_edges"]),
                queue_size=len(state["queue"]),
                nodes=len(state["actual_graph"]["nodes"]),
                edges=len(state["actual_graph"]["edges"])
            )

            return state

        except json.JSONDecodeError as e:
            logger.error(
                "checkpoint_load_failed_invalid_json",
                checkpoint_path=str(self.checkpoint_path),
                error=str(e)
            )
            return None

        except Exception as e:
            logger.error(
                "checkpoint_load_failed",
                checkpoint_path=str(self.checkpoint_path),
                error=str(e)
            )
            return None

    def resume_crawl(self, navigator: Any) -> bool:
        """
        Восстановить состояние navigator из checkpoint.

        Args:
            navigator: Экземпляр MenuNavigator для восстановления

        Returns:
            True если resume успешен, False иначе (нет checkpoint или ошибка)

        Example:
            >>> navigator = MenuNavigator(config_path)
            >>> manager = CheckpointManager()
            >>> if manager.resume_crawl(navigator):
            ...     print("Прогресс восстановлен из checkpoint")
            ... else:
            ...     print("Начинаем новый обход")
        """
        # Загрузить checkpoint
        state = self.load()

        if not state:
            logger.info("no_checkpoint_to_resume")
            return False

        try:
            # Восстановить состояние navigator
            navigator.visited_edges = state["visited_edges"]
            # Queue будет восстановлена в методе crawl()
            # Но сохраним её в специальном атрибуте для использования
            navigator._checkpoint_queue = state["queue"]
            navigator.actual_graph = state["actual_graph"]

            logger.info(
                "crawl_resumed",
                visited_edges=len(navigator.visited_edges),
                queue_size=len(state["queue"]),
                timestamp=state["timestamp"]
            )

            return True

        except Exception as e:
            logger.error(
                "resume_crawl_failed",
                error=str(e)
            )
            return False

    def delete(self) -> bool:
        """
        Удалить checkpoint файл.

        Returns:
            True если удаление успешно, False иначе

        Example:
            >>> manager = CheckpointManager()
            >>> manager.delete()
            True
        """
        try:
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
                logger.info(
                    "checkpoint_deleted",
                    checkpoint_path=str(self.checkpoint_path)
                )
                return True
            else:
                logger.warning(
                    "checkpoint_not_found_for_deletion",
                    checkpoint_path=str(self.checkpoint_path)
                )
                return False

        except Exception as e:
            logger.error(
                "checkpoint_delete_failed",
                checkpoint_path=str(self.checkpoint_path),
                error=str(e)
            )
            return False

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """
        Проверить, устарел ли checkpoint.

        Args:
            max_age_hours: Максимальный возраст checkpoint в часах (default: 24)

        Returns:
            True если checkpoint устарел или не существует, False иначе

        Example:
            >>> manager = CheckpointManager()
            >>> if manager.is_stale(max_age_hours=12):
            ...     print("Checkpoint устарел, игнорируем")
            ...     manager.delete()
        """
        state = self.load()

        if not state:
            return True

        try:
            timestamp_str = state.get("timestamp")
            if not timestamp_str:
                return True

            # Парсить timestamp
            checkpoint_time = datetime.fromisoformat(timestamp_str)
            now = datetime.utcnow()

            age_hours = (now - checkpoint_time).total_seconds() / 3600

            is_stale = age_hours > max_age_hours

            if is_stale:
                logger.warning(
                    "checkpoint_is_stale",
                    age_hours=age_hours,
                    max_age_hours=max_age_hours
                )

            return is_stale

        except Exception as e:
            logger.error(
                "checkpoint_staleness_check_failed",
                error=str(e)
            )
            return True

    def get_info(self) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о checkpoint без полной загрузки.

        Returns:
            Словарь с метаданными checkpoint или None

        Example:
            >>> manager = CheckpointManager()
            >>> info = manager.get_info()
            >>> if info:
            ...     print(f"Checkpoint от {info['timestamp']}")
            ...     print(f"Посещено рёбер: {info['visited_edges']}")
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return {
                "timestamp": data.get("timestamp"),
                "visited_edges": len(data.get("visited_edges", [])),
                "queue_size": len(data.get("queue", [])),
                "nodes": len(data.get("actual_graph", {}).get("nodes", {})),
                "edges": len(data.get("actual_graph", {}).get("edges", [])),
                "file_size": self.checkpoint_path.stat().st_size
            }

        except Exception as e:
            logger.error("get_checkpoint_info_failed", error=str(e))
            return None


# Пример использования
if __name__ == "__main__":
    # Создать CheckpointManager
    manager = CheckpointManager(Path("test_progress.json"))

    # Симуляция состояния crawler
    test_state = {
        "visited_edges": {
            (None, "menu_main"),
            ("menu_main", "menu_chats"),
            ("menu_main", "menu_system")
        },
        "queue": deque([
            ("menu_chats", "chat_actions"),
            ("menu_system", "menu_access")
        ]),
        "actual_graph": {
            "nodes": {
                "menu_main": {"type": "menu", "description": "Главное меню"},
                "menu_chats": {"type": "menu", "description": "Чаты"}
            },
            "edges": [
                {"from": None, "to": "menu_main", "button_text": "Start"},
                {"from": "menu_main", "to": "menu_chats", "button_text": "📱 Чаты"}
            ]
        }
    }

    # Сохранить checkpoint
    print("=== Сохранение checkpoint ===")
    success = manager.save(test_state)
    print(f"Сохранение: {'✅ Успех' if success else '❌ Ошибка'}")

    # Получить информацию
    print("\n=== Информация о checkpoint ===")
    info = manager.get_info()
    if info:
        print(f"Timestamp: {info['timestamp']}")
        print(f"Посещено рёбер: {info['visited_edges']}")
        print(f"Размер очереди: {info['queue_size']}")
        print(f"Размер файла: {info['file_size']} байт")

    # Загрузить checkpoint
    print("\n=== Загрузка checkpoint ===")
    loaded_state = manager.load()
    if loaded_state:
        print(f"✅ Checkpoint загружен")
        print(f"Visited edges: {len(loaded_state['visited_edges'])}")
        print(f"Queue size: {len(loaded_state['queue'])}")
    else:
        print("❌ Не удалось загрузить checkpoint")

    # Проверить актуальность
    print("\n=== Проверка актуальности ===")
    is_stale = manager.is_stale(max_age_hours=1)
    print(f"Checkpoint устарел (>1ч): {'Да' if is_stale else 'Нет'}")

    # Удалить checkpoint
    print("\n=== Удаление checkpoint ===")
    deleted = manager.delete()
    print(f"Удаление: {'✅ Успех' if deleted else '❌ Ошибка'}")
