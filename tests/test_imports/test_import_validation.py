"""Import validation and testing system for VoxPersona.

This module provides comprehensive validation of import patterns,
dependency management, and fallback mechanisms.
"""

import os
import sys
import ast
import inspect
import importlib
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from enum import Enum
import logging

from tests.framework.base_test import BaseTest
from src.import_utils import SafeImporter
from .test_context_simulation import ContextSimulator, ExecutionContext


class ImportResult(Enum):
    """Import test results."""
    SUCCESS = "success"           # Import succeeded
    FALLBACK = "fallback"        # Fallback mock returned
    OPTIONAL = "optional"        # Optional dependency missing
    FAILURE = "failure"          # Import failed completely


@dataclass
class ImportTest:
    """Represents an import test case."""
    module_name: str
    description: str
    required: bool = True
    fallback_expected: bool = False
    context_dependent: bool = False
    min_version: Optional[str] = None
    alternatives: List[str] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


@dataclass
class ImportTestResult:
    """Result of an import test."""
    test: ImportTest
    result: ImportResult
    module: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    context: Optional[str] = None
    version: Optional[str] = None
    is_mock: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'module_name': self.test.module_name,
            'description': self.test.description,
            'result': self.result.value,
            'required': self.test.required,
            'fallback_expected': self.test.fallback_expected,
            'error': self.error,
            'execution_time': self.execution_time,
            'context': self.context,
            'version': self.version,
            'is_mock': self.is_mock
        }


