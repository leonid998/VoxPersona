"""
Menu Crawler - основной модуль для обхода меню VoxPersona бота.

Модули:
- navigator: Основной навигатор с BFS алгоритмом
- coverage_verifier: Проверка покрытия expected vs actual (TODO)
- report_builder: Генерация отчётов JSON/Markdown (TODO)
- utils: Утилиты (CircuitBreaker, CheckpointManager, cleanup, logging)
"""

from .navigator import MenuNavigator

__all__ = ["MenuNavigator"]
