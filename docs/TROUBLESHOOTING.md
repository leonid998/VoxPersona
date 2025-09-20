# VoxPersona Troubleshooting Guide

This guide helps diagnose and resolve common issues in the VoxPersona system with the enhanced reliability infrastructure.

## Quick Diagnostics

### System Health Check
```bash
# Check overall system status
python -c "from src.monitoring import get_monitoring_system; print(get_monitoring_system().get_status())"

# Check environment detection
python -c "from src.environment import get_environment_summary; print(get_environment_summary())"

# Check import diagnostics
python -c "from src.import_utils import get_import_diagnostics; print(get_import_diagnostics())"
```

## Common Issues and Solutions

### Import and Module Issues

#### Issue: Import Errors on Startup
**Symptoms:**
- ModuleNotFoundError or ImportError during startup
- Application fails to start completely

**Diagnosis:**
```bash
python scripts/validate_imports.py --all-src
```

**Solutions:**
1. **Use Enhanced Import System:**
   ```python
   # Instead of:
   import config
   
   # Use:
   from import_utils import safe_import
   config = safe_import('config')
   ```

2. **Check Python Path:**
   ```bash
   python -c "import sys; print('\n'.join(sys.path))"
   ```

3. **Verify Virtual Environment:**
   ```bash
   pip list | grep -E "(pyrogram|minio|tiktoken)"
   ```

#### Issue: Relative Import Failures
**Symptoms:**
- "attempted relative import with no known parent package"
- Works in some contexts but fails in others

**Solutions:**
1. **Update to SafeImporter:**
   ```python
   # Add fallback handling
   try:
       from .relative_module import function
   except ImportError:
       from import_utils import safe_import
       module = safe_import('relative_module')
       function = getattr(module, 'function')
   ```

2. **Use Package Context Detection:**
   ```python
   from import_utils import ImportContext
   if ImportContext.is_package_context():
       from .module import item
   else:
       from src.module import item
   ```

### Configuration Issues

#### Issue: Configuration Loading Failures
**Symptoms:**
- Missing environment variables
- Hardcoded paths not working across environments

**Diagnosis:**
```bash
python scripts/validate_config.py --all
```

**Solutions:**
1. **Use Dynamic Configuration:**
   ```python
   # Instead of hardcoded paths:
   STORAGE_DIR = "/root/app/storage"
   
   # Use dynamic paths:
   from path_manager import get_path, PathType
   STORAGE_DIR = get_path(PathType.AUDIO_STORAGE)
   ```

2. **Environment-Aware Config:**
   ```python
   from environment import is_test, is_docker, is_ci
   
   if is_test():
       DB_NAME = "test_database"
   elif is_docker():
       DB_HOST = "postgres"  # Docker service name
   else:
       DB_HOST = "localhost"
   ```

### Path and Permission Issues

#### Issue: Permission Denied Errors
**Symptoms:**
- Cannot create directories
- Cannot write files
- Different behavior in CI/Docker vs local

**Solutions:**
1. **Use Path Manager:**
   ```python
   from path_manager import get_path, PathType
   
   # Automatically handles permissions and fallbacks
   audio_dir = get_path(PathType.AUDIO_STORAGE)
   ```

2. **Check Write Permissions:**
   ```python
   from path_manager import has_write_permissions
   if not has_write_permissions():
       # Handle read-only environment
       pass
   ```

#### Issue: Path Resolution Failures
**Symptoms:**
- Files not found in different environments
- Hardcoded paths breaking

**Solutions:**
1. **Environment-Aware Paths:**
   ```python
   from path_manager import get_path, PathType
   from environment import get_environment
   
   env = get_environment()
   if env.env_type.value == "ci_cd":
       # Use temporary paths in CI
       pass
   ```

### Error Recovery Issues

#### Issue: Cascading Failures
**Symptoms:**
- Single error causes complete system shutdown
- No graceful degradation

