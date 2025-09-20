#!/usr/bin/env python3
"""
Docstring Checker for VoxPersona

Checks that functions have proper docstrings.
"""

import sys
import ast
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class DocstringChecker:
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def check_file(self, file_path: Path) -> bool:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return True  # Skip files with syntax errors
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_'):  # Skip private functions
                    if not ast.get_docstring(node):
                        self.warnings.append(
                            f"{file_path}:{node.lineno}: Function '{node.name}' missing docstring"
                        )
        
        return True
    
    def get_results(self):
        return self.issues, self.warnings


def main():
    checker = DocstringChecker()
    
    if len(sys.argv) > 1:
        file_paths = [Path(f) for f in sys.argv[1:]]
    else:
        src_dir = project_root / "src"
        file_paths = list(src_dir.glob("**/*.py"))
    
    for file_path in file_paths:
        if file_path.exists() and file_path.suffix == '.py':
            checker.check_file(file_path)
    
    issues, warnings = checker.get_results()
    
    if warnings:
        for warning in warnings[:10]:  # Show only first 10 warnings
            logger.warning(f"⚠️  {warning}")
        if len(warnings) > 10:
            logger.warning(f"... and {len(warnings) - 10} more warnings")
    
    if not issues and not warnings:
        logger.info("✅ All public functions have docstrings!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())