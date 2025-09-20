"""
Error Recovery System for VoxPersona

This module provides comprehensive error recovery with graceful degradation
to prevent cascading system failures. It implements multiple recovery strategies
for different types of errors and maintains system stability.

Key Features:
- Multi-level recovery strategies
- Error classification and routing
- Graceful degradation mechanisms
- Recovery attempt tracking
- Circuit breaker patterns
- Fallback service implementations
"""

import logging
import time
import traceback
import functools
import threading
from typing import Dict, List, Optional, Any, Callable, Union, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from contextlib import contextmanager
import sys
from pathlib import Path

# Import our custom modules with fallback handling
try:
    from import_utils import safe_import, MockObject
    from environment import get_environment, EnvironmentType
    from path_manager import get_path, PathType, get_temp_path
except ImportError as e:
    logging.warning(f"Could not import custom modules: {e}")
    # Create minimal fallbacks
    def safe_import(*args, **kwargs):
        return None
    
    class MockObject:
        def __init__(self, name): self.name = name
        def __getattr__(self, item): return MockObject(f"{self.name}.{item}")
        def __call__(self, *args, **kwargs): return MockObject(f"{self.name}()")
    
    def get_environment():
        return MockObject("environment")
    
    def get_path(*args, **kwargs):
        return Path.cwd()
    
    def get_temp_path(*args, **kwargs):
        return Path("/tmp")

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can be recovered from"""
    IMPORT_ERROR = "import_error"
    CONFIG_ERROR = "config_error"  
    PERMISSION_ERROR = "permission_error"
    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"
    STORAGE_ERROR = "storage_error"
    NETWORK_ERROR = "network_error"
    RESOURCE_ERROR = "resource_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryStrategy(Enum):
    """Available recovery strategies"""
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    MOCK = "mock"
    CACHE = "cache"
    IGNORE = "ignore"
    FAIL_FAST = "fail_fast"


@dataclass
class RecoveryAttempt:
    """Information about a recovery attempt"""
    error_type: ErrorType
    strategy: RecoveryStrategy
    timestamp: float
    success: bool
    error_message: str
    recovery_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryPolicy:
    """Policy for handling a specific error type"""
    error_type: ErrorType
    strategies: List[RecoveryStrategy]
    max_attempts: int = 3
    backoff_multiplier: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 300.0  # 5 minutes


class RecoveryProvider(ABC):
    """Abstract base class for recovery providers"""
    
    @abstractmethod
    def can_handle(self, error_type: ErrorType, error: Exception) -> bool:
        """Check if this provider can handle the given error"""
        pass
    
    @abstractmethod
    def recover(self, error_type: ErrorType, error: Exception, context: Dict[str, Any]) -> Any:
        """Attempt to recover from the error"""
        pass


class ImportRecoveryProvider(RecoveryProvider):
    """Recovery provider for import errors"""
    
    def can_handle(self, error_type: ErrorType, error: Exception) -> bool:
        return error_type == ErrorType.IMPORT_ERROR or isinstance(error, (ImportError, ModuleNotFoundError))
    
    def recover(self, error_type: ErrorType, error: Exception, context: Dict[str, Any]) -> Any:
        module_name = context.get('module_name', 'unknown')
        
        logger.info(f"Attempting import recovery for module: {module_name}")
        
        # Try alternative import methods
        recovery_methods = [
            self._try_safe_import,
            self._try_sys_path_import,
            self._try_relative_import,
            self._create_mock_module
        ]
        
        for method in recovery_methods:
            try:
                result = method(module_name, context)
                if result:
                    logger.info(f"Import recovery successful using {method.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"Import recovery method {method.__name__} failed: {e}")
        
        # Final fallback to mock
        logger.warning(f"Using mock object for module {module_name}")
        return MockObject(module_name)
    
    def _try_safe_import(self, module_name: str, context: Dict[str, Any]) -> Any:
        """Try using safe_import if available"""
        if safe_import:
            return safe_import(module_name, required=False, fallback_to_mock=False)
        return None
    
    def _try_sys_path_import(self, module_name: str, context: Dict[str, Any]) -> Any:
        """Try importing by adding paths to sys.path"""
        import importlib
        
        # Try adding common paths
        additional_paths = [
            str(Path.cwd() / "src"),
            str(Path.cwd()),
            str(Path(__file__).parent),
        ]
        
        for path in additional_paths:
            if path not in sys.path:
                sys.path.insert(0, path)
                try:
                    return importlib.import_module(module_name)
                except ImportError:
                    sys.path.remove(path)
        
        return None
    
    def _try_relative_import(self, module_name: str, context: Dict[str, Any]) -> Any:
        """Try relative import"""
        import importlib
        
        package = context.get('package')
        if package:
            try:
                return importlib.import_module(f".{module_name}", package)
            except ImportError:
                pass
        
        return None
    
    def _create_mock_module(self, module_name: str, context: Dict[str, Any]) -> Any:
        """Create a mock module as last resort"""
        return MockObject(module_name)


class ConfigRecoveryProvider(RecoveryProvider):
    """Recovery provider for configuration errors"""
    
    def can_handle(self, error_type: ErrorType, error: Exception) -> bool:
        return error_type == ErrorType.CONFIG_ERROR
    
    def recover(self, error_type: ErrorType, error: Exception, context: Dict[str, Any]) -> Any:
        config_key = context.get('config_key', 'unknown')
        default_value = context.get('default_value')
        
        logger.info(f"Attempting config recovery for key: {config_key}")
        
        # Try various recovery strategies
        recovery_methods = [
            self._try_environment_variable,
            self._try_default_config,
            self._try_fallback_value,
        ]
        
        for method in recovery_methods:
            try:
                result = method(config_key, context)
                if result is not None:
                    logger.info(f"Config recovery successful using {method.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"Config recovery method {method.__name__} failed: {e}")
        
        logger.warning(f"Using default value for config key {config_key}: {default_value}")
        return default_value
    
    def _try_environment_variable(self, config_key: str, context: Dict[str, Any]) -> Any:
        """Try to get config from environment variable"""
        import os
        return os.environ.get(config_key.upper())
    
    def _try_default_config(self, config_key: str, context: Dict[str, Any]) -> Any:
        """Try to load from default configuration"""
        default_configs = {
            'db_host': 'localhost',
            'db_port': '5432',
            'api_timeout': '30',
            'max_retries': '3',
            'temp_dir': str(get_temp_path()),
        }
        return default_configs.get(config_key.lower())
    
    def _try_fallback_value(self, config_key: str, context: Dict[str, Any]) -> Any:
        """Return context-provided fallback value"""
        return context.get('fallback_value')


class PermissionRecoveryProvider(RecoveryProvider):
    """Recovery provider for permission errors"""
    
    def can_handle(self, error_type: ErrorType, error: Exception) -> bool:
        return (error_type == ErrorType.PERMISSION_ERROR or 
                isinstance(error, (PermissionError, OSError)) and error.errno in [13, 1])
    
    def recover(self, error_type: ErrorType, error: Exception, context: Dict[str, Any]) -> Any:
        path = context.get('path', 'unknown')
        operation = context.get('operation', 'unknown')
        
        logger.info(f"Attempting permission recovery for {operation} on {path}")
        
        recovery_methods = [
            self._try_alternative_location,
            self._try_temp_location,
            self._try_memory_operation,
        ]
        
        for method in recovery_methods:
            try:
                result = method(path, operation, context)
                if result:
                    logger.info(f"Permission recovery successful using {method.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"Permission recovery method {method.__name__} failed: {e}")
        
        logger.error(f"Could not recover from permission error for {operation} on {path}")
        return None
    
    def _try_alternative_location(self, path: str, operation: str, context: Dict[str, Any]) -> Any:
        """Try alternative location with better permissions"""
        from pathlib import Path
        
        path_obj = Path(path)
        alternative_bases = [
            Path.home() / "VoxPersona",
            Path.cwd() / "alt_storage",
            get_temp_path("alt_storage")
        ]
        
        for base in alternative_bases:
            try:
                alt_path = base / path_obj.name
                alt_path.parent.mkdir(parents=True, exist_ok=True)
                
                if operation == 'write':
                    # Test write access
                    test_file = alt_path.parent / ".write_test"
                    test_file.touch()
                    test_file.unlink()
                    return str(alt_path)
                elif operation == 'read':
                    if alt_path.exists():
                        return str(alt_path)
                
            except Exception:
                continue
        
        return None
    
    def _try_temp_location(self, path: str, operation: str, context: Dict[str, Any]) -> Any:
        """Try using temporary location"""
        import tempfile
        from pathlib import Path
        
        try:
            path_obj = Path(path)
            temp_path = get_temp_path() / path_obj.name
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Using temporary location: {temp_path}")
            return str(temp_path)
            
        except Exception as e:
            logger.debug(f"Temp location recovery failed: {e}")
            return None
    
    def _try_memory_operation(self, path: str, operation: str, context: Dict[str, Any]) -> Any:
        """Try in-memory operation as last resort"""
        if operation in ['read', 'write']:
            logger.info("Falling back to in-memory operation")
            return ":memory:"  # Special indicator for in-memory operation
        return None


class APIRecoveryProvider(RecoveryProvider):
    """Recovery provider for API errors"""
    
    def can_handle(self, error_type: ErrorType, error: Exception) -> bool:
        return error_type == ErrorType.API_ERROR
    
    def recover(self, error_type: ErrorType, error: Exception, context: Dict[str, Any]) -> Any:
        api_name = context.get('api_name', 'unknown')
        operation = context.get('operation', 'unknown')
        
        logger.info(f"Attempting API recovery for {api_name}.{operation}")
        
        recovery_methods = [
            self._try_alternative_endpoint,
            self._try_cached_response,
            self._try_fallback_service,
            self._try_mock_response,
        ]
        
        for method in recovery_methods:
            try:
                result = method(api_name, operation, context)
                if result is not None:
                    logger.info(f"API recovery successful using {method.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"API recovery method {method.__name__} failed: {e}")
        
        logger.warning(f"Using mock response for {api_name}.{operation}")
        return self._create_mock_response(api_name, operation, context)
    
    def _try_alternative_endpoint(self, api_name: str, operation: str, context: Dict[str, Any]) -> Any:
        """Try alternative API endpoint"""
        # This would contain logic to try alternative endpoints
        # For now, return None to try next strategy
        return None
    
    def _try_cached_response(self, api_name: str, operation: str, context: Dict[str, Any]) -> Any:
        """Try to return cached response"""
        # This would contain logic to retrieve cached responses
        # For now, return None to try next strategy
        return None
    
    def _try_fallback_service(self, api_name: str, operation: str, context: Dict[str, Any]) -> Any:
        """Try fallback service implementation"""
        # This would contain logic for fallback services
        # For now, return None to try next strategy
        return None
    
    def _create_mock_response(self, api_name: str, operation: str, context: Dict[str, Any]) -> Any:
        """Create a mock response"""
        if operation == 'transcribe':
            return {"text": "Mock transcription", "confidence": 0.5}
        elif operation == 'analyze':
            return {"analysis": "Mock analysis", "score": 0.5}
        else:
            return {"status": "mock_response", "data": {}}


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 300.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = 'closed'  # closed, open, half-open
        self._lock = threading.Lock()
    
    def can_proceed(self) -> bool:
        """Check if operation can proceed"""
        with self._lock:
            if self.state == 'closed':
                return True
            elif self.state == 'open':
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = 'half-open'
                    return True
                return False
            else:  # half-open
                return True
    
    def record_success(self):
        """Record successful operation"""
        with self._lock:
            self.failure_count = 0
            self.state = 'closed'
    
    def record_failure(self):
        """Record failed operation"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'


