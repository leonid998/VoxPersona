"""
Test package for VoxPersona MinIO Integration

This package contains unit and integration tests for the enhanced MinIO integration.
"""

import os
import sys

# Add the src directory to the Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), 'src')
sys.path.insert(0, src_dir)

# Load test environment variables
from dotenv import load_dotenv
test_env_path = os.path.join(current_dir, '.env.test')
if os.path.exists(test_env_path):
    load_dotenv(test_env_path, override=True)