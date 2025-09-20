"""
Defensive Import System for VoxPersona

This module provides a robust import system that handles various execution contexts
(package, standalone, CI/CD) with automatic fallback mechanisms to prevent
cascading failures from import errors.

Key Features:
- Automatic context detection (package vs standalone execution)
- Fallback from relative to absolute imports
- Detailed error logging and diagnostics
- Graceful degradation with mock objects when needed
- Thread-safe import operations
"""

import sys
import os
import logging
import importlib
import importlib.util
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path
import threading
from functools import wraps
from types import ModuleType

logger = logging.getLogger(__name__)

class ImportContext:
    """Detect and manage different execution contexts"""
    
    @staticmethod
    def is_package_context() -> bool:
        """Check if we're running within a package context"""
        frame = sys._getframe(1)
        return frame.f_globals.get('__package__') is not None
    
    @staticmethod
    def is_docker_context() -> bool:
        """Check if we're running in a Docker container"""
        return os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
    
    @staticmethod
    def is_ci_context() -> bool:
        """Check if we're running in a CI/CD environment"""
        ci_indicators = ['CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_URL']
        return any(os.environ.get(indicator) for indicator in ci_indicators)
    
    @staticmethod
    def is_test_context() -> bool:
        """Check if we're running in a test environment"""
        return (
            'pytest' in sys.modules or
            'unittest' in sys.modules or
            os.environ.get('RUN_MODE') == 'TEST' or
            'test' in sys.argv[0].lower()
        )
    
    @staticmethod
    def get_context_info() -> Dict[str, Any]:
        """Get comprehensive context information"""
        return {
            'package_context': ImportContext.is_package_context(),
            'docker_context': ImportContext.is_docker_context(),
            'ci_context': ImportContext.is_ci_context(),
            'test_context': ImportContext.is_test_context(),
            'python_path': sys.path,
            'current_module': sys._getframe(1).f_globals.get('__name__'),
            'current_package': sys._getframe(1).f_globals.get('__package__'),
            'working_directory': os.getcwd(),
            'script_path': sys.argv[0] if sys.argv else None
        }


class ImportError(Exception):
    """Custom exception for import-related errors"""
    def __init__(self, message: str, module_name: str, context: Dict[str, Any]):
        super().__init__(message)
        self.module_name = module_name
        self.context = context


class MockObject:
    """A mock object that can be used as a fallback when imports fail"""
    
    def __init__(self, name: str):
        self.name = name
        self._attributes = {}
    
    def __getattr__(self, item):
        if item not in self._attributes:
            self._attributes[item] = MockObject(f"{self.name}.{item}")
        return self._attributes[item]
    
    def __call__(self, *args, **kwargs):
        logger.warning(f"Mock object {self.name} called with args={args}, kwargs={kwargs}")
        return MockObject(f"{self.name}()")
    
    def __str__(self):
        return f"MockObject({self.name})"
    
    def __repr__(self):
        return self.__str__()