class ErrorRecoveryManager:
    """
    Main error recovery manager that coordinates recovery attempts
    """
    
    def __init__(self):
        self.providers: List[RecoveryProvider] = []
        self.policies: Dict[ErrorType, RecoveryPolicy] = {}
        self.attempt_history: List[RecoveryAttempt] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        
        # Initialize default providers
        self._register_default_providers()
        self._initialize_default_policies()
    
    def _register_default_providers(self):
        """Register default recovery providers"""
        self.register_provider(ImportRecoveryProvider())
        self.register_provider(ConfigRecoveryProvider())
        self.register_provider(PermissionRecoveryProvider())
        self.register_provider(APIRecoveryProvider())
    
    def _initialize_default_policies(self):
        """Initialize default recovery policies"""
        self.policies = {
            ErrorType.IMPORT_ERROR: RecoveryPolicy(
                error_type=ErrorType.IMPORT_ERROR,
                strategies=[RecoveryStrategy.FALLBACK, RecoveryStrategy.MOCK],
                max_attempts=2,
                initial_delay=0.1
            ),
            ErrorType.CONFIG_ERROR: RecoveryPolicy(
                error_type=ErrorType.CONFIG_ERROR,
                strategies=[RecoveryStrategy.FALLBACK, RecoveryStrategy.DEGRADE],
                max_attempts=3,
                initial_delay=0.5
            ),
            ErrorType.PERMISSION_ERROR: RecoveryPolicy(
                error_type=ErrorType.PERMISSION_ERROR,
                strategies=[RecoveryStrategy.FALLBACK, RecoveryStrategy.DEGRADE],
                max_attempts=3,
                initial_delay=1.0
            ),
            ErrorType.API_ERROR: RecoveryPolicy(
                error_type=ErrorType.API_ERROR,
                strategies=[RecoveryStrategy.RETRY, RecoveryStrategy.CACHE, RecoveryStrategy.MOCK],
                max_attempts=3,
                initial_delay=2.0,
                circuit_breaker_threshold=5
            ),
            ErrorType.DATABASE_ERROR: RecoveryPolicy(
                error_type=ErrorType.DATABASE_ERROR,
                strategies=[RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK],
                max_attempts=3,
                initial_delay=1.0,
                circuit_breaker_threshold=3
            ),
            ErrorType.NETWORK_ERROR: RecoveryPolicy(
                error_type=ErrorType.NETWORK_ERROR,
                strategies=[RecoveryStrategy.RETRY, RecoveryStrategy.CACHE],
                max_attempts=5,
                initial_delay=1.0,
                backoff_multiplier=2.0
            ),
        }
    
    def register_provider(self, provider: RecoveryProvider):
        """Register a recovery provider"""
        self.providers.append(provider)
        logger.debug(f"Registered recovery provider: {provider.__class__.__name__}")
    
    def classify_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorType:
        """Classify an error to determine recovery strategy"""
        context = context or {}
        
        if isinstance(error, (ImportError, ModuleNotFoundError)):
            return ErrorType.IMPORT_ERROR
        elif isinstance(error, (PermissionError, OSError)) and getattr(error, 'errno', None) in [13, 1]:
            return ErrorType.PERMISSION_ERROR
        elif 'config' in str(error).lower() or 'configuration' in str(error).lower():
            return ErrorType.CONFIG_ERROR
        elif 'api' in str(error).lower() or 'http' in str(error).lower():
            return ErrorType.API_ERROR
        elif 'database' in str(error).lower() or 'connection' in str(error).lower():
            return ErrorType.DATABASE_ERROR
        elif 'network' in str(error).lower() or 'timeout' in str(error).lower():
            return ErrorType.NETWORK_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR
    
    def recover(self, error: Exception, context: Dict[str, Any] = None) -> Any:
        """
        Attempt to recover from an error
        
        Args:
            error: The exception that occurred
            context: Additional context for recovery
            
        Returns:
            Recovery result or None if recovery failed
        """
        context = context or {}
        error_type = self.classify_error(error, context)
        
        logger.info(f"Attempting recovery for {error_type.value}: {error}")
        
        # Check circuit breaker
        breaker_key = f"{error_type.value}_{context.get('operation', 'default')}"
        if breaker_key not in self.circuit_breakers:
            policy = self.policies.get(error_type, RecoveryPolicy(error_type, []))
            self.circuit_breakers[breaker_key] = CircuitBreaker(
                policy.circuit_breaker_threshold,
                policy.circuit_breaker_timeout
            )
        
        circuit_breaker = self.circuit_breakers[breaker_key]
        if not circuit_breaker.can_proceed():
            logger.warning(f"Circuit breaker open for {breaker_key}")
            return None
        
        # Find suitable provider
        provider = self._find_provider(error_type, error)
        if not provider:
            logger.error(f"No recovery provider found for {error_type.value}")
            circuit_breaker.record_failure()
            return None
        
        # Attempt recovery
        start_time = time.time()
        try:
            result = provider.recover(error_type, error, context)
            recovery_time = time.time() - start_time
            
            # Record successful attempt
            attempt = RecoveryAttempt(
                error_type=error_type,
                strategy=RecoveryStrategy.FALLBACK,  # This could be more specific
                timestamp=start_time,
                success=True,
                error_message=str(error),
                recovery_time=recovery_time,
                details=context
            )
            
            with self._lock:
                self.attempt_history.append(attempt)
                # Keep only last 1000 attempts
                if len(self.attempt_history) > 1000:
                    self.attempt_history = self.attempt_history[-1000:]
            
            circuit_breaker.record_success()
            logger.info(f"Recovery successful for {error_type.value} in {recovery_time:.2f}s")
            return result
            
        except Exception as recovery_error:
            recovery_time = time.time() - start_time
            
            # Record failed attempt
            attempt = RecoveryAttempt(
                error_type=error_type,
                strategy=RecoveryStrategy.FALLBACK,
                timestamp=start_time,
                success=False,
                error_message=str(recovery_error),
                recovery_time=recovery_time,
                details=context
            )
            
            with self._lock:
                self.attempt_history.append(attempt)
            
            circuit_breaker.record_failure()
            logger.error(f"Recovery failed for {error_type.value}: {recovery_error}")
            return None
    
    def _find_provider(self, error_type: ErrorType, error: Exception) -> Optional[RecoveryProvider]:
        """Find a suitable recovery provider for the given error"""
        for provider in self.providers:
            if provider.can_handle(error_type, error):
                return provider
        return None
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        with self._lock:
            total_attempts = len(self.attempt_history)
            successful_attempts = sum(1 for attempt in self.attempt_history if attempt.success)
            
            if total_attempts == 0:
                return {"total_attempts": 0, "success_rate": 0.0}
            
            success_rate = successful_attempts / total_attempts
            
            # Group by error type
            error_type_stats = {}
            for attempt in self.attempt_history:
                error_type = attempt.error_type.value
                if error_type not in error_type_stats:
                    error_type_stats[error_type] = {"total": 0, "successful": 0}
                
                error_type_stats[error_type]["total"] += 1
                if attempt.success:
                    error_type_stats[error_type]["successful"] += 1
            
            return {
                "total_attempts": total_attempts,
                "successful_attempts": successful_attempts,
                "success_rate": success_rate,
                "error_type_breakdown": error_type_stats,
                "circuit_breaker_states": {
                    key: breaker.state for key, breaker in self.circuit_breakers.items()
                }
            }


