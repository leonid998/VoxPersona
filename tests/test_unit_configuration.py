"""
Unit Tests for Configuration Validation

This module provides comprehensive testing of the VoxPersona configuration system including:
- Environment detection and validation
- Dynamic path resolution testing
- Configuration fallback mechanisms
- Permission handling validation
- Health reporting and validation checks
"""

import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tests.test_config import get_test_config, test_env_manager


class TestEnvironmentDetection(unittest.TestCase):
    """Test environment detection mechanisms"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_pytest_detection(self):
        """Test PyTest environment detection"""
        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_something.py'}):
            # Clear config module to force reimport
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            self.assertTrue(config.is_testing_environment())
            self.assertTrue(config.IS_TESTING)
    
    def test_sys_modules_pytest_detection(self):
        """Test PyTest detection via sys.modules"""
        with patch.dict(sys.modules, {'pytest': MagicMock()}):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            self.assertTrue(config.is_testing_environment())
    
    def test_custom_testing_flag_detection(self):
        """Test custom IS_TESTING flag detection"""
        with patch.dict(os.environ, {'IS_TESTING': 'true'}):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            self.assertTrue(config.is_testing_environment())
            self.assertTrue(config.IS_TESTING)
    
    def test_run_mode_detection(self):
        """Test RUN_MODE environment variable detection"""
        with patch.dict(os.environ, {'RUN_MODE': 'TEST'}):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            self.assertTrue(config.is_testing_environment())
            self.assertEqual(config.RUN_MODE, 'TEST')
    
    def test_production_environment_detection(self):
        """Test production environment detection"""
        with patch.dict(os.environ, {
            'RUN_MODE': 'PROD',
            'IS_TESTING': 'false',
            'PYTEST_CURRENT_TEST': '',
        }, clear=False):
            # Remove pytest from sys.modules if present
            if 'pytest' in sys.modules:
                pytest_module = sys.modules.pop('pytest')
            else:
                pytest_module = None
            
            try:
                if 'src.config' in sys.modules:
                    del sys.modules['src.config']
                
                import src.config as config
                self.assertFalse(config.is_testing_environment())
                
            finally:
                # Restore pytest module if it was there
                if pytest_module is not None:
                    sys.modules['pytest'] = pytest_module
    
    def test_environment_priority_order(self):
        """Test environment detection priority order"""
        # Test that PYTEST_CURRENT_TEST has highest priority
        with patch.dict(os.environ, {
            'PYTEST_CURRENT_TEST': 'test.py',
            'IS_TESTING': 'false',
            'RUN_MODE': 'PROD'
        }):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            self.assertTrue(config.is_testing_environment())


class TestDynamicPathResolution(unittest.TestCase):
    """Test dynamic path resolution functionality"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dirs = []
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Clean up temporary directories"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def create_temp_dir(self) -> str:
        """Create and track temporary directory"""
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def test_storage_directory_creation(self):
        """Test storage directory creation"""
        temp_base = self.create_temp_dir()
        
        # Mock storage directories to use temp location
        with patch.dict(os.environ, {'TEMP_STORAGE_BASE': temp_base}):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            # Modify STORAGE_DIRS to use temp location
            test_dirs = {
                "audio": os.path.join(temp_base, "audio_files"),
                "text_without_roles": os.path.join(temp_base, "text_without_roles"), 
                "text_with_roles": os.path.join(temp_base, "text_with_roles")
            }
            
            config.STORAGE_DIRS = test_dirs
            
            # Test directory creation
            config.ensure_storage_directories()
            
            # Verify directories were created
            for dir_name, dir_path in test_dirs.items():
                with self.subTest(directory=dir_name):
                    self.assertTrue(os.path.exists(dir_path), 
                                  f"Directory {dir_path} was not created")
                    self.assertTrue(os.path.isdir(dir_path),
                                  f"Path {dir_path} is not a directory")
    
    def test_rag_directory_creation(self):
        """Test RAG index directory creation"""
        temp_base = self.create_temp_dir()
        
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Set RAG directory to temp location
        config.RAG_INDEX_DIR = os.path.join(temp_base, "rag_indices")
        
        # Test RAG directory creation
        result = config.ensure_rag_directory()
        
        self.assertTrue(result, "ensure_rag_directory should return True on success")
        self.assertTrue(os.path.exists(config.RAG_INDEX_DIR),
                       f"RAG directory {config.RAG_INDEX_DIR} was not created")
    
    def test_directory_creation_failure_handling(self):
        """Test handling of directory creation failures"""
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Try to create directory in non-existent parent
        invalid_path = "/non/existent/path/that/cannot/be/created"
        config.RAG_INDEX_DIR = invalid_path
        
        # Should handle failure gracefully
        result = config.ensure_rag_directory()
        self.assertFalse(result, "ensure_rag_directory should return False on failure")
    
    def test_path_resolution_across_platforms(self):
        """Test path resolution works across different platforms"""
        test_paths = [
            "/unix/style/path",
            "C:\\Windows\\Style\\Path", 
            "./relative/path",
            "../parent/relative/path"
        ]
        
        for test_path in test_paths:
            with self.subTest(path=test_path):
                # Test that Path can handle the format
                path_obj = Path(test_path)
                self.assertIsInstance(path_obj, Path)
                
                # Test path operations
                self.assertIsInstance(str(path_obj), str)
                self.assertIsInstance(path_obj.parts, tuple)


