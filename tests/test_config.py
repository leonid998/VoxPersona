"""
Comprehensive Test Configuration and Environment Management

This module provides centralized configuration for all testing scenarios including:
- Environment-specific test settings
- Resource allocation and limits
- Test data management configuration
- Parallel execution parameters
"""

import os
import sys
import tempfile
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# Test Environment Configuration
@dataclass
class TestEnvironmentConfig:
    """Configuration for different testing environments"""
    name: str
    description: str
    
    # Database Configuration
    db_config: Dict[str, Any] = field(default_factory=dict)
    
    # MinIO Configuration  
    minio_config: Dict[str, Any] = field(default_factory=dict)
    
    # API Configuration
    api_config: Dict[str, Any] = field(default_factory=dict)
    
    # Resource Limits
    max_parallel_tests: int = 4
    timeout_seconds: int = 300
    memory_limit_mb: int = 512
    
    # Environment-specific flags
    requires_services: bool = True
    mock_external_apis: bool = False
    cleanup_after_tests: bool = True

@dataclass
class TestResourceConfig:
    """Test resource management configuration"""
    temp_dir: Optional[str] = None
    test_data_dir: Optional[str] = None
    fixture_dir: Optional[str] = None
    output_dir: Optional[str] = None
    max_temp_size_mb: int = 1024
    cleanup_temp_files: bool = True

@dataclass
class TestExecutionConfig:
    """Test execution parameters"""
    parallel_workers: int = 4
    test_timeout: int = 300
    retry_failed_tests: bool = True
    max_retries: int = 2
    capture_output: bool = True
    verbose_output: bool = False
    fail_fast: bool = False

