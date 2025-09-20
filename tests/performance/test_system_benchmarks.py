"""System benchmarks and performance regression testing for VoxPersona.

This module provides comprehensive system benchmarks, performance baselines,
and regression detection for the VoxPersona platform.
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import statistics
import threading
from dataclasses import dataclass, asdict
from datetime import datetime

from tests.framework.base_test import BasePerformanceTest
from src.import_utils import SafeImporter
from src.config import VoxPersonaConfig
from src.environment import EnvironmentDetector


@dataclass
class BenchmarkResult:
    """Represents a benchmark test result."""
    name: str
    category: str
    value: float
    unit: str
    timestamp: float
    environment: str
    metadata: Dict[str, Any]
    passed: bool
    threshold: Optional[float] = None
    baseline: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class SystemBenchmarkTests(BasePerformanceTest):
    """Comprehensive system benchmark tests."""
    
    def setUp(self):
        """Set up benchmark test environment."""
        super().setUp()
        self.importer = SafeImporter()
        self.config = VoxPersonaConfig()
        self.env_detector = EnvironmentDetector()
        
        # Get environment info
        self.env_info = self.env_detector.detect_environment()
        self.environment = self.env_info['environment']
        
        # Benchmark results storage
        self.benchmark_results = []
        
        # Performance thresholds by category
        self.thresholds = {
            'import_performance': {
                'single_import': 0.1,      # seconds
                'batch_import': 2.0,       # seconds for 10 imports
                'fallback_import': 0.5,    # seconds for fallback
            },
            'system_performance': {
                'startup_time': 5.0,       # seconds
                'config_loading': 1.0,     # seconds
                'environment_detection': 0.5,  # seconds
            },
            'file_operations': {
                'file_read': 0.1,          # seconds per MB
                'file_write': 0.2,         # seconds per MB
                'directory_scan': 2.0,     # seconds for 1000 files
            },
            'memory_performance': {
                'memory_growth': 50,       # MB maximum growth
                'memory_efficiency': 0.8,  # memory usage ratio
            },
            'concurrency': {
                'thread_performance': 5.0, # seconds for 10 threads
                'lock_contention': 0.1,    # seconds wait time
            }
        }
        
        # Load baselines if available
        self.baselines = self._load_performance_baselines()
    
    def tearDown(self):
        """Clean up and save benchmark results."""
        # Save benchmark results
        self._save_benchmark_results()
        super().tearDown()
    
    def _load_performance_baselines(self) -> Dict[str, float]:
        """Load performance baselines from file."""
        baseline_file = Path(self.config.get_data_path()) / "performance_baselines.json"
        
        if baseline_file.exists():
            try:
                with open(baseline_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load baselines: {e}")
        
        # Default baselines if file doesn't exist
        return {
            'import_numpy': 0.5,
            'import_librosa': 1.0,
            'system_startup': 3.0,
            'config_load': 0.5,
            'environment_detect': 0.2,
            'file_read_1mb': 0.05,
            'batch_import_10': 1.5
        }
    
    def _save_benchmark_results(self):
        """Save benchmark results to file."""
        if not self.benchmark_results:
            return
        
        results_file = Path(self.config.get_data_path()) / f"benchmark_results_{int(time.time())}.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(results_file, 'w') as f:
                json.dump([result.to_dict() for result in self.benchmark_results], f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save benchmark results: {e}")
    
    def _record_benchmark(self, 
                         name: str, 
                         category: str, 
                         value: float, 
                         unit: str,
                         threshold: Optional[float] = None,
                         metadata: Dict[str, Any] = None) -> BenchmarkResult:
        """Record a benchmark result."""
        if metadata is None:
            metadata = {}
        
        baseline = self.baselines.get(name)
        passed = True
        
        if threshold is not None:
            passed = value <= threshold
        elif baseline is not None:
            # Consider it passed if within 50% of baseline
            passed = value <= baseline * 1.5
        
        result = BenchmarkResult(
            name=name,
            category=category,
            value=value,
            unit=unit,
            timestamp=time.time(),
            environment=self.environment,
            metadata=metadata,
            passed=passed,
            threshold=threshold,
            baseline=baseline
        )
        
        self.benchmark_results.append(result)
        
        # Also log as performance metric
        self.log_performance_metric(name, value, metadata)
        
        return result
    
    def test_import_performance_benchmarks(self):
        """Benchmark import performance across different modules."""
        # Test single import performance
        modules_to_test = [
            ('os', 'standard'),
            ('sys', 'standard'),
            ('json', 'standard'),
            ('pathlib', 'standard'),
            ('numpy', 'scientific'),
            ('librosa', 'scientific'),
            ('matplotlib', 'optional'),
            ('requests', 'optional'),
            ('non_existent_module', 'fallback')
        ]
        
        for module_name, category in modules_to_test:
            with self.subTest(module=module_name):
                start_time = time.time()
                
                # Import module
                result_module = self.importer.safe_import(module_name)
                
                import_time = time.time() - start_time
                
                # Verify import succeeded
                self.assertIsNotNone(result_module)
                
                # Record benchmark
                benchmark_name = f"import_{module_name}"
                threshold = self.thresholds['import_performance']['single_import']
                
                if category == 'fallback':
                    threshold = self.thresholds['import_performance']['fallback_import']
                
                result = self._record_benchmark(
                    benchmark_name,
                    'import_performance',
                    import_time,
                    'seconds',
                    threshold,
                    {'module': module_name, 'category': category}
                )
                
                # Assert performance requirement
                self.assertTrue(result.passed, 
                              f"Import {module_name} too slow: {import_time:.3f}s")
    
    def test_batch_import_performance(self):
        """Benchmark batch import performance."""
        modules = ['os', 'sys', 'json', 'pathlib', 'time', 'threading', 're', 'logging', 'sqlite3', 'tempfile']
        
        start_time = time.time()
        
        imported_modules = []
        for module_name in modules:
            module = self.importer.safe_import(module_name)
            self.assertIsNotNone(module)
            imported_modules.append(module)
        
        batch_time = time.time() - start_time
        
        # Record benchmark
        result = self._record_benchmark(
            'batch_import_10',
            'import_performance',
            batch_time,
            'seconds',
            self.thresholds['import_performance']['batch_import'],
            {'modules_count': len(modules)}
        )
        
        self.assertTrue(result.passed, f"Batch import too slow: {batch_time:.3f}s")
        self.assertEqual(len(imported_modules), len(modules))
    
    def test_system_startup_performance(self):
        """Benchmark system startup and initialization."""
        start_time = time.time()
        
        # Simulate system startup sequence
        # 1. Environment detection
        env_start = time.time()
        env_detector = EnvironmentDetector()
        env_info = env_detector.detect_environment()
        env_time = time.time() - env_start
        
        # 2. Configuration loading
        config_start = time.time()
        config = VoxPersonaConfig()
        config.load_for_environment(env_info)
        config_time = time.time() - config_start
        
        # 3. Import system initialization
        import_start = time.time()
        importer = SafeImporter()
        import_time = time.time() - import_start
        
        total_startup_time = time.time() - start_time
        
        # Record individual benchmarks
        self._record_benchmark(
            'environment_detect',
            'system_performance',
            env_time,
            'seconds',
            self.thresholds['system_performance']['environment_detection'],
            {'environment': env_info['environment']}
        )
        
        self._record_benchmark(
            'config_load',
            'system_performance',
            config_time,
            'seconds',
            self.thresholds['system_performance']['config_loading']
        )
        
        # Record total startup time
        result = self._record_benchmark(
            'system_startup',
            'system_performance',
            total_startup_time,
            'seconds',
            self.thresholds['system_performance']['startup_time'],
            {
                'env_time': env_time,
                'config_time': config_time,
                'import_time': import_time
            }
        )
        
        self.assertTrue(result.passed, f"System startup too slow: {total_startup_time:.3f}s")
    
    def test_file_operations_performance(self):
        """Benchmark file operation performance."""
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        try:
            # Test file write performance
            test_data = b'x' * (1024 * 1024)  # 1MB of data
            test_file = Path(temp_dir) / 'benchmark_test.bin'
            
            write_start = time.time()
            with open(test_file, 'wb') as f:
                f.write(test_data)
            write_time = time.time() - write_start
            
            # Test file read performance
            read_start = time.time()
            with open(test_file, 'rb') as f:
                read_data = f.read()
            read_time = time.time() - read_start
            
            # Verify data integrity
            self.assertEqual(len(read_data), len(test_data))
            
            # Record benchmarks
            write_result = self._record_benchmark(
                'file_write_1mb',
                'file_operations',
                write_time,
                'seconds',
                self.thresholds['file_operations']['file_write'],
                {'data_size_mb': 1}
            )
            
            read_result = self._record_benchmark(
                'file_read_1mb',
                'file_operations',
                read_time,
                'seconds',
                self.thresholds['file_operations']['file_read'],
                {'data_size_mb': 1}
            )
            
            self.assertTrue(write_result.passed, f"File write too slow: {write_time:.3f}s")
            self.assertTrue(read_result.passed, f"File read too slow: {read_time:.3f}s")
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_directory_scanning_performance(self):
        """Benchmark directory scanning performance."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create many test files
            num_files = 100  # Reduced from 1000 for faster testing
            for i in range(num_files):
                test_file = Path(temp_dir) / f'test_file_{i:04d}.txt'
                test_file.write_text(f'Test file {i}')
            
            # Benchmark directory scanning
            scan_start = time.time()
            files_found = list(Path(temp_dir).glob('*.txt'))
            scan_time = time.time() - scan_start
            
            # Verify all files found
            self.assertEqual(len(files_found), num_files)
            
            # Record benchmark (scale to 1000 files equivalent)
            scaled_time = scan_time * (1000 / num_files)
            result = self._record_benchmark(
                'directory_scan_1000',
                'file_operations',
                scaled_time,
                'seconds',
                self.thresholds['file_operations']['directory_scan'],
                {
                    'actual_files': num_files,
                    'actual_time': scan_time,
                    'scaled_time': scaled_time
                }
            )
            
            self.assertTrue(result.passed, f"Directory scan too slow: {scaled_time:.3f}s (scaled)")
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_memory_performance_benchmarks(self):
        """Benchmark memory usage and efficiency."""
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Get initial memory
        gc.collect()  # Force garbage collection
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive operations
        large_data = []
        for i in range(10):
            # Create some data structures
            data_chunk = [j * 0.1 for j in range(10000)]  # 10k floats
            large_data.append(data_chunk)
            
            # Import some modules
            self.importer.safe_import(f'test_module_{i}')
        
        # Get peak memory
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = peak_memory - initial_memory
        
        # Clean up and measure final memory
        large_data.clear()
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Calculate memory efficiency (how much was cleaned up)
        cleaned_memory = peak_memory - final_memory
        efficiency = cleaned_memory / memory_growth if memory_growth > 0 else 1.0
        
        # Record benchmarks
        growth_result = self._record_benchmark(
            'memory_growth',
            'memory_performance',
            memory_growth,
            'MB',
            self.thresholds['memory_performance']['memory_growth'],
            {
                'initial_mb': initial_memory,
                'peak_mb': peak_memory,
                'final_mb': final_memory
            }
        )
        
        efficiency_result = self._record_benchmark(
            'memory_efficiency',
            'memory_performance',
            efficiency,
            'ratio',
            self.thresholds['memory_performance']['memory_efficiency'],
            {
                'cleaned_mb': cleaned_memory,
                'growth_mb': memory_growth
            }
        )
        
        self.assertTrue(growth_result.passed, f"Memory growth too high: {memory_growth:.2f}MB")
        self.assertGreaterEqual(efficiency, 0.5, f"Memory efficiency too low: {efficiency:.2f}")
    
    def test_concurrency_performance(self):
        """Benchmark concurrent operation performance."""
        import threading
        import concurrent.futures
        
        # Test thread creation and execution
        results = []
        errors = []
        
        def worker_task(worker_id):
            """Simple worker task."""
            try:
                # Simulate some work
                start_time = time.time()
                
                # Import operation (thread-safe)
                module = self.importer.safe_import(f'worker_module_{worker_id}')
                
                # Some computation
                result = sum(i * 0.1 for i in range(1000))
                
                work_time = time.time() - start_time
                return {
                    'worker_id': worker_id,
                    'work_time': work_time,
                    'result': result,
                    'module_imported': module is not None
                }
            except Exception as e:
                errors.append(f"Worker {worker_id}: {str(e)}")
                return None
        
        # Benchmark thread performance
        thread_start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        thread_time = time.time() - thread_start
        
        # Filter out None results (errors)
        valid_results = [r for r in results if r is not None]
        
        # Record benchmark
        result = self._record_benchmark(
            'thread_performance_10',
            'concurrency',
            thread_time,
            'seconds',
            self.thresholds['concurrency']['thread_performance'],
            {
                'workers': 10,
                'successful': len(valid_results),
                'errors': len(errors),
                'avg_work_time': statistics.mean([r['work_time'] for r in valid_results]) if valid_results else 0
            }
        )
        
        self.assertTrue(result.passed, f"Thread performance too slow: {thread_time:.3f}s")
        self.assertGreaterEqual(len(valid_results), 8, "Too many thread failures")
        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
    
    def test_lock_contention_performance(self):
        """Benchmark performance under lock contention."""
        import threading
        
        shared_resource = {'counter': 0}
        lock = threading.Lock()
        contention_times = []
        
        def contending_worker(worker_id, iterations=100):
            """Worker that competes for shared resource."""
            for i in range(iterations):
                wait_start = time.time()
                
                with lock:
                    wait_time = time.time() - wait_start
                    contention_times.append(wait_time)
                    
                    # Simulate some work with the shared resource
                    shared_resource['counter'] += 1
                    time.sleep(0.001)  # 1ms of "work"
        
        # Start multiple competing threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=contending_worker, args=(i, 20))
            threads.append(thread)
        
        start_time = time.time()
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Analyze contention
        max_wait = max(contention_times) if contention_times else 0
        avg_wait = statistics.mean(contention_times) if contention_times else 0
        
        # Record benchmarks
        contention_result = self._record_benchmark(
            'lock_contention_max',
            'concurrency',
            max_wait,
            'seconds',
            self.thresholds['concurrency']['lock_contention'],
            {
                'total_time': total_time,
                'avg_wait': avg_wait,
                'max_wait': max_wait,
                'threads': 5,
                'operations': len(contention_times)
            }
        )
        
        self.assertTrue(contention_result.passed, f"Lock contention too high: {max_wait:.3f}s")
        self.assertEqual(shared_resource['counter'], 100, "Shared resource corrupted")
    
    def test_performance_regression_detection(self):
        """Detect performance regressions against baselines."""
        regressions = []
        improvements = []
        
        for result in self.benchmark_results:
            if result.baseline is not None:
                regression_threshold = result.baseline * 1.3  # 30% slower = regression
                improvement_threshold = result.baseline * 0.8  # 20% faster = improvement
                
                if result.value > regression_threshold:
                    regressions.append({
                        'name': result.name,
                        'baseline': result.baseline,
                        'current': result.value,
                        'regression_factor': result.value / result.baseline
                    })
                elif result.value < improvement_threshold:
                    improvements.append({
                        'name': result.name,
                        'baseline': result.baseline,
                        'current': result.value,
                        'improvement_factor': result.baseline / result.value
                    })
        
        # Record regression analysis
        self._record_benchmark(
            'regression_analysis',
            'meta',
            len(regressions),
            'count',
            0,  # Should be 0 regressions
            {
                'regressions': regressions,
                'improvements': improvements,
                'total_benchmarks': len(self.benchmark_results)
            }
        )
        
        # Report findings
        if regressions:
            regression_report = "\n".join([
                f"  - {r['name']}: {r['current']:.3f}s vs {r['baseline']:.3f}s "
                f"({r['regression_factor']:.2f}x slower)"
                for r in regressions
            ])
            print(f"Performance regressions detected:\n{regression_report}")
        
        if improvements:
            improvement_report = "\n".join([
                f"  - {i['name']}: {i['current']:.3f}s vs {i['baseline']:.3f}s "
                f"({i['improvement_factor']:.2f}x faster)"
                for i in improvements
            ])
            print(f"Performance improvements detected:\n{improvement_report}")
        
        # Fail test if critical regressions found
        critical_regressions = [r for r in regressions if r['regression_factor'] > 2.0]
        self.assertEqual(len(critical_regressions), 0, 
                        f"Critical performance regressions: {critical_regressions}")
    
    def test_generate_performance_report(self):
        """Generate comprehensive performance report."""
        # Group results by category
        categories = {}
        for result in self.benchmark_results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
        
        # Generate summary statistics
        report = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'total_benchmarks': len(self.benchmark_results),
            'passed': len([r for r in self.benchmark_results if r.passed]),
            'failed': len([r for r in self.benchmark_results if not r.passed]),
            'categories': {}
        }
        
        for category, results in categories.items():
            values = [r.value for r in results]
            report['categories'][category] = {
                'count': len(results),
                'passed': len([r for r in results if r.passed]),
                'min_value': min(values) if values else 0,
                'max_value': max(values) if values else 0,
                'avg_value': statistics.mean(values) if values else 0,
                'median_value': statistics.median(values) if values else 0
            }
        
        # Save detailed report
        report_file = Path(self.config.get_data_path()) / f"performance_report_{int(time.time())}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Performance report saved to: {report_file}")
        except Exception as e:
            print(f"Warning: Could not save performance report: {e}")
        
        # Verify report quality
        self.assertGreater(report['total_benchmarks'], 10, "Not enough benchmarks")
        self.assertGreater(report['passed'] / report['total_benchmarks'], 0.8, 
                          "Too many benchmark failures")
        
        return report


if __name__ == '__main__':
    import unittest
    unittest.main()