"""
Test Framework Base Classes for VoxPersona

This module provides base test classes and utilities for the enhanced
testing infrastructure, including support for different test levels
and environment simulation.
"""

import unittest
import asyncio
import tempfile
import shutil
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, patch, MagicMock
from contextlib import asynccontextmanager, contextmanager
import threading
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import our systems
try:
    from import_utils import safe_import, MockObject
    from environment import get_environment, EnvironmentType
    from path_manager import get_path_manager, PathType
    from error_recovery import get_recovery_manager
    ENHANCED_SYSTEMS_AVAILABLE = True
except ImportError:
    ENHANCED_SYSTEMS_AVAILABLE = False

# Configure test logging
logging.basicConfig(level=logging.WARNING)
test_logger = logging.getLogger('voxpersona.tests')


class VoxPersonaTestCase(unittest.TestCase):
    """
    Base test case for VoxPersona tests with enhanced capabilities
    """
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create temporary directory for test files
        self.temp_dir = Path(tempfile.mkdtemp(prefix='voxpersona_test_'))
        self.addCleanup(self._cleanup_temp_dir)
        
        # Store original environment
        self.original_env = dict(os.environ)
        self.addCleanup(self._restore_environment)
        
        # Set test environment
        os.environ['RUN_MODE'] = 'TEST'
        os.environ['TEST_MODE'] = 'true'
        
        # Initialize test-specific configurations
        self._setup_test_config()
    
    def tearDown(self):
        """Clean up after test"""
        super().tearDown()
    
    def _cleanup_temp_dir(self):
        """Clean up temporary directory"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _restore_environment(self):
        """Restore original environment variables"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def _setup_test_config(self):
        """Set up test-specific configuration"""
        # Override common config values for testing
        test_env_vars = {
            'DB_HOST': 'localhost',
            'DB_PORT': '5432',
            'DB_NAME': 'test_voxpersona',
            'DB_USER': 'test_user',
            'DB_PASSWORD': 'test_password',
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'test_access',
            'MINIO_SECRET_KEY': 'test_secret',
            'OPENAI_API_KEY': 'test_openai_key',
            'ANTHROPIC_API_KEY': 'test_anthropic_key',
            'TELEGRAM_BOT_TOKEN': 'test_bot_token',
            'API_ID': '12345',
            'API_HASH': 'test_api_hash',
        }
        
        for key, value in test_env_vars.items():
            if key not in os.environ:
                os.environ[key] = value
    
    def create_temp_file(self, name: str, content: str = "") -> Path:
        """Create a temporary file for testing"""
        file_path = self.temp_dir / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def create_temp_dir(self, name: str) -> Path:
        """Create a temporary directory for testing"""
        dir_path = self.temp_dir / name
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    def assert_file_exists(self, file_path: Path, msg: str = None):
        """Assert that a file exists"""
        if not file_path.exists():
            raise AssertionError(msg or f"File does not exist: {file_path}")
    
    def assert_dir_exists(self, dir_path: Path, msg: str = None):
        """Assert that a directory exists"""
        if not dir_path.exists() or not dir_path.is_dir():
            raise AssertionError(msg or f"Directory does not exist: {dir_path}")
    
    def assert_no_errors_in_logs(self, log_records: List, msg: str = None):
        """Assert that no ERROR level logs are present"""
        error_logs = [r for r in log_records if r.levelno >= logging.ERROR]
        if error_logs:
            error_messages = [r.getMessage() for r in error_logs]
            raise AssertionError(
                msg or f"Found {len(error_logs)} error logs: {error_messages}"
            )


class AsyncVoxPersonaTestCase(VoxPersonaTestCase):
    """
    Base test case for async VoxPersona tests
    """
    
    def setUp(self):
        """Set up async test environment"""
        super().setUp()
        
        # Create event loop for async tests
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.addCleanup(self._cleanup_event_loop)
    
    def _cleanup_event_loop(self):
        """Clean up event loop"""
        if self.loop and not self.loop.is_closed():
            self.loop.close()
    
    def run_async(self, coro):
        """Run an async coroutine in the test loop"""
        return self.loop.run_until_complete(coro)
    
    @asynccontextmanager
    async def async_temp_context(self):
        """Async context manager for temporary resources"""
        temp_resources = []
        try:
            yield temp_resources
        finally:
            # Clean up async resources
            for resource in temp_resources:
                if hasattr(resource, 'close'):
                    await resource.close()


