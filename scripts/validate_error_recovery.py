#!/usr/bin/env python3
"""
Error Recovery Usage Validator for VoxPersona

This script validates that error recovery patterns are properly used
throughout the codebase.

Usage:
    python scripts/validate_error_recovery.py [file1.py] [file2.py] ...
"""

import sys
import ast
import logging
from pathlib import Path
from typing import List
import re

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ErrorRecoveryValidator:
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def validate_file(self, file_path: Path) -> bool:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for risky operations without recovery
        risky_patterns = [
            (r'open\s*\([^)]*["\'][^"\']*["\'][^)]*\)', 'File operations should have error recovery'),
            (r'os\.makedirs\s*\([^)]*\)', 'Directory creation should use path_manager or recovery'),
            (r'import\s+\w+', 'Imports should use safe_import for critical modules'),
        ]
        
        for pattern, message in risky_patterns:
            if re.search(pattern, content) and '@with_recovery' not in content:
                self.warnings.append(f"{file_path}: {message}")
        
        return True
    
    def get_results(self):
        return self.issues, self.warnings


def main():
    validator = ErrorRecoveryValidator()
    
    if len(sys.argv) > 1:
        file_paths = [Path(f) for f in sys.argv[1:]]
    else:
        src_dir = project_root / "src"
        file_paths = list(src_dir.glob("**/*.py"))
    
    for file_path in file_paths:
        if file_path.exists() and file_path.suffix == '.py':
            validator.validate_file(file_path)
    
    issues, warnings = validator.get_results()
    
    if warnings:
        for warning in warnings:
            logger.warning(f"⚠️  {warning}")
    
    if not issues and not warnings:
        logger.info("✅ Error recovery patterns look good!")
    
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())