"""
Unit tests for import_utils module

Tests the SafeImporter system and its various import strategies
"""

import unittest
import sys
import os
import tempfile
import importlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from framework import VoxPersonaTestCase, skip_if_no_enhanced_systems

try:
    from import_utils import (
        SafeImporter, ImportContext, MockObject, safe_import,
        import_from, require_module, optional_import, get_import_diagnostics
    )
    IMPORT_UTILS_AVAILABLE = True
except ImportError:
    IMPORT_UTILS_AVAILABLE = False


@unittest.skipUnless(IMPORT_UTILS_AVAILABLE, "import_utils not available")
class TestImportContext(VoxPersonaTestCase):
    """Test ImportContext functionality"""
    
    def test_is_package_context_detection(self):
        """Test package context detection"""
        # This is tricky to test directly, so we test the logic
        with patch('sys._getframe') as mock_frame:
            mock_globals = {'__package__': 'test_package'}
            mock_frame.return_value.f_globals = mock_globals
            
            result = ImportContext.is_package_context()
            self.assertTrue(result)
            
            # Test when no package
            mock_globals = {'__package__': None}
            mock_frame.return_value.f_globals = mock_globals
            
            result = ImportContext.is_package_context()
            self.assertFalse(result)
    
    def test_is_docker_context_detection(self):
        """Test Docker context detection"""
        # Test with .dockerenv file
        docker_file = self.temp_dir / '.dockerenv'
        docker_file.touch()
        
        with patch('os.path.exists', return_value=True):
            result = ImportContext.is_docker_context()
            self.assertTrue(result)
        
        # Test with environment variable
        with patch.dict(os.environ, {'DOCKER_CONTAINER': 'true'}):
            result = ImportContext.is_docker_context()
            self.assertTrue(result)
        
        # Test negative case
        with patch('os.path.exists', return_value=False), \
             patch.dict(os.environ, {}, clear=True):
            result = ImportContext.is_docker_context()
            self.assertFalse(result)
    
    def test_is_ci_context_detection(self):
        """Test CI context detection"""
        ci_vars = ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_URL']
        
        for var in ci_vars:
            with patch.dict(os.environ, {var: 'true'}):
                result = ImportContext.is_ci_context()
                self.assertTrue(result, f"Should detect CI with {var}")
        
        # Test negative case
        with patch.dict(os.environ, {}, clear=True):
            result = ImportContext.is_ci_context()
            self.assertFalse(result)
    
    def test_is_test_context_detection(self):
        """Test test context detection"""
        # Test with RUN_MODE
        with patch.dict(os.environ, {'RUN_MODE': 'TEST'}):
            result = ImportContext.is_test_context()
            self.assertTrue(result)
        
        # Test with pytest in sys.modules
        with patch.dict(sys.modules, {'pytest': Mock()}):
            result = ImportContext.is_test_context()
            self.assertTrue(result)
        
        # Test with test in argv
        with patch.object(sys, 'argv', ['test_script.py']):
            result = ImportContext.is_test_context()
            self.assertTrue(result)
    
    def test_get_context_info(self):
        """Test comprehensive context information gathering"""
        context_info = ImportContext.get_context_info()
        
        # Check that all expected keys are present
        expected_keys = [
            'package_context', 'docker_context', 'ci_context', 'test_context',
            'python_path', 'current_module', 'current_package', 
            'working_directory', 'script_path'
        ]
        
        for key in expected_keys:
            self.assertIn(key, context_info)
        
        # Check types
        self.assertIsInstance(context_info['package_context'], bool)
        self.assertIsInstance(context_info['docker_context'], bool)
        self.assertIsInstance(context_info['ci_context'], bool)
        self.assertIsInstance(context_info['test_context'], bool)
        self.assertIsInstance(context_info['python_path'], list)


