"""Comprehensive health check system for VoxPersona components.

This module provides health checks for all critical system components
including database, MinIO storage, APIs, and file system.
"""

import os
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

from ..import_utils import SafeImporter
from ..config import VoxPersonaConfig
from ..error_recovery import ErrorRecoveryManager


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: float
    response_time: float


class BaseHealthCheck:
    """Base class for all health checks."""
    
    def __init__(self, name: str, timeout: float = 30.0):
        """Initialize health check.
        
        Args:
            name: Name of the component being checked
            timeout: Maximum time to wait for check completion
        """
        self.name = name
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.importer = SafeImporter()
        self.recovery_manager = ErrorRecoveryManager()
    
    def check(self) -> HealthCheckResult:
        """Perform health check with timeout and error handling."""
        start_time = time.time()
        
        try:
            # Run check with timeout
            result = self._run_check_with_timeout()
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                component=self.name,
                status=result.get('status', HealthStatus.UNKNOWN),
                message=result.get('message', 'Check completed'),
                details=result.get('details', {}),
                timestamp=start_time,
                response_time=response_time
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # Attempt recovery
            if self.recovery_manager.handle_error(e, context={'component': self.name}):
                status = HealthStatus.WARNING
                message = f"Check failed but recovered: {str(e)}"
            else:
                status = HealthStatus.CRITICAL
                message = f"Check failed: {str(e)}"
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details={'error': str(e), 'error_type': type(e).__name__},
                timestamp=start_time,
                response_time=response_time
            )
    
    def _run_check_with_timeout(self) -> Dict[str, Any]:
        """Run the actual health check with timeout."""
        result = {'status': HealthStatus.UNKNOWN}
        
        def check_thread():
            nonlocal result
            try:
                result = self._perform_check()
            except Exception as e:
                result = {
                    'status': HealthStatus.CRITICAL,
                    'message': f"Check thread failed: {str(e)}",
                    'details': {'error': str(e)}
                }
        
        thread = threading.Thread(target=check_thread)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)
        
        if thread.is_alive():
            result = {
                'status': HealthStatus.CRITICAL,
                'message': f"Health check timed out after {self.timeout}s",
                'details': {'timeout': self.timeout}
            }
        
        return result
    
    def _perform_check(self) -> Dict[str, Any]:
        """Override this method to implement specific health check logic."""
        raise NotImplementedError("Subclasses must implement _perform_check")


class DatabaseHealthCheck(BaseHealthCheck):
    """Health check for database connectivity and operations."""
    
    def __init__(self, config: Optional[VoxPersonaConfig] = None):
        super().__init__("database", timeout=15.0)
        self.config = config or VoxPersonaConfig()
    
    def _perform_check(self) -> Dict[str, Any]:
        """Check database connectivity and basic operations."""
        # Import database modules
        sqlite3 = self.importer.safe_import('sqlite3')
        
        if not hasattr(sqlite3, 'connect'):
            return {
                'status': HealthStatus.CRITICAL,
                'message': 'Database module not available',
                'details': {'sqlite3_available': False}
            }
        
        # Get database path
        db_path = self.config.get_database_path()
        
        try:
            # Test connection
            with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    # Check database schema
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    
                    return {
                        'status': HealthStatus.HEALTHY,
                        'message': 'Database is accessible and responsive',
                        'details': {
                            'database_path': str(db_path),
                            'table_count': len(tables),
                            'tables': [table[0] for table in tables]
                        }
                    }
                else:
                    return {
                        'status': HealthStatus.CRITICAL,
                        'message': 'Database query returned unexpected result',
                        'details': {'query_result': result}
                    }
                    
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'message': f'Database connection failed: {str(e)}',
                'details': {
                    'database_path': str(db_path),
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            }