class IntegrationTestCase(VoxPersonaTestCase):
    """
    Base class for integration tests that test component interactions
    """
    
    def setUp(self):
        """Set up integration test environment"""
        super().setUp()
        
        # Set up test services
        self._setup_test_services()
    
    def _setup_test_services(self):
        """Set up mock services for integration testing"""
        # Mock external services
        self.mock_openai = Mock()
        self.mock_anthropic = Mock()
        self.mock_minio = Mock()
        self.mock_postgres = Mock()
        
        # Store mocks for easy access
        self.mocks = {
            'openai': self.mock_openai,
            'anthropic': self.mock_anthropic,
            'minio': self.mock_minio,
            'postgres': self.mock_postgres,
        }
    
    def configure_mock_service(self, service_name: str, **config):
        """Configure a mock service with specific behavior"""
        mock_service = self.mocks.get(service_name)
        if not mock_service:
            raise ValueError(f"Unknown service: {service_name}")
        
        for attr, value in config.items():
            setattr(mock_service, attr, value)
    
    def simulate_service_failure(self, service_name: str, exception: Exception):
        """Simulate a service failure for testing error recovery"""
        mock_service = self.mocks.get(service_name)
        if not mock_service:
            raise ValueError(f"Unknown service: {service_name}")
        
        mock_service.side_effect = exception


class PerformanceTestCase(VoxPersonaTestCase):
    """
    Base class for performance tests with timing and resource monitoring
    """
    
    def setUp(self):
        """Set up performance test environment"""
        super().setUp()
        
        # Performance monitoring
        self.start_time = None
        self.performance_metrics = {}
        self.resource_monitors = []
    
    def start_performance_monitoring(self):
        """Start monitoring performance metrics"""
        self.start_time = time.time()
        self.performance_metrics = {
            'start_time': self.start_time,
            'memory_start': self._get_memory_usage(),
        }
    
    def stop_performance_monitoring(self):
        """Stop monitoring and record final metrics"""
        end_time = time.time()
        self.performance_metrics.update({
            'end_time': end_time,
            'duration': end_time - self.start_time,
            'memory_end': self._get_memory_usage(),
        })
        
        # Calculate memory delta
        memory_delta = (self.performance_metrics['memory_end'] - 
                       self.performance_metrics['memory_start'])
        self.performance_metrics['memory_delta'] = memory_delta
        
        return self.performance_metrics
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            # Fallback if psutil not available
            return 0
    
    def assert_performance_threshold(self, metric: str, threshold: float, 
                                   comparison: str = 'less_than'):
        """Assert that a performance metric meets threshold"""
        if metric not in self.performance_metrics:
            raise AssertionError(f"Performance metric '{metric}' not recorded")
        
        value = self.performance_metrics[metric]
        
        if comparison == 'less_than' and value >= threshold:
            raise AssertionError(
                f"Performance metric '{metric}' ({value}) should be less than {threshold}"
            )
        elif comparison == 'greater_than' and value <= threshold:
            raise AssertionError(
                f"Performance metric '{metric}' ({value}) should be greater than {threshold}"
            )
    
    def assert_execution_time_under(self, max_seconds: float):
        """Assert that execution time is under specified seconds"""
        self.assert_performance_threshold('duration', max_seconds, 'less_than')
    
    def assert_memory_usage_under(self, max_bytes: int):
        """Assert that memory usage delta is under specified bytes"""
        self.assert_performance_threshold('memory_delta', max_bytes, 'less_than')


class EnvironmentSimulator:
    """
    Utility class for simulating different execution environments
    """
    
    def __init__(self):
        self.original_env = {}
        self.patches = []
    
    @contextmanager
    def simulate_environment(self, env_type: str, **env_vars):
        """Context manager to simulate specific environment"""
        # Store original environment
        self.original_env = dict(os.environ)
        
        try:
            # Clear and set new environment
            os.environ.clear()
            
            # Set base environment variables based on type
            if env_type == 'ci':
                os.environ.update({
                    'CI': 'true',
                    'GITHUB_ACTIONS': 'true',
                    'RUNNER_OS': 'Linux',
                    'HOME': '/home/runner',
                })
            elif env_type == 'docker':
                os.environ.update({
                    'DOCKER_CONTAINER': 'true',
                    'HOME': '/app',
                })
                # Create docker indicator file
                docker_env_file = Path('/.dockerenv')
                if not docker_env_file.exists():
                    docker_env_file.touch()
                    self.patches.append(lambda: docker_env_file.unlink(missing_ok=True))
            elif env_type == 'development':
                os.environ.update({
                    'HOME': str(Path.home()),
                    'USER': os.getlogin() if hasattr(os, 'getlogin') else 'developer',
                })
            elif env_type == 'test':
                os.environ.update({
                    'RUN_MODE': 'TEST',
                    'PYTEST_CURRENT_TEST': 'test_example',
                })
            
            # Apply custom environment variables
            os.environ.update(env_vars)
            
            yield
            
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(self.original_env)
            
            # Apply cleanup patches
            for patch_func in self.patches:
                try:
                    patch_func()
                except Exception:
                    pass
            self.patches.clear()


