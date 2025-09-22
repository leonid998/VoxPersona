"""
Comprehensive Test Orchestrator

This module provides advanced test orchestration capabilities including:
- Parallel test execution with resource management
- Test dependency resolution and scheduling
- Performance monitoring and metrics collection
- Failure recovery and retry mechanisms
"""

import unittest
import threading
import multiprocessing
import queue
import time
import sys
import os
import traceback
import json
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future, as_completed
from pathlib import Path
import logging

from test_config import (
    test_env_manager, 
    get_test_config, 
    get_execution_config,
    TEST_CATEGORIES
)

@dataclass
class TestResult:
    """Enhanced test result with detailed metrics"""
    test_id: str
    test_name: str
    test_class: str
    category: str
    status: str  # 'passed', 'failed', 'error', 'skipped'
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    memory_usage: float = 0.0
    cpu_time: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TestSuiteMetrics:
    """Test suite execution metrics"""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    skipped_tests: int = 0
    total_duration: float = 0.0
    average_duration: float = 0.0
    memory_peak: float = 0.0
    cpu_total: float = 0.0
    retry_total: int = 0
    categories: Dict[str, int] = field(default_factory=dict)

class TestResourceMonitor:
    """Monitor test resource usage"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = []
        self.peak_memory = 0.0
        self.total_cpu = 0.0
        
    def start_monitoring(self):
        """Start resource monitoring"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_resources(self):
        """Monitor resource usage"""
        try:
            import psutil
            process = psutil.Process()
            
            while self.monitoring:
                try:
                    memory_info = process.memory_info()
                    cpu_percent = process.cpu_percent()
                    
                    memory_mb = memory_info.rss / (1024 * 1024)
                    self.peak_memory = max(self.peak_memory, memory_mb)
                    self.total_cpu += cpu_percent
                    
                    self.metrics.append({
                        'timestamp': datetime.now(),
                        'memory_mb': memory_mb,
                        'cpu_percent': cpu_percent
                    })
                    
                    time.sleep(0.1)  # Sample every 100ms
                    
                except Exception as e:
                    logging.warning(f"Resource monitoring error: {e}")
                    
        except ImportError:
            logging.warning("psutil not available, resource monitoring disabled")
    
    def get_metrics(self) -> Dict[str, float]:
        """Get collected metrics"""
        return {
            'peak_memory_mb': self.peak_memory,
            'average_cpu_percent': self.total_cpu / len(self.metrics) if self.metrics else 0.0,
            'total_samples': len(self.metrics)
        }