class MinIOHealthCheck(BaseHealthCheck):
    """Health check for MinIO storage service."""
    
    def __init__(self, config: Optional[VoxPersonaConfig] = None):
        super().__init__("minio", timeout=20.0)
        self.config = config or VoxPersonaConfig()
    
    def _perform_check(self) -> Dict[str, Any]:
        """Check MinIO connectivity and basic operations."""
        # Import MinIO module
        minio = self.importer.safe_import('minio')
        
        if not hasattr(minio, 'Minio'):
            return {
                'status': HealthStatus.WARNING,
                'message': 'MinIO module not available, using fallback storage',
                'details': {'minio_available': False, 'fallback_enabled': True}
            }
        
        # Get MinIO configuration
        storage_config = self.config.get_storage_config()
        
        try:
            # Create MinIO client
            client = minio.Minio(
                endpoint=storage_config.get('endpoint', 'localhost:9000'),
                access_key=storage_config.get('access_key', 'minioadmin'),
                secret_key=storage_config.get('secret_key', 'minioadmin'),
                secure=storage_config.get('secure', False)
            )
            
            # Test connection by listing buckets
            buckets = list(client.list_buckets())
            
            # Test bucket operations
            test_bucket = storage_config.get('bucket', 'voxpersona-test')
            bucket_exists = client.bucket_exists(test_bucket)
            
            return {
                'status': HealthStatus.HEALTHY,
                'message': 'MinIO is accessible and responsive',
                'details': {
                    'endpoint': storage_config.get('endpoint'),
                    'bucket_count': len(buckets),
                    'test_bucket_exists': bucket_exists,
                    'secure_connection': storage_config.get('secure', False)
                }
            }
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if 'connection' in error_msg or 'timeout' in error_msg:
                status = HealthStatus.CRITICAL
                message = f'MinIO connection failed: {str(e)}'
            elif 'auth' in error_msg or 'access denied' in error_msg:
                status = HealthStatus.CRITICAL
                message = f'MinIO authentication failed: {str(e)}'
            else:
                status = HealthStatus.WARNING
                message = f'MinIO check failed, fallback available: {str(e)}'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'endpoint': storage_config.get('endpoint'),
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'fallback_available': True
                }
            }


class FileSystemHealthCheck(BaseHealthCheck):
    """Health check for file system access and permissions."""
    
    def __init__(self, config: Optional[VoxPersonaConfig] = None):
        super().__init__("filesystem", timeout=10.0)
        self.config = config or VoxPersonaConfig()
    
    def _perform_check(self) -> Dict[str, Any]:
        """Check file system access and permissions."""
        from ..path_manager import PathManager
        
        path_manager = PathManager()
        checks = {}
        issues = []
        
        # Check critical directories
        critical_paths = [
            ('data', path_manager.get_data_path()),
            ('logs', path_manager.get_logs_path()),
            ('temp', path_manager.get_temp_path()),
            ('config', path_manager.get_config_path().parent)
        ]
        
        for path_name, path in critical_paths:
            try:
                # Check if path exists and is accessible
                path_exists = path.exists()
                
                if path_exists:
                    # Check read/write permissions
                    can_read = os.access(str(path), os.R_OK)
                    can_write = os.access(str(path), os.W_OK)
                    
                    if path.is_dir():
                        # Test directory operations
                        test_file = path / f'.health_check_{int(time.time())}'
                        try:
                            test_file.write_text('health check')
                            test_file.unlink()
                            can_create_files = True
                        except Exception:
                            can_create_files = False
                    else:
                        can_create_files = can_write
                    
                    checks[path_name] = {
                        'exists': path_exists,
                        'readable': can_read,
                        'writable': can_write,
                        'can_create_files': can_create_files,
                        'path': str(path)
                    }
                    
                    if not (can_read and can_write and can_create_files):
                        issues.append(f"{path_name} has insufficient permissions")
                        
                else:
                    # Try to create the directory
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        checks[path_name] = {
                            'exists': True,
                            'readable': True,
                            'writable': True,
                            'can_create_files': True,
                            'path': str(path),
                            'created': True
                        }
                    except Exception as e:
                        checks[path_name] = {
                            'exists': False,
                            'readable': False,
                            'writable': False,
                            'can_create_files': False,
                            'path': str(path),
                            'error': str(e)
                        }
                        issues.append(f"Cannot create {path_name} directory: {str(e)}")
                        
            except Exception as e:
                checks[path_name] = {
                    'error': str(e),
                    'path': str(path)
                }
                issues.append(f"Error checking {path_name}: {str(e)}")
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(str(path_manager.get_data_path()))
            
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            used_percent = (used / total) * 100
            
            checks['disk_space'] = {
                'total_gb': round(total_gb, 2),
                'free_gb': round(free_gb, 2),
                'used_percent': round(used_percent, 2)
            }
            
            if free_gb < 1.0:  # Less than 1GB free
                issues.append(f"Low disk space: only {free_gb:.2f}GB free")
            elif used_percent > 90:
                issues.append(f"Disk usage high: {used_percent:.1f}% used")
                
        except Exception as e:
            checks['disk_space'] = {'error': str(e)}
            issues.append(f"Cannot check disk space: {str(e)}")
        
        # Determine overall status
        if not issues:
            status = HealthStatus.HEALTHY
            message = "File system is accessible with proper permissions"
        elif len(issues) == 1 and 'disk space' in issues[0].lower():
            status = HealthStatus.WARNING
            message = f"File system accessible but: {issues[0]}"
        else:
            status = HealthStatus.CRITICAL
            message = f"File system issues: {'; '.join(issues)}"
        
        return {
            'status': status,
            'message': message,
            'details': {
                'checks': checks,
                'issues': issues,
                'total_issues': len(issues)
            }
        }