class MockFactory:
    """
    Factory for creating consistent mocks across tests
    """
    
    @staticmethod
    def create_mock_config():
        """Create a mock config module"""
        mock_config = Mock()
        mock_config.DB_CONFIG = {
            'host': 'localhost',
            'port': 5432,
            'dbname': 'test_db',
            'user': 'test_user',
            'password': 'test_pass'
        }
        mock_config.TELEGRAM_BOT_TOKEN = 'test_token'
        mock_config.API_ID = '12345'
        mock_config.API_HASH = 'test_hash'
        mock_config.STORAGE_DIRS = {
            'audio': '/tmp/test_audio',
            'text_without_roles': '/tmp/test_text',
            'text_with_roles': '/tmp/test_text_roles'
        }
        return mock_config
    
    @staticmethod
    def create_mock_minio_manager():
        """Create a mock MinIO manager"""
        mock_manager = Mock()
        mock_manager.upload_file.return_value = True
        mock_manager.download_file.return_value = True
        mock_manager.delete_file.return_value = True
        mock_manager.list_files.return_value = []
        return mock_manager
    
    @staticmethod
    def create_mock_recovery_manager():
        """Create a mock error recovery manager"""
        mock_manager = Mock()
        mock_manager.recover.return_value = "Mock recovery result"
        mock_manager.classify_error.return_value = "mock_error_type"
        return mock_manager


# Utility functions
def skip_if_no_enhanced_systems(test_func):
    """Decorator to skip test if enhanced systems are not available"""
    return unittest.skipUnless(
        ENHANCED_SYSTEMS_AVAILABLE,
        "Enhanced systems not available"
    )(test_func)


def requires_service(service_name: str):
    """Decorator to skip test if required service is not available"""
    def decorator(test_func):
        return unittest.skipUnless(
            _is_service_available(service_name),
            f"Service '{service_name}' not available"
        )(test_func)
    return decorator


def _is_service_available(service_name: str) -> bool:
    """Check if a service is available for testing"""
    # This could be expanded to actually check service availability
    return True  # For now, assume services are available


# Test discovery utilities
def discover_test_modules(test_dir: Path) -> List[str]:
    """Discover test modules in a directory"""
    test_modules = []
    for test_file in test_dir.rglob("test_*.py"):
        # Convert path to module name
        rel_path = test_file.relative_to(test_dir.parent)
        module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
        test_modules.append(module_name)
    return test_modules


def create_test_suite(test_classes: List[type]) -> unittest.TestSuite:
    """Create a test suite from test classes"""
    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite


# Test execution utilities
class TestResultCollector:
    """Collects and analyzes test results"""
    
    def __init__(self):
        self.results = []
        self.performance_data = []
        self.error_patterns = {}
    
    def add_result(self, test_name: str, result: str, duration: float, 
                   details: Dict[str, Any] = None):
        """Add a test result"""
        self.results.append({
            'test_name': test_name,
            'result': result,
            'duration': duration,
            'details': details or {}
        })
    
    def add_performance_data(self, test_name: str, metrics: Dict[str, Any]):
        """Add performance data for a test"""
        self.performance_data.append({
            'test_name': test_name,
            'metrics': metrics
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of test results"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['result'] == 'PASS'])
        failed_tests = len([r for r in self.results if r['result'] == 'FAIL'])
        error_tests = len([r for r in self.results if r['result'] == 'ERROR'])
        
        total_duration = sum(r['duration'] for r in self.results)
        avg_duration = total_duration / total_tests if total_tests > 0 else 0
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'error_tests': error_tests,
            'success_rate': passed_tests / total_tests if total_tests > 0 else 0,
            'total_duration': total_duration,
            'average_duration': avg_duration,
            'performance_tests': len(self.performance_data)
        }