#!/usr/bin/env python3
"""
Comprehensive Test Runner for VoxPersona

Enhanced test runner with support for:
- Comprehensive testing strategy implementation 
- Parallel test execution with resource management
- Cross-environment validation
- Error scenario testing with failure simulation
- Performance monitoring and metrics collection

Usage:
    python run_tests.py                          # Run all tests with orchestrator
    python run_tests.py --unit                   # Run only unit tests
    python run_tests.py --integration            # Run only integration tests
    python run_tests.py --comprehensive          # Run comprehensive test suite
    python run_tests.py --environment dev        # Specify test environment
    python run_tests.py --parallel 8             # Set parallel workers
    python run_tests.py --verbose                # Run with verbose output
    python run_tests.py --category unit          # Run specific test category
    python run_tests.py --pattern "test_config*" # Run tests matching pattern
"""

import unittest
import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Optional

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import test modules
from tests.test_minio_manager import *
from tests.test_integration import *

# Import new comprehensive testing infrastructure
try:
    from tests.test_orchestrator import orchestrator, run_comprehensive_tests
    from tests.test_config import (
        test_env_manager, 
        get_test_config, 
        get_execution_config,
        TEST_CATEGORIES
    )
    COMPREHENSIVE_TESTING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Comprehensive testing infrastructure not available: {e}")
    COMPREHENSIVE_TESTING_AVAILABLE = False


def setup_test_logging(verbose=False):
    """Setup logging for tests"""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def discover_tests(test_pattern=None):
    """Discover and load tests"""
    loader = unittest.TestLoader()
    
    if test_pattern:
        suite = loader.loadTestsFromName(test_pattern)
    else:
        # Discover all tests in the tests directory
        test_dir = os.path.dirname(os.path.abspath(__file__))
        suite = loader.discover(test_dir, pattern='test_*.py')
    
    return suite