class APIHealthCheck(BaseHealthCheck):
    """Health check for external API dependencies."""
    
    def __init__(self, config: Optional[VoxPersonaConfig] = None):
        super().__init__("apis", timeout=25.0)
        self.config = config or VoxPersonaConfig()
    
    def _perform_check(self) -> Dict[str, Any]:
        """Check external API connectivity and response."""
        # Import requests module
        requests = self.importer.safe_import('requests')
        
        if not hasattr(requests, 'get'):
            return {
                'status': HealthStatus.WARNING,
                'message': 'HTTP client not available, API checks skipped',
                'details': {'requests_available': False}
            }
        
        api_checks = {}
        issues = []
        
        # Get API endpoints from config
        api_config = self.config.get_api_config()
        
        # Default health check endpoints
        default_endpoints = [
            ('system_health', 'http://localhost:8000/health'),
            ('api_status', 'http://localhost:8000/api/v1/status')
        ]
        
        # Combine configured and default endpoints
        endpoints = []
        if api_config and 'endpoints' in api_config:
            endpoints.extend(api_config['endpoints'].items())
        endpoints.extend(default_endpoints)
        
        for name, url in endpoints:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=5.0)
                response_time = time.time() - start_time
                
                api_checks[name] = {
                    'url': url,
                    'status_code': response.status_code,
                    'response_time': round(response_time, 3),
                    'accessible': True
                }
                
                if response.status_code != 200:
                    issues.append(f"{name} returned status {response.status_code}")
                elif response_time > 2.0:
                    issues.append(f"{name} slow response: {response_time:.1f}s")
                    
            except Exception as e:
                api_checks[name] = {
                    'url': url,
                    'error': str(e),
                    'accessible': False
                }
                
                # Don't treat connection errors as critical if they're optional
                if 'localhost' in url:
                    issues.append(f"{name} unavailable (optional): {str(e)}")
                else:
                    issues.append(f"{name} failed: {str(e)}")
        
        # Determine status
        critical_issues = [issue for issue in issues if 'optional' not in issue]
        
        if not issues:
            status = HealthStatus.HEALTHY
            message = "All API endpoints are accessible"
        elif not critical_issues:
            status = HealthStatus.WARNING
            message = f"Optional APIs unavailable: {len(issues)} issues"
        else:
            status = HealthStatus.CRITICAL
            message = f"API connectivity issues: {len(critical_issues)} critical"
        
        return {
            'status': status,
            'message': message,
            'details': {
                'endpoints': api_checks,
                'issues': issues,
                'total_endpoints': len(endpoints),
                'accessible_endpoints': len([c for c in api_checks.values() if c.get('accessible', False)])
            }
        }