class ImportValidator:
    """Validates import behavior and dependencies."""
    
    def __init__(self):
        """Initialize import validator."""
        self.logger = logging.getLogger(__name__)
        self.importer = SafeImporter()
        self.test_results = []
        
        # Standard test cases
        self.standard_tests = self._create_standard_tests()
        self.scientific_tests = self._create_scientific_tests()
        self.optional_tests = self._create_optional_tests()
    
    def _create_standard_tests(self) -> List[ImportTest]:
        """Create standard library import tests."""
        return [
            ImportTest("os", "Operating system interface", required=True),
            ImportTest("sys", "System-specific parameters", required=True),
            ImportTest("json", "JSON encoder/decoder", required=True),
            ImportTest("pathlib", "Object-oriented filesystem paths", required=True),
            ImportTest("logging", "Logging facility", required=True),
            ImportTest("threading", "Thread-based parallelism", required=True),
            ImportTest("time", "Time access and conversions", required=True),
            ImportTest("re", "Regular expression operations", required=True),
            ImportTest("sqlite3", "SQLite database interface", required=True),
            ImportTest("tempfile", "Temporary file/directory creation", required=True),
            ImportTest("shutil", "High-level file operations", required=True),
            ImportTest("subprocess", "Subprocess management", required=True),
            ImportTest("urllib", "URL handling modules", required=True),
            ImportTest("email", "Email handling package", required=True),
            ImportTest("smtplib", "SMTP protocol client", required=True)
        ]
    
    def _create_scientific_tests(self) -> List[ImportTest]:
        """Create scientific/ML library import tests."""
        return [
            ImportTest(
                "numpy", 
                "Numerical computing library",
                required=True,
                fallback_expected=True,
                min_version="1.19.0"
            ),
            ImportTest(
                "librosa", 
                "Audio analysis library",
                required=True,
                fallback_expected=True,
                alternatives=["scipy.io.wavfile"]
            ),
            ImportTest(
                "matplotlib", 
                "Plotting library",
                required=False,
                fallback_expected=True,
                alternatives=["seaborn", "plotly"]
            ),
            ImportTest(
                "matplotlib.pyplot", 
                "Pyplot interface",
                required=False,
                fallback_expected=True
            ),
            ImportTest(
                "pandas", 
                "Data manipulation library",
                required=False,
                fallback_expected=True
            ),
            ImportTest(
                "scipy", 
                "Scientific computing library",
                required=False,
                fallback_expected=True
            ),
            ImportTest(
                "sklearn", 
                "Machine learning library",
                required=False,
                fallback_expected=True,
                alternatives=["scikit-learn"]
            ),
            ImportTest(
                "tensorflow", 
                "Machine learning framework",
                required=False,
                fallback_expected=True,
                alternatives=["torch", "keras"]
            ),
            ImportTest(
                "torch", 
                "PyTorch machine learning library",
                required=False,
                fallback_expected=True,
                alternatives=["tensorflow"]
            )
        ]
    
    def _create_optional_tests(self) -> List[ImportTest]:
        """Create optional dependency import tests."""
        return [
            ImportTest(
                "minio", 
                "MinIO client library",
                required=False,
                fallback_expected=True,
                context_dependent=True
            ),
            ImportTest(
                "requests", 
                "HTTP library",
                required=False,
                fallback_expected=True,
                alternatives=["urllib3", "httpx"]
            ),
            ImportTest(
                "jinja2", 
                "Template engine",
                required=False,
                fallback_expected=True
            ),
            ImportTest(
                "reportlab", 
                "PDF generation library",
                required=False,
                fallback_expected=True,
                alternatives=["fpdf", "weasyprint"]
            ),
            ImportTest(
                "pytest", 
                "Testing framework",
                required=False,
                fallback_expected=True,
                context_dependent=True
            ),
            ImportTest(
                "coverage", 
                "Code coverage measurement",
                required=False,
                fallback_expected=True,
                context_dependent=True
            ),
            ImportTest(
                "black", 
                "Code formatter",
                required=False,
                fallback_expected=True,
                context_dependent=True
            ),
            ImportTest(
                "flake8", 
                "Code linter",
                required=False,
                fallback_expected=True,
                context_dependent=True
            )
        ]
    
    def run_import_test(self, test: ImportTest, context: Optional[str] = None) -> ImportTestResult:
        """Run individual import test.
        
        Args:
            test: Import test case
            context: Execution context
            
        Returns:
            Test result
        """
        import time
        
        start_time = time.time()
        result = ImportTestResult(test=test, result=ImportResult.FAILURE, context=context)
        
        try:
            # Attempt import
            module = self.importer.safe_import(test.module_name)
            execution_time = time.time() - start_time
            
            if module is None:
                result.result = ImportResult.FAILURE
                result.error = "Import returned None"
            else:
                result.module = module
                result.execution_time = execution_time
                
                # Check if it's a mock object
                is_mock = self._is_mock_object(module)
                result.is_mock = is_mock
                
                if is_mock:
                    if test.fallback_expected:
                        result.result = ImportResult.FALLBACK
                    elif not test.required:
                        result.result = ImportResult.OPTIONAL
                    else:
                        result.result = ImportResult.FAILURE
                        result.error = "Required module returned mock"
                else:
                    result.result = ImportResult.SUCCESS
                    
                    # Get version if available
                    version = self._get_module_version(module)
                    result.version = version
                    
                    # Check minimum version if specified
                    if test.min_version and version:
                        if not self._check_version(version, test.min_version):
                            result.error = f"Version {version} < required {test.min_version}"
                            if test.required:
                                result.result = ImportResult.FAILURE
        
        except Exception as e:
            result.error = str(e)
            result.execution_time = time.time() - start_time
            
            if not test.required:
                result.result = ImportResult.OPTIONAL
            else:
                result.result = ImportResult.FAILURE
        
        return result
    
    def _is_mock_object(self, obj: Any) -> bool:
        """Check if object is a mock."""
        if obj is None:
            return False
        
        # Check for mock indicators
        obj_type = type(obj)
        obj_name = getattr(obj_type, '__name__', '')
        
        # Common mock patterns
        mock_indicators = [
            'Mock' in obj_name,
            'MagicMock' in obj_name,
            hasattr(obj, '_mock_name'),
            hasattr(obj, '_spec_class'),
            not hasattr(obj, '__file__') and hasattr(obj, '__name__')
        ]
        
        return any(mock_indicators)
    
    def _get_module_version(self, module: Any) -> Optional[str]:
        """Get module version."""
        version_attrs = ['__version__', 'version', 'VERSION']
        
        for attr in version_attrs:
            if hasattr(module, attr):
                version = getattr(module, attr)
                if isinstance(version, str):
                    return version
                elif hasattr(version, '__str__'):
                    return str(version)
        
        return None
    
    def _check_version(self, current: str, required: str) -> bool:
        """Check if current version meets requirement."""
        try:
            from packaging import version
            return version.parse(current) >= version.parse(required)
        except ImportError:
            # Fallback to simple string comparison
            return current >= required
    
    def run_test_suite(self, 
                      test_groups: List[str] = None,
                      contexts: List[ExecutionContext] = None) -> Dict[str, List[ImportTestResult]]:
        """Run comprehensive import test suite.
        
        Args:
            test_groups: Test groups to run ('standard', 'scientific', 'optional')
            contexts: Execution contexts to test
            
        Returns:
            Dictionary mapping contexts to test results
        """
        if test_groups is None:
            test_groups = ['standard', 'scientific', 'optional']
        
        if contexts is None:
            contexts = [ExecutionContext.PACKAGE, ExecutionContext.STANDALONE]
        
        # Collect tests
        all_tests = []
        
        if 'standard' in test_groups:
            all_tests.extend(self.standard_tests)
        if 'scientific' in test_groups:
            all_tests.extend(self.scientific_tests)
        if 'optional' in test_groups:
            all_tests.extend(self.optional_tests)
        
        results = {}
        
        # Test in each context
        for context in contexts:
            context_results = []
            
            with ContextSimulator() as simulator:
                try:
                    context_info = simulator.simulate_context(context)
                    
                    for test in all_tests:
                        # Skip context-dependent tests in irrelevant contexts
                        if test.context_dependent and not self._is_relevant_context(test, context):
                            continue
                        
                        result = self.run_import_test(test, context.value)
                        context_results.append(result)
                        
                        self.logger.debug(
                            f"Test {test.module_name} in {context.value}: {result.result.value}"
                        )
                
                except Exception as e:
                    self.logger.error(f"Error testing context {context.value}: {e}")
            
            results[context.value] = context_results
        
        return results
    
    def _is_relevant_context(self, test: ImportTest, context: ExecutionContext) -> bool:
        """Check if test is relevant for context."""
        # Development tools are mainly relevant in development/CI contexts
        dev_tools = ['pytest', 'coverage', 'black', 'flake8']
        
        if test.module_name in dev_tools:
            return context in [
                ExecutionContext.DEVELOPMENT,
                ExecutionContext.CI_GITHUB, 
                ExecutionContext.CI_GITLAB,
                ExecutionContext.TEST
            ]
        
        # MinIO might not be available in all contexts
        if test.module_name == 'minio':
            return context not in [ExecutionContext.STANDALONE]
        
        return True
    
    def generate_report(self, results: Dict[str, List[ImportTestResult]]) -> Dict[str, Any]:
        """Generate comprehensive test report.
        
        Args:
            results: Test results by context
            
        Returns:
            Report dictionary
        """
        report = {
            'summary': {},
            'by_context': {},
            'failures': [],
            'warnings': [],
            'recommendations': []
        }
        
        total_tests = 0
        total_successes = 0
        total_fallbacks = 0
        total_failures = 0
        
        for context, context_results in results.items():
            context_summary = {
                'total': len(context_results),
                'success': 0,
                'fallback': 0,
                'optional': 0,
                'failure': 0,
                'tests': []
            }
            
            for result in context_results:
                total_tests += 1
                
                result_dict = result.to_dict()
                context_summary['tests'].append(result_dict)
                
                if result.result == ImportResult.SUCCESS:
                    context_summary['success'] += 1
                    total_successes += 1
                elif result.result == ImportResult.FALLBACK:
                    context_summary['fallback'] += 1
                    total_fallbacks += 1
                elif result.result == ImportResult.OPTIONAL:
                    context_summary['optional'] += 1
                elif result.result == ImportResult.FAILURE:
                    context_summary['failure'] += 1
                    total_failures += 1
                    
                    # Add to failures list
                    report['failures'].append({
                        'context': context,
                        'module': result.test.module_name,
                        'error': result.error,
                        'required': result.test.required
                    })
                
                # Add warnings for unexpected results
                if result.test.required and result.result != ImportResult.SUCCESS:
                    report['warnings'].append({
                        'context': context,
                        'module': result.test.module_name,
                        'issue': f"Required module had result: {result.result.value}",
                        'error': result.error
                    })
            
            report['by_context'][context] = context_summary
        
        # Overall summary
        report['summary'] = {
            'total_tests': total_tests,
            'success_rate': (total_successes / total_tests * 100) if total_tests > 0 else 0,
            'fallback_rate': (total_fallbacks / total_tests * 100) if total_tests > 0 else 0,
            'failure_rate': (total_failures / total_tests * 100) if total_tests > 0 else 0,
            'contexts_tested': len(results),
            'critical_failures': len([f for f in report['failures'] if f['required']])
        }
        
        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(results)
        
        return report
    
    def _generate_recommendations(self, results: Dict[str, List[ImportTestResult]]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check for consistent failures
        failed_modules = {}
        for context, context_results in results.items():
            for result in context_results:
                if result.result == ImportResult.FAILURE and result.test.required:
                    module_name = result.test.module_name
                    if module_name not in failed_modules:
                        failed_modules[module_name] = []
                    failed_modules[module_name].append(context)
        
        for module, contexts in failed_modules.items():
            if len(contexts) > 1:
                recommendations.append(
                    f"Module '{module}' fails consistently across contexts: {', '.join(contexts)}. "
                    f"Consider adding to fallback system."
                )
        
        # Check for missing scientific libraries
        scientific_missing = []
        for context, context_results in results.items():
            for result in context_results:
                if (result.test.module_name in ['numpy', 'librosa'] and 
                    result.result in [ImportResult.FAILURE, ImportResult.FALLBACK]):
                    scientific_missing.append(result.test.module_name)
        
        if scientific_missing:
            recommendations.append(
                f"Critical scientific libraries missing or mocked: {', '.join(set(scientific_missing))}. "
                f"Consider improving installation documentation."
            )
        
        # Check fallback coverage
        fallback_needed = []
        for context, context_results in results.items():
            for result in context_results:
                if (result.test.required and 
                    result.result == ImportResult.FAILURE and
                    not result.test.fallback_expected):
                    fallback_needed.append(result.test.module_name)
        
        if fallback_needed:
            recommendations.append(
                f"Required modules need fallback mechanisms: {', '.join(set(fallback_needed))}"
            )
        
        return recommendations
    
    def validate_source_imports(self, source_path: Path) -> Dict[str, Any]:
        """Validate imports in source code files.
        
        Args:
            source_path: Path to source directory
            
        Returns:
            Validation report
        """
        report = {
            'files_scanned': 0,
            'imports_found': [],
            'issues': [],
            'recommendations': []
        }
        
        python_files = list(source_path.rglob('*.py'))
        report['files_scanned'] = len(python_files)
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                
                # Parse AST
                tree = ast.parse(source_code, filename=str(file_path))
                
                # Extract imports
                imports = self._extract_imports_from_ast(tree)
                
                for import_info in imports:
                    import_info['file'] = str(file_path.relative_to(source_path))
                    report['imports_found'].append(import_info)
                    
                    # Validate import
                    self._validate_import_in_source(import_info, report)
                    
            except Exception as e:
                report['issues'].append({
                    'file': str(file_path.relative_to(source_path)),
                    'type': 'parse_error',
                    'message': f"Failed to parse file: {str(e)}"
                })
        
        return report
    
    def _extract_imports_from_ast(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract import information from AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'type': 'import',
                        'module': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno
                    })
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append({
                        'type': 'from_import',
                        'module': module,
                        'name': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno,
                        'level': node.level
                    })
        
        return imports
    
    def _validate_import_in_source(self, import_info: Dict[str, Any], report: Dict[str, Any]):
        """Validate individual import from source code."""
        module_name = import_info['module']
        
        # Check for known problematic imports
        problematic_imports = {
            'tkinter': 'GUI library not available in headless environments',
            'win32api': 'Windows-specific, will fail on other platforms',
            'pwd': 'Unix-specific, will fail on Windows'
        }
        
        if module_name in problematic_imports:
            report['issues'].append({
                'file': import_info['file'],
                'line': import_info['line'],
                'type': 'platform_specific',
                'module': module_name,
                'message': problematic_imports[module_name]
            })
        
        # Check for imports without fallback handling
        if module_name in ['minio', 'librosa', 'matplotlib']:
            report['recommendations'].append({
                'file': import_info['file'],
                'line': import_info['line'],
                'type': 'fallback_recommended',
                'module': module_name,
                'message': f"Consider using SafeImporter for {module_name}"
            })