# Global error recovery manager
_recovery_manager = ErrorRecoveryManager()


def get_recovery_manager() -> ErrorRecoveryManager:
    """Get the global error recovery manager"""
    return _recovery_manager


def recover_from_error(error: Exception, context: Dict[str, Any] = None) -> Any:
    """Convenience function to recover from an error"""
    return _recovery_manager.recover(error, context)


def with_recovery(context: Dict[str, Any] = None):
    """
    Decorator to automatically handle errors with recovery
    
    Usage:
        @with_recovery({'operation': 'file_read', 'path': '/some/path'})
        def read_file(path):
            with open(path, 'r') as f:
                return f.read()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Error in {func.__name__}: {e}")
                
                recovery_context = context or {}
                recovery_context.update({
                    'function_name': func.__name__,
                    'args': args[:3],  # First 3 args only to avoid huge logs
                    'kwargs': {k: v for k, v in kwargs.items() if len(str(v)) < 100}
                })
                
                result = recover_from_error(e, recovery_context)
                if result is not None:
                    return result
                
                # If recovery failed, re-raise the original error
                raise
        
        return wrapper
    return decorator


@contextmanager
def recovery_context(context: Dict[str, Any] = None):
    """
    Context manager for error recovery
    
    Usage:
        with recovery_context({'operation': 'api_call', 'api_name': 'openai'}):
            result = some_api_call()
    """
    try:
        yield
    except Exception as e:
        logger.debug(f"Error in recovery context: {e}")
        
        result = recover_from_error(e, context or {})
        if result is not None:
            return result
        
        # If recovery failed, re-raise the original error
        raise


if __name__ == "__main__":
    # When run directly, show recovery manager status
    print("VoxPersona Error Recovery System")
    print("=" * 40)
    
    recovery_manager = get_recovery_manager()
    stats = recovery_manager.get_recovery_stats()
    
    print(f"Recovery attempts: {stats['total_attempts']}")
    print(f"Success rate: {stats['success_rate']:.2%}")
    
    if stats['error_type_breakdown']:
        print("\nError type breakdown:")
        for error_type, breakdown in stats['error_type_breakdown'].items():
            success_rate = breakdown['successful'] / breakdown['total'] if breakdown['total'] > 0 else 0
            print(f"  {error_type}: {breakdown['successful']}/{breakdown['total']} ({success_rate:.2%})")
    
    if stats['circuit_breaker_states']:
        print("\nCircuit breaker states:")
        for key, state in stats['circuit_breaker_states'].items():
            print(f"  {key}: {state}")