class TestConfigurationFallbackMechanisms(unittest.TestCase):
    """Test configuration fallback mechanisms"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_database_config_fallback(self):
        """Test database configuration fallback"""
        # Test with missing environment variables
        with patch.dict(os.environ, {}, clear=True):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            # Should have fallback database configuration
            self.assertIsInstance(config.DB_CONFIG, dict)
            
            # Should contain required keys even if values are None
            required_keys = ['dbname', 'user', 'password', 'host', 'port']
            for key in required_keys:
                self.assertIn(key, config.DB_CONFIG)
    
    def test_minio_config_fallback(self):
        """Test MinIO configuration fallback"""
        with patch.dict(os.environ, {}, clear=True):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            # Should have fallback MinIO configuration
            self.assertIsNotNone(config.MINIO_AUDIO_BUCKET_NAME)
            self.assertEqual(config.MINIO_AUDIO_BUCKET_NAME, "voxpersona-audio")
    
    def test_integer_config_fallback(self):
        """Test integer configuration fallback"""
        with patch.dict(os.environ, {
            'MINIO_HEALTH_CHECK_INTERVAL': 'invalid',
            'MINIO_MAX_RETRIES': 'not_a_number'
        }):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            # Should fall back to default values
            self.assertEqual(config.MINIO_HEALTH_CHECK_INTERVAL, 60)
            self.assertEqual(config.MINIO_MAX_RETRIES, 3)
    
    def test_boolean_config_fallback(self):
        """Test boolean configuration fallback"""
        with patch.dict(os.environ, {'MINIO_USE_SSL': 'invalid_bool'}):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            # Should fall back to False for invalid boolean
            self.assertFalse(config.MINIO_USE_SSL)
    
    def test_tiktoken_encoding_fallback(self):
        """Test tiktoken encoding fallback"""
        # Test when model is not available
        with patch.dict(os.environ, {'REPORT_MODEL_NAME': ''}):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            # Should fall back to default encoding
            self.assertIsNotNone(config.ENC)
        
        # Test when tiktoken fails entirely
        with patch('tiktoken.encoding_for_model', side_effect=Exception("Tiktoken error")):
            with patch('tiktoken.get_encoding') as mock_get_encoding:
                mock_get_encoding.return_value = MagicMock()
                
                if 'src.config' in sys.modules:
                    del sys.modules['src.config']
                
                import src.config as config
                
                # Should fall back to cl100k_base
                mock_get_encoding.assert_called_with("cl100k_base")


class TestPermissionHandling(unittest.TestCase):
    """Test permission handling and validation"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dirs = []
    
    def tearDown(self):
        """Clean up temporary directories"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def create_temp_dir(self) -> str:
        """Create and track temporary directory"""
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def test_readable_directory_access(self):
        """Test access to readable directories"""
        temp_dir = self.create_temp_dir()
        
        # Ensure directory is readable
        os.chmod(temp_dir, 0o755)
        
        # Test directory access
        self.assertTrue(os.access(temp_dir, os.R_OK))
        self.assertTrue(os.access(temp_dir, os.X_OK))
    
    def test_writable_directory_access(self):
        """Test access to writable directories"""
        temp_dir = self.create_temp_dir()
        
        # Ensure directory is writable
        os.chmod(temp_dir, 0o755)
        
        # Test directory write access
        self.assertTrue(os.access(temp_dir, os.W_OK))
        
        # Test creating files in directory
        test_file = os.path.join(temp_dir, "test_file.txt")
        try:
            with open(test_file, 'w') as f:
                f.write("test content")
            self.assertTrue(os.path.exists(test_file))
        except PermissionError:
            self.fail("Should be able to write to writable directory")
    
    @unittest.skipIf(os.name == 'nt', "Permission tests not reliable on Windows")
    def test_readonly_directory_handling(self):
        """Test handling of read-only directories"""
        temp_dir = self.create_temp_dir()
        
        # Make directory read-only
        os.chmod(temp_dir, 0o555)
        
        try:
            # Should not be able to write to read-only directory
            self.assertFalse(os.access(temp_dir, os.W_OK))
            
            # Test that code handles read-only gracefully
            test_file = os.path.join(temp_dir, "test_file.txt")
            with self.assertRaises(PermissionError):
                with open(test_file, 'w') as f:
                    f.write("test content")
                    
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_dir, 0o755)
    
    def test_permission_error_recovery(self):
        """Test recovery from permission errors"""
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Mock permission error during directory creation
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            # Should handle permission error gracefully
            try:
                config.ensure_storage_directories()
                # Should not raise exception
            except PermissionError:
                self.fail("Should handle permission errors gracefully")


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation mechanisms"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_required_api_keys_validation_production(self):
        """Test required API keys validation in production"""
        # Test missing API keys in production
        with patch.dict(os.environ, {
            'RUN_MODE': 'PROD',
            'IS_TESTING': 'false'
        }, clear=True):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            with self.assertRaises(ValueError) as context:
                import src.config as config
            
            self.assertIn("Missing required API keys", str(context.exception))
    
    def test_api_keys_validation_skipped_testing(self):
        """Test API keys validation is skipped in testing"""
        with patch.dict(os.environ, {
            'RUN_MODE': 'TEST',
            'IS_TESTING': 'true'
        }, clear=True):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            try:
                import src.config as config
                # Should not raise exception in testing mode
                self.assertTrue(config.IS_TESTING)
            except ValueError:
                self.fail("Should not validate API keys in testing mode")
    
    def test_database_config_validation(self):
        """Test database configuration validation"""
        # Test with valid database config
        with patch.dict(os.environ, {
            'RUN_MODE': 'TEST',
            'TEST_DB_NAME': 'test_db',
            'TEST_DB_USER': 'test_user',
            'TEST_DB_PASSWORD': 'test_pass',
            'TEST_DB_HOST': 'localhost',
            'TEST_DB_PORT': '5432'
        }):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            self.assertEqual(config.DB_CONFIG['dbname'], 'test_db')
            self.assertEqual(config.DB_CONFIG['user'], 'test_user')
            self.assertEqual(config.DB_CONFIG['host'], 'localhost')
            self.assertEqual(config.DB_CONFIG['port'], '5432')
    
    def test_minio_configuration_validation(self):
        """Test MinIO configuration validation"""
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'test_access',
            'MINIO_SECRET_KEY': 'test_secret',
            'MINIO_BUCKET_NAME': 'test-bucket'
        }):
            if 'src.config' in sys.modules:
                del sys.modules['src.config']
            
            import src.config as config
            
            self.assertEqual(config.MINIO_ENDPOINT, 'localhost:9000')
            self.assertEqual(config.MINIO_ACCESS_KEY, 'test_access')
            self.assertEqual(config.MINIO_SECRET_KEY, 'test_secret')
            self.assertEqual(config.MINIO_BUCKET_NAME, 'test-bucket')


class TestHealthReporting(unittest.TestCase):
    """Test configuration health reporting"""
    
    def test_environment_health_check(self):
        """Test environment health check functionality"""
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Should be able to detect testing environment
        self.assertTrue(config.is_testing_environment())
        
        # Should have basic configuration loaded
        self.assertIsNotNone(config.DB_CONFIG)
        self.assertIsNotNone(config.processed_texts)
        self.assertIsNotNone(config.user_states)
    
    def test_configuration_completeness_check(self):
        """Test configuration completeness validation"""
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Test that essential configuration items exist
        essential_configs = [
            'DB_CONFIG',
            'STORAGE_DIRS', 
            'RAG_INDEX_DIR',
            'processed_texts',
            'user_states',
            'authorized_users'
        ]
        
        for config_name in essential_configs:
            with self.subTest(config=config_name):
                self.assertTrue(hasattr(config, config_name),
                              f"Essential config {config_name} is missing")
    
    def test_configuration_types_validation(self):
        """Test configuration types are correct"""
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Test configuration types
        self.assertIsInstance(config.DB_CONFIG, dict)
        self.assertIsInstance(config.STORAGE_DIRS, dict)
        self.assertIsInstance(config.processed_texts, dict)
        self.assertIsInstance(config.user_states, dict)
        self.assertIsInstance(config.authorized_users, set)
        self.assertIsInstance(config.IS_TESTING, bool)


if __name__ == '__main__':
    unittest.main(verbosity=2)