def run_unit_tests(verbose=False):
    """Run only unit tests"""
    print("=" * 60)
    print("Running Unit Tests for MinIO Manager")
    print("=" * 60)
    
    setup_test_logging(verbose)
    
    # Load specific unit test classes
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add unit test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRetryableMinIOOperation))
    suite.addTests(loader.loadTestsFromTestCase(TestMinIOHealthMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestMinIOManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMinIOManagerIntegration))
    
    return run_test_suite(suite, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run only integration tests"""
    print("=" * 60)
    print("Running Integration Tests for Audio Processing")
    print("=" * 60)
    
    setup_test_logging(verbose)
    
    # Load integration test classes
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add integration test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAudioProcessingIntegration))
    
    return run_test_suite(suite, "Integration Tests")


def run_all_tests(verbose=False):
    """Run all tests"""
    print("=" * 60)
    print("Running All Tests for VoxPersona MinIO Integration")
    print("=" * 60)
    
    setup_test_logging(verbose)
    
    # Discover all tests
    suite = discover_tests()
    return run_test_suite(suite, "All Tests")


def run_comprehensive_tests_enhanced(verbose=False):
    """Run comprehensive test suite with orchestrator"""
    if not COMPREHENSIVE_TESTING_AVAILABLE:
        print("Comprehensive testing infrastructure not available. Running legacy tests...")
        return run_all_tests(verbose)
    
    print("=" * 60)
    print("Running Comprehensive Test Suite with Enhanced Orchestrator")
    print("=" * 60)
    
    setup_test_logging(verbose)
    
    try:
        # Setup test environment
        if not test_env_manager.setup_environment():
            print("Failed to setup test environment")
            return False
        
        # Run comprehensive tests
        session_report = run_comprehensive_tests()
        
        # Print results
        overall = session_report['overall_metrics']
        success = overall.failed_tests == 0 and overall.error_tests == 0
        
        print(f"\nComprehensive Test Results:")
        print(f"Total Tests: {overall.total_tests}")
        print(f"Passed: {overall.passed_tests}")
        print(f"Failed: {overall.failed_tests}")
        print(f"Errors: {overall.error_tests}")
        print(f"Success Rate: {session_report['success_rate']:.1f}%")
        print(f"Duration: {overall.total_duration:.2f}s")
        
        return success
        
    except Exception as e:
        print(f"Error running comprehensive tests: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False
    
    finally:
        test_env_manager.cleanup_environment()


def run_category_tests(category: str, verbose=False):
    """Run tests for specific category"""
    if not COMPREHENSIVE_TESTING_AVAILABLE:
        print(f"Category testing not available. Running all tests...")
        return run_all_tests(verbose)
    
    if category not in TEST_CATEGORIES:
        print(f"Unknown test category: {category}")
        print(f"Available categories: {', '.join(TEST_CATEGORIES.keys())}")
        return False
    
    print("=" * 60)
    print(f"Running {category.title()} Tests")
    print("=" * 60)
    
    setup_test_logging(verbose)
    
    try:
        # Discover tests for category
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Load tests matching category pattern
        test_dir = os.path.dirname(os.path.abspath(__file__))
        pattern = f'test_{category}_*.py'
        
        try:
            discovered = loader.discover(test_dir, pattern=pattern)
            suite.addTest(discovered)
        except Exception as e:
            print(f"Failed to discover {category} tests: {e}")
            return False
        
        if suite.countTestCases() == 0:
            print(f"No tests found for category: {category}")
            return True
        
        # Execute tests
        runner = unittest.TextTestRunner(
            verbosity=2 if verbose else 1,
            stream=sys.stdout,
            descriptions=True,
            failfast=False
        )
        
        result = runner.run(suite)
        
        # Print summary
        success = len(result.failures) == 0 and len(result.errors) == 0
        print(f"\n{category.title()} Tests Summary:")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Success: {success}")
        
        return success
        
    except Exception as e:
        print(f"Error running {category} tests: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def run_pattern_tests(pattern: str, verbose=False):
    """Run tests matching specific pattern"""
    print("=" * 60)
    print(f"Running Tests Matching Pattern: {pattern}")
    print("=" * 60)
    
    setup_test_logging(verbose)
    
    try:
        # Discover tests matching pattern
        loader = unittest.TestLoader()
        test_dir = os.path.dirname(os.path.abspath(__file__))
        
        suite = loader.discover(test_dir, pattern=pattern)
        
        if suite.countTestCases() == 0:
            print(f"No tests found matching pattern: {pattern}")
            return True
        
        return run_test_suite(suite, f"Pattern: {pattern}")
        
    except Exception as e:
        print(f"Error running pattern tests: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def run_test_suite(suite, suite_name):
    """Run a test suite and return results"""
    start_time = datetime.now()
    
    # Create a test runner with appropriate verbosity
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    # Run the tests
    result = runner.run(suite)
    
    # Calculate duration
    end_time = datetime.now()
    duration = end_time - start_time
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"{suite_name} Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Duration: {duration.total_seconds():.2f} seconds")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%" if result.testsRun > 0 else "No tests run")
    
    # Print failure details if any
    if result.failures:
        print(f"\nFailures ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.splitlines()[-1] if traceback else 'Unknown failure'}")
    
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.splitlines()[-1] if traceback else 'Unknown error'}")
    
    # Return success status
    return len(result.failures) == 0 and len(result.errors) == 0


def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []
    
    try:
        import minio
    except ImportError:
        missing_deps.append('minio')
    
    try:
        import dotenv
    except ImportError:
        missing_deps.append('python-dotenv')
    
    if missing_deps:
        print("Error: Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install missing dependencies:")
        print(f"  pip install {' '.join(missing_deps)}")
        return False
    
    return True


def main():
    """Enhanced main test runner function with comprehensive testing support"""
    parser = argparse.ArgumentParser(description="VoxPersona Comprehensive Test Runner")
    parser.add_argument('--unit', action='store_true', help='Run only unit tests')
    parser.add_argument('--integration', action='store_true', help='Run only integration tests')
    parser.add_argument('--comprehensive', action='store_true', help='Run comprehensive test suite with orchestrator')
    parser.add_argument('--category', choices=list(TEST_CATEGORIES.keys()) if COMPREHENSIVE_TESTING_AVAILABLE else [], help='Run specific test category')
    parser.add_argument('--environment', choices=['development', 'testing', 'production', 'hybrid'], help='Specify test environment')
    parser.add_argument('--parallel', type=int, help='Number of parallel workers')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--pattern', help='Test pattern to run (e.g., test_config_*.py)')
    parser.add_argument('--fail-fast', action='store_true', help='Stop on first failure')
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup environment if specified
    if args.environment and COMPREHENSIVE_TESTING_AVAILABLE:
        if not test_env_manager.switch_environment(args.environment):
            print(f"Unknown environment: {args.environment}")
            sys.exit(1)
        print(f"Using test environment: {args.environment}")
    
    # Set parallel workers if specified
    if args.parallel and COMPREHENSIVE_TESTING_AVAILABLE:
        test_env_manager.execution_config.parallel_workers = args.parallel
        print(f"Using {args.parallel} parallel workers")
    
    print("VoxPersona Comprehensive Test Runner")
    print(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if COMPREHENSIVE_TESTING_AVAILABLE:
        env_config = get_test_config()
        print(f"Environment: {env_config.name} - {env_config.description}")
    
    print("")
    
    success = True
    
    try:
        if args.comprehensive and COMPREHENSIVE_TESTING_AVAILABLE:
            success = run_comprehensive_tests_enhanced(args.verbose)
        elif args.category and COMPREHENSIVE_TESTING_AVAILABLE:
            success = run_category_tests(args.category, args.verbose)
        elif args.pattern:
            success = run_pattern_tests(args.pattern, args.verbose)
        elif args.unit:
            success = run_unit_tests(args.verbose)
        elif args.integration:
            success = run_integration_tests(args.verbose)
        else:
            # Default to comprehensive if available, otherwise all tests
            if COMPREHENSIVE_TESTING_AVAILABLE:
                success = run_comprehensive_tests_enhanced(args.verbose)
            else:
                success = run_all_tests(args.verbose)
            
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        success = False
    except Exception as e:
        print(f"\nUnexpected error running tests: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        success = False
    
    # Exit with appropriate code
    exit_code = 0 if success else 1
    print(f"\nTest run completed with exit code: {exit_code}")
    
    if COMPREHENSIVE_TESTING_AVAILABLE and success:
        print("\n✅ All tests passed! System is ready for deployment.")
    elif not success:
        print("\n❌ Some tests failed. Please review and fix issues before deployment.")
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()