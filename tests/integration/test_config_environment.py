"""Integration tests for Config + Environment interaction."""
import os
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from tests.framework.base_test import BaseIntegrationTest
from src.config import VoxPersonaConfig
from src.environment import EnvironmentDetector
from src.path_manager import PathManager


class TestConfigEnvironmentIntegration(BaseIntegrationTest):
    """Test integration between configuration and environment systems."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.json"
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        super().tearDown()
    
    def test_config_adapts_to_environment_changes(self):
        """Test that configuration adapts when environment changes."""
        detector = EnvironmentDetector()
        config = VoxPersonaConfig()
        
        # Test development environment
        with patch.dict(os.environ, {"VOXPERSONA_ENV": "development"}):
            detector._cached_environment = None  # Clear cache
            env_info = detector.detect_environment()
            config.load_for_environment(env_info)
            
            self.assertEqual(env_info['environment'], 'development')
            self.assertTrue(config.debug_mode)
            self.assertIn('debug', config.log_level.lower())
    
    def test_path_resolution_with_different_environments(self):
        """Test path resolution across different environments."""
        path_manager = PathManager()
        
        # Test CI environment
        with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}):
            detector = EnvironmentDetector()
            detector._cached_environment = None
            env_info = detector.detect_environment()
            
            self.assertEqual(env_info['environment'], 'ci')
            
            # Test path resolution in CI
            config_path = path_manager.get_config_path()
            self.assertTrue(config_path.exists() or config_path.parent.exists())
    
    def test_config_loading_with_missing_files(self):
        """Test configuration loading with missing files in different environments."""
        config = VoxPersonaConfig()
        
        # Test with non-existent config file
        with patch.dict(os.environ, {"VOXPERSONA_CONFIG": str(self.config_file)}):
            # Should not raise exception, should use defaults
            result = config.load_config()
            self.assertIsNotNone(result)
            self.assertEqual(config.app_name, "VoxPersona")
    
    def test_environment_specific_config_overrides(self):
        """Test that environment-specific configurations override defaults."""
        config = VoxPersonaConfig()
        
        # Test production environment overrides
        with patch.dict(os.environ, {
            "VOXPERSONA_ENV": "production",
            "VOXPERSONA_DEBUG": "false",
            "VOXPERSONA_LOG_LEVEL": "ERROR"
        }):
            detector = EnvironmentDetector()
            detector._cached_environment = None
            env_info = detector.detect_environment()
            config.load_for_environment(env_info)
            
            self.assertEqual(env_info['environment'], 'production')
            self.assertFalse(config.debug_mode)
            self.assertEqual(config.log_level, "ERROR")
    
    def test_docker_environment_integration(self):
        """Test configuration in Docker environment."""
        with patch.dict(os.environ, {
            "DOCKER_CONTAINER": "true",
            "HOSTNAME": "voxpersona-container"
        }):
            detector = EnvironmentDetector()
            detector._cached_environment = None
            env_info = detector.detect_environment()
            
            self.assertEqual(env_info['environment'], 'docker')
            self.assertTrue(env_info['is_containerized'])
            
            # Test path resolution in Docker
            path_manager = PathManager()
            data_path = path_manager.get_data_path()
            self.assertIsNotNone(data_path)
    
    def test_config_validation_across_environments(self):
        """Test configuration validation in different environments."""
        config = VoxPersonaConfig()
        
        environments = ['development', 'production', 'test', 'ci']
        
        for env in environments:
            with patch.dict(os.environ, {"VOXPERSONA_ENV": env}):
                detector = EnvironmentDetector()
                detector._cached_environment = None
                env_info = detector.detect_environment()
                
                # Configuration should be valid in all environments
                result = config.load_for_environment(env_info)
                self.assertIsNotNone(result)
                self.assertTrue(config.validate_config())
    
    def test_concurrent_environment_detection(self):
        """Test concurrent environment detection and configuration loading."""
        import threading
        import time
        
        results = []
        errors = []
        
        def load_config_worker():
            try:
                detector = EnvironmentDetector()
                config = VoxPersonaConfig()
                env_info = detector.detect_environment()
                config.load_for_environment(env_info)
                results.append((env_info['environment'], config.debug_mode))
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=load_config_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertFalse(errors, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5)
        
        # All results should be consistent
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(result, first_result)


class TestImportRecoveryIntegration(BaseIntegrationTest):
    """Test integration between import system and error recovery."""
    
    def test_import_recovery_integration(self):
        """Test that import failures trigger recovery mechanisms."""
        from src.import_utils import SafeImporter
        from src.error_recovery import ErrorRecoveryManager
        
        importer = SafeImporter()
        recovery_manager = ErrorRecoveryManager()
        
        # Test import of non-existent module with recovery
        with patch('src.error_recovery.ErrorRecoveryManager.handle_error') as mock_handle:
            mock_handle.return_value = True
            
            result = importer.safe_import('non_existent_module_12345')
            
            # Should get mock object
            self.assertIsNotNone(result)
            self.assertTrue(hasattr(result, '__name__'))
            
            # Recovery should have been called
            mock_handle.assert_called()
    
    def test_cascading_import_recovery(self):
        """Test recovery from cascading import failures."""
        from src.import_utils import SafeImporter
        
        importer = SafeImporter()
        
        # Test multiple import failures
        modules = ['fake_module_1', 'fake_module_2', 'fake_module_3']
        results = []
        
        for module in modules:
            result = importer.safe_import(module)
            results.append(result)
        
        # All should return mock objects
        for result in results:
            self.assertIsNotNone(result)
            self.assertTrue(hasattr(result, '__name__'))
    
    def test_storage_minio_integration(self):
        """Test storage system integration with MinIO."""
        from src.import_utils import SafeImporter
        
        importer = SafeImporter()
        
        # Test MinIO import with fallback
        minio_mock = importer.safe_import('minio')
        self.assertIsNotNone(minio_mock)
        
        # Mock should provide expected interface
        if hasattr(minio_mock, 'Minio'):
            client = minio_mock.Minio('localhost:9000')
            self.assertIsNotNone(client)


if __name__ == '__main__':
    unittest.main()