class TestMockObject(VoxPersonaTestCase):
    """Test MockObject functionality"""
    
    def test_mock_object_creation(self):
        """Test MockObject creation and basic functionality"""
        mock = MockObject('test_module')
        self.assertEqual(mock.name, 'test_module')
    
    def test_mock_object_attribute_access(self):
        """Test MockObject attribute access"""
        mock = MockObject('test_module')
        
        # Access non-existent attribute
        attr = mock.some_attribute
        self.assertIsInstance(attr, MockObject)
        self.assertEqual(attr.name, 'test_module.some_attribute')
        
        # Access the same attribute again (should be cached)
        attr2 = mock.some_attribute
        self.assertIs(attr, attr2)
    
    def test_mock_object_call(self):
        """Test MockObject call functionality"""
        mock = MockObject('test_function')
        
        # Call the mock object
        result = mock('arg1', 'arg2', kwarg='value')
        self.assertIsInstance(result, MockObject)
        self.assertEqual(result.name, 'test_function()')
    
    def test_mock_object_chaining(self):
        """Test MockObject method chaining"""
        mock = MockObject('test_module')
        
        # Chain attribute access and calls
        result = mock.submodule.function('arg').method()
        self.assertIsInstance(result, MockObject)
        self.assertTrue('test_module.submodule.function().method()' in result.name)
    
    def test_mock_object_str_repr(self):
        """Test MockObject string representation"""
        mock = MockObject('test_module')
        
        str_repr = str(mock)
        self.assertEqual(str_repr, 'MockObject(test_module)')
        
        repr_str = repr(mock)
        self.assertEqual(repr_str, 'MockObject(test_module)')


@unittest.skipUnless(IMPORT_UTILS_AVAILABLE, "import_utils not available")
class TestSafeImporter(VoxPersonaTestCase):
    """Test SafeImporter functionality"""
    
    def setUp(self):
        super().setUp()
        self.importer = SafeImporter()
    
    def test_singleton_pattern(self):
        """Test that SafeImporter follows singleton pattern"""
        importer1 = SafeImporter()
        importer2 = SafeImporter()
        self.assertIs(importer1, importer2)
    
    def test_safe_import_standard_library(self):
        """Test importing standard library modules"""
        os_module = self.importer.safe_import('os')
        self.assertIsNotNone(os_module)
        self.assertTrue(hasattr(os_module, 'path'))
        self.assertFalse(isinstance(os_module, MockObject))
    
    def test_safe_import_nonexistent_module(self):
        """Test importing non-existent module with fallback to mock"""
        mock_module = self.importer.safe_import('nonexistent_module_12345')
        self.assertIsInstance(mock_module, MockObject)
        self.assertEqual(mock_module.name, 'nonexistent_module_12345')
    
    def test_safe_import_required_failure(self):
        """Test that required import failure raises exception"""
        with self.assertRaises(Exception):
            self.importer.safe_import(
                'nonexistent_module_12345', 
                fallback_to_mock=False, 
                required=True
            )
    
    def test_safe_import_caching(self):
        """Test that successfully imported modules are cached"""
        # Import the same module twice
        module1 = self.importer.safe_import('os')
        module2 = self.importer.safe_import('os')
        
        # Should return the same cached instance
        self.assertIs(module1, module2)
    
    def test_safe_import_with_package(self):
        """Test safe import with package parameter"""
        # This is harder to test without creating actual modules
        # Test that package parameter is passed through
        with patch.object(self.importer, '_get_import_strategies') as mock_strategies:
            mock_strategies.return_value = []
            
            self.importer.safe_import('test_module', package='test_package')
            mock_strategies.assert_called_once_with('test_module', 'test_package')
    
    def test_import_strategies_order(self):
        """Test that import strategies are tried in correct order"""
        strategies = self.importer._get_import_strategies('test_module', 'test_package')
        
        # Should have multiple strategies
        self.assertGreater(len(strategies), 0)
        
        # First strategy should be direct import
        self.assertEqual(strategies[0][0], 'direct_import')
    
    def test_path_based_import(self):
        """Test path-based import strategy"""
        # Create a temporary Python file
        test_module_path = self.temp_dir / 'test_module.py'
        test_module_path.write_text('TEST_VAR = "test_value"')
        
        # Patch Path.cwd to return our temp directory
        with patch('pathlib.Path.cwd', return_value=self.temp_dir):
            module = self.importer._path_based_import('test_module')
            
            if module:  # May not work in all environments
                self.assertTrue(hasattr(module, 'TEST_VAR'))
                self.assertEqual(module.TEST_VAR, 'test_value')


