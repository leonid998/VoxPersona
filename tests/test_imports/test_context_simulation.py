"""Context simulation and import validation testing system.

This module provides comprehensive testing of import behavior across
different execution contexts including package, standalone, and CI environments.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from unittest.mock import patch, MagicMock
from enum import Enum
import subprocess
import threading
import time

from tests.framework.base_test import BaseTest
from src.import_utils import SafeImporter
from src.environment import EnvironmentDetector


class ExecutionContext(Enum):
    """Different execution contexts for testing."""
    PACKAGE = "package"           # Running as installed package
    STANDALONE = "standalone"     # Running as standalone script
    CI_GITHUB = "ci_github"       # GitHub Actions CI
    CI_GITLAB = "ci_gitlab"       # GitLab CI
    DOCKER = "docker"             # Docker container
    DEVELOPMENT = "development"   # Development environment
    PRODUCTION = "production"     # Production environment
    TEST = "test"                 # Test environment


class ContextSimulator:
    """Simulates different execution contexts for import testing."""
    
    def __init__(self):
        """Initialize context simulator."""
        self.original_env = os.environ.copy()
        self.original_sys_path = sys.path.copy()
        self.original_modules = set(sys.modules.keys())
        self.temp_dirs = []
        
    def __enter__(self):
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and cleanup."""
        self.cleanup()
    
    def simulate_context(self, context: ExecutionContext) -> Dict[str, Any]:
        """Simulate specific execution context.
        
        Args:
            context: Context to simulate
            
        Returns:
            Dictionary with context information and cleanup function
        """
        if context == ExecutionContext.PACKAGE:
            return self._simulate_package_context()
        elif context == ExecutionContext.STANDALONE:
            return self._simulate_standalone_context()
        elif context == ExecutionContext.CI_GITHUB:
            return self._simulate_github_ci_context()
        elif context == ExecutionContext.CI_GITLAB:
            return self._simulate_gitlab_ci_context()
        elif context == ExecutionContext.DOCKER:
            return self._simulate_docker_context()
        elif context == ExecutionContext.DEVELOPMENT:
            return self._simulate_development_context()
        elif context == ExecutionContext.PRODUCTION:
            return self._simulate_production_context()
        elif context == ExecutionContext.TEST:
            return self._simulate_test_context()
        else:
            raise ValueError(f"Unknown context: {context}")
    
    def _simulate_package_context(self) -> Dict[str, Any]:
        """Simulate running as installed package."""
        # Create fake package structure
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        
        package_dir = Path(temp_dir) / "voxpersona"
        package_dir.mkdir()
        
        # Create __init__.py
        (package_dir / "__init__.py").write_text('__version__ = "1.0.0"')
        
        # Update sys.path
        sys.path.insert(0, str(temp_dir))
        
        # Set package environment
        env_patches = {
            "PYTHONPATH": str(temp_dir),
            "VOXPERSONA_PACKAGE_MODE": "true"
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.PACKAGE,
            "package_dir": package_dir,
            "temp_dir": temp_dir,
            "env_patches": env_patches,
            "description": "Package installation context"
        }
    
    def _simulate_standalone_context(self) -> Dict[str, Any]:
        """Simulate running as standalone script."""
        # Create standalone script directory
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        
        script_path = Path(temp_dir) / "voxpersona_standalone.py"
        script_path.write_text("""
# Standalone VoxPersona script
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Standalone execution marker
STANDALONE_MODE = True
""")
        
        # Remove package-related paths
        original_path = sys.path.copy()
        sys.path = [p for p in sys.path if 'voxpersona' not in p.lower()]
        sys.path.insert(0, str(temp_dir))
        
        # Set standalone environment
        env_patches = {
            "VOXPERSONA_STANDALONE": "true",
            "PYTHONPATH": str(temp_dir)
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.STANDALONE,
            "script_path": script_path,
            "temp_dir": temp_dir,
            "original_path": original_path,
            "env_patches": env_patches,
            "description": "Standalone script execution"
        }
    
    def _simulate_github_ci_context(self) -> Dict[str, Any]:
        """Simulate GitHub Actions CI environment."""
        env_patches = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_WORKFLOW": "VoxPersona CI",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_NUMBER": "42",
            "GITHUB_SHA": "abc123def456",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "test/voxpersona",
            "GITHUB_WORKSPACE": "/github/workspace",
            "RUNNER_OS": "Linux",
            "RUNNER_ARCH": "X64"
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.CI_GITHUB,
            "env_patches": env_patches,
            "description": "GitHub Actions CI environment"
        }
    
    def _simulate_gitlab_ci_context(self) -> Dict[str, Any]:
        """Simulate GitLab CI environment."""
        env_patches = {
            "CI": "true",
            "GITLAB_CI": "true",
            "CI_JOB_ID": "123456",
            "CI_JOB_NAME": "test",
            "CI_JOB_STAGE": "test",
            "CI_PIPELINE_ID": "789012",
            "CI_COMMIT_SHA": "abc123def456",
            "CI_COMMIT_REF_NAME": "main",
            "CI_PROJECT_NAME": "voxpersona",
            "CI_PROJECT_PATH": "test/voxpersona",
            "CI_SERVER_NAME": "GitLab"
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.CI_GITLAB,
            "env_patches": env_patches,
            "description": "GitLab CI environment"
        }
    
    def _simulate_docker_context(self) -> Dict[str, Any]:
        """Simulate Docker container environment."""
        env_patches = {
            "DOCKER_CONTAINER": "true",
            "HOSTNAME": "voxpersona-container",
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/root",
            "VOXPERSONA_DOCKER": "true"
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.DOCKER,
            "env_patches": env_patches,
            "description": "Docker container environment"
        }
    
    def _simulate_development_context(self) -> Dict[str, Any]:
        """Simulate development environment."""
        env_patches = {
            "VOXPERSONA_ENV": "development",
            "VOXPERSONA_DEBUG": "true",
            "VOXPERSONA_LOG_LEVEL": "DEBUG",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1"
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.DEVELOPMENT,
            "env_patches": env_patches,
            "description": "Development environment"
        }
    
    def _simulate_production_context(self) -> Dict[str, Any]:
        """Simulate production environment."""
        env_patches = {
            "VOXPERSONA_ENV": "production",
            "VOXPERSONA_DEBUG": "false",
            "VOXPERSONA_LOG_LEVEL": "ERROR",
            "PYTHONOPTIMIZE": "2"
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.PRODUCTION,
            "env_patches": env_patches,
            "description": "Production environment"
        }
    
    def _simulate_test_context(self) -> Dict[str, Any]:
        """Simulate test environment."""
        env_patches = {
            "VOXPERSONA_ENV": "test",
            "VOXPERSONA_TESTING": "true",
            "VOXPERSONA_LOG_LEVEL": "WARNING",
            "PYTHONPATH": os.pathsep.join(sys.path)
        }
        
        for key, value in env_patches.items():
            os.environ[key] = value
        
        return {
            "context": ExecutionContext.TEST,
            "env_patches": env_patches,
            "description": "Test environment"
        }
    
    def cleanup(self):
        """Clean up simulated context."""
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore sys.path
        sys.path.clear()
        sys.path.extend(self.original_sys_path)
        
        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
        self.temp_dirs.clear()
        
        # Remove added modules (keep original ones)
        current_modules = set(sys.modules.keys())
        added_modules = current_modules - self.original_modules
        
        for module_name in added_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]


