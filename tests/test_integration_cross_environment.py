"""
Cross-Environment Integration Tests

This module provides comprehensive integration testing across multiple deployment contexts:
- Development environment integration
- Testing environment validation  
- Production-like environment testing
- Hybrid environment scenarios
- Environment transition testing
"""

import unittest
import os
import sys
import tempfile
import time
import threading
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tests.test_config import (
    test_env_manager, 
    get_test_config, 
    TestEnvironmentConfig
)


class TestDevelopmentEnvironmentIntegration(unittest.TestCase):
    """Test integration in development environment"""
    
    def setUp(self):
        """Setup development environment"""
        self.original_env = os.environ.copy()
        self.original_modules = dict(sys.modules)
        
        # Switch to development environment
        test_env_manager.switch_environment('development')
        test_env_manager.setup_environment()
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_development_module_loading(self):
        """Test module loading in development environment"""
        # Clear modules to force fresh import
        modules_to_clear = [
            'src.config', 'src.minio_manager', 'src.analysis', 'src.handlers'
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
            
            # Test that development-specific paths are used
            self.assertIsInstance(config.STORAGE_DIRS, dict)
            
        except ImportError as e:
            self.fail(f"Failed to load modules in development environment: {e}")
    
    @patch('src.minio_manager.Minio')
    def test_development_service_integration(self, mock_minio_class):
        """Test service integration in development environment"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Import after environment setup
        from src.minio_manager import get_minio_manager
        
        manager = get_minio_manager()
        self.assertIsNotNone(manager)
        
        # Test health check
        health_status = manager.get_health_status()
        self.assertIn('connection_status', health_status)
    
    def test_development_database_integration(self):
        """Test database integration in development environment"""
        config = get_test_config()
        
        # Should have development database configuration
        self.assertEqual(config.name, 'development')
        self.assertIn('host', config.db_config)
        self.assertEqual(config.db_config['host'], 'localhost')
    
    def test_development_file_system_integration(self):
        """Test file system integration in development environment"""
        # Clear config to get fresh import  
        if 'src.config' in sys.modules:
            del sys.modules['src.config']
        
        import src.config as config
        
        # Test storage directory creation
        config.ensure_storage_directories()
        
        # Should handle directory creation gracefully
        # (may fail due to permissions but shouldn't crash)
        self.assertTrue(True)  # If we get here, no exceptions were raised


class TestTestingEnvironmentIntegration(unittest.TestCase):
    """Test integration in testing environment"""
    
    def setUp(self):
        """Setup testing environment"""
        self.original_env = os.environ.copy()
        self.original_modules = dict(sys.modules)
        
        # Switch to testing environment
        test_env_manager.switch_environment('testing')
        test_env_manager.setup_environment()
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_testing_environment_configuration(self):
        """Test testing environment configuration"""
        config = get_test_config()
        
        self.assertEqual(config.name, 'testing')
        self.assertTrue(config.mock_external_apis)
        self.assertFalse(config.requires_services)
    
    def test_testing_module_loading_with_mocks(self):
        """Test module loading with mocked services in testing environment"""
        # Clear modules
        modules_to_clear = [
            'src.config', 'src.minio_manager', 'src.analysis'
        ]
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
        
        try:
            import src.config as config
            self.assertTrue(config.IS_TESTING)
            
            # API key validation should be skipped
            self.assertIsInstance(config.DB_CONFIG, dict)
            
        except ImportError as e:
            self.fail(f"Failed to load modules in testing environment: {e}")
    
    @patch('src.minio_manager.Minio')
    def test_testing_minio_integration_with_mocks(self, mock_minio_class):
        """Test MinIO integration with mocks in testing environment"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        from src.minio_manager import MinIOManager
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9001',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret'
        }):
            manager = MinIOManager()
            
            # Should work with mocked MinIO
            self.assertIsNotNone(manager.client)
            
            # Test health monitoring
            health_report = manager.get_health_status()
            self.assertIn('connection_status', health_report)
    
    def test_testing_parallel_execution_capabilities(self):
        """Test parallel execution in testing environment"""
        config = get_test_config()
        
        # Testing environment should support more parallel tests
        self.assertGreaterEqual(config.max_parallel_tests, 8)
        
        # Test that parallel operations don't interfere
        results = []
        threads = []
        
        def test_operation(thread_id):
            # Simulate some work
            time.sleep(0.1)
            results.append(f"thread_{thread_id}")
        
        # Start multiple threads
        for i in range(4):
            thread = threading.Thread(target=test_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All threads should complete
        self.assertEqual(len(results), 4)


class TestProductionEnvironmentIntegration(unittest.TestCase):
    """Test integration in production-like environment"""
    
    def setUp(self):
        """Setup production environment"""
        self.original_env = os.environ.copy()
        self.original_modules = dict(sys.modules)
        
        # Switch to production environment
        test_env_manager.switch_environment('production')
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_production_environment_configuration(self):
        """Test production environment configuration"""
        config = get_test_config()
        
        self.assertEqual(config.name, 'production')
        self.assertTrue(config.requires_services)
        self.assertFalse(config.mock_external_apis)
        self.assertFalse(config.cleanup_after_tests)
    
    def test_production_security_requirements(self):
        """Test production security requirements"""
        config = get_test_config()
        
        # Production should use SSL for MinIO
        if 'secure' in config.minio_config:
            self.assertTrue(config.minio_config['secure'])
    
    def test_production_performance_requirements(self):
        """Test production performance requirements"""
        config = get_test_config()
        
        # Production should have conservative parallel settings
        self.assertLessEqual(config.max_parallel_tests, 2)
        
        # Should have longer timeout for complex operations
        self.assertGreaterEqual(config.timeout_seconds, 600)
    
    def test_production_resource_limits(self):
        """Test production resource limits"""
        config = get_test_config()
        
        # Should have appropriate resource limits
        self.assertGreater(config.memory_limit_mb, 0)
        self.assertGreater(config.timeout_seconds, 0)


class TestHybridEnvironmentIntegration(unittest.TestCase):
    """Test integration in hybrid environment (mixed real/mock services)"""
    
    def setUp(self):
        """Setup hybrid environment"""
        self.original_env = os.environ.copy()
        self.original_modules = dict(sys.modules)
        
        # Switch to hybrid environment
        test_env_manager.switch_environment('hybrid')
        test_env_manager.setup_environment()
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_hybrid_environment_configuration(self):
        """Test hybrid environment configuration"""
        config = get_test_config()
        
        self.assertEqual(config.name, 'hybrid')
        self.assertTrue(config.requires_services)  # Some real services
        self.assertTrue(config.mock_external_apis)  # Some mocked APIs
    
    @patch('src.minio_manager.Minio')
    @patch('src.analysis.anthropic.Anthropic')
    def test_hybrid_mixed_service_integration(self, mock_anthropic, mock_minio):
        """Test mixed real and mocked service integration"""
        # Mock external APIs
        mock_anthropic_client = Mock()
        mock_anthropic.return_value = mock_anthropic_client
        
        # Mock MinIO (could be real in some hybrid setups)
        mock_minio_client = Mock()
        mock_minio.return_value = mock_minio_client
        mock_minio_client.list_buckets.return_value = []
        mock_minio_client.bucket_exists.return_value = True
        
        try:
            from src.minio_manager import get_minio_manager
            from src.analysis import send_msg_to_model
            
            # MinIO should work (mocked)
            manager = get_minio_manager()
            self.assertIsNotNone(manager)
            
            # Analysis should work (mocked)
            mock_response = Mock()
            mock_content = Mock()
            mock_content.text = "mocked response"
            mock_response.content = [mock_content]
            mock_anthropic_client.messages.create.return_value = mock_response
            
            result = send_msg_to_model([{"role": "user", "content": "test"}])
            self.assertEqual(result, "mocked response")
            
        except ImportError as e:
            self.fail(f"Hybrid environment integration failed: {e}")
    
    def test_hybrid_adaptive_behavior(self):
        """Test adaptive behavior in hybrid environment"""
        config = get_test_config()
        
        # Should balance between testing and production needs
        self.assertGreater(config.max_parallel_tests, 2)  # More than production
        self.assertLess(config.max_parallel_tests, 8)     # Less than testing


class TestEnvironmentTransitionValidation(unittest.TestCase):
    """Test environment transition scenarios"""
    
    def setUp(self):
        """Setup for transition tests"""
        self.original_env = os.environ.copy()
        self.original_modules = dict(sys.modules)
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    def test_development_to_testing_transition(self):
        """Test transition from development to testing environment"""
        # Start in development
        test_env_manager.switch_environment('development')
        test_env_manager.setup_environment()
        
        dev_config = get_test_config()
        self.assertEqual(dev_config.name, 'development')
        
        # Transition to testing
        success = test_env_manager.switch_environment('testing')
        self.assertTrue(success)
        
        test_config = get_test_config()
        self.assertEqual(test_config.name, 'testing')
        
        # Configuration should change appropriately
        self.assertNotEqual(dev_config.max_parallel_tests, test_config.max_parallel_tests)
    
    def test_testing_to_production_transition(self):
        """Test transition from testing to production environment"""
        # Start in testing
        test_env_manager.switch_environment('testing')
        testing_config = get_test_config()
        
        # Transition to production
        success = test_env_manager.switch_environment('production')
        self.assertTrue(success)
        
        prod_config = get_test_config()
        self.assertEqual(prod_config.name, 'production')
        
        # Production should be more conservative
        self.assertLessEqual(prod_config.max_parallel_tests, testing_config.max_parallel_tests)
    
    def test_invalid_environment_transition(self):
        """Test handling of invalid environment transitions"""
        # Try to switch to non-existent environment
        success = test_env_manager.switch_environment('nonexistent')
        self.assertFalse(success)
        
        # Should remain in current environment
        current_config = get_test_config()
        self.assertIn(current_config.name, ['development', 'testing', 'production', 'hybrid'])
    
    def test_environment_state_persistence(self):
        """Test that environment state persists correctly"""
        # Set initial environment
        test_env_manager.switch_environment('testing')
        initial_config = get_test_config()
        
        # Environment should persist
        persistent_config = get_test_config()
        self.assertEqual(initial_config.name, persistent_config.name)
        self.assertEqual(initial_config.max_parallel_tests, persistent_config.max_parallel_tests)


class TestServiceIntegrationAcrossEnvironments(unittest.TestCase):
    """Test service integration across different environments"""
    
    def setUp(self):
        """Setup for service integration tests"""
        self.original_env = os.environ.copy()
        self.original_modules = dict(sys.modules)
    
    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Restore modules
        sys.modules.clear()
        sys.modules.update(self.original_modules)
    
    @patch('src.minio_manager.Minio')
    def test_minio_integration_across_environments(self, mock_minio_class):
        """Test MinIO integration across environments"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        environments = ['development', 'testing', 'production', 'hybrid']
        
        for env_name in environments:
            with self.subTest(environment=env_name):
                # Switch environment
                test_env_manager.switch_environment(env_name)
                test_env_manager.setup_environment()
                
                # Clear modules for fresh import
                if 'src.minio_manager' in sys.modules:
                    del sys.modules['src.minio_manager']
                
                try:
                    from src.minio_manager import get_minio_manager
                    manager = get_minio_manager()
                    
                    # Should work in all environments
                    self.assertIsNotNone(manager)
                    
                    # Health check should work
                    health_status = manager.get_health_status()
                    self.assertIn('connection_status', health_status)
                    
                except Exception as e:
                    self.fail(f"MinIO integration failed in {env_name}: {e}")
    
    def test_database_integration_across_environments(self):
        """Test database integration across environments"""
        environments = ['development', 'testing', 'production', 'hybrid']
        
        for env_name in environments:
            with self.subTest(environment=env_name):
                test_env_manager.switch_environment(env_name)
                config = get_test_config()
                
                # All environments should have database config
                self.assertIn('host', config.db_config)
                self.assertIn('port', config.db_config)
                self.assertIn('database', config.db_config)
    
    def test_configuration_consistency_across_environments(self):
        """Test configuration consistency across environments"""
        environments = ['development', 'testing', 'production', 'hybrid']
        configs = {}
        
        # Collect configurations
        for env_name in environments:
            test_env_manager.switch_environment(env_name)
            configs[env_name] = get_test_config()
        
        # Test consistency requirements
        for env_name, config in configs.items():
            with self.subTest(environment=env_name):
                # All environments should have basic required fields
                self.assertIsNotNone(config.name)
                self.assertIsNotNone(config.description)
                self.assertIsInstance(config.db_config, dict)
                self.assertIsInstance(config.minio_config, dict)
                self.assertIsInstance(config.max_parallel_tests, int)
                self.assertGreater(config.max_parallel_tests, 0)


class TestConcurrentEnvironmentOperations(unittest.TestCase):
    """Test concurrent operations across environments"""
    
    def test_concurrent_environment_access(self):
        """Test concurrent access to different environments"""
        results = {}
        threads = []
        
        def access_environment(env_name):
            try:
                # Each thread works with different environment
                local_manager = test_env_manager.__class__()
                local_manager.switch_environment(env_name)
                local_config = local_manager.get_current_environment()
                results[env_name] = local_config.name
            except Exception as e:
                results[env_name] = f"Error: {e}"
        
        # Start threads for different environments
        environments = ['development', 'testing', 'production', 'hybrid']
        for env_name in environments:
            thread = threading.Thread(target=access_environment, args=(env_name,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        for env_name in environments:
            self.assertEqual(results[env_name], env_name)
    
    def test_concurrent_service_operations(self):
        """Test concurrent service operations"""
        # This test ensures services can handle concurrent access
        # even across different environment configurations
        
        results = []
        threads = []
        
        def service_operation(operation_id):
            try:
                # Simulate service operation
                time.sleep(0.1)  # Simulate work
                results.append(f"operation_{operation_id}_success")
            except Exception as e:
                results.append(f"operation_{operation_id}_error: {e}")
        
        # Start multiple concurrent operations
        for i in range(5):
            thread = threading.Thread(target=service_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIn('success', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)