class TestEnvironmentManager:
    """Manages test environment configuration and setup"""
    
    def __init__(self):
        self.environments = self._initialize_environments()
        self.current_env = self._detect_environment()
        self.resource_config = self._initialize_resource_config()
        self.execution_config = self._initialize_execution_config()
        
    def _initialize_environments(self) -> Dict[str, TestEnvironmentConfig]:
        """Initialize predefined test environments"""
        return {
            'development': TestEnvironmentConfig(
                name='development',
                description='Local development environment with real services',
                db_config={
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'voxpersona_dev',
                    'user': 'test_user',
                    'password': 'test_pass'
                },
                minio_config={
                    'endpoint': 'localhost:9000',
                    'access_key': 'minioadmin',
                    'secret_key': 'minioadmin',
                    'secure': False
                },
                api_config={
                    'openai_api_key': os.getenv('TEST_OPENAI_API_KEY', 'test-key'),
                    'anthropic_api_key': os.getenv('TEST_ANTHROPIC_API_KEY', 'test-key')
                },
                requires_services=True,
                mock_external_apis=False
            ),
            
            'testing': TestEnvironmentConfig(
                name='testing',
                description='Isolated testing environment with mocked services',
                db_config={
                    'host': 'localhost',
                    'port': 5433,
                    'database': 'voxpersona_test',
                    'user': 'test_user',
                    'password': 'test_pass'
                },
                minio_config={
                    'endpoint': 'localhost:9001',
                    'access_key': 'testaccess',
                    'secret_key': 'testsecret',
                    'secure': False
                },
                api_config={
                    'openai_api_key': 'mock-openai-key',
                    'anthropic_api_key': 'mock-anthropic-key'
                },
                max_parallel_tests=8,
                requires_services=False,
                mock_external_apis=True
            ),
            
            'production': TestEnvironmentConfig(
                name='production',
                description='Production-like environment for integration tests',
                db_config={
                    'host': os.getenv('PROD_TEST_DB_HOST', 'localhost'),
                    'port': int(os.getenv('PROD_TEST_DB_PORT', '5432')),
                    'database': os.getenv('PROD_TEST_DB_NAME', 'voxpersona_prod_test'),
                    'user': os.getenv('PROD_TEST_DB_USER', 'prod_test_user'),
                    'password': os.getenv('PROD_TEST_DB_PASSWORD', 'prod_test_pass')
                },
                minio_config={
                    'endpoint': os.getenv('PROD_TEST_MINIO_ENDPOINT', 'minio:9000'),
                    'access_key': os.getenv('PROD_TEST_MINIO_ACCESS_KEY', 'prodaccess'),
                    'secret_key': os.getenv('PROD_TEST_MINIO_SECRET_KEY', 'prodsecret'),
                    'secure': True
                },
                api_config={
                    'openai_api_key': os.getenv('PROD_TEST_OPENAI_API_KEY'),
                    'anthropic_api_key': os.getenv('PROD_TEST_ANTHROPIC_API_KEY')
                },
                max_parallel_tests=2,
                timeout_seconds=600,
                requires_services=True,
                mock_external_apis=False,
                cleanup_after_tests=False
            ),
            
            'hybrid': TestEnvironmentConfig(
                name='hybrid',
                description='Mixed environment with some real and some mocked services',
                db_config={
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'voxpersona_hybrid',
                    'user': 'hybrid_user',
                    'password': 'hybrid_pass'
                },
                minio_config={
                    'endpoint': 'localhost:9000',
                    'access_key': 'hybridaccess',
                    'secret_key': 'hybridsecret',
                    'secure': False
                },
                api_config={
                    'openai_api_key': os.getenv('HYBRID_OPENAI_API_KEY', 'mock-key'),
                    'anthropic_api_key': 'mock-anthropic-key'
                },
                max_parallel_tests=6,
                requires_services=True,
                mock_external_apis=True
            )
        }
    
    def _detect_environment(self) -> str:
        """Auto-detect current test environment"""
        # Check for explicit environment variable
        env = os.getenv('TEST_ENVIRONMENT', '').lower()
        if env in self.environments:
            return env
            
        # Check for CI/CD indicators
        if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
            return 'testing'
            
        # Check for production indicators
        if os.getenv('PRODUCTION') or os.getenv('PROD'):
            return 'production'
            
        # Default to development
        return 'development'
    
    def _initialize_resource_config(self) -> TestResourceConfig:
        """Initialize resource configuration"""
        base_dir = Path(__file__).parent
        
        return TestResourceConfig(
            temp_dir=os.getenv('TEST_TEMP_DIR', tempfile.gettempdir()),
            test_data_dir=str(base_dir / 'test_data'),
            fixture_dir=str(base_dir / 'fixtures'),
            output_dir=str(base_dir / 'output'),
            max_temp_size_mb=int(os.getenv('TEST_MAX_TEMP_SIZE_MB', '1024')),
            cleanup_temp_files=os.getenv('TEST_CLEANUP_TEMP', 'true').lower() == 'true'
        )
    
    def _initialize_execution_config(self) -> TestExecutionConfig:
        """Initialize test execution configuration"""
        return TestExecutionConfig(
            parallel_workers=int(os.getenv('TEST_PARALLEL_WORKERS', '4')),
            test_timeout=int(os.getenv('TEST_TIMEOUT', '300')),
            retry_failed_tests=os.getenv('TEST_RETRY_FAILED', 'true').lower() == 'true',
            max_retries=int(os.getenv('TEST_MAX_RETRIES', '2')),
            capture_output=os.getenv('TEST_CAPTURE_OUTPUT', 'true').lower() == 'true',
            verbose_output=os.getenv('TEST_VERBOSE', 'false').lower() == 'true',
            fail_fast=os.getenv('TEST_FAIL_FAST', 'false').lower() == 'true'
        )
    
    def get_current_environment(self) -> TestEnvironmentConfig:
        """Get current test environment configuration"""
        return self.environments[self.current_env]
    
    def switch_environment(self, env_name: str) -> bool:
        """Switch to a different test environment"""
        if env_name not in self.environments:
            return False
        self.current_env = env_name
        return True
    
    def setup_environment(self) -> bool:
        """Setup the current test environment"""
        env = self.get_current_environment()
        
        try:
            # Create necessary directories
            self._create_directories()
            
            # Setup environment variables
            self._setup_environment_variables(env)
            
            # Initialize logging
            self._setup_logging()
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to setup test environment: {e}")
            return False
    
    def _create_directories(self):
        """Create necessary test directories"""
        for dir_path in [
            self.resource_config.test_data_dir,
            self.resource_config.fixture_dir,
            self.resource_config.output_dir
        ]:
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _setup_environment_variables(self, env: TestEnvironmentConfig):
        """Setup environment variables for testing"""
        # Set test environment flag
        os.environ['IS_TESTING'] = 'true'
        os.environ['RUN_MODE'] = 'TEST'
        
        # Database configuration
        for key, value in env.db_config.items():
            os.environ[f'TEST_DB_{key.upper()}'] = str(value)
        
        # MinIO configuration
        for key, value in env.minio_config.items():
            os.environ[f'MINIO_{key.upper()}'] = str(value)
        
        # API configuration
        for key, value in env.api_config.items():
            if value:  # Only set if value is not None/empty
                os.environ[key.upper()] = str(value)
    
    def _setup_logging(self):
        """Setup logging for tests"""
        log_level = logging.DEBUG if self.execution_config.verbose_output else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(
                    Path(self.resource_config.output_dir) / f'test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
                )
            ]
        )
    
    def cleanup_environment(self):
        """Cleanup test environment"""
        env = self.get_current_environment()
        
        if not env.cleanup_after_tests:
            return
            
        if self.resource_config.cleanup_temp_files:
            self._cleanup_temp_files()
    
    def _cleanup_temp_files(self):
        """Clean up temporary test files"""
        temp_dir = Path(self.resource_config.temp_dir)
        if temp_dir.exists():
            for file_path in temp_dir.glob('test_*'):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                    elif file_path.is_dir():
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    logging.warning(f"Failed to cleanup {file_path}: {e}")

