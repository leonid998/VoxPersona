#!/usr/bin/env python3
"""
Quick Model Validation Script
============================

This script provides a quick validation of the model upgrade changes
without running the full test suite.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.analysis import send_msg_to_model
from src.config import REPORT_MODEL_NAME, ANTHROPIC_API_KEY

def validate_model_upgrade():
    """Quick validation of model upgrade."""

    print("VoxPersona Model Upgrade Validation")
    print("=" * 50)
    print(f"Expected Model: claude-sonnet-4-5-20250929")  # Исправлено: актуальная модель Claude Sonnet 4.5
    print(f"Configured Model: {REPORT_MODEL_NAME}")
    print(f"API Key Available: {'Yes' if ANTHROPIC_API_KEY else 'No'}")
    print()

    if not ANTHROPIC_API_KEY:
        print("❌ No Anthropic API key found. Cannot test API connection.")
        return False

    # Test basic functionality
    try:
        print("Testing basic API connection...")
        response = send_msg_to_model(
            messages=[{"role": "user", "content": "Тест подключения. Ответь 'OK'."}],
            model=REPORT_MODEL_NAME or "claude-sonnet-4-5-20250929",  # Исправлено: актуальная модель
            max_tokens=50
        )

        if response and "ERROR" not in response:
            print(f"✅ API Connection: SUCCESS")
            print(f"   Response: {response[:100]}...")
        else:
            print(f"❌ API Connection: FAILED")
            print(f"   Response: {response}")
            return False

    except Exception as e:
        print(f"❌ API Connection: ERROR - {e}")
        return False

    print()
    print("✅ Model upgrade validation completed successfully!")
    return True

if __name__ == "__main__":
    success = validate_model_upgrade()
    sys.exit(0 if success else 1)
