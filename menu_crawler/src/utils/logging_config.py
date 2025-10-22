"""
Централизованная конфигурация structured logging для Menu Crawler.

Использует structlog для JSON-форматированных логов с контекстными полями,
ISO timestamps и автоматическими stack traces при исключениях.
"""

import logging
import sys
from typing import Optional

import structlog


def setup_logging(log_level: str = "INFO") -> structlog.BoundLogger:
    """
    Настроить structured logging для Menu Crawler.

    Конфигурирует structlog с JSON renderer, ISO timestamps,
    автоматическими stack traces и контекстными полями.

    Должна вызываться ОДИН РАЗ при старте приложения.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Настроенный logger для использования в модулях

    Example:
        >>> logger = setup_logging("DEBUG")
        >>> logger.info("crawler_started", session_id="20251022_153000")
    """
    # Конфигурация structlog
    structlog.configure(
        processors=[
            # Добавить уровень лога (info, warning, error)
            structlog.stdlib.add_log_level,

            # Добавить имя logger'а
            structlog.stdlib.add_logger_name,

            # Timestamp в ISO формате (UTC)
            structlog.processors.TimeStamper(fmt="iso", utc=True),

            # Stack trace при исключениях
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,

            # JSON renderer для машиночитаемых логов
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Настроить stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )

    # Вернуть root logger для Menu Crawler
    logger = structlog.get_logger("menu_crawler")
    logger.info("logging_configured", level=log_level)

    return logger


def get_logger(module_name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Получить logger для конкретного модуля.

    Возвращает logger с привязанным контекстом модуля.
    Должна вызываться в каждом модуле для получения специфичного logger'а.

    Args:
        module_name: Имя модуля (например "navigator", "cleanup")
                     Если None, вернет root logger "menu_crawler"

    Returns:
        Logger с привязанным контекстом модуля

    Example:
        >>> nav_logger = get_logger("navigator")
        >>> nav_logger.info("bfs_started", queue_size=1)

        >>> # JSON output:
        >>> # {"event": "bfs_started", "queue_size": 1, "level": "info",
        >>> #  "timestamp": "2025-10-22T15:30:00.123Z", "logger": "menu_crawler.navigator"}
    """
    if module_name:
        return structlog.get_logger(f"menu_crawler.{module_name}")
    return structlog.get_logger("menu_crawler")


if __name__ == "__main__":
    # Демонстрация использования logging_config
    print("=== Пример использования structured logging ===\n")

    # Настройка logging (вызывается ОДИН РАЗ при старте)
    logger = setup_logging("DEBUG")

    # Базовое логирование
    print("\n1. Базовое логирование:")
    logger.info("crawler_started", session_id="20251022_153000")

    # Логирование с контекстом
    print("\n2. Логирование с контекстными полями:")
    logger.info(
        "edge_visited",
        from_node="menu_main",
        to_node="menu_chats",
        depth=1,
        action="click"
    )

    # Предупреждение
    print("\n3. Предупреждения:")
    logger.warning(
        "rate_limit_hit",
        wait_seconds=5,
        attempt=2,
        max_attempts=3
    )

    # Ошибка
    print("\n4. Ошибки:")
    logger.error(
        "cleanup_failed",
        error="Connection timeout",
        table="conversations",
        session_id="20251022_153000"
    )

    # Логирование из конкретного модуля
    print("\n5. Модульные logger'ы:")
    nav_logger = get_logger("navigator")
    nav_logger.info("bfs_started", queue_size=1, root_node="menu_main")

    cleanup_logger = get_logger("cleanup")
    cleanup_logger.info("cleanup_started", session_id="20251022_153000")

    breaker_logger = get_logger("circuit_breaker")
    breaker_logger.warning("circuit_opened", failures=3, threshold=3)

    # Демонстрация exception logging
    print("\n6. Exception logging (с автоматическим stack trace):")
    try:
        result = 1 / 0
    except ZeroDivisionError as e:
        logger.error(
            "calculation_failed",
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True
        )

    print("\n=== Пример интеграции в модули ===\n")
    print("""
# navigator.py
from utils.logging_config import get_logger

logger = get_logger("navigator")

def crawl_menu():
    logger.info("crawler_started", user_id=TEST_USER_ID)
    logger.info("edge_visited", from_node=parent, to_node=child)
    logger.info("checkpoint_saved", edges=len(visited_edges))

# circuit_breaker.py
from utils.logging_config import get_logger

logger = get_logger("circuit_breaker")

def handle_rate_limit():
    logger.warning("rate_limit_hit", wait_seconds=5, attempt=2)
    logger.error("circuit_opened", failures=3)

# cleanup.py
from utils.logging_config import get_logger

logger = get_logger("cleanup")

def cleanup_session():
    logger.info("cleanup_started", session_id=session_id)
    logger.info("cleaned_table", table="conversations", rows_deleted=5)
    logger.error("cleanup_failed", error=str(e))
    """)