class SafeImporter:
    """
    A thread-safe importer that tries multiple import strategies and provides fallbacks
    """
    
    _instance = None
    _lock = threading.Lock()
    _imported_modules: Dict[str, ModuleType] = {}
    _failed_imports: Dict[str, List[str]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.context = ImportContext.get_context_info()
            self._initialized = True
    
    def safe_import(
        self,
        module_name: str,
        package: Optional[str] = None,
        fallback_to_mock: bool = True,
        required: bool = True
    ) -> Union[ModuleType, MockObject, None]:
        """
        Safely import a module with multiple fallback strategies
        
        Args:
            module_name: Name of the module to import
            package: Package name for relative imports
            fallback_to_mock: Whether to return a mock object if all imports fail
            required: Whether this import is required for system operation
            
        Returns:
            Imported module, mock object, or None
        """
        with self._lock:
            # Check if already imported
            if module_name in self._imported_modules:
                return self._imported_modules[module_name]
            
            strategies = self._get_import_strategies(module_name, package)
            
            for strategy_name, strategy_func in strategies:
                try:
                    logger.debug(f"Trying import strategy '{strategy_name}' for {module_name}")
                    module = strategy_func()
                    if module:
                        self._imported_modules[module_name] = module
                        logger.info(f"Successfully imported {module_name} using {strategy_name}")
                        return module
                        
                except Exception as e:
                    error_msg = f"Import strategy '{strategy_name}' failed for {module_name}: {e}"
                    logger.debug(error_msg)
                    
                    if module_name not in self._failed_imports:
                        self._failed_imports[module_name] = []
                    self._failed_imports[module_name].append(error_msg)
            
            # All strategies failed
            self._log_import_failure(module_name)
            
            if fallback_to_mock:
                mock_obj = MockObject(module_name)
                logger.warning(f"Using mock object for {module_name}")
                return mock_obj
            
            if required:
                raise ImportError(
                    f"Failed to import required module {module_name}",
                    module_name,
                    self.context
                )
            
            return None
    
    def _get_import_strategies(self, module_name: str, package: Optional[str] = None) -> List[tuple]:
        """Get ordered list of import strategies to try"""
        strategies = []
        
        # Strategy 1: Direct import (works for absolute and installed packages)
        strategies.append(("direct_import", lambda: importlib.import_module(module_name)))
        
        # Strategy 2: Relative import (if in package context)
        if self.context['package_context'] and package:
            strategies.append((
                "relative_import",
                lambda: importlib.import_module(f".{module_name}", package)
            ))
        
        # Strategy 3: Path-based import (for local modules)
        strategies.append(("path_based_import", lambda: self._path_based_import(module_name)))
        
        # Strategy 4: Search in sys.path
        strategies.append(("sys_path_search", lambda: self._sys_path_search(module_name)))
        
        return strategies
    
    def _path_based_import(self, module_name: str) -> Optional[ModuleType]:
        """Try to import module by searching filesystem paths"""
        possible_paths = [
            Path.cwd() / "src" / f"{module_name}.py",
            Path.cwd() / f"{module_name}.py",
            Path(__file__).parent / f"{module_name}.py",
        ]
        
        for path in possible_paths:
            if path.exists():
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return module
        
        return None
    
    def _sys_path_search(self, module_name: str) -> Optional[ModuleType]:
        """Search for module in sys.path directories"""
        for path in sys.path:
            module_path = Path(path) / f"{module_name}.py"
            if module_path.exists():
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return module
        
        return None
    
    def _log_import_failure(self, module_name: str):
        """Log detailed information about import failure"""
        logger.error(f"Failed to import {module_name} after trying all strategies")
        logger.error(f"Context: {self.context}")
        
        if module_name in self._failed_imports:
            logger.error("Failed attempts:")
            for attempt in self._failed_imports[module_name]:
                logger.error(f"  - {attempt}")


# Global importer instance
_importer = SafeImporter()


def safe_import(
    module_name: str,
    package: Optional[str] = None,
    fallback_to_mock: bool = True,
    required: bool = True
) -> Union[ModuleType, MockObject, None]:
    """
    Convenient function for safe module importing
    
    Usage:
        # Basic import
        config = safe_import('config')
        
        # Relative import with package
        utils = safe_import('utils', package='mypackage')
        
        # Optional import (returns None if fails)
        optional_module = safe_import('optional_module', required=False, fallback_to_mock=False)
    """
    return _importer.safe_import(module_name, package, fallback_to_mock, required)


def import_from(module_name: str, *attributes: str, package: Optional[str] = None) -> Dict[str, Any]:
    """
    Safely import specific attributes from a module
    
    Usage:
        # Import specific functions
        funcs = import_from('utils', 'function1', 'function2')
        
        # Use the imported functions
        result = funcs['function1']()
    """
    module = safe_import(module_name, package=package)
    result = {}
    
    for attr in attributes:
        if hasattr(module, attr):
            result[attr] = getattr(module, attr)
        else:
            logger.warning(f"Attribute '{attr}' not found in module '{module_name}'")
            result[attr] = MockObject(f"{module_name}.{attr}")
    
    return result


def require_module(module_name: str, package: Optional[str] = None):
    """
    Decorator to ensure a module is available before function execution
    
    Usage:
        @require_module('config')
        def process_config():
            # This function will only run if 'config' module is available
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            module = safe_import(module_name, package=package, required=True)
            if isinstance(module, MockObject):
                raise ImportError(f"Required module '{module_name}' not available")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def optional_import(module_name: str, default_value: Any = None, package: Optional[str] = None) -> Any:
    """
    Import a module optionally, returning a default value if import fails
    
    Usage:
        # Import optional module with default
        optional_config = optional_import('optional_config', default_value={})
    """
    try:
        module = safe_import(module_name, package=package, required=False, fallback_to_mock=False)
        return module if module is not None else default_value
    except:
        return default_value


def get_import_diagnostics() -> Dict[str, Any]:
    """Get diagnostic information about import system state"""
    return {
        'context': _importer.context,
        'imported_modules': list(_importer._imported_modules.keys()),
        'failed_imports': dict(_importer._failed_imports),
        'import_count': len(_importer._imported_modules),
        'failure_count': len(_importer._failed_imports)
    }


# Convenience functions for common import patterns
def safe_import_config():
    """Safely import the config module with VoxPersona-specific fallbacks"""
    return safe_import('config', fallback_to_mock=False, required=True)


def safe_import_handlers():
    """Safely import the handlers module"""
    return safe_import('handlers', fallback_to_mock=True, required=False)


def safe_import_analysis():
    """Safely import the analysis module"""
    return safe_import('analysis', fallback_to_mock=True, required=False)


# Module-level convenience imports for backward compatibility
if __name__ != "__main__":
    # Only perform automatic imports when this module is imported, not when run directly
    try:
        # These will be available as module attributes if imports succeed
        globals().update(import_from('config', 'DB_CONFIG', 'TELEGRAM_BOT_TOKEN', package=None))
    except:
        logger.debug("Could not perform automatic convenience imports")