class ImportTestSuite(BaseTest):
    """Comprehensive import test suite."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.validator = ImportValidator()
        self.simulator = ContextSimulator()
    
    def tearDown(self):
        """Clean up test environment."""
        self.simulator.cleanup()
        super().tearDown()
    
    def test_standard_library_imports(self):
        """Test standard library imports across contexts."""
        results = self.validator.run_test_suite(
            test_groups=['standard'],
            contexts=[ExecutionContext.PACKAGE, ExecutionContext.STANDALONE]
        )
        
        # All standard library imports should succeed
        for context, context_results in results.items():
            for result in context_results:
                with self.subTest(context=context, module=result.test.module_name):
                    self.assertEqual(result.result, ImportResult.SUCCESS,
                                   f"Standard library import failed: {result.error}")
    
    def test_scientific_library_fallbacks(self):
        """Test scientific library fallback behavior."""
        results = self.validator.run_test_suite(
            test_groups=['scientific'],
            contexts=[ExecutionContext.STANDALONE]
        )
        
        for context, context_results in results.items():
            for result in context_results:
                with self.subTest(context=context, module=result.test.module_name):
                    # Should either succeed or fallback, never fail completely
                    self.assertIn(result.result, [
                        ImportResult.SUCCESS,
                        ImportResult.FALLBACK,
                        ImportResult.OPTIONAL
                    ], f"Scientific library should have fallback: {result.error}")
    
    def test_optional_dependencies(self):
        """Test optional dependency handling."""
        results = self.validator.run_test_suite(
            test_groups=['optional'],
            contexts=[ExecutionContext.PACKAGE]
        )
        
        for context, context_results in results.items():
            for result in context_results:
                with self.subTest(context=context, module=result.test.module_name):
                    # Optional dependencies should never cause complete failure
                    self.assertNotEqual(result.result, ImportResult.FAILURE,
                                      f"Optional dependency should not fail: {result.error}")
    
    def test_import_consistency_across_contexts(self):
        """Test import consistency across different contexts."""
        results = self.validator.run_test_suite(
            test_groups=['standard'],
            contexts=[
                ExecutionContext.PACKAGE,
                ExecutionContext.STANDALONE,
                ExecutionContext.CI_GITHUB,
                ExecutionContext.DOCKER
            ]
        )
        
        # Group results by module
        module_results = {}
        for context, context_results in results.items():
            for result in context_results:
                module_name = result.test.module_name
                if module_name not in module_results:
                    module_results[module_name] = {}
                module_results[module_name][context] = result
        
        # Check consistency
        for module_name, contexts in module_results.items():
            with self.subTest(module=module_name):
                results_set = set(result.result for result in contexts.values())
                
                # Standard library should be consistent
                if module_name in ['os', 'sys', 'json', 'pathlib']:
                    self.assertEqual(len(results_set), 1,
                                   f"Inconsistent results for {module_name}: {results_set}")
                    self.assertEqual(list(results_set)[0], ImportResult.SUCCESS)
    
    def test_import_performance(self):
        """Test import performance across contexts."""
        results = self.validator.run_test_suite(
            test_groups=['standard'],
            contexts=[ExecutionContext.PACKAGE]
        )
        
        for context, context_results in results.items():
            for result in context_results:
                with self.subTest(context=context, module=result.test.module_name):
                    # Imports should be reasonably fast (< 1 second each)
                    self.assertLess(result.execution_time, 1.0,
                                  f"Import too slow: {result.execution_time}s")
    
    def test_source_code_validation(self):
        """Test validation of source code imports."""
        # Create temporary source files for testing
        temp_dir = tempfile.mkdtemp()
        try:
            source_path = Path(temp_dir)
            
            # Create test file with various import patterns
            test_file = source_path / "test_imports.py"
            test_file.write_text("""
import os
import sys
from pathlib import Path
import numpy as np
import librosa
from minio import Minio
import definitely_not_a_real_module
""")
            
            report = self.validator.validate_source_imports(source_path)
            
            # Should find imports
            self.assertGreater(report['files_scanned'], 0)
            self.assertGreater(len(report['imports_found']), 0)
            
            # Should have recommendations for fallback imports
            fallback_recommendations = [
                r for r in report['recommendations'] 
                if r.get('type') == 'fallback_recommended'
            ]
            self.assertGreater(len(fallback_recommendations), 0)
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_comprehensive_report_generation(self):
        """Test comprehensive report generation."""
        results = self.validator.run_test_suite(
            test_groups=['standard', 'optional'],
            contexts=[ExecutionContext.PACKAGE, ExecutionContext.STANDALONE]
        )
        
        report = self.validator.generate_report(results)
        
        # Check report structure
        self.assertIn('summary', report)
        self.assertIn('by_context', report)
        self.assertIn('failures', report)
        self.assertIn('recommendations', report)
        
        # Check summary data
        summary = report['summary']
        self.assertIn('total_tests', summary)
        self.assertIn('success_rate', summary)
        self.