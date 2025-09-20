"""
VoxPersona Test Framework

This package provides comprehensive testing utilities and base classes
for the VoxPersona project's enhanced testing infrastructure.
"""

from .base import (
    VoxPersonaTestCase,
    AsyncVoxPersonaTestCase,
    IntegrationTestCase,
    PerformanceTestCase,
    EnvironmentSimulator,
    MockFactory,
    TestResultCollector,
    skip_if_no_enhanced_systems,
    requires_service,
    discover_test_modules,
    create_test_suite,
)

__all__ = [
    'VoxPersonaTestCase',
    'AsyncVoxPersonaTestCase', 
    'IntegrationTestCase',
    'PerformanceTestCase',
    'EnvironmentSimulator',
    'MockFactory',
    'TestResultCollector',
    'skip_if_no_enhanced_systems',
    'requires_service',
    'discover_test_modules',
    'create_test_suite',
]

# Version info
__version__ = '1.0.0'
__author__ = 'VoxPersona Team'