#!/usr/bin/env python3
"""
Import Pattern Validator for VoxPersona

This script validates that Python files follow the enhanced import patterns
using the SafeImporter system and proper error recovery mechanisms.

Usage:
    python scripts/validate_imports.py [file1.py] [file2.py] ...
    
Return codes:
    0: All validations passed
    1: Validation failures found
    2: Script error
"""

import sys
import os
import ast
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import argparse
import re

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ImportPatternValidator:
    """Validates import patterns against VoxPersona best practices"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        
        # Patterns for different import types
        self.safe_import_pattern = re.compile(r'safe_import\s*\(')
        self.with_recovery_pattern = re.compile(r'@with_recovery\s*\(')
        self.recovery_context_pattern = re.compile(r'with\s+recovery_context\s*\(')
        
        # Modules that should use SafeImporter
        self.critical_modules = {
            'config', 'handlers', 'analysis', 'run_analysis', 
            'storage', 'minio_manager', 'validators', 'utils'
        }
        
        # Allowed standard library imports (don't need SafeImporter)
        self.stdlib_modules = {
            'os', 'sys', 'logging', 'asyncio', 'threading', 'time',
            'json', 'pathlib', 'typing', 'dataclasses', 'enum',
            'functools', 'contextlib', 'collections', 'itertools',
            'tempfile', 'shutil', 'subprocess', 'datetime', 'uuid',
            're', 'math', 'random', 'hashlib', 'base64'
        }
        
        # Third-party modules that are expected to be stable
        self.stable_third_party = {
            'pyrogram', 'minio', 'tiktoken', 'dotenv', 'pytest',
            'numpy', 'pandas', 'requests', 'aiohttp'
        }
    
    def validate_file(self, file_path: Path) -> bool:
        """
        Validate a single Python file for import patterns
        
        Returns:
            True if validation passes, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                self.issues.append(f"{file_path}: Syntax error - {e}")
                return False
            
            # Analyze imports
            self._analyze_imports(tree, file_path, content)
            
            # Check for recovery patterns
            self._check_recovery_patterns(content, file_path)
            
            # Check for deprecated patterns
            self._check_deprecated_patterns(content, file_path)
            
            return len([issue for issue in self.issues if str(file_path) in issue]) == 0
            
        except Exception as e:
            self.issues.append(f"{file_path}: Failed to validate - {e}")
            return False
    
    def _analyze_imports(self, tree: ast.AST, file_path: Path, content: str):
        """Analyze import statements in the AST"""
        
        has_safe_import = 'safe_import' in content
        has_enhanced_systems = 'ENHANCED_SYSTEMS_AVAILABLE' in content
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import_module(alias.name, file_path, has_safe_import, has_enhanced_systems)
            
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ''
                
                # Check relative imports
                if node.level > 0:
                    self._check_relative_import(node, file_path, content)
                
                # Check specific module imports
                if module_name:
                    self._check_import_module(module_name, file_path, has_safe_import, has_enhanced_systems)
                
                # Check for specific import names
                for alias in node.names:
                    if alias.name == '*':
                        self.issues.append(
                            f"{file_path}: Wildcard import from {module_name} - "
                            "use specific imports instead"
                        )
    
    def _check_import_module(self, module_name: str, file_path: Path, 
                           has_safe_import: bool, has_enhanced_systems: bool):
        """Check if a module import follows best practices"""
        
        # Extract the base module name
        base_module = module_name.split('.')[0]
        
        # Skip standard library and stable third-party modules
        if base_module in self.stdlib_modules or base_module in self.stable_third_party:
            return
        
        # Check if critical modules are using SafeImporter
        if base_module in self.critical_modules:
            if not has_safe_import and not has_enhanced_systems:
                self.issues.append(
                    f"{file_path}: Critical module '{module_name}' should use SafeImporter. "
                    "Import 'safe_import' from 'import_utils' and use safe_import() function."
                )
        
        # Check for project modules without proper handling
        if base_module not in self.stdlib_modules and base_module not in self.stable_third_party:
            if not has_safe_import and not has_enhanced_systems and file_path.name != 'import_utils.py':
                self.warnings.append(
                    f"{file_path}: Module '{module_name}' might benefit from SafeImporter. "
                    "Consider using safe_import() for better error handling."
                )
    
    def _check_relative_import(self, node: ast.ImportFrom, file_path: Path, content: str):
        """Check relative import patterns"""
        
        # Relative imports should have fallback handling
        if node.level > 0:
            # Check if there's try-except around the import area
            lines = content.split('\n')
            import_line = node.lineno - 1
            
            # Look for try-except blocks around the import
            has_error_handling = False
            
            # Check 10 lines before and after for try-except
            start_line = max(0, import_line - 10)
            end_line = min(len(lines), import_line + 10)
            
            for i in range(start_line, end_line):
                line = lines[i].strip()
                if line.startswith('try:') or 'except' in line or 'safe_import' in line:
                    has_error_handling = True
                    break
            
            if not has_error_handling:
                self.warnings.append(
                    f"{file_path}:{node.lineno}: Relative import without error handling. "
                    "Consider adding try-except or using SafeImporter."
                )
    
    def _check_recovery_patterns(self, content: str, file_path: Path):
        """Check for proper use of error recovery patterns"""
        
        # Functions that should have recovery decorators
        risky_patterns = [
            r'def.*load.*\(',
            r'def.*save.*\(',
            r'def.*init.*\(',
            r'def.*connect.*\(',
            r'def.*create.*\(',
            r'async def.*load.*\(',
            r'async def.*save.*\(',
            r'async def.*init.*\(',
        ]
        
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern in risky_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if the function has recovery decorator
                    prev_lines = lines[max(0, i-3):i-1]
                    has_recovery = any('@with_recovery' in prev_line for prev_line in prev_lines)
                    
                    if not has_recovery and 'def __' not in line:  # Skip dunder methods
                        self.warnings.append(
                            f"{file_path}:{i}: Function '{line.strip()}' might benefit from "
                            "@with_recovery decorator for better error handling."
                        )
    
    def _check_deprecated_patterns(self, content: str, file_path: Path):
        """Check for deprecated import patterns that should be updated"""
        
        # Deprecated patterns
        deprecated_patterns = [
            (r'from\s+config\s+import\s+.*', 
             "Direct config imports should use safe_import('config') for better reliability"),
            (r'import\s+(handlers|analysis|storage|utils)\s*$', 
             "Critical module imports should use SafeImporter"),
            (r'os\.makedirs\s*\([^)]*exist_ok\s*=\s*True\)', 
             "Consider using path_manager.get_path() for environment-aware directory creation"),
        ]
        
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern, message in deprecated_patterns:
                if re.search(pattern, line):
                    self.warnings.append(f"{file_path}:{i}: {message}")
    
    def get_results(self) -> Tuple[List[str], List[str]]:
        """Get validation results"""
        return self.issues, self.warnings


