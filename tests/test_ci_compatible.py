"""
CI-Compatible Tests for VoxPersona

Basic tests that can run in CI environment without external dependencies.
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.ci_markers import is_ci_environment

class TestCICompatible(unittest.TestCase):
    """Tests that run reliably in CI environment"""
    
    def test_python_version(self):
        """Test that Python version is correct"""
        self.assertEqual(sys.version_info.major, 3)
        self.assertEqual(sys.version_info.minor, 10)
        print(f"✅ Python version: {sys.version}")
    
    def test_project_structure(self):
        """Test that project structure is correct"""
        project_root = Path(__file__).parent.parent
        
        # Check main directories exist
        self.assertTrue((project_root / 'src').exists(), "src directory missing")
        self.assertTrue((project_root / 'tests').exists(), "tests directory missing")
        self.assertTrue((project_root / 'prompts').exists(), "prompts directory missing")
        
        # Check key files exist
        self.assertTrue((project_root / 'requirements.txt').exists(), "requirements.txt missing")
        self.assertTrue((project_root / 'README.md').exists(), "README.md missing")
        self.assertTrue((project_root / 'Dockerfile').exists(), "Dockerfile missing")
        
        print("✅ Project structure is correct")
    
    def test_basic_imports(self):
        """Test that basic imports work"""
        try:
            import src.config
            import src.datamodels
            import src.utils
            print("✅ Basic imports successful")
        except ImportError as e:
            self.fail(f"Basic import failed: {e}")
    
    def test_ci_environment_detection(self):
        """Test CI environment detection"""
        ci_detected = is_ci_environment()
        if os.getenv('CI') == 'true':
            self.assertTrue(ci_detected, "CI environment not detected when CI=true")
            print("✅ Running in CI environment")
        else:
            print("✅ Running in local environment")
    
    def test_configuration_loading(self):
        """Test basic configuration loading without external services"""
        try:
            from src.config import (
                API_ID, API_HASH, TELEGRAM_BOT_TOKEN,
                OPENAI_API_KEY, ANTHROPIC_API_KEY,
                PASSWORD, RUN_MODE
            )
            
            # In CI, these might be None or empty, which is expected
            self.assertIsNotNone(RUN_MODE, "RUN_MODE should be set")
            print(f"✅ Configuration loaded, RUN_MODE: {RUN_MODE}")
            
        except ImportError as e:
            self.fail(f"Configuration import failed: {e}")

class TestMinimalFunctionality(unittest.TestCase):
    """Test minimal functionality without external dependencies"""
    
    def test_datamodels_import(self):
        """Test that data models can be imported"""
        try:
            from src.datamodels import (
                mapping_scenario_names, mapping_report_type_names,
                OPENAI_AUDIO_EXTS, mapping_building_names,
                REPORT_MAPPING, spinner_chars
            )
            print("✅ Data models imported successfully")
        except ImportError as e:
            self.fail(f"Data models import failed: {e}")
    
    def test_utilities_basic(self):
        """Test basic utility functions"""
        try:
            from src.utils import openai_audio_filter, count_tokens
            
            # Test count_tokens function
            test_text = "Hello world"
            token_count = count_tokens(test_text)
            self.assertIsInstance(token_count, int)
            self.assertGreater(token_count, 0)
            
            print(f"✅ Utilities work: '{test_text}' -> {token_count} tokens")
            
        except ImportError as e:
            self.skipTest(f"Utils not available: {e}")
        except AttributeError as e:
            self.skipTest(f"Utility functions not available: {e}")

if __name__ == '__main__':
    print("Running CI-Compatible Tests for VoxPersona")
    print(f"Python version: {sys.version}")
    print(f"CI Environment: {is_ci_environment()}")
    print("-" * 60)
    
    unittest.main(verbosity=2)