# Global test environment manager instance
test_env_manager = TestEnvironmentManager()

# Convenience functions for test configuration
def get_test_config() -> TestEnvironmentConfig:
    """Get current test environment configuration"""
    return test_env_manager.get_current_environment()

def get_resource_config() -> TestResourceConfig:
    """Get test resource configuration"""
    return test_env_manager.resource_config

def get_execution_config() -> TestExecutionConfig:
    """Get test execution configuration"""
    return test_env_manager.execution_config

def setup_test_environment() -> bool:
    """Setup test environment"""
    return test_env_manager.setup_environment()

def cleanup_test_environment():
    """Cleanup test environment"""
    test_env_manager.cleanup_environment()

# Test category configuration
TEST_CATEGORIES = {
    'unit': {
        'description': 'Unit tests for individual components',
        'timeout': 60,
        'parallel': True,
        'retry': True
    },
    'integration': {
        'description': 'Integration tests for component interactions',
        'timeout': 180,
        'parallel': True,
        'retry': True
    },
    'system': {
        'description': 'End-to-end system tests',
        'timeout': 300,
        'parallel': False,
        'retry': True
    },
    'performance': {
        'description': 'Performance and load tests',
        'timeout': 600,
        'parallel': False,
        'retry': False
    },
    'security': {
        'description': 'Security and vulnerability tests',
        'timeout': 240,
        'parallel': True,
        'retry': True
    }
}

# Test data generation configuration
TEST_DATA_CONFIG = {
    'audio_files': {
        'formats': ['wav', 'mp3', 'ogg', 'flac'],
        'sizes': ['small', 'medium', 'large'],  # <1MB, 1-50MB, 50MB-2GB
        'durations': [30, 180, 3600, 7200],     # seconds
        'sample_rates': [16000, 22050, 44100],
        'channels': [1, 2]
    },
    'text_data': {
        'languages': ['en', 'ru'],
        'sizes': ['short', 'medium', 'long'],    # <100, 100-1000, >1000 words
        'types': ['interview', 'design', 'mixed']
    },
    'metadata': {
        'users': ['user_123', 'user_456', 'user_789'],
        'buildings': ['hotel', 'restaurant', 'spa'],
        'categories': ['interview', 'design', 'analysis'],
        'dates': [
            datetime.now().isoformat(),
            (datetime.now() - timedelta(days=1)).isoformat(),
            (datetime.now() - timedelta(days=30)).isoformat(),
            (datetime.now() - timedelta(days=90)).isoformat()
        ]
    }
}