def validate_files(file_paths: List[Path]) -> bool:
    """
    Validate multiple files for import patterns
    
    Returns:
        True if all validations pass, False otherwise
    """
    validator = ImportPatternValidator()
    all_passed = True
    
    for file_path in file_paths:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            all_passed = False
            continue
        
        if not file_path.suffix == '.py':
            logger.debug(f"Skipping non-Python file: {file_path}")
            continue
        
        logger.info(f"Validating: {file_path}")
        passed = validator.validate_file(file_path)
        if not passed:
            all_passed = False
    
    # Report results
    issues, warnings = validator.get_results()
    
    if issues:
        logger.error(f"Found {len(issues)} import pattern issues:")
        for issue in issues:
            logger.error(f"  ❌ {issue}")
    
    if warnings:
        logger.warning(f"Found {len(warnings)} import pattern warnings:")
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
    
    if not issues and not warnings:
        logger.info("✅ All import patterns are valid!")
    elif not issues:
        logger.info("✅ No critical import issues found (warnings present)")
    
    return all_passed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate VoxPersona import patterns")
    parser.add_argument('files', nargs='*', help='Python files to validate')
    parser.add_argument('--all-src', action='store_true', 
                       help='Validate all Python files in src/ directory')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine files to validate
    if args.all_src:
        src_dir = project_root / "src"
        if src_dir.exists():
            file_paths = list(src_dir.glob("**/*.py"))
        else:
            logger.error("src/ directory not found")
            return 2
    elif args.files:
        file_paths = [Path(f) for f in args.files]
    else:
        # Default: validate all modified Python files in src/
        src_dir = project_root / "src"
        if src_dir.exists():
            file_paths = list(src_dir.glob("*.py"))
        else:
            logger.error("No files specified and src/ directory not found")
            return 2
    
    if not file_paths:
        logger.warning("No Python files found to validate")
        return 0
    
    try:
        success = validate_files(file_paths)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Validation script error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())