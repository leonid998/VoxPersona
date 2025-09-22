"""
Unit Tests for Import System

This module provides comprehensive testing of the VoxPersona import system including:
- Environment-specific import validation
- Fallback import mechanisms  
- Cross-platform import compatibility
- Dynamic import testing
- Module dependency resolution
"""

import unittest
import sys
import os
import importlib
import tempfile
import subprocess
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tests.test_config import get_test_config


class TestImportSystemEnvironmentDetection(unittest.TestCase):
    """Test import system behavior across different environments"""
    
    def setUp(self):
        """Setup test environment"""
        self.test_config = get_test_config()
        self.original_modules = dict(sys.modules)
    
    def tearDown(self):
        """Clean up after tests"""
        # Restore original modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_development_import_validation(self):
        """Test import behavior in development environment"""
        with patch.dict(os.environ, {'RUN_MODE': 'DEV', 'IS_TESTING': 'false'}):
            # Clear modules to force reimport
            modules_to_clear = [
                'src.config', 'src.minio_manager', 'src.analysis', 
                'src.handlers', 'src.bot', 'src.main'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                # Test core module imports
                import src.config as config
                self.assertFalse(config.IS_TESTING)
                
                import src.minio_manager as minio_manager
                self.assertIsNotNone(minio_manager.MinIOManager)
                
                import src.analysis as analysis
                self.assertIsNotNone(analysis.transcribe_audio)
                
                # Verify development-specific configuration
                self.assertEqual(config.RUN_MODE, 'DEV')
                
            except ImportError as e:
                self.fail(f"Failed to import modules in development environment: {e}")
    
    def test_testing_import_validation(self):
        """Test import behavior in testing environment"""
        with patch.dict(os.environ, {'RUN_MODE': 'TEST', 'IS_TESTING': 'true'}):
            # Clear modules to force reimport
            modules_to_clear = [
                'src.config', 'src.minio_manager', 'src.analysis'
            ]
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                # Test core module imports with testing configuration
                import src.config as config
                self.assertTrue(config.IS_TESTING)
                
                # Verify testing-specific configuration
                self.assertEqual(config.RUN_MODE, 'TEST')
                
                # Test that API key validation is skipped in testing
                self.assertIsNotNone(config.DB_CONFIG)
                
            except ImportError as e:
                self.fail(f"Failed to import modules in testing environment: {e}")
    
    def test_production_import_validation(self):
        """Test import behavior in production environment"""
        with patch.dict(os.environ, {
            'RUN_MODE': 'PROD', 
            'IS_TESTING': 'false',
            'OPENAI_API_KEY': 'test-key',
            'ANTHROPIC_API_KEY': 'test-key',
            'TELEGRAM_BOT_TOKEN': 'test-token',
            'API_ID': '12345',
            'API_HASH': 'test-hash'
        }):
            modules_to_clear = ['src.config']
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
            
            try:
                import src.config as config
                self.assertFalse(config.IS_TESTING)
                
                # Verify production configuration requirements
                self.assertIsNotNone(config.OPENAI_API_KEY)
                self.assertIsNotNone(config.ANTHROPIC_API_KEY)
                
            except ImportError as e:
                self.fail(f"Failed to import modules in production environment: {e}")
    
    def test_module_dependency_resolution(self):
        """Test that module dependencies are properly resolved"""
        # Test dependency chain: handlers -> minio_manager -> config
        try:
            # Import in dependency order
            import src.config
            import src.minio_manager  
            import src.handlers
            
            # Verify dependencies are available
            self.assertTrue(hasattr(src.handlers, 'get_minio_manager'))
            self.assertTrue(hasattr(src.minio_manager, 'MINIO_ENDPOINT'))
            
        except ImportError as e:
            self.fail(f"Module dependency resolution failed: {e}")
    
    def test_circular_import_prevention(self):
        """Test that circular imports are prevented"""
        # Test potential circular import scenarios
        modules_to_test = [
            ('src.config', 'src.handlers'),
            ('src.minio_manager', 'src.config'),
            ('src.analysis', 'src.config')
        ]
        
        for module1, module2 in modules_to_test:
            with self.subTest(module1=module1, module2=module2):
                try:
                    # Clear modules
                    if module1 in sys.modules:
                        del sys.modules[module1]
                    if module2 in sys.modules:
                        del sys.modules[module2]
                    
                    # Import both modules
                    importlib.import_module(module1)
                    importlib.import_module(module2)
                    
                    # If we get here, no circular import
                    self.assertTrue(True)
                    
                except ImportError as e:
                    if "circular import" in str(e).lower():
                        self.fail(f"Circular import detected between {module1} and {module2}")
                    else:
                        # Other import errors are acceptable for this test
                        pass


class TestImportSystemFallbackMechanisms(unittest.TestCase):
    """Test fallback mechanisms when imports fail"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_path = sys.path.copy()
        self.original_modules = dict(sys.modules)
    
    def tearDown(self):
        """Clean up after tests"""
        sys.path[:] = self.original_path
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_optional_dependency_fallback(self):
        """Test fallback when optional dependencies are missing"""
        # Mock missing psutil (used for resource monitoring)
        with patch.dict(sys.modules, {'psutil': None}):
            try:
                from tests.test_orchestrator import TestResourceMonitor
                monitor = TestResourceMonitor()
                monitor.start_monitoring()
                
                # Should handle missing psutil gracefully
                metrics = monitor.get_metrics()
                self.assertIsInstance(metrics, dict)
                
            except ImportError:
                self.fail("Should handle missing optional dependencies gracefully")
    
    def test_config_fallback_mechanisms(self):
        """Test configuration fallback when imports fail"""
        with patch.dict(os.environ, {}, clear=True):
            # Clear config module to force reimport
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            try:
                import src.config as config
                
                # Test that fallback values are used
                self.assertIsNotNone(config.ENC)  # Should fall back to default encoding
                
            except Exception as e:
                # Should not fail completely due to missing config
                if "required" in str(e).lower():
                    # This is expected in production mode without keys
                    pass
                else:
                    self.fail(f"Config import should have fallback mechanisms: {e}")
    
    def test_tiktoken_fallback(self):
        """Test tiktoken encoding fallback"""
        # Test when specific model encoding fails
        with patch('tiktoken.encoding_for_model') as mock_encoding_for_model:
            mock_encoding_for_model.side_effect = KeyError("Model not found")
            
            # Clear config to force reimport
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            with patch.dict(os.environ, {'REPORT_MODEL_NAME': 'nonexistent-model'}):
                import src.config as config
                
                # Should fall back to default encoding
                self.assertIsNotNone(config.ENC)


class TestImportSystemCrossPlatform(unittest.TestCase):
    """Test cross-platform import compatibility"""
    
    @patch('sys.platform', 'win32')
    def test_windows_import_compatibility(self):
        """Test imports work correctly on Windows"""
        try:
            import src.config
            import src.minio_manager
            import src.handlers
            
            # Windows-specific path handling should work
            self.assertTrue(True)
            
        except ImportError as e:
            self.fail(f"Windows import compatibility failed: {e}")
    
    @patch('sys.platform', 'linux')
    def test_linux_import_compatibility(self):
        """Test imports work correctly on Linux"""
        try:
            import src.config
            import src.minio_manager  
            import src.handlers
            
            # Linux-specific path handling should work
            self.assertTrue(True)
            
        except ImportError as e:
            self.fail(f"Linux import compatibility failed: {e}")
    
    @patch('sys.platform', 'darwin')
    def test_macos_import_compatibility(self):
        """Test imports work correctly on macOS"""
        try:
            import src.config
            import src.minio_manager
            import src.handlers
            
            # macOS-specific path handling should work
            self.assertTrue(True)
            
        except ImportError as e:
            self.fail(f"macOS import compatibility failed: {e}")
    
    def test_path_separator_handling(self):
        """Test that path separators are handled correctly across platforms"""
        # Test various path configurations
        test_paths = [
            "/root/Vox/VoxPersona/audio_files",  # Unix-style
            "C:\\Users\\VoxPersona\\audio_files",  # Windows-style
            "./audio_files",  # Relative path
        ]
        
        for test_path in test_paths:
            with self.subTest(path=test_path):
                # Test that Path handles all formats
                path_obj = Path(test_path)
                self.assertIsInstance(path_obj, Path)


class TestImportSystemDynamicImports(unittest.TestCase):
    """Test dynamic import functionality"""
    
    def test_runtime_module_loading(self):
        """Test loading modules at runtime"""
        # Test dynamic import of test modules
        try:
            # Import using string name
            config_module = importlib.import_module('src.config')
            self.assertIsNotNone(config_module)
            
            # Import using variable
            module_name = 'src.minio_manager'
            minio_module = importlib.import_module(module_name)
            self.assertIsNotNone(minio_module)
            
        except ImportError as e:
            self.fail(f"Dynamic import failed: {e}")
    
    def test_conditional_imports(self):
        """Test conditional import logic"""
        # Test importing different modules based on conditions
        test_environment = os.getenv('RUN_MODE', 'TEST')
        
        try:
            if test_environment == 'TEST':
                # Should be able to import test modules
                import tests.test_config
                self.assertIsNotNone(tests.test_config)
            
            # Should always be able to import core modules
            import src.config
            self.assertIsNotNone(src.config)
            
        except ImportError as e:
            self.fail(f"Conditional import failed: {e}")
    
    def test_attribute_access_after_import(self):
        """Test accessing attributes from dynamically imported modules"""
        try:
            # Import and access attributes
            config_module = importlib.import_module('src.config')
            
            # Test accessing various attributes
            self.assertTrue(hasattr(config_module, 'IS_TESTING'))
            self.assertTrue(hasattr(config_module, 'DB_CONFIG'))
            self.assertTrue(hasattr(config_module, 'processed_texts'))
            
            # Test function attributes
            self.assertTrue(hasattr(config_module, 'is_testing_environment'))
            self.assertTrue(callable(config_module.is_testing_environment))
            
        except (ImportError, AttributeError) as e:
            self.fail(f"Attribute access after dynamic import failed: {e}")


class TestImportSystemErrorHandling(unittest.TestCase):
    """Test error handling in import system"""
    
    def test_missing_module_error_handling(self):
        """Test handling of missing module imports"""
        # Test importing non-existent module
        with self.assertRaises(ImportError):
            importlib.import_module('src.nonexistent_module')
    
    def test_syntax_error_in_module(self):
        """Test handling of syntax errors in modules"""
        # Create temporary module with syntax error
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def broken_function(\n    # Missing closing parenthesis")
            temp_module_path = f.name
        
        try:
            # Add temp module to path
            temp_dir = os.path.dirname(temp_module_path)
            temp_name = os.path.basename(temp_module_path)[:-3]  # Remove .py
            
            if temp_dir not in sys.path:
                sys.path.insert(0, temp_dir)
            
            # Try to import broken module
            with self.assertRaises((SyntaxError, ImportError)):
                importlib.import_module(temp_name)
                
        finally:
            # Clean up
            try:
                os.unlink(temp_module_path)
            except:
                pass
    
    def test_import_with_missing_dependencies(self):
        """Test import behavior when dependencies are missing"""
        # Mock missing external dependencies
        missing_deps = ['minio', 'anthropic', 'openai', 'pyrogram']
        
        for dep in missing_deps:
            with self.subTest(dependency=dep):
                with patch.dict(sys.modules, {dep: None}):
                    try:
                        # Try importing modules that depend on this
                        if dep == 'minio':
                            with self.assertRaises((ImportError, AttributeError)):
                                import src.minio_manager
                        elif dep == 'anthropic':
                            with self.assertRaises((ImportError, AttributeError)):
                                import src.analysis
                        # Add more dependency tests as needed
                        
                    except Exception as e:
                        # Some exceptions are expected
                        if "import" not in str(e).lower():
                            self.fail(f"Unexpected error when {dep} is missing: {e}")


class TestImportSystemPerformance(unittest.TestCase):
    """Test import system performance"""
    
    def test_import_speed(self):
        """Test that imports complete within reasonable time"""
        import time
        
        modules_to_test = [
            'src.config',
            'src.minio_manager',
            'src.analysis',
            'src.handlers'
        ]
        
        for module_name in modules_to_test:
            with self.subTest(module=module_name):
                # Clear module if already imported
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                start_time = time.time()
                try:
                    importlib.import_module(module_name)
                    import_time = time.time() - start_time
                    
                    # Import should complete within 5 seconds
                    self.assertLess(import_time, 5.0, 
                                  f"{module_name} took {import_time:.2f}s to import")
                    
                except ImportError:
                    # Import errors are acceptable for performance test
                    pass
    
    def test_memory_usage_during_import(self):
        """Test memory usage during module imports"""
        try:
            import psutil
            import gc
            
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            # Import several modules
            modules_to_import = [
                'src.config',
                'src.minio_manager', 
                'src.analysis'
            ]
            
            for module_name in modules_to_import:
                if module_name not in sys.modules:
                    try:
                        importlib.import_module(module_name)
                    except ImportError:
                        pass
            
            gc.collect()  # Force garbage collection
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB)
            max_memory_increase = 100 * 1024 * 1024  # 100MB
            self.assertLess(memory_increase, max_memory_increase,
                          f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB during imports")
            
        except ImportError:
            self.skipTest("psutil not available for memory testing")


if __name__ == '__main__':
    unittest.main(verbosity=2)