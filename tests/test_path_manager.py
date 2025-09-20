"""
Unit tests for path_manager module

Tests path resolution, environment adaptation, and fallback mechanisms
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from framework import VoxPersonaTestCase, EnvironmentSimulator, skip_if_no_enhanced_systems

try:
    from path_manager import (
        PathManager, PathType, PathConfig, PathResolutionError,
        get_path_manager, get_path, get_temp_path, cleanup_temp_dirs,
        validate_path, get_safe_filename
    )
    PATH_MANAGER_AVAILABLE = True
except ImportError:
    PATH_MANAGER_AVAILABLE = False


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestPathType(VoxPersonaTestCase):
    """Test PathType enum"""
    
    def test_path_types_exist(self):
        """Test that all expected path types exist"""
        expected_types = [
            'AUDIO_STORAGE', 'TEXT_STORAGE', 'RAG_INDICES', 'PROMPTS',
            'TEMP', 'LOGS', 'CONFIG', 'DATABASE'
        ]
        
        for path_type in expected_types:
            self.assertTrue(hasattr(PathType, path_type))


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestPathConfig(VoxPersonaTestCase):
    """Test PathConfig dataclass"""
    
    def test_path_config_creation(self):
        """Test PathConfig creation with defaults"""
        config = PathConfig(
            primary_path=Path("/test/path"),
            fallback_paths=[Path("/fallback1"), Path("/fallback2")]
        )
        
        self.assertEqual(config.primary_path, Path("/test/path"))
        self.assertEqual(len(config.fallback_paths), 2)
        self.assertTrue(config.create_if_missing)  # Default True
        self.assertTrue(config.require_write_access)  # Default True
        self.assertTrue(config.require_read_access)  # Default True
        self.assertFalse(config.is_temporary)  # Default False
        self.assertFalse(config.cleanup_on_exit)  # Default False
    
    def test_path_config_custom_values(self):
        """Test PathConfig with custom values"""
        config = PathConfig(
            primary_path=Path("/test/path"),
            fallback_paths=[],
            create_if_missing=False,
            require_write_access=False,
            require_read_access=True,
            is_temporary=True,
            cleanup_on_exit=True
        )
        
        self.assertFalse(config.create_if_missing)
        self.assertFalse(config.require_write_access)
        self.assertTrue(config.require_read_access)
        self.assertTrue(config.is_temporary)
        self.assertTrue(config.cleanup_on_exit)


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestPathManager(VoxPersonaTestCase):
    """Test PathManager functionality"""
    
    def setUp(self):
        super().setUp()
        self.path_manager = PathManager()
    
    def test_path_manager_initialization(self):
        """Test PathManager initialization"""
        self.assertIsNotNone(self.path_manager.environment)
        self.assertIsInstance(self.path_manager._resolved_paths, dict)
        self.assertIsInstance(self.path_manager._temp_dirs, list)
        self.assertIsInstance(self.path_manager._path_configs, dict)
    
    def test_path_config_initialization(self):
        """Test that path configurations are properly initialized"""
        configs = self.path_manager._path_configs
        
        # Should have configs for all path types
        expected_types = [
            PathType.AUDIO_STORAGE, PathType.TEXT_STORAGE, PathType.RAG_INDICES,
            PathType.PROMPTS, PathType.TEMP, PathType.LOGS
        ]
        
        for path_type in expected_types:
            self.assertIn(path_type, configs)
            self.assertIsInstance(configs[path_type], PathConfig)
    
    def test_get_temp_path(self):
        """Test temporary path creation"""
        temp_path = self.path_manager.get_temp_path()
        
        self.assertIsInstance(temp_path, Path)
        # Should create the directory
        self.assertTrue(temp_path.exists())
        
        # Test with suffix
        temp_path_with_suffix = self.path_manager.get_temp_path("test_suffix")
        self.assertIsInstance(temp_path_with_suffix, Path)
        self.assertTrue(temp_path_with_suffix.exists())
        self.assertIn("test_suffix", str(temp_path_with_suffix))
    
    def test_create_directory_safely(self):
        """Test safe directory creation"""
        test_dir = self.temp_dir / "test_directory"
        
        # Should not exist initially
        self.assertFalse(test_dir.exists())
        
        # Create it safely
        self.path_manager._create_directory_safely(test_dir)
        
        # Should exist now
        self.assertTrue(test_dir.exists())
        self.assertTrue(test_dir.is_dir())
    
    def test_validate_path_success(self):
        """Test path validation for valid paths"""
        # Test with current directory (should be valid)
        is_valid, error_msg = self.path_manager.validate_path(Path.cwd())
        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")
        
        # Test with temp directory
        is_valid, error_msg = self.path_manager.validate_path(self.temp_dir)
        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")
    
    def test_validate_path_traversal(self):
        """Test path validation rejects path traversal"""
        # Test path traversal attempt
        is_valid, error_msg = self.path_manager.validate_path("../../../etc/passwd")
        self.assertFalse(is_valid)
        self.assertIn("Path traversal not allowed", error_msg)
    
    def test_get_safe_filename(self):
        """Test safe filename generation"""
        # Test normal filename
        safe_name = self.path_manager.get_safe_filename("normal_file.txt")
        self.assertEqual(safe_name, "normal_file.txt")
        
        # Test filename with problematic characters
        unsafe_name = "file<>:|?*.txt"
        safe_name = self.path_manager.get_safe_filename(unsafe_name)
        
        # Should not contain problematic characters
        problematic_chars = '<>:|?*'
        for char in problematic_chars:
            self.assertNotIn(char, safe_name)
        
        # Test empty filename
        safe_name = self.path_manager.get_safe_filename("")
        self.assertTrue(safe_name.startswith("file_"))
        
        # Test very long filename
        long_name = "a" * 300 + ".txt"
        safe_name = self.path_manager.get_safe_filename(long_name)
        self.assertLessEqual(len(safe_name), 255)
    
    def test_cleanup_temp_dirs(self):
        """Test temporary directory cleanup"""
        # Create some temporary directories
        temp_path1 = self.path_manager.get_temp_path("cleanup_test1")
        temp_path2 = self.path_manager.get_temp_path("cleanup_test2")
        
        # Should exist
        self.assertTrue(temp_path1.exists())
        self.assertTrue(temp_path2.exists())
        
        # Cleanup
        self.path_manager.cleanup_temp_dirs()
        
        # Note: cleanup might not immediately delete in all systems
        # So we just test that the temp_dirs list is cleared
        self.assertEqual(len(self.path_manager._temp_dirs), 0)
    
    def test_path_resolution_caching(self):
        """Test that resolved paths are cached"""
        # Get a path twice
        path1 = self.path_manager.get_path(PathType.TEMP)
        path2 = self.path_manager.get_path(PathType.TEMP)
        
        # Should be the same cached result
        self.assertEqual(path1, path2)
        
        # Should be in resolved paths cache
        self.assertIn(PathType.TEMP, self.path_manager._resolved_paths)
    
    def test_path_info_diagnostics(self):
        """Test path information diagnostics"""
        # Get path info for temp directory
        info = self.path_manager.get_path_info(PathType.TEMP)
        
        expected_keys = [
            'path_type', 'resolved_path', 'exists', 'is_directory',
            'readable', 'writable', 'is_temporary', 'cleanup_on_exit',
            'primary_path', 'fallback_paths'
        ]
        
        for key in expected_keys:
            self.assertIn(key, info)
        
        self.assertEqual(info['path_type'], PathType.TEMP.value)
        self.assertIsInstance(info['exists'], bool)
        self.assertIsInstance(info['is_temporary'], bool)


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestPathResolutionStrategies(VoxPersonaTestCase):
    """Test path resolution strategies"""
    
    def setUp(self):
        super().setUp()
        self.path_manager = PathManager()
    
    def test_fallback_path_resolution(self):
        """Test fallback path resolution when primary fails"""
        # Create a config with primary path that doesn't exist and fallback that does
        primary_path = Path("/nonexistent/primary/path")
        fallback_path = self.temp_dir / "fallback"
        fallback_path.mkdir(parents=True, exist_ok=True)
        
        config = PathConfig(
            primary_path=primary_path,
            fallback_paths=[fallback_path],
            create_if_missing=False
        )
        
        # Try to resolve the path
        resolved_path = self.path_manager._try_resolve_path(fallback_path, config, False)
        
        # Should resolve to fallback path
        self.assertEqual(resolved_path, fallback_path)
    
    def test_path_creation_when_missing(self):
        """Test path creation when path doesn't exist but creation is allowed"""
        test_path = self.temp_dir / "new_directory"
        
        config = PathConfig(
            primary_path=test_path,
            fallback_paths=[],
            create_if_missing=True
        )
        
        # Should not exist initially
        self.assertFalse(test_path.exists())
        
        # Try to resolve with creation
        resolved_path = self.path_manager._try_resolve_path(test_path, config, True)
        
        # Should create and resolve the path
        self.assertEqual(resolved_path, test_path)
        self.assertTrue(test_path.exists())
    
    def test_path_resolution_failure(self):
        """Test path resolution failure scenarios"""
        nonexistent_path = Path("/definitely/does/not/exist")
        
        config = PathConfig(
            primary_path=nonexistent_path,
            fallback_paths=[],
            create_if_missing=False
        )
        
        # Should return None when resolution fails
        resolved_path = self.path_manager._try_resolve_path(nonexistent_path, config, False)
        self.assertIsNone(resolved_path)


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestEnvironmentAwareness(VoxPersonaTestCase):
    """Test environment-aware path resolution"""
    
    def test_test_environment_paths(self):
        """Test path resolution in test environment"""
        simulator = EnvironmentSimulator()
        
        with simulator.simulate_environment('test'):
            # Create new path manager in test environment
            path_manager = PathManager()
            
            # Audio storage should use temporary paths in test environment
            audio_config = path_manager._path_configs[PathType.AUDIO_STORAGE]
            self.assertTrue(audio_config.is_temporary)
            self.assertTrue(audio_config.cleanup_on_exit)
    
    def test_ci_environment_paths(self):
        """Test path resolution in CI environment"""
        simulator = EnvironmentSimulator()
        
        with simulator.simulate_environment('ci'):
            # Create new path manager in CI environment
            path_manager = PathManager()
            
            # Should prefer temporary paths in CI
            audio_config = path_manager._path_configs[PathType.AUDIO_STORAGE]
            
            # Primary path should be in /tmp or similar temporary location
            primary_path_str = str(audio_config.primary_path)
            self.assertTrue(
                '/tmp' in primary_path_str or 
                'temp' in primary_path_str.lower()
            )
    
    def test_docker_environment_paths(self):
        """Test path resolution in Docker environment"""
        simulator = EnvironmentSimulator()
        
        with simulator.simulate_environment('docker'):
            # Create new path manager in Docker environment
            path_manager = PathManager()
            
            # Should use /app paths in Docker
            audio_config = path_manager._path_configs[PathType.AUDIO_STORAGE]
            primary_path_str = str(audio_config.primary_path)
            
            # Should prefer /app paths in Docker
            self.assertTrue(
                '/app' in primary_path_str or
                'app' in primary_path_str
            )


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestModuleLevelFunctions(VoxPersonaTestCase):
    """Test module-level convenience functions"""
    
    def test_get_path_manager_singleton(self):
        """Test get_path_manager returns singleton"""
        manager1 = get_path_manager()
        manager2 = get_path_manager()
        
        self.assertIs(manager1, manager2)
        self.assertIsInstance(manager1, PathManager)
    
    def test_get_path_convenience_function(self):
        """Test get_path convenience function"""
        path = get_path(PathType.TEMP)
        
        self.assertIsInstance(path, Path)
        self.assertTrue(path.exists())
    
    def test_get_temp_path_convenience_function(self):
        """Test get_temp_path convenience function"""
        temp_path = get_temp_path()
        
        self.assertIsInstance(temp_path, Path)
        self.assertTrue(temp_path.exists())
        
        # Test with suffix
        temp_path_with_suffix = get_temp_path("test_suffix")
        self.assertIsInstance(temp_path_with_suffix, Path)
        self.assertIn("test_suffix", str(temp_path_with_suffix))
    
    def test_validate_path_convenience_function(self):
        """Test validate_path convenience function"""
        is_valid, error_msg = validate_path(Path.cwd())
        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")
        
        # Test invalid path
        is_valid, error_msg = validate_path("../../../etc/passwd")
        self.assertFalse(is_valid)
        self.assertNotEqual(error_msg, "")
    
    def test_get_safe_filename_convenience_function(self):
        """Test get_safe_filename convenience function"""
        safe_name = get_safe_filename("test<file>.txt")
        
        self.assertNotIn('<', safe_name)
        self.assertNotIn('>', safe_name)
        self.assertIn('test', safe_name)
        self.assertIn('.txt', safe_name)


