#!/usr/bin/env python3
"""
Environment Compatibility Checker for VoxPersona

This script checks if code is compatible across different execution environments
(CI/CD, Docker, local development, production).

Usage:
    python scripts/check_environment_compatibility.py [file1.py] [file2.py] ...
    
Return codes:
    0: All compatibility checks passed
    1: Compatibility issues found
    2: Script error
"""

import sys
import os
import ast
import logging
from pathlib import Path
from typing import List, Dict, Set, Any
import argparse
import re

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class EnvironmentCompatibilityChecker:
    """Checks code for environment compatibility issues"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        
        # Platform-specific patterns that might cause issues
        self.platform_specific_patterns = [
            (r'\\\\', 'Windows-specific path separator - use Path() or os.path.join()'),
            (r'/home/[^"\']*', 'Linux-specific home path - use Path.home()'),
            (r'/root/[^"\']*', 'Linux-specific root path - use dynamic paths'),
            (r'C:\\[^"\']*', 'Windows-specific path - use dynamic paths'),
            (r'/tmp/[^"\']*', 'Unix-specific temp path - use tempfile or path_manager'),
            (r'/var/[^"\']*', 'Unix-specific system path - use dynamic paths'),
            (r'/usr/[^"\']*', 'Unix-specific system path - use dynamic paths'),
        ]
        
        # Environment-specific functions that need compatibility handling
        self.env_specific_functions = {
            'os.getuid': 'Unix-only function - add platform check',
            'os.getgid': 'Unix-only function - add platform check', 
            'pwd.getpwuid': 'Unix-only function - add platform check',
            'grp.getgrgid': 'Unix-only function - add platform check',
            'os.fork': 'Unix-only function - not available on Windows',
        }
        
        # Hardcoded values that should be environment-aware
        self.hardcoded_patterns = [
            (r'port\s*=\s*\d{4,5}', 'Hardcoded port - use environment variable'),
            (r'host\s*=\s*["\']localhost["\']', 'Hardcoded localhost - use environment-aware config'),
            (r'timeout\s*=\s*\d+', 'Hardcoded timeout - consider environment-specific values'),
        ]
    
    def check_file(self, file_path: Path) -> bool:
        """Check a single file for environment compatibility"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST for detailed analysis
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                self.issues.append(f"{file_path}: Syntax error - {e}")
                return False
            
            # Check platform-specific patterns
            self._check_platform_patterns(content, file_path)
            
            # Check environment-specific functions
            self._check_env_functions(tree, file_path)
            
            # Check hardcoded values
            self._check_hardcoded_values(content, file_path)
            
            # Check import compatibility
            self._check_import_compatibility(tree, file_path)
            
            # Check path handling
            self._check_path_handling(content, file_path)
            
            # Check environment detection usage
            self._check_environment_detection(content, file_path)
            
            return len([issue for issue in self.issues if str(file_path) in issue]) == 0
            
        except Exception as e:
            self.issues.append(f"{file_path}: Failed to check compatibility - {e}")
            return False
    
    def _check_platform_patterns(self, content: str, file_path: Path):
        """Check for platform-specific patterns"""
        for pattern, message in self.platform_specific_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                self.warnings.append(f"{file_path}: {message} - Found: {match}")
    
    def _check_env_functions(self, tree: ast.AST, file_path: Path):
        """Check for environment-specific function calls"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                
                if func_name in self.env_specific_functions:
                    message = self.env_specific_functions[func_name]
                    self.warnings.append(f"{file_path}:{node.lineno}: {message}")
    
    def _check_hardcoded_values(self, content: str, file_path: Path):
        """Check for hardcoded values that should be configurable"""
        for pattern, message in self.hardcoded_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                self.warnings.append(f"{file_path}: {message} - Found: {match}")
    
    def _check_import_compatibility(self, tree: ast.AST, file_path: Path):
        """Check import statements for compatibility issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    self._check_module_compatibility(module_name, file_path, node.lineno)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._check_module_compatibility(node.module, file_path, node.lineno)
    
    def _check_module_compatibility(self, module_name: str, file_path: Path, line_no: int):
        """Check if imported module has compatibility considerations"""
        # Windows-specific modules
        windows_modules = ['winreg', 'winsound', 'msvcrt']
        if module_name in windows_modules:
            self.warnings.append(
                f"{file_path}:{line_no}: Windows-specific module '{module_name}' - "
                "add platform compatibility check"
            )
        
        # Unix-specific modules  
        unix_modules = ['pwd', 'grp', 'termios', 'tty', 'pty']
        if module_name in unix_modules:
            self.warnings.append(
                f"{file_path}:{line_no}: Unix-specific module '{module_name}' - "
                "add platform compatibility check"
            )
    
    def _check_path_handling(self, content: str, file_path: Path):
        """Check path handling for cross-platform compatibility"""
        # Check for string concatenation for paths
        path_concat_patterns = [
            r'["\'][^"\']*[/\\][^"\']*["\'][^"\']*\+',
            r'\+[^"\']*["\'][^"\']*[/\\]',
        ]
        
        for pattern in path_concat_patterns:
            if re.search(pattern, content):
                self.warnings.append(
                    f"{file_path}: String concatenation for paths detected - "
                    "use Path() or os.path.join() for cross-platform compatibility"
                )
        
        # Check for direct separator usage
        if '\\\\' in content or ('"/"' in content and file_path.suffix == '.py'):
            self.warnings.append(
                f"{file_path}: Direct path separator usage - "
                "use os.sep or Path() for cross-platform compatibility"
            )
    
    def _check_environment_detection(self, content: str, file_path: Path):
        """Check if environment detection is properly used"""
        # Look for environment-sensitive code without proper detection
        sensitive_patterns = [
            'makedirs',
            'open(',
            'subprocess.',
            'os.system',
            'tempfile.',
        ]
        
        has_env_detection = any([
            'get_environment()' in content,
            'is_docker()' in content,
            'is_ci()' in content,
            'is_test()' in content,
            'EnvironmentType' in content,
        ])
        
        if not has_env_detection:
            sensitive_code_found = any(pattern in content for pattern in sensitive_patterns)
            if sensitive_code_found:
                self.warnings.append(
                    f"{file_path}: Environment-sensitive operations found without "
                    "environment detection - consider using environment detection system"
                )
    
    def get_results(self) -> tuple:
        """Get compatibility check results"""  
        return self.issues, self.warnings


