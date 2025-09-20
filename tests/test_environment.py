"""
Unit tests for environment module

Tests environment detection and context analysis functionality
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from framework import VoxPersonaTestCase, EnvironmentSimulator, skip_if_no_enhanced_systems

try:
    from environment import (
        EnvironmentDetector, EnvironmentType, EnvironmentInfo,
        get_environment, is_development, is_production, is_test,
        is_ci, is_docker, get_safe_temp_dir, has_write_permissions,
        get_environment_summary
    )
    ENVIRONMENT_AVAILABLE = True
except ImportError:
    ENVIRONMENT_AVAILABLE = False


@unittest.skipUnless(ENVIRONMENT_AVAILABLE, "environment module not available")
class TestEnvironmentType(VoxPersonaTestCase):
    """Test EnvironmentType enum"""
    
    def test_environment_types_exist(self):
        """Test that all expected environment types exist"""
        expected_types = [
            'DEVELOPMENT', 'TEST', 'CI_CD', 'DOCKER', 'PRODUCTION', 'UNKNOWN'
        ]
        
        for env_type in expected_types:
            self.assertTrue(hasattr(EnvironmentType, env_type))
    
    def test_environment_type_values(self):
        """Test environment type values"""
        self.assertEqual(EnvironmentType.DEVELOPMENT.value, "development")
        self.assertEqual(EnvironmentType.TEST.value, "test")
        self.assertEqual(EnvironmentType.CI_CD.value, "ci_cd")
        self.assertEqual(EnvironmentType.DOCKER.value, "docker")
        self.assertEqual(EnvironmentType.PRODUCTION.value, "production")
        self.assertEqual(EnvironmentType.UNKNOWN.value, "unknown")


@unittest.skipUnless(ENVIRONMENT_AVAILABLE, "environment module not available")
class TestEnvironmentDetector(VoxPersonaTestCase):
    """Test EnvironmentDetector functionality"""
    
    def setUp(self):
        super().setUp()
        self.detector = EnvironmentDetector()
    
    def test_detector_initialization(self):
        """Test detector initialization"""
        self.assertIsNotNone(self.detector._detection_rules)
        self.assertIsInstance(self.detector._detection_rules, dict)
        
        # Check that all environment types have rules
        for env_type in EnvironmentType:
            if env_type != EnvironmentType.UNKNOWN:
                self.assertIn(env_type, self.detector._detection_rules)
    
    def test_system_info_collection(self):
        """Test system information collection"""
        system_info = self.detector._get_system_info()
        
        expected_keys = [
            'platform', 'system', 'machine', 'processor',
            'python_version', 'hostname', 'cwd', 'argv', 'executable'
        ]
        
        for key in expected_keys:
            self.assertIn(key, system_info)
    
    def test_user_info_collection(self):
        """Test user information collection"""
        user_info = self.detector._get_user_info()
        
        expected_keys = ['username', 'home_dir']
        
        for key in expected_keys:
            self.assertIn(key, user_info)
        
        # home_dir should be a valid path
        if user_info['home_dir']:
            self.assertTrue(Path(user_info['home_dir']).exists())
    
    def test_python_info_collection(self):
        """Test Python environment information collection"""
        python_info = self.detector._get_python_info()
        
        expected_keys = [
            'version', 'version_info', 'executable', 'path',
            'modules', 'prefix', 'base_prefix', 'in_virtualenv'
        ]
        
        for key in expected_keys:
            self.assertIn(key, python_info)
        
        # Check types
        self.assertIsInstance(python_info['version'], str)
        self.assertIsInstance(python_info['path'], list)
        self.assertIsInstance(python_info['modules'], list)
        self.assertIsInstance(python_info['in_virtualenv'], bool)
    
    def test_ci_env_vars_detection(self):
        """Test CI environment variable detection"""
        # Test positive case
        with patch.dict(os.environ, {'CI': 'true'}):
            result = self.detector._check_ci_env_vars()
            self.assertTrue(result)
        
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            result = self.detector._check_ci_env_vars()
            self.assertTrue(result)
        
        # Test negative case
        with patch.dict(os.environ, {}, clear=True):
            result = self.detector._check_ci_env_vars()
            self.assertFalse(result)
    
    def test_docker_detection(self):
        """Test Docker environment detection"""
        # Test dockerenv file detection
        with patch('os.path.exists', return_value=True):
            result = self.detector._check_dockerenv_file()
            self.assertTrue(result)
        
        # Test environment variable detection
        with patch.dict(os.environ, {'DOCKER_CONTAINER': 'true'}):
            result = self.detector._check_docker_env_vars()
            self.assertTrue(result)
        
        # Test negative case
        with patch('os.path.exists', return_value=False), \
             patch.dict(os.environ, {}, clear=True):
            result = self.detector._check_dockerenv_file()
            self.assertFalse(result)
            result = self.detector._check_docker_env_vars()
            self.assertFalse(result)
    
    def test_test_environment_detection(self):
        """Test test environment detection"""
        # Test RUN_MODE detection
        with patch.dict(os.environ, {'RUN_MODE': 'TEST'}):
            result = self.detector._check_test_env_vars()
            self.assertTrue(result)
        
        # Test pytest detection
        with patch.dict(sys.modules, {'pytest': Mock()}):
            result = self.detector._check_test_frameworks()
            self.assertTrue(result)
        
        # Test argv detection
        with patch.object(sys, 'argv', ['test_runner.py']):
            result = self.detector._check_test_argv()
            self.assertTrue(result)
    
    def test_production_detection(self):
        """Test production environment detection"""
        # Test environment variables
        with patch.dict(os.environ, {'NODE_ENV': 'production'}):
            result = self.detector._check_prod_env_vars()
            self.assertTrue(result)
        
        # Test production paths
        with patch('os.getcwd', return_value='/var/www/app'):
            result = self.detector._check_prod_paths()
            self.assertTrue(result)
    
    def test_development_detection(self):
        """Test development environment detection"""
        # Mock user context for development
        user_info = {
            'username': 'developer',
            'home_dir': str(Path.home())
        }
        
        with patch.object(self.detector, '_get_user_info', return_value=user_info):
            with patch('os.access', return_value=True):
                result = self.detector._check_dev_user_context()
                # Result depends on actual system, so we just check it's boolean
                self.assertIsInstance(result, bool)
    
    def test_environment_detection_caching(self):
        """Test that environment detection results are cached"""
        # First call
        env1 = self.detector.detect_environment()
        
        # Second call should return cached result
        env2 = self.detector.detect_environment()
        
        self.assertIs(env1, env2)
    
    def test_safe_temp_dir_selection(self):
        """Test safe temporary directory selection"""
        temp_dir = self.detector._get_safe_temp_dir()
        
        self.assertIsInstance(temp_dir, Path)
        self.assertTrue(temp_dir.exists())


@unittest.skipUnless(ENVIRONMENT_AVAILABLE, "environment module not available")
class TestEnvironmentSimulation(VoxPersonaTestCase):
    """Test environment simulation capabilities"""
    
    def setUp(self):
        super().setUp()
        self.simulator = EnvironmentSimulator()
    
    def test_ci_environment_simulation(self):
        """Test CI environment simulation"""
        with self.simulator.simulate_environment('ci'):
            self.assertTrue(os.environ.get('CI'))
            self.assertTrue(os.environ.get('GITHUB_ACTIONS'))
            
            # Test environment detection in simulated environment
            detector = EnvironmentDetector()
            result = detector._check_ci_env_vars()
            self.assertTrue(result)
    
    def test_docker_environment_simulation(self):
        """Test Docker environment simulation"""
        with self.simulator.simulate_environment('docker'):
            self.assertTrue(os.environ.get('DOCKER_CONTAINER'))
            
            # Test environment detection
            detector = EnvironmentDetector()
            result = detector._check_docker_env_vars()
            self.assertTrue(result)
    
    def test_test_environment_simulation(self):
        """Test test environment simulation"""
        with self.simulator.simulate_environment('test'):
            self.assertEqual(os.environ.get('RUN_MODE'), 'TEST')
            
            # Test environment detection
            detector = EnvironmentDetector()
            result = detector._check_test_env_vars()
            self.assertTrue(result)
    
    def test_custom_environment_variables(self):
        """Test custom environment variable setting"""
        with self.simulator.simulate_environment('test', CUSTOM_VAR='custom_value'):
            self.assertEqual(os.environ.get('CUSTOM_VAR'), 'custom_value')
    
    def test_environment_restoration(self):
        """Test that environment is properly restored after simulation"""
        original_env = dict(os.environ)
        
        with self.simulator.simulate_environment('ci', TEST_VAR='test_value'):
            # Environment should be different
            self.assertNotEqual(dict(os.environ), original_env)
            self.assertEqual(os.environ.get('TEST_VAR'), 'test_value')
        
        # Environment should be restored (mostly - some system vars might differ)
        self.assertNotIn('TEST_VAR', os.environ)
        self.assertNotIn('CI', os.environ)


@unittest.skipUnless(ENVIRONMENT_AVAILABLE, "environment module not available")
class TestEnvironmentFunctions(VoxPersonaTestCase):
    """Test module-level environment functions"""
    
    def test_get_environment_function(self):
        """Test get_environment function"""
        env = get_environment()
        
        self.assertIsInstance(env, EnvironmentInfo)
        self.assertTrue(hasattr(env, 'env_type'))
        self.assertTrue(hasattr(env, 'is_containerized'))
        self.assertTrue(hasattr(env, 'is_ci'))
        self.assertTrue(hasattr(env, 'is_test'))
    
    def test_environment_type_functions(self):
        """Test individual environment type check functions"""
        # These functions should return boolean values
        self.assertIsInstance(is_development(), bool)
        self.assertIsInstance(is_production(), bool)
        self.assertIsInstance(is_test(), bool)
        self.assertIsInstance(is_ci(), bool)
        self.assertIsInstance(is_docker(), bool)
    
    def test_utility_functions(self):
        """Test utility functions"""
        # get_safe_temp_dir should return a Path
        temp_dir = get_safe_temp_dir()
        self.assertIsInstance(temp_dir, Path)
        self.assertTrue(temp_dir.exists())
        
        # has_write_permissions should return boolean
        result = has_write_permissions()
        self.assertIsInstance(result, bool)
    
    def test_environment_summary(self):
        """Test environment summary generation"""
        summary = get_environment_summary()
        
        self.assertIsInstance(summary, str)
        self.assertIn('Environment:', summary)
        self.assertIn('Confidence:', summary)
        
        # Should contain various environment indicators
        expected_indicators = ['Containerized:', 'CI/CD:', 'Test:', 'Write Permissions:']
        for indicator in expected_indicators:
            self.assertIn(indicator, summary)


@unittest.skipUnless(ENVIRONMENT_AVAILABLE, "environment module not available")
class TestEnvironmentIntegration(VoxPersonaTestCase):
    """Test environment detection integration scenarios"""
    
    def test_multiple_environment_indicators(self):
        """Test detection when multiple environment indicators are present"""
        simulator = EnvironmentSimulator()
        
        # Simulate environment with both CI and test indicators
        with simulator.simulate_environment('ci'):
            os.environ['RUN_MODE'] = 'TEST'
            os.environ['PYTEST_CURRENT_TEST'] = 'test_example'
            
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            
            # Should detect as CI (typically higher priority)
            # But both flags should be true
            self.assertTrue(env.is_ci)
            self.assertTrue(env.is_test)
    
    def test_confidence_scoring(self):
        """Test confidence scoring for environment detection"""
        simulator = EnvironmentSimulator()
        
        # Clear environment for low confidence
        with simulator.simulate_environment('development'):
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            
            # Confidence should be a float between 0 and 1
            self.assertIsInstance(env.confidence_score, float)
            self.assertGreaterEqual(env.confidence_score, 0.0)
            self.assertLessEqual(env.confidence_score, 1.0)
    
    def test_unknown_environment_handling(self):
        """Test handling of unknown environments"""
        # Create a completely clean environment
        with patch.dict(os.environ, {}, clear=True), \
             patch('sys.modules', {}), \
             patch.object(sys, 'argv', []):
            
            detector = EnvironmentDetector()
            env = detector.detect_environment()
            
            # Should handle gracefully, possibly detecting as unknown
            self.assertIsInstance(env, EnvironmentInfo)
            
            # Confidence should be low for unknown environment
            if env.env_type == EnvironmentType.UNKNOWN:
                self.assertLess(env.confidence_score, 0.5)


if __name__ == '__main__':
    unittest.main()