**Solutions:**
1. **Add Error Recovery:**
   ```python
   from error_recovery import with_recovery, recover_from_error
   
   @with_recovery({'operation': 'file_processing'})
   def process_file(file_path):
       # Your code here
       pass
   ```

2. **Use Recovery Context:**
   ```python
   from error_recovery import recovery_context
   
   with recovery_context({'operation': 'api_call'}):
       result = api_call()
   ```

### Performance Issues

#### Issue: Slow Application Startup
**Diagnosis:**
- Check system metrics during startup
- Monitor resource usage

**Solutions:**
1. **Optimize RAG Loading:**
   ```python
   # Load RAGs asynchronously
   asyncio.create_task(load_rags())
   ```

2. **Use Monitoring:**
   ```python
   from monitoring import get_monitoring_system
   monitoring = get_monitoring_system()
   monitoring.start()
   ```

### Testing Issues

#### Issue: Tests Failing in CI
**Symptoms:**
- Tests pass locally but fail in CI
- Environment-specific failures

**Solutions:**
1. **Use Test Framework:**
   ```python
   from tests.framework import VoxPersonaTestCase, EnvironmentSimulator
   
   class MyTest(VoxPersonaTestCase):
       def test_feature(self):
           with EnvironmentSimulator().simulate_environment('ci'):
               # Test in CI environment
               pass
   ```

2. **Run Validation Scripts:**
   ```bash
   python scripts/check_environment_compatibility.py --all-src
   ```

## Environment-Specific Issues

### Docker Environment

#### Issue: Volume Mounting Problems
**Solutions:**
```yaml
# docker-compose.yml
volumes:
  - ./rag_indices:/app/rag_indices
  - ./audio_files:/app/audio_files
```

#### Issue: Service Communication
**Solutions:**
```python
# Use service names in Docker
DB_HOST = "postgres"  # Not localhost
MINIO_ENDPOINT = "minio:9000"
```

### CI/CD Environment

#### Issue: Limited Resources
**Solutions:**
1. **Use Temporary Storage:**
   ```python
   from environment import is_ci
   if is_ci():
       # Use in-memory or temporary storage
       pass
   ```

2. **Skip Resource-Intensive Tests:**
   ```python
   @unittest.skipIf(is_ci(), "Skip in CI")
   def test_large_file_processing(self):
       pass
   ```

### Production Environment

#### Issue: Resource Exhaustion
**Solutions:**
1. **Monitor Resources:**
   ```python
   from monitoring import get_monitoring_system
   monitoring = get_monitoring_system()
   
   # Set up alerts
   monitoring.alert_manager.add_alert_rule(
       'system.memory.usage', 90.0, AlertLevel.WARNING, 
       'High memory usage'
   )
   ```

## Advanced Diagnostics

### System Health Dashboard
```python
from monitoring import get_monitoring_system
from environment import get_environment_summary
from import_utils import get_import_diagnostics

def system_health_report():
    monitoring = get_monitoring_system()
    
    return {
        'environment': get_environment_summary(),
        'imports': get_import_diagnostics(),
        'monitoring': monitoring.get_status(),
        'timestamp': datetime.now().isoformat()
    }
```

### Error Recovery Statistics
```python
from error_recovery import get_recovery_manager

def recovery_stats():
    manager = get_recovery_manager()
    return manager.get_recovery_stats()
```

### Performance Baseline
```python
from tests.framework import PerformanceTestCase

class SystemPerformanceTest(PerformanceTestCase):
    def test_startup_time(self):
        self.start_performance_monitoring()
        # Startup code
        metrics = self.stop_performance_monitoring()
        self.assert_execution_time_under(30.0)  # 30 seconds
```

## Getting Help

1. **Check Logs:** All components use structured logging
2. **Run Diagnostics:** Use the validation scripts in `scripts/`
3. **Monitor System:** Enable the monitoring system for real-time insights
4. **Review Environment:** Ensure proper environment detection

For additional support, check the system logs and monitoring data for detailed error information.