def check_files(file_paths: List[Path]) -> bool:
    """Check multiple files for environment compatibility"""
    checker = EnvironmentCompatibilityChecker()
    all_passed = True
    
    for file_path in file_paths:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            all_passed = False
            continue
        
        if not file_path.suffix == '.py':
            logger.debug(f"Skipping non-Python file: {file_path}")
            continue
        
        logger.info(f"Checking compatibility: {file_path}")
        passed = checker.check_file(file_path)
        if not passed:
            all_passed = False
    
    # Report results
    issues, warnings = checker.get_results()
    
    if issues:
        logger.error(f"Found {len(issues)} compatibility issues:")
        for issue in issues:
            logger.error(f"  ❌ {issue}")
    
    if warnings:
        logger.warning(f"Found {len(warnings)} compatibility warnings:")
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
    
    if not issues and not warnings:
        logger.info("✅ All files are environment compatible!")
    elif not issues:
        logger.info("✅ No critical compatibility issues found (warnings present)")
    
    return all_passed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Check VoxPersona environment compatibility")
    parser.add_argument('files', nargs='*', help='Python files to check')
    parser.add_argument('--all-src', action='store_true',
                       help='Check all Python files in src/ directory')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine files to check
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
        # Default: check all Python files in current directory and src/
        file_paths = []
        for pattern in ["*.py", "src/**/*.py"]:
            file_paths.extend(project_root.glob(pattern))
    
    if not file_paths:
        logger.warning("No Python files found to check")
        return 0
    
    try:
        success = check_files(file_paths)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Compatibility check script error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())