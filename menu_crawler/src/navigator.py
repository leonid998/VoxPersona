"""
Menu Navigator для VoxPersona.

Основной модуль для обхода меню бота через BFS алгоритм.
Использует Pyrogram для взаимодействия с Telegram.
"""

import asyncio
import json
import os
from collections import deque
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message

# Загрузить переменные окружения
load_dotenv()


class MenuNavigator:
    """
    Навигатор по меню бота с использованием BFS алгоритма.

    Attributes:
        config (dict): Конфигурация crawler (whitelist/blacklist)
        expected_graph (dict): Ожидаемый граф меню из menu_graph.json
        client (Client): Pyrogram клиент для взаимодействия с ботом
        visited_edges (set): Посещенные рёбра графа (from, to)
        actual_graph (dict): Фактический граф меню, собранный во время обхода
    """

    def __init__(self, config_path: Path):
        """
        Инициализация навигатора.

        Args:
            config_path: Путь к директории с конфигами (config/)
        """
        self.config_path = config_path

        # Загрузить конфигурацию
        self.config = self._load_config(config_path / "crawler_config.json")
        self.expected_graph = self._load_menu_graph(config_path / "menu_graph.json")

        # Получить credentials из .env
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")

        if not api_id or not api_hash:
            raise ValueError("API_ID и API_HASH должны быть установлены в .env файле")

        # Инициализировать Pyrogram клиент
        # Используем user-аккаунт (НЕ бота) для отправки callback_query
        # Используем готовую сессию test_user_session (создаётся локально и копируется на сервер)
        self.client = Client(
            "test_user_session",
            api_id=int(api_id),
            api_hash=api_hash,
            workdir=str(Path(__file__).parent.parent.parent)  # Корень проекта VoxPersona/
        )

        # State для обхода
        self.visited_edges: Set[Tuple[Optional[str], str]] = set()
        self.actual_graph: Dict[str, any] = {
            "nodes": {},
            "edges": []
        }

        # TEST_USER_ID для безопасности
        self.test_user_id = int(os.getenv("TEST_USER_ID", "0"))
        if self.test_user_id == 0:
            raise ValueError("TEST_USER_ID должен быть установлен в .env файле")

        # Alias для удобства (используется в main.py)
        self.user_id = self.test_user_id

        # Bot username для отправки команд
        self.bot_username = os.getenv("BOT_USERNAME", "market_res_bot")

        # CheckpointManager для сохранения прогресса
        from .utils.checkpoint_manager import CheckpointManager
        checkpoint_dir = Path(__file__).parent.parent  # menu_crawler/
        self.checkpoint_manager = CheckpointManager(checkpoint_dir / "progress.json")

        # Атрибут для восстановления queue из checkpoint
        self._checkpoint_queue = None

        # Текущее сообщение от бота (для актуального message_id)
        self.current_message: Optional[Message] = None

        # Текущий узел в графе меню (для отслеживания местоположения)
        self.current_node: str = "menu_main"  # Начинаем с главного меню

    def _load_config(self, config_file: Path) -> dict:
        """
        Загрузить crawler_config.json.

        Args:
            config_file: Путь к crawler_config.json

        Returns:
            Словарь с конфигурацией (safe_navigation, forbidden_actions)
        """
        if not config_file.exists():
            raise FileNotFoundError(f"Конфигурация не найдена: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Добавить параметры по умолчанию
        config.setdefault("throttle_delay", 2.0)  # 2 сек между запросами
        config.setdefault("callback_timeout", 10)  # 10 сек timeout

        return config

    def _load_menu_graph(self, graph_file: Path) -> dict:
        """
        Загрузить menu_graph.json.

        Args:
            graph_file: Путь к menu_graph.json

        Returns:
            Словарь с ожидаемым графом меню (nodes, edges)
        """
        if not graph_file.exists():
            raise FileNotFoundError(f"Граф меню не найден: {graph_file}")

        with open(graph_file, 'r', encoding='utf-8') as f:
            graph = json.load(f)

        return graph

    def _is_safe_navigation(self, callback_data: str) -> bool:
        """
        Проверить, безопасен ли callback_data для навигации.

        Логика:
        1. Если callback_data в safe_navigation whitelist → разрешено
        2. Если callback_data в forbidden_actions blacklist → запрещено
        3. Если callback_data начинается с префикса из whitelist → разрешено
        4. Иначе → запрещено (по умолчанию безопасно)

        Args:
            callback_data: Callback data кнопки

        Returns:
            True если навигация безопасна, False иначе
        """
        safe_navigation = self.config.get("safe_navigation", [])
        forbidden_actions = self.config.get("forbidden_actions", [])

        # Приоритет 1: Whitelist (явное разрешение)
        if callback_data in safe_navigation:
            return True

        # Приоритет 2: Blacklist (явный запрет)
        if callback_data in forbidden_actions:
            return False

        # Приоритет 3: Префиксы из whitelist
        # Например: "menu_" разрешает "menu_main", "menu_chats"
        for safe_prefix in safe_navigation:
            if callback_data.startswith(safe_prefix):
                return True

        # По умолчанию: запрещено (осторожный подход)
        return False

    async def _send_callback(self, callback_data: str) -> Optional[Message]:
        """
        Отправить callback_query боту используя актуальный message_id.

        Args:
            callback_data: Callback data кнопки для нажатия

        Returns:
            Обновлённое сообщение с новым меню (или None при ошибке)

        Raises:
            FloodWait: При достижении Rate Limit (обрабатывается в crawl)
            TimeoutError: При превышении timeout (10 сек)
        """
        import structlog
        logger = structlog.get_logger(__name__)

        try:
            # Использовать текущее сообщение (обновляется после каждого callback)
            if self.current_message is None:
                # Fallback: получить последнее сообщение от бота
                async for message in self.client.get_chat_history(self.bot_username, limit=1):
                    self.current_message = message
                    break
                else:
                    logger.error("no_messages_found", bot_username=self.bot_username)
                    return None

            # Проверить наличие InlineKeyboard
            if not self.current_message.reply_markup:
                logger.warning("no_keyboard", callback_data=callback_data)
                # Попробовать обновить сообщение
                async for message in self.client.get_chat_history(self.bot_username, limit=1):
                    self.current_message = message
                    if self.current_message.reply_markup:
                        break
                else:
                    return None

            # КРИТИЧНО: Проверить что callback_data есть в текущей клавиатуре
            available_callbacks = []
            for row in self.current_message.reply_markup.inline_keyboard:
                for button in row:
                    if button.callback_data:
                        available_callbacks.append(button.callback_data)

            if callback_data not in available_callbacks:
                logger.warning(
                    "callback_not_in_keyboard",
                    callback_data=callback_data,
                    available_callbacks=available_callbacks,
                    message_id=self.current_message.id
                )
                return None

            # Отправить callback_query используя АКТУАЛЬНЫЙ message_id
            logger.info("sending_callback", callback_data=callback_data, message_id=self.current_message.id)

            # НОВЫЙ ПОДХОД: отправить команду /test_callback боту
            await self.client.send_message(
                self.bot_username,
                f"/test_callback {callback_data}"
            )

            # Подождать обновления (бот отредактирует сообщение)
            await asyncio.sleep(2.0)

            # Получить обновлённое сообщение (пропускаем служебные сообщения)
            updated_message = None
            async for message in self.client.get_chat_history(self.bot_username, limit=5):
                # Пропустить служебные сообщения от test_callback
                if message.text and any(x in message.text for x in ["✅ Test callback", "🤖", "⚠️", "❌"]):
                    continue
                # Найти сообщение с клавиатурой (это обновлённое меню)
                if message.reply_markup:
                    updated_message = message
                    break

            if not updated_message:
                logger.warning("no_updated_message", callback_data=callback_data)
                return None

            # Сохранить актуальное сообщение для следующего callback
            self.current_message = updated_message

            logger.info("callback_success", callback_data=callback_data, new_message_id=updated_message.id)
            return updated_message

        except FloodWait as e:
            # FloodWait пробрасывается наверх для обработки CircuitBreaker
            logger.warning("flood_wait", callback_data=callback_data, wait_seconds=e.value)
            raise

        except Exception as e:
            logger.error("callback_error", callback_data=callback_data, error=str(e))
            # При ошибке сбросить current_message для fallback
            self.current_message = None
            return None

    def _parse_keyboard(self, message: Optional[Message]) -> List[Tuple[str, str]]:
        """
        Парсить InlineKeyboard из сообщения.

        Args:
            message: Сообщение от бота с InlineKeyboard

        Returns:
            Список кортежей (button_text, callback_data)
        """
        import structlog
        logger = structlog.get_logger(__name__)

        if not message or not message.reply_markup:
            return []

        buttons = []

        try:
            # Извлечь кнопки из InlineKeyboard
            for row in message.reply_markup.inline_keyboard:
                for button in row:
                    if button.callback_data:
                        buttons.append((button.text, button.callback_data))

            logger.info(
                "keyboard_parsed",
                buttons_count=len(buttons),
                buttons=[b[1] for b in buttons]  # только callback_data
            )

        except Exception as e:
            logger.error("keyboard_parse_error", error=str(e))

        return buttons

    def _add_to_actual_graph(
        self,
        parent: Optional[str],
        child: str,
        button_text: str
    ) -> None:
        """
        Добавить узел и ребро в actual_graph.

        Args:
            parent: Родительский callback_data (None для корня)
            child: Дочерний callback_data
            button_text: Текст кнопки
        """
        # Добавить узел (если новый)
        if child not in self.actual_graph["nodes"]:
            self.actual_graph["nodes"][child] = {
                "type": "unknown",  # тип можно определить позже
                "description": button_text
            }

        # Добавить ребро
        edge = {
            "from": parent,
            "to": child,
            "button_text": button_text
        }

        # Проверить, не добавлено ли уже такое ребро
        if edge not in self.actual_graph["edges"]:
            self.actual_graph["edges"].append(edge)

    def _find_path(self, from_node: str, to_node: str) -> List[str]:
        """
        Найти кратчайший путь между двумя узлами в графе меню.

        Использует BFS для поиска пути в menu_graph.json.

        Args:
            from_node: Начальный узел (callback_data)
            to_node: Целевой узел (callback_data)

        Returns:
            Список callback_data для перехода от from_node к to_node.
            Пустой список если путь не найден.

        Example:
            >>> path = self._find_path("menu_chats", "menu_system")
            >>> # ["menu_main", "menu_system"]
        """
        import structlog
        logger = structlog.get_logger(__name__)

        if from_node == to_node:
            return []

        # BFS для поиска пути
        queue = deque([(from_node, [from_node])])
        visited = {from_node}

        while queue:
            node, path = queue.popleft()

            # Проверить все исходящие рёбра из текущего узла
            for edge in self.expected_graph.get("edges", []):
                if edge["from"] == node:
                    next_node = edge["to"]

                    if next_node == to_node:
                        # Нашли целевой узел!
                        return path + [next_node]

                    if next_node not in visited:
                        visited.add(next_node)
                        queue.append((next_node, path + [next_node]))

        # Путь не найден
        logger.warning(
            "path_not_found",
            from_node=from_node,
            to_node=to_node,
            visited_count=len(visited)
        )
        return []

    def _get_node_for_callback(self, callback_data: str) -> Optional[str]:
        """
        Найти узел, из которого доступен данный callback_data.

        Ищет в menu_graph.json, какой узел имеет исходящее ребро
        с указанным callback_data.

        Args:
            callback_data: Callback data кнопки

        Returns:
            callback_data родительского узла или None если не найден

        Example:
            >>> node = self._get_node_for_callback("menu_system")
            >>> # "menu_main"
        """
        import structlog
        logger = structlog.get_logger(__name__)

        # Поиск в expected_graph
        for edge in self.expected_graph.get("edges", []):
            if edge["to"] == callback_data or edge.get("callback_data") == callback_data:
                from_node = edge["from"]
                logger.debug(
                    "found_parent_node",
                    callback_data=callback_data,
                    from_node=from_node
                )
                return from_node

        # Не найдено - возможно динамическая кнопка
        logger.debug(
            "parent_node_not_found",
            callback_data=callback_data,
            hint="Возможно, это динамическая кнопка с UUID"
        )
        return None

    async def _navigate_to(self, target_node: str) -> bool:
        """
        Навигировать к указанному узлу в графе меню.

        Если текущий узел (self.current_node) != target_node,
        найти путь через _find_path() и выполнить последовательность переходов.

        Args:
            target_node: Целевой узел (callback_data)

        Returns:
            True если навигация успешна, False если путь не найден

        Example:
            >>> # Текущий узел: menu_chats
            >>> success = await self._navigate_to("menu_main")
            >>> # Выполнит переход: menu_chats → menu_main
        """
        import structlog
        logger = structlog.get_logger(__name__)

        if self.current_node == target_node:
            # Уже в нужном узле
            logger.debug("already_at_target_node", node=target_node)
            return True

        # Найти путь
        path = self._find_path(self.current_node, target_node)

        if not path:
            logger.error(
                "navigation_path_not_found",
                from_node=self.current_node,
                to_node=target_node
            )
            return False

        logger.info(
            "navigating_to_node",
            from_node=self.current_node,
            to_node=target_node,
            path=path
        )

        # Выполнить последовательность переходов
        for i, next_node in enumerate(path):
            if next_node == self.current_node:
                continue  # Уже в этом узле

            # Найти callback_data для перехода current_node → next_node
            callback_to_send = None
            for edge in self.expected_graph.get("edges", []):
                if edge["from"] == self.current_node and edge["to"] == next_node:
                    callback_to_send = edge.get("callback_data", edge["to"])
                    break

            if not callback_to_send:
                logger.error(
                    "callback_not_found_for_edge",
                    from_node=self.current_node,
                    to_node=next_node
                )
                return False

            # Отправить callback
            try:
                logger.debug(
                    "navigation_step",
                    step=i + 1,
                    total_steps=len(path),
                    callback_data=callback_to_send
                )

                response = await self._send_callback(callback_to_send)

                # Обновить текущий узел
                self.current_node = next_node

                # Throttling
                await asyncio.sleep(self.config.get("throttle_delay", 2.0))

            except Exception as e:
                logger.error(
                    "navigation_step_failed",
                    step=i + 1,
                    callback_data=callback_to_send,
                    error=str(e)
                )
                return False

        logger.info(
            "navigation_completed",
            from_node=path[0] if path else self.current_node,
            to_node=target_node
        )
        return True

    def resume_from_checkpoint(self) -> bool:
        """
        Восстановить состояние из checkpoint перед запуском crawl().

        Returns:
            True если resume успешен, False если checkpoint не найден

        Example:
            >>> navigator = MenuNavigator(config_path)
            >>> if navigator.resume_from_checkpoint():
            ...     print("Восстановлен из checkpoint")
            ... else:
            ...     print("Начинаем новый обход")
            >>> await navigator.crawl()
        """
        return self.checkpoint_manager.resume_crawl(self)

    async def init_crawler(self) -> None:
        """
        Инициализировать crawler.

        1. Запустить Pyrogram клиент
        2. Проверить TEST_USER_ID (должен быть не 0)
        3. Отправить /start боту для получения главного меню

        Raises:
            ValueError: Если TEST_USER_ID не установлен
            RuntimeError: Если не удалось получить главное меню
        """
        # Запустить клиент
        await self.client.start()
        print(f"✅ Pyrogram клиент запущен (session: menu_crawler_session)")

        # Получить информацию о пользователе
        me = await self.client.get_me()
        self.username = me.username if me.username else f"user_{me.id}"

        # Проверить TEST_USER_ID
        if self.test_user_id == 0:
            raise ValueError("TEST_USER_ID не может быть 0. Установите в .env")

        print(f"✅ TEST_USER_ID: {self.test_user_id}")
        print(f"✅ Username: @{self.username}")

        # Отправить /start боту для получения главного меню
        try:
            await self.client.send_message(self.bot_username, "/start")
            print(f"✅ Отправлена команда /start боту @{self.bot_username}")

            # Подождать ответа (3 секунды - бот может отвечать с задержкой)
            await asyncio.sleep(3)
        except Exception as e:
            raise RuntimeError(f"Ошибка при отправке /start: {e}")

    async def crawl(self) -> Set[Tuple[Optional[str], str]]:
        """
        Основной метод обхода меню через BFS алгоритм.

        Алгоритм:
        1. Получить первую клавиатуру от бота через /start
        2. Инициализировать queue с реальными callback_data из клавиатуры
        3. Пока queue не пуста:
           a. Взять (parent, callback_data) из queue
           b. Проверить visited_edges (skip если посещен)
           c. Проверить whitelist/blacklist (skip запрещенные)
           d. Отправить callback через _send_callback()
           e. Применить throttling (2 сек delay)
           f. Парсить keyboard через _parse_keyboard()
           g. Добавить детей в queue
           h. Обновить visited_edges
           i. Checkpoint каждые 10 узлов
        4. Вернуть visited_edges

        Returns:
            Множество посещенных рёбер (from, to)
        """
        import structlog
        from .utils.circuit_breaker import CircuitBreaker

        logger = structlog.get_logger(__name__)

        # Инициализация УЖЕ выполнена в main.py через init_crawler()
        # НЕ вызываем повторно!

        logger.info("crawler_started", test_user_id=self.test_user_id)

        # Попытка восстановления из checkpoint
        checkpoint_resumed = False
        if self._checkpoint_queue is not None:
            # Resume из checkpoint (вызван resume_crawl перед crawl)
            queue = self._checkpoint_queue
            checkpoint_resumed = True
            logger.info(
                "resuming_from_checkpoint",
                visited_edges=len(self.visited_edges),
                queue_size=len(queue)
            )
        else:
            # Проверить наличие checkpoint файла
            checkpoint_info = self.checkpoint_manager.get_info()
            if checkpoint_info:
                # Checkpoint существует, но resume не был вызван
                # Можно автоматически восстановить или начать с нуля
                # Для безопасности начнём с нуля, но залогируем предупреждение
                logger.warning(
                    "checkpoint_exists_but_not_resumed",
                    checkpoint_info=checkpoint_info,
                    message="Обнаружен существующий checkpoint, но resume не был вызван. Начинаем новый обход."
                )

            # Получить начальную клавиатуру от бота (уже отправлен /start в init_crawler)
            async for message in self.client.get_chat_history(self.bot_username, limit=1):
                initial_message = message
                break
            else:
                logger.error("no_initial_message_found", bot_username=self.bot_username)
                raise RuntimeError("Не удалось получить начальное сообщение от бота")

            # Сохранить initial_message как current_message для первого callback
            self.current_message = initial_message

            # Парсить начальную клавиатуру
            initial_buttons = self._parse_keyboard(initial_message)

            if not initial_buttons:
                logger.error("no_initial_keyboard", bot_username=self.bot_username)
                raise RuntimeError("Бот не прислал inline keyboard при /start")

            # Инициализация BFS с реальными callback_data из клавиатуры
            queue = deque()
            for button_text, callback_data in initial_buttons:
                queue.append((None, callback_data))
                # Добавить в actual_graph корневые узлы
                self._add_to_actual_graph(None, callback_data, button_text)

            logger.info(
                "initial_keyboard_parsed",
                buttons_count=len(initial_buttons),
                initial_callbacks=[cb for _, cb in initial_buttons]
            )

        circuit_breaker = CircuitBreaker(max_failures=3, backoff_base=2.0)
        checkpoint_counter = 0

        # Получить throttle delay из конфига
        throttle_delay = self.config.get("throttle_delay", 2.0)

        logger.info(
            "bfs_initialized",
            initial_node="menu_main",
            throttle_delay=throttle_delay
        )

        # Основной цикл BFS
        while queue:
            parent, callback_data = queue.popleft()
            edge = (parent, callback_data)

            # Проверка 1: Уже посещён?
            if edge in self.visited_edges:
                logger.debug("edge_already_visited", edge=edge)
                continue

            # Проверка 2: Безопасная навигация?
            if not self._is_safe_navigation(callback_data):
                logger.warning(
                    "skipping_forbidden_action",
                    callback_data=callback_data,
                    parent=parent
                )
                continue

            logger.info(
                "visiting_edge",
                from_node=parent,
                to_node=callback_data,
                queue_size=len(queue)
            )

            # 🧭 ИНТЕЛЛЕКТУАЛЬНАЯ НАВИГАЦИЯ с использованием menu_graph.json
            # Найти, из какого узла доступен этот callback
            target_from_node = self._get_node_for_callback(callback_data)

            if target_from_node and target_from_node != self.current_node:
                # Требуется навигация к нужному узлу
                logger.info(
                    "navigation_required",
                    current_node=self.current_node,
                    target_node=target_from_node,
                    callback_data=callback_data
                )

                navigation_success = await self._navigate_to(target_from_node)

                if not navigation_success:
                    logger.error(
                        "navigation_failed_skipping_edge",
                        callback_data=callback_data,
                        current_node=self.current_node,
                        target_node=target_from_node
                    )
                    continue  # Пропустить этот callback - недостижим

            # Отправка callback с обработкой FloodWait
            try:
                response = await self._send_callback(callback_data)

                # Успех - сброс Circuit Breaker
                circuit_breaker.reset()

                # Обновить текущий узел после успешного перехода
                self.current_node = callback_data
                logger.debug(
                    "current_node_updated",
                    current_node=self.current_node
                )

                # Throttling (задержка между запросами)
                await asyncio.sleep(throttle_delay)

            except FloodWait as e:
                # Обработка Rate Limit через Circuit Breaker
                logger.warning(
                    "rate_limit_encountered",
                    callback_data=callback_data,
                    wait_seconds=e.value
                )

                should_retry = await circuit_breaker.handle_error(e)

                if should_retry:
                    # Retry - вернуть edge в начало queue
                    queue.appendleft((parent, callback_data))
                    logger.info("retry_edge", edge=edge)
                    continue
                else:
                    # Circuit opened - прекращаем обход
                    logger.error(
                        "circuit_breaker_stopped_crawl",
                        visited_edges=len(self.visited_edges),
                        remaining_queue=len(queue)
                    )
                    break

            except Exception as e:
                logger.error(
                    "unexpected_error",
                    callback_data=callback_data,
                    error=str(e)
                )
                # Продолжаем обход, пропуская проблемный узел
                continue

            # Парсинг keyboard и добавление детей в queue
            if response:
                buttons = self._parse_keyboard(response)

                for button_text, child_callback in buttons:
                    # Добавить в actual_graph
                    self._add_to_actual_graph(callback_data, child_callback, button_text)

                    # Добавить в queue (если ещё не посещён и безопасен)
                    child_edge = (callback_data, child_callback)
                    if child_edge not in self.visited_edges:
                        if self._is_safe_navigation(child_callback):
                            queue.append((callback_data, child_callback))
                            logger.debug(
                                "added_to_queue",
                                parent=callback_data,
                                child=child_callback
                            )

            # Пометить ребро как посещённое
            self.visited_edges.add(edge)

            # Checkpoint (каждые 10 узлов)
            checkpoint_counter += 1
            if checkpoint_counter % 10 == 0:
                # Сохранить checkpoint
                checkpoint_state = {
                    "visited_edges": self.visited_edges,
                    "queue": queue,
                    "actual_graph": self.actual_graph
                }
                self.checkpoint_manager.save(checkpoint_state)

                logger.info(
                    "checkpoint",
                    visited_edges=len(self.visited_edges),
                    queue_size=len(queue),
                    actual_graph_nodes=len(self.actual_graph["nodes"]),
                    actual_graph_edges=len(self.actual_graph["edges"])
                )

        # Финальная статистика
        logger.info(
            "crawler_finished",
            visited_edges=len(self.visited_edges),
            actual_graph_nodes=len(self.actual_graph["nodes"]),
            actual_graph_edges=len(self.actual_graph["edges"]),
            circuit_breaker_state=circuit_breaker.get_state()
        )

        return self.visited_edges

    async def cleanup(self) -> None:
        """
        Очистить ресурсы после завершения обхода.

        - Остановить Pyrogram клиент
        """
        if self.client.is_connected:
            await self.client.stop()
            print("✅ Pyrogram клиент остановлен")


# Пример использования
async def main():
    """Тестовый запуск navigator."""
    config_path = Path(__file__).parent.parent / "config"

    navigator = MenuNavigator(config_path)

    try:
        visited = await navigator.crawl()
        print(f"\n✅ Обход завершен. Посещено рёбер: {len(visited)}")
    except Exception as e:
        print(f"❌ Ошибка во время обхода: {e}")
    finally:
        await navigator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
