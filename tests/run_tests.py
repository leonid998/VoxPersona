#!/usr/bin/env python3
"""
Test Runner for VoxPersona MinIO Integration

Runs all unit and integration tests for the MinIO functionality.
Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run only unit tests
    python run_tests.py --integration      # Run only integration tests
    python run_tests.py --verbose          # Run with verbose output
"""

import unittest
import sys
import os
import argparse
import logging
from datetime import datetime

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import test modules
from tests.test_minio_manager import *
from tests.test_integration import *


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
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="VoxPersona MinIO Integration Test Runner")
    parser.add_argument('--unit', action='store_true', help='Run only unit tests')
    parser.add_argument('--integration', action='store_true', help='Run only integration tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--pattern', help='Test pattern to run (e.g., test_minio_manager.TestMinIOManager)')
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("VoxPersona MinIO Integration Test Runner")
    print(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    success = True
    
    try:
        if args.pattern:
            # Run specific test pattern
            print(f"Running tests matching pattern: {args.pattern}")
            setup_test_logging(args.verbose)
            suite = discover_tests(args.pattern)
            success = run_test_suite(suite, f"Pattern: {args.pattern}")
        elif args.unit:
            success = run_unit_tests(args.verbose)
        elif args.integration:
            success = run_integration_tests(args.verbose)
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
    sys.exit(exit_code)


if __name__ == '__main__':
    main()