class ImportContextTest(BaseTest):
    """Test import behavior across different contexts."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.simulator = ContextSimulator()
        self.importer = SafeImporter()
        self.env_detector = EnvironmentDetector()
    
    def tearDown(self):
        """Clean up test environment."""
        self.simulator.cleanup()
        super().tearDown()
    
    def test_import_in_package_context(self):
        """Test imports in package context."""
        with self.simulator:
            context_info = self.simulator.simulate_context(ExecutionContext.PACKAGE)
            
            # Test standard imports
            os_module = self.importer.safe_import('os')
            self.assertIsNotNone(os_module)
            self.assertTrue(hasattr(os_module, 'path'))
            
            # Test scientific imports
            numpy_module = self.importer.safe_import('numpy')
            self.assertIsNotNone(numpy_module)
            
            # Environment should detect package context
            env_info = self.env_detector.detect_environment()
            self.assertIn('package', env_info.get('context_markers', []))
    
    def test_import_in_standalone_context(self):
        """Test imports in standalone context."""
        with self.simulator:
            context_info = self.simulator.simulate_context(ExecutionContext.STANDALONE)
            
            # Test that imports still work in standalone
            sys_module = self.importer.safe_import('sys')
            self.assertIsNotNone(sys_module)
            
            # Test fallback for missing modules
            missing_module = self.importer.safe_import('definitely_not_installed_module')
            self.assertIsNotNone(missing_module)
            self.assertTrue(hasattr(missing_module, '__name__'))
            
            # Environment should detect standalone context
            env_info = self.env_detector.detect_environment()
            self.assertTrue(env_info.get('is_standalone', False))
    
    def test_import_in_ci_contexts(self):
        """Test imports in CI environments."""
        ci_contexts = [ExecutionContext.CI_GITHUB, ExecutionContext.CI_GITLAB]
        
        for ci_context in ci_contexts:
            with self.simulator:
                context_info = self.simulator.simulate_context(ci_context)
                
                # Test basic imports
                json_module = self.importer.safe_import('json')
                self.assertIsNotNone(json_module)
                
                # Test that environment is detected as CI
                env_info = self.env_detector.detect_environment()
                self.assertEqual(env_info['environment'], 'ci')
                
                # Test missing optional dependencies
                optional_module = self.importer.safe_import('optional_ci_dependency')
                self.assertIsNotNone(optional_module)  # Should get mock
    
    def test_import_in_docker_context(self):
        """Test imports in Docker context."""
        with self.simulator:
            context_info = self.simulator.simulate_context(ExecutionContext.DOCKER)
            
            # Test container-aware imports
            pathlib_module = self.importer.safe_import('pathlib')
            self.assertIsNotNone(pathlib_module)
            
            # Environment should detect Docker
            env_info = self.env_detector.detect_environment()
            self.assertTrue(env_info.get('is_containerized', False))
            self.assertEqual(env_info['environment'], 'docker')
    
    def test_import_fallback_behavior(self):
        """Test import fallback behavior across contexts."""
        test_modules = [
            'numpy',
            'librosa', 
            'matplotlib',
            'minio',
            'tensorflow',
            'definitely_not_a_real_module'
        ]
        
        contexts = [
            ExecutionContext.PACKAGE,
            ExecutionContext.STANDALONE,
            ExecutionContext.CI_GITHUB,
            ExecutionContext.DOCKER
        ]
        
        for context in contexts:
            with self.simulator:
                context_info = self.simulator.simulate_context(context)
                
                for module_name in test_modules:
                    with self.subTest(context=context, module=module_name):
                        # Import should never fail, should return real module or mock
                        module = self.importer.safe_import(module_name)
                        self.assertIsNotNone(module)
                        
                        # Mock modules should have basic attributes
                        if not hasattr(module, '__file__'):  # Likely a mock
                            self.assertTrue(hasattr(module, '__name__'))
    
    def test_concurrent_imports_different_contexts(self):
        """Test concurrent imports across different contexts."""
        import threading
        import time
        
        results = {}
        errors = []
        
        def import_worker(context, worker_id):
            try:
                with ContextSimulator():
                    simulator = ContextSimulator()
                    context_info = simulator.simulate_context(context)
                    
                    importer = SafeImporter()
                    
                    # Test multiple imports
                    modules = ['os', 'sys', 'json', 'pathlib', 'fake_module']
                    imported_modules = {}
                    
                    for module_name in modules:
                        module = importer.safe_import(module_name)
                        imported_modules[module_name] = module is not None
                    
                    results[f"{context.value}_{worker_id}"] = {
                        'context': context.value,
                        'imports': imported_modules,
                        'success': True
                    }
                    
            except Exception as e:
                errors.append(f"{context.value}_{worker_id}: {str(e)}")
        
        # Start workers for different contexts
        threads = []
        contexts = [
            ExecutionContext.PACKAGE,
            ExecutionContext.STANDALONE,
            ExecutionContext.CI_GITHUB,
            ExecutionContext.DOCKER
        ]
        
        for i, context in enumerate(contexts):
            thread = threading.Thread(target=import_worker, args=(context, i))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertFalse(errors, f"Errors occurred: {errors}")
        self.assertEqual(len(results), len(contexts))
        
        # All workers should have successfully imported modules
        for worker_result in results.values():
            self.assertTrue(worker_result['success'])
            for module_name, imported in worker_result['imports'].items():
                self.assertTrue(imported, f"Failed to import {module_name}")
    
    def test_environment_detection_consistency(self):
        """Test that environment detection is consistent across contexts."""
        contexts = [
            ExecutionContext.DEVELOPMENT,
            ExecutionContext.PRODUCTION,
            ExecutionContext.TEST,
            ExecutionContext.CI_GITHUB,
            ExecutionContext.DOCKER
        ]
        
        for context in contexts:
            with self.simulator:
                context_info = self.simulator.simulate_context(context)
                
                # Run detection multiple times
                detector = EnvironmentDetector()
                
                env_results = []
                for _ in range(3):
                    env_info = detector.detect_environment()
                    env_results.append(env_info['environment'])
                
                # Results should be consistent
                self.assertEqual(len(set(env_results)), 1, 
                               f"Inconsistent environment detection for {context}")
                
                # Environment should match expected context
                expected_env = self._get_expected_environment(context)
                if expected_env:
                    self.assertEqual(env_results[0], expected_env)
    
    def _get_expected_environment(self, context: ExecutionContext) -> Optional[str]:
        """Get expected environment name for context."""
        mapping = {
            ExecutionContext.DEVELOPMENT: 'development',
            ExecutionContext.PRODUCTION: 'production',
            ExecutionContext.TEST: 'test',
            ExecutionContext.CI_GITHUB: 'ci',
            ExecutionContext.CI_GITLAB: 'ci',
            ExecutionContext.DOCKER: 'docker'
        }
        return mapping.get(context)


if __name__ == '__main__':
    import unittest
    unittest.main()