class TestSafeImportFunctions(VoxPersonaTestCase):
    """Test module-level safe import functions"""
    
    @skip_if_no_enhanced_systems
    def test_safe_import_function(self):
        """Test safe_import convenience function"""
        os_module = safe_import('os')
        self.assertIsNotNone(os_module)
        self.assertTrue(hasattr(os_module, 'path'))
    
    @skip_if_no_enhanced_systems
    def test_import_from_function(self):
        """Test import_from function"""
        attrs = import_from('os', 'path', 'environ')
        
        self.assertIn('path', attrs)
        self.assertIn('environ', attrs)
        self.assertIsNotNone(attrs['path'])
        self.assertIsNotNone(attrs['environ'])
    
    @skip_if_no_enhanced_systems
    def test_import_from_missing_attribute(self):
        """Test import_from with missing attribute"""
        attrs = import_from('os', 'nonexistent_attribute')
        
        self.assertIn('nonexistent_attribute', attrs)
        self.assertIsInstance(attrs['nonexistent_attribute'], MockObject)
    
    @skip_if_no_enhanced_systems
    def test_optional_import_success(self):
        """Test optional_import with successful import"""
        result = optional_import('os', default_value='default')
        self.assertIsNotNone(result)
        self.assertNotEqual(result, 'default')
    
    @skip_if_no_enhanced_systems
    def test_optional_import_failure(self):
        """Test optional_import with failed import"""
        result = optional_import('nonexistent_module_12345', default_value='default')
        self.assertEqual(result, 'default')
    
    @skip_if_no_enhanced_systems
    def test_require_module_decorator(self):
        """Test require_module decorator"""
        @require_module('os')
        def test_function():
            return 'success'
        
        # Should work with existing module
        result = test_function()
        self.assertEqual(result, 'success')
        
        # Should fail with non-existent module
        @require_module('nonexistent_module_12345')
        def failing_function():
            return 'should not reach here'
        
        with self.assertRaises(Exception):
            failing_function()
    
    @skip_if_no_enhanced_systems
    def test_get_import_diagnostics(self):
        """Test import diagnostics function"""
        # Import something first to have data
        safe_import('os')
        
        diagnostics = get_import_diagnostics()
        
        expected_keys = [
            'context', 'imported_modules', 'failed_imports',
            'import_count', 'failure_count'
        ]
        
        for key in expected_keys:
            self.assertIn(key, diagnostics)
        
        self.assertIsInstance(diagnostics['imported_modules'], list)
        self.assertIsInstance(diagnostics['failed_imports'], dict)
        self.assertIsInstance(diagnostics['import_count'], int)
        self.assertIsInstance(diagnostics['failure_count'], int)


class TestImportErrorScenarios(VoxPersonaTestCase):
    """Test various import error scenarios and recovery"""
    
    @skip_if_no_enhanced_systems
    def test_import_error_recovery(self):
        """Test that import errors are properly handled"""
        # Try to import a module that definitely doesn't exist
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            result = safe_import('definitely_nonexistent_module')
            
            # Should return a mock object
            self.assertIsInstance(result, MockObject)
    
    @skip_if_no_enhanced_systems  
    def test_permission_error_during_import(self):
        """Test handling of permission errors during import"""
        with patch('importlib.import_module', side_effect=PermissionError("Access denied")):
            result = safe_import('test_module')
            
            # Should still return a mock object
            self.assertIsInstance(result, MockObject)
    
    @skip_if_no_enhanced_systems
    def test_multiple_import_strategies_failure(self):
        """Test when multiple import strategies fail"""
        importer = SafeImporter()
        
        # Mock all strategies to fail
        with patch.object(importer, '_get_import_strategies') as mock_get_strategies:
            mock_get_strategies.return_value = [
                ('strategy1', lambda: None),
                ('strategy2', lambda: None),
                ('strategy3', lambda: None),
            ]
            
            result = importer.safe_import('test_module')
            self.assertIsInstance(result, MockObject)


if __name__ == '__main__':
    unittest.main()