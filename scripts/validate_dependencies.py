#!/usr/bin/env python3
"""
Dependency Validator for VoxPersona

Validates that requirements.txt has proper structure and security.
"""

import sys
import logging
from pathlib import Path
import re

project_root = Path(__file__).parent.parent
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class DependencyValidator:
    def __init__(self):
        self.issues = []
        self.warnings = []
        
        # Known security issues with specific versions
        self.security_issues = {
            'pillow': ['<8.3.2', 'Security vulnerability in older versions'],
            'requests': ['<2.20.0', 'Security vulnerability in older versions'],
            'urllib3': ['<1.26.5', 'Security vulnerability in older versions'],
        }
    
    def validate_requirements(self, file_path: Path) -> bool:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Check for version pinning
            if '==' not in line and '>=' not in line:
                self.warnings.append(
                    f"{file_path}:{line_num}: Package '{line}' not version pinned"
                )
            
            # Check for security issues
            package_name = line.split('==')[0].split('>=')[0].split('<')[0].lower()
            if package_name in self.security_issues:
                version_constraint, issue = self.security_issues[package_name]
                self.warnings.append(
                    f"{file_path}:{line_num}: {issue} - check version constraints"
                )
        
        return len([issue for issue in self.issues if str(file_path) in issue]) == 0
    
    def get_results(self):
        return self.issues, self.warnings


def main():
    validator = DependencyValidator()
    
    if len(sys.argv) > 1:
        file_paths = [Path(f) for f in sys.argv[1:]]
    else:
        file_paths = [project_root / "requirements.txt"]
    
    for file_path in file_paths:
        if file_path.exists():
            logger.info(f"Validating: {file_path}")
            validator.validate_requirements(file_path)
    
    issues, warnings = validator.get_results()
    
    if warnings:
        for warning in warnings:
            logger.warning(f"⚠️  {warning}")
    
    if not issues and not warnings:
        logger.info("✅ Dependencies look good!")
    
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())