class HealthCheckManager:
    """Manager for coordinating all health checks."""
    
    def __init__(self, config: Optional[VoxPersonaConfig] = None):
        """Initialize health check manager.
        
        Args:
            config: VoxPersona configuration instance
        """
        self.config = config or VoxPersonaConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize health checks
        self.health_checks = {
            'database': DatabaseHealthCheck(self.config),
            'minio': MinIOHealthCheck(self.config),
            'filesystem': FileSystemHealthCheck(self.config),
            'apis': APIHealthCheck(self.config)
        }
        
        self._last_results = {}
        self._check_lock = threading.Lock()
    
    def run_all_checks(self, parallel: bool = True) -> Dict[str, HealthCheckResult]:
        """Run all health checks.
        
        Args:
            parallel: Whether to run checks in parallel
            
        Returns:
            Dictionary mapping component names to health check results
        """
        with self._check_lock:
            if parallel:
                return self._run_checks_parallel()
            else:
                return self._run_checks_sequential()
    
    def _run_checks_parallel(self) -> Dict[str, HealthCheckResult]:
        """Run health checks in parallel."""
        import concurrent.futures
        
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all checks
            future_to_name = {
                executor.submit(check.check): name 
                for name, check in self.health_checks.items()
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    results[name] = result
                    self._last_results[name] = result
                except Exception as e:
                    self.logger.error(f"Health check {name} failed: {e}")
                    results[name] = HealthCheckResult(
                        component=name,
                        status=HealthStatus.CRITICAL,
                        message=f"Check execution failed: {str(e)}",
                        details={'error': str(e)},
                        timestamp=time.time(),
                        response_time=0.0
                    )
        
        return results
    
    def _run_checks_sequential(self) -> Dict[str, HealthCheckResult]:
        """Run health checks sequentially."""
        results = {}
        
        for name, check in self.health_checks.items():
            try:
                result = check.check()
                results[name] = result
                self._last_results[name] = result
            except Exception as e:
                self.logger.error(f"Health check {name} failed: {e}")
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.CRITICAL,
                    message=f"Check execution failed: {str(e)}",
                    details={'error': str(e)},
                    timestamp=time.time(),
                    response_time=0.0
                )
        
        return results
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary.
        
        Returns:
            Dictionary with system health overview
        """
        results = self.run_all_checks()
        
        status_counts = {status.value: 0 for status in HealthStatus}
        total_response_time = 0
        components_with_issues = []
        
        for name, result in results.items():
            status_counts[result.status.value] += 1
            total_response_time += result.response_time
            
            if result.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                components_with_issues.append({
                    'component': name,
                    'status': result.status.value,
                    'message': result.message
                })
        
        # Determine overall system status
        if status_counts['critical'] > 0:
            overall_status = HealthStatus.CRITICAL
            overall_message = f"{status_counts['critical']} critical component(s)"
        elif status_counts['warning'] > 0:
            overall_status = HealthStatus.WARNING
            overall_message = f"{status_counts['warning']} component(s) with warnings"
        elif status_counts['unknown'] > 0:
            overall_status = HealthStatus.WARNING
            overall_message = f"{status_counts['unknown']} component(s) status unknown"
        else:
            overall_status = HealthStatus.HEALTHY
            overall_message = "All components healthy"
        
        return {
            'overall_status': overall_status.value,
            'overall_message': overall_message,
            'total_components': len(results),
            'status_breakdown': status_counts,
            'total_response_time': round(total_response_time, 3),
            'average_response_time': round(total_response_time / len(results), 3) if results else 0,
            'components_with_issues': components_with_issues,
            'timestamp': time.time()
        }
    
    def get_component_health(self, component_name: str) -> Optional[HealthCheckResult]:
        """Get health status for specific component.
        
        Args:
            component_name: Name of component to check
            
        Returns:
            Health check result or None if component not found
        """
        if component_name in self.health_checks:
            return self.health_checks[component_name].check()
        return None
    
    def get_last_results(self) -> Dict[str, HealthCheckResult]:
        """Get last health check results without running new checks.
        
        Returns:
            Dictionary of last health check results
        """
        return self._last_results.copy()


# Convenience function for quick health check
def quick_health_check(config: Optional[VoxPersonaConfig] = None) -> Dict[str, Any]:
    """Perform a quick health check of all system components.
    
    Args:
        config: Optional VoxPersona configuration
        
    Returns:
        System health summary
    """
    manager = HealthCheckManager(config)
    return manager.get_system_health_summary()


if __name__ == '__main__':
    # Example usage
    print("Running VoxPersona health checks...")
    summary = quick_health_check()
    
    print(f"\nOverall Status: {summary['overall_status'].upper()}")
    print(f"Message: {summary['overall_message']}")
    print(f"Total Components: {summary['total_components']}")
    print(f"Response Time: {summary['total_response_time']}s")
    
    if summary['components_with_issues']:
        print("\nIssues Found:")
        for issue in summary['components_with_issues']:
            print(f"  - {issue['component']}: {issue['status']} - {issue['message']}")