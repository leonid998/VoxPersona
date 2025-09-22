"""
CI Test Markers for VoxPersona

Provides decorators and utilities to skip tests that require external services
or heavy dependencies in CI environments.
"""

import os
import unittest
import functools
from typing import Callable

def is_ci_environment() -> bool:
    """Check if running in CI environment"""
    return any([
        os.getenv('CI') == 'true',
        os.getenv('GITHUB_ACTIONS') == 'true',
        os.getenv('SKIP_MINIO_TESTS') == 'true',
        os.getenv('SKIP_TORCH_TESTS') == 'true'
    ])

def requires_minio(func: Callable) -> Callable:
    """Skip test if MinIO is not available or in CI"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if is_ci_environment() or os.getenv('SKIP_MINIO_TESTS') == 'true':
            raise unittest.SkipTest("MinIO tests skipped in CI environment")
        
        try:
            import minio
        except ImportError:
            raise unittest.SkipTest("MinIO not available")
        
        return func(*args, **kwargs)
    return wrapper

def requires_torch(func: Callable) -> Callable:
    """Skip test if torch is not available or in CI"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if is_ci_environment() or os.getenv('SKIP_TORCH_TESTS') == 'true':
            raise unittest.SkipTest("Torch tests skipped in CI environment")
        
        try:
            import torch
        except ImportError:
            raise unittest.SkipTest("Torch not available")
        
        return func(*args, **kwargs)
    return wrapper

def requires_external_service(service_name: str):
    """Skip test if external service is not available"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if is_ci_environment():
                raise unittest.SkipTest(f"{service_name} tests skipped in CI environment")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def ci_skip_if(condition: bool, reason: str = "Skipped in CI"):
    """Skip test if condition is true"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if condition and is_ci_environment():
                raise unittest.SkipTest(reason)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Class decorators
def skip_in_ci(cls):
    """Skip entire test class in CI environment"""
    if is_ci_environment():
        return unittest.skip("Entire class skipped in CI environment")(cls)
    return cls

def requires_local_environment(cls):
    """Mark test class as requiring local environment"""
    if is_ci_environment():
        return unittest.skip("Requires local environment with external services")(cls)
    return cls