# -*- coding: utf-8 -*-
"""
Модуль утилит VoxPersona.

Содержит вспомогательные функции и классы для работы проекта.
"""

from .json_size_estimator import (
    estimate_json_size,
    calculate_file_stats,
    get_truncation_strategy,
    JSONSizeEstimator,
)

__all__ = [
    'estimate_json_size',
    'calculate_file_stats',
    'get_truncation_strategy',
    'JSONSizeEstimator',
]
