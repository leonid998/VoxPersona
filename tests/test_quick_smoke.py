#!/usr/bin/env python3
"""
Quick Smoke Tests for VoxPersona

These are fast tests that run during pre-commit to catch basic issues.
"""

import sys
import unittest
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class TestQuickSmoke(unittest.TestCase):
    """Quick smoke tests for basic functionality"""
    
    def test_imports_work(self):
        """Test that our enhanced systems can be imported"""
        try:
            from import_utils import safe_import
            from environment import get_environment
            from path_manager import get_path_manager
            from error_recovery import get_recovery_manager
            self.assertTrue(True, "All imports successful")
        except ImportError as e:
            self.fail(f"Import failed: {e}")
    
    def test_environment_detection(self):
        """Test basic environment detection"""
        try:
            from environment import get_environment
            env = get_environment()
            self.assertIsNotNone(env)
            self.assertTrue(hasattr(env, 'env_type'))
        except Exception as e:
            self.fail(f"Environment detection failed: {e}")
    
    def test_safe_import_basic(self):
        """Test basic safe import functionality"""
        try:
            from import_utils import safe_import
            os_module = safe_import('os')
            self.assertIsNotNone(os_module)
            self.assertTrue(hasattr(os_module, 'path'))
        except Exception as e:
            self.fail(f"Safe import failed: {e}")
    
    def test_path_manager_basic(self):
        """Test basic path manager functionality"""
        try:
            from path_manager import get_path_manager, PathType
            manager = get_path_manager()
            self.assertIsNotNone(manager)
            # Try to get a temp path
            temp_path = manager.get_temp_path()
            self.assertIsNotNone(temp_path)
        except Exception as e:
            self.fail(f"Path manager failed: {e}")
    
    def test_error_recovery_basic(self):
        """Test basic error recovery functionality"""
        try:
            from error_recovery import get_recovery_manager, recover_from_error
            manager = get_recovery_manager()
            self.assertIsNotNone(manager)
            
            # Test error classification
            error_type = manager.classify_error(ImportError("test"))
            self.assertIsNotNone(error_type)
        except Exception as e:
            self.fail(f"Error recovery failed: {e}")


if __name__ == '__main__':
    unittest.main()