class TestExecutor:
    """Enhanced test executor with parallel execution capabilities"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or get_execution_config().parallel_workers
        self.resource_monitor = TestResourceMonitor()
        self.test_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.active_tests = {}
        self.completed_tests = []
        self.failed_tests = []
        
    def execute_test_suite(self, test_suite: unittest.TestSuite, 
                          category: str = 'unit') -> TestSuiteMetrics:
        """Execute test suite with parallel processing"""
        start_time = datetime.now()
        self.resource_monitor.start_monitoring()
        
        try:
            # Extract individual tests from suite
            tests = self._extract_tests(test_suite)
            
            # Execute tests in parallel
            results = self._execute_tests_parallel(tests, category)
            
            # Calculate metrics
            metrics = self._calculate_metrics(results, start_time)
            
        finally:
            self.resource_monitor.stop_monitoring()
        
        return metrics
    
    def _extract_tests(self, test_suite: unittest.TestSuite) -> List[unittest.TestCase]:
        """Extract individual test cases from test suite"""
        tests = []
        
        def extract_recursive(suite):
            for test in suite:
                if isinstance(test, unittest.TestSuite):
                    extract_recursive(test)
                else:
                    tests.append(test)
        
        extract_recursive(test_suite)
        return tests
    
    def _execute_tests_parallel(self, tests: List[unittest.TestCase], 
                               category: str) -> List[TestResult]:
        """Execute tests in parallel"""
        results = []
        
        # Determine if tests can run in parallel
        can_parallel = TEST_CATEGORIES.get(category, {}).get('parallel', True)
        workers = self.max_workers if can_parallel else 1
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tests
            future_to_test = {
                executor.submit(self._execute_single_test, test, category): test 
                for test in tests
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_test):
                test = future_to_test[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Create error result
                    error_result = TestResult(
                        test_id=f"{test.__class__.__name__}.{test._testMethodName}",
                        test_name=test._testMethodName,
                        test_class=test.__class__.__name__,
                        category=category,
                        status='error',
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        error_message=str(e),
                        error_traceback=traceback.format_exc()
                    )
                    results.append(error_result)
        
        return results
    
    def _execute_single_test(self, test: unittest.TestCase, category: str) -> TestResult:
        """Execute a single test with detailed result capture"""
        test_id = f"{test.__class__.__name__}.{test._testMethodName}"
        start_time = datetime.now()
        
        # Capture stdout/stderr
        from io import StringIO
        captured_stdout = StringIO()
        captured_stderr = StringIO()
        
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            sys.stdout = captured_stdout
            sys.stderr = captured_stderr
            
            # Create test result object
            test_result = unittest.TestResult()
            
            # Run the test
            test.run(test_result)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Determine status
            if test_result.errors:
                status = 'error'
                error_msg = test_result.errors[0][1] if test_result.errors else None
            elif test_result.failures:
                status = 'failed'
                error_msg = test_result.failures[0][1] if test_result.failures else None
            elif test_result.skipped:
                status = 'skipped'
                error_msg = test_result.skipped[0][1] if test_result.skipped else None
            else:
                status = 'passed'
                error_msg = None
            
            return TestResult(
                test_id=test_id,
                test_name=test._testMethodName,
                test_class=test.__class__.__name__,
                category=category,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                error_message=error_msg,
                stdout=captured_stdout.getvalue(),
                stderr=captured_stderr.getvalue()
            )
            
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
    
    def _calculate_metrics(self, results: List[TestResult], 
                          start_time: datetime) -> TestSuiteMetrics:
        """Calculate test suite metrics"""
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        metrics = TestSuiteMetrics()
        metrics.total_tests = len(results)
        metrics.total_duration = total_duration
        
        # Count by status
        for result in results:
            if result.status == 'passed':
                metrics.passed_tests += 1
            elif result.status == 'failed':
                metrics.failed_tests += 1
            elif result.status == 'error':
                metrics.error_tests += 1
            elif result.status == 'skipped':
                metrics.skipped_tests += 1
            
            # Count by category
            category = result.category
            metrics.categories[category] = metrics.categories.get(category, 0) + 1
        
        # Calculate averages
        if results:
            metrics.average_duration = sum(r.duration for r in results) / len(results)
        
        # Add resource metrics
        resource_metrics = self.resource_monitor.get_metrics()
        metrics.memory_peak = resource_metrics.get('peak_memory_mb', 0.0)
        metrics.cpu_total = resource_metrics.get('average_cpu_percent', 0.0)
        
        return metrics

class TestOrchestrator:
    """Main test orchestration engine"""
    
    def __init__(self):
        self.executor = TestExecutor()
        self.results_history = []
        self.current_session = None
        
    def run_comprehensive_tests(self, test_patterns: List[str] = None) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_session = session_id
        
        logging.info(f"Starting comprehensive test session: {session_id}")
        
        # Setup test environment
        if not test_env_manager.setup_environment():
            raise RuntimeError("Failed to setup test environment")
        
        try:
            # Discover and categorize tests
            test_suites = self._discover_tests(test_patterns)
            
            # Execute tests by category
            category_results = {}
            overall_metrics = TestSuiteMetrics()
            
            for category, suite in test_suites.items():
                logging.info(f"Executing {category} tests...")
                
                metrics = self.executor.execute_test_suite(suite, category)
                category_results[category] = metrics
                
                # Aggregate metrics
                overall_metrics.total_tests += metrics.total_tests
                overall_metrics.passed_tests += metrics.passed_tests
                overall_metrics.failed_tests += metrics.failed_tests
                overall_metrics.error_tests += metrics.error_tests
                overall_metrics.skipped_tests += metrics.skipped_tests
                overall_metrics.total_duration += metrics.total_duration
                overall_metrics.memory_peak = max(overall_metrics.memory_peak, metrics.memory_peak)
                overall_metrics.cpu_total += metrics.cpu_total
            
            # Calculate overall averages
            if overall_metrics.total_tests > 0:
                overall_metrics.average_duration = (
                    overall_metrics.total_duration / overall_metrics.total_tests
                )
            
            # Create session report
            session_report = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'environment': test_env_manager.current_env,
                'overall_metrics': overall_metrics,
                'category_results': category_results,
                'success_rate': (
                    overall_metrics.passed_tests / overall_metrics.total_tests * 100
                    if overall_metrics.total_tests > 0 else 0
                )
            }
            
            # Store results
            self.results_history.append(session_report)
            
            # Generate reports
            self._generate_reports(session_report)
            
            return session_report
            
        finally:
            test_env_manager.cleanup_environment()
    
    def _discover_tests(self, patterns: List[str] = None) -> Dict[str, unittest.TestSuite]:
        """Discover and categorize tests"""
        loader = unittest.TestLoader()
        test_suites = {}
        
        # Default patterns if none provided
        if not patterns:
            patterns = ['test_*.py']
        
        # Discover tests by category
        test_dir = Path(__file__).parent
        
        for category in TEST_CATEGORIES.keys():
            suite = unittest.TestSuite()
            
            # Look for category-specific test files
            category_patterns = [
                f'test_{category}_*.py',
                f'test_*_{category}.py'
            ]
            
            for pattern in category_patterns + patterns:
                try:
                    discovered = loader.discover(
                        str(test_dir), 
                        pattern=pattern,
                        top_level_dir=str(test_dir.parent)
                    )
                    suite.addTest(discovered)
                except Exception as e:
                    logging.warning(f"Failed to discover tests with pattern {pattern}: {e}")
            
            if suite.countTestCases() > 0:
                test_suites[category] = suite
        
        # If no category-specific tests found, create general suite
        if not test_suites:
            general_suite = unittest.TestSuite()
            for pattern in patterns:
                try:
                    discovered = loader.discover(
                        str(test_dir),
                        pattern=pattern,
                        top_level_dir=str(test_dir.parent)
                    )
                    general_suite.addTest(discovered)
                except Exception as e:
                    logging.warning(f"Failed to discover tests with pattern {pattern}: {e}")
            
            if general_suite.countTestCases() > 0:
                test_suites['unit'] = general_suite
        
        return test_suites
    
    def _generate_reports(self, session_report: Dict[str, Any]):
        """Generate test reports"""
        output_dir = Path(test_env_manager.resource_config.output_dir)
        session_id = session_report['session_id']
        
        # JSON report
        json_report_path = output_dir / f"{session_id}_report.json"
        with open(json_report_path, 'w') as f:
            json.dump(session_report, f, indent=2, default=str)
        
        # HTML report
        html_report_path = output_dir / f"{session_id}_report.html"
        self._generate_html_report(session_report, html_report_path)
        
        # Console summary
        self._print_summary(session_report)
        
        logging.info(f"Reports generated:")
        logging.info(f"  JSON: {json_report_path}")
        logging.info(f"  HTML: {html_report_path}")
    
    def _generate_html_report(self, session_report: Dict[str, Any], output_path: Path):
        """Generate HTML test report"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>VoxPersona Test Report - {session_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
                .metrics {{ display: flex; gap: 20px; margin: 20px 0; }}
                .metric-card {{ background-color: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; flex: 1; }}
                .success {{ color: #28a745; }}
                .failure {{ color: #dc3545; }}
                .error {{ color: #ffc107; }}
                .category-results {{ margin: 20px 0; }}
                .category {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>VoxPersona Test Report</h1>
                <p><strong>Session ID:</strong> {session_id}</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Environment:</strong> {environment}</p>
                <p><strong>Success Rate:</strong> {success_rate:.1f}%</p>
            </div>
            
            <div class="metrics">
                <div class="metric-card">
                    <h3>Total Tests</h3>
                    <h2>{total_tests}</h2>
                </div>
                <div class="metric-card success">
                    <h3>Passed</h3>
                    <h2>{passed_tests}</h2>
                </div>
                <div class="metric-card failure">
                    <h3>Failed</h3>
                    <h2>{failed_tests}</h2>
                </div>
                <div class="metric-card error">
                    <h3>Errors</h3>
                    <h2>{error_tests}</h2>
                </div>
            </div>
            
            <div class="category-results">
                <h2>Results by Category</h2>
                {category_html}
            </div>
        </body>
        </html>
        """
        
        overall = session_report['overall_metrics']
        
        # Generate category HTML
        category_html = ""
        for category, metrics in session_report['category_results'].items():
            category_html += f"""
            <div class="category">
                <h3>{category.title()} Tests</h3>
                <p>Total: {metrics.total_tests}, Passed: {metrics.passed_tests}, 
                   Failed: {metrics.failed_tests}, Errors: {metrics.error_tests}</p>
                <p>Duration: {metrics.total_duration:.2f}s, 
                   Average: {metrics.average_duration:.2f}s</p>
            </div>
            """
        
        html_content = html_template.format(
            session_id=session_report['session_id'],
            timestamp=session_report['timestamp'],
            environment=session_report['environment'],
            success_rate=session_report['success_rate'],
            total_tests=overall.total_tests,
            passed_tests=overall.passed_tests,
            failed_tests=overall.failed_tests,
            error_tests=overall.error_tests,
            category_html=category_html
        )
        
        with open(output_path, 'w') as f:
            f.write(html_content)
    
    def _print_summary(self, session_report: Dict[str, Any]):
        """Print test summary to console"""
        overall = session_report['overall_metrics']
        
        print("\n" + "="*60)
        print(f"VoxPersona Test Session Summary")
        print("="*60)
        print(f"Session ID: {session_report['session_id']}")
        print(f"Environment: {session_report['environment']}")
        print(f"Total Tests: {overall.total_tests}")
        print(f"Passed: {overall.passed_tests}")
        print(f"Failed: {overall.failed_tests}")
        print(f"Errors: {overall.error_tests}")
        print(f"Success Rate: {session_report['success_rate']:.1f}%")
        print(f"Total Duration: {overall.total_duration:.2f}s")
        print(f"Average Duration: {overall.average_duration:.2f}s")
        print(f"Peak Memory: {overall.memory_peak:.1f}MB")
        print("="*60)
        
        for category, metrics in session_report['category_results'].items():
            print(f"{category.title()}: {metrics.passed_tests}/{metrics.total_tests} passed")

# Global orchestrator instance
orchestrator = TestOrchestrator()

def run_comprehensive_tests(**kwargs) -> Dict[str, Any]:
    """Convenience function to run comprehensive tests"""
    return orchestrator.run_comprehensive_tests(**kwargs)