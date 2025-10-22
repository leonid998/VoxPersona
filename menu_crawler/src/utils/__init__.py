"""
Утилиты для Menu Crawler.

Модули:
- circuit_breaker: Circuit Breaker для обработки Rate Limits
- checkpoint_manager: Checkpoint/Resume для восстановления после сбоев
- cleanup: Очистка тестовых данных из БД (TODO)
- logging_config: Настройка structured logging (TODO)
"""

from .circuit_breaker import CircuitBreaker
from .checkpoint_manager import CheckpointManager

__all__ = ["CircuitBreaker", "CheckpointManager"]
