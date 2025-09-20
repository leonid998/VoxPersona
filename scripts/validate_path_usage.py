#!/usr/bin/env python3
"""
Path Usage Validator for VoxPersona

This script validates that path handling follows best practices
using the path_manager system.
"""

import sys
import logging
from pathlib import Path
import re

project_root = Path(__file__).parent.parent
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class PathUsageValidator:
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def validate_file(self, file_path: Path) -> bool:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for hardcoded paths
        hardcoded_patterns = [
            (r'/root/[^"\']*', 'Hardcoded root path - use path_manager'),
            (r'C:\\[^"\']*', 'Hardcoded Windows path - use path_manager'),
            (r'/tmp/[^"\']*', 'Hardcoded temp path - use get_temp_path()'),
        ]
        
        for pattern, message in hardcoded_patterns:
            if re.search(pattern, content):
                self.warnings.append(f"{file_path}: {message}")
        
        # Check for proper path_manager usage
        if 'makedirs' in content and 'path_manager' not in content:
            self.warnings.append(f"{file_path}: Directory creation without path_manager")
        
        return True
    
    def get_results(self):
        return self.issues, self.warnings


def main():
    validator = PathUsageValidator()
    
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
        logger.info("✅ Path usage patterns look good!")
    
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())