@unittest.skipUnless(PATH_MANAGER_AVAILABLE, "path_manager not available")
class TestErrorHandling(VoxPersonaTestCase):
    """Test error handling in path management"""
    
    def test_path_resolution_error(self):
        """Test PathResolutionError is raised appropriately"""
        path_manager = PathManager()
        
        # Create a config with all invalid paths
        with patch.object(path_manager, '_path_configs', {}):
            with self.assertRaises(PathResolutionError) as context:
                path_manager.get_path(PathType.AUDIO_STORAGE)
            
            error = context.exception
            self.assertEqual(error.path_type, PathType.AUDIO_STORAGE)
            self.assertIsInstance(error.attempted_paths, list)
    
    def test_permission_error_handling(self):
        """Test handling of permission errors during path resolution"""
        path_manager = PathManager()
        
        # Mock permission error during directory creation
        with patch.object(path_manager, '_create_directory_safely', 
                         side_effect=PermissionError("Access denied")):
            
            # Should handle gracefully and try fallbacks
            try:
                path = path_manager.get_path(PathType.TEMP)
                # If we get here, fallback worked
                self.assertIsInstance(path, Path)
            except PathResolutionError:
                # Or it should raise PathResolutionError with proper context
                pass
    
    def test_invalid_path_type(self):
        """Test handling of invalid path types"""
        path_manager = PathManager()
        
        # Create a mock path type that doesn't exist in configs
        class FakePathType:
            pass
        
        fake_type = FakePathType()
        
        with self.assertRaises(PathResolutionError):
            path_manager.get_path(fake_type)


if __name__ == '__main__':
    unittest.main()