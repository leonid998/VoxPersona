# MinIO Integration Enhancement for VoxPersona

## Overview

This document describes the enhanced MinIO integration implemented for VoxPersona, providing comprehensive object storage capabilities for audio file management.

## Features

### 🔧 Enhanced Infrastructure
- **Docker Integration**: Complete MinIO service in docker-compose.yml
- **Health Monitoring**: Automated health checks and service monitoring  
- **Retry Mechanisms**: Robust error recovery with exponential backoff
- **Security**: SSL support and proper access control

### 📁 Complete CRUD Operations
- **Upload**: Audio file upload with metadata and progress tracking
- **Download**: File retrieval with streaming support
- **Delete**: Single file and bulk deletion capabilities
- **List**: User-based file listing and search functionality

### 📊 Monitoring & Analytics
- **Performance Metrics**: Operation success rates and response times
- **Storage Analytics**: Usage monitoring and capacity planning
- **Health Reports**: Comprehensive service status reporting

## Architecture

### Core Components

1. **MinIOManager**: Main interface for all MinIO operations
2. **MinIOHealthMonitor**: Service health and performance monitoring
3. **RetryableMinIOOperation**: Handles operation retries with backoff
4. **ObjectInfo**: Structured file metadata representation

### Enhanced Workflow

```
Telegram Bot → Audio Handler → MinIOManager → MinIO Cluster
                    ↓              ↓
              Health Monitor ← Performance Metrics
```

## Installation & Setup

### 1. Update Docker Configuration

The enhanced docker-compose.yml includes a complete MinIO service:

```yaml
minio:
  image: minio/minio:RELEASE.2025-01-23T22-51-28Z
  container_name: voxpersona_minio
  restart: unless-stopped
  environment:
    MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
    MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
  ports:
    - "9000:9000"  # S3 API
    - "9001:9001"  # Web Console
  volumes:
    - minio_data:/data
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
    interval: 30s
    timeout: 20s
    retries: 3
```

### 2. Environment Variables

Configure the following environment variables:

```bash
# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=voxpersona_admin_2025
MINIO_SECRET_KEY=SecureVoxPersona2025!@#
MINIO_BUCKET_NAME=voxpersona-storage
MINIO_AUDIO_BUCKET_NAME=voxpersona-audio
MINIO_USE_SSL=false

# Health Check Configuration
MINIO_HEALTH_CHECK_INTERVAL=60
MINIO_MAX_RETRIES=3
MINIO_RETRY_BACKOFF=2.0

# Storage Configuration
MINIO_MAX_FILE_SIZE=2147483648  # 2GB
MINIO_CLEANUP_DAYS=30
```

### 3. Start Services

```bash
# Start all services including MinIO
docker-compose up -d

# Check MinIO service status
docker-compose logs minio

# Verify MinIO is accessible
curl http://localhost:9000/minio/health/ready
```

## Usage Examples

### Basic Operations

```python
from src.minio_manager import get_minio_manager

# Get MinIO manager instance
manager = get_minio_manager()

# Upload audio file with metadata
success = manager.upload_audio_file(
    file_path='/path/to/audio.wav',
    object_name='user_123/interview_20250120.wav',
    metadata={
        'user_id': '123',
        'session_type': 'interview',
        'upload_date': '2025-01-20'
    }
)

# Download file for processing
local_path = manager.download_audio_file(
    object_name='user_123/interview_20250120.wav',
    local_path='/tmp/downloaded_audio.wav'
)

# Get file as stream (no local storage)
stream = manager.get_audio_stream('user_123/interview_20250120.wav')
audio_data = stream.read()

# List user's files
files = manager.list_user_audio_files(user_id=123)
for file_info in files:
    print(f"File: {file_info.object_name}, Size: {file_info.size}")

# Delete file
success = manager.delete_audio_file('user_123/old_audio.wav')
```

### Advanced Operations

```python
# Search files by metadata
interview_files = manager.search_files_by_metadata({
    'session_type': 'interview',
    'user_id': '123'
})

# Clean up old files (older than 30 days)
deleted_count = manager.cleanup_old_files(days_old=30)
print(f"Cleaned up {deleted_count} old files")

# Get storage usage statistics
usage = manager.get_storage_usage()
print(f"Total storage: {usage['total_size_mb']} MB")
print(f"File count: {usage['file_count']}")

# Get comprehensive health status
status = manager.get_health_status()
print(f"Connection status: {status['connection_status']}")
print(f"Success rate: {status['health_report']['success_rate']}%")
```

### Progress Tracking

```python
def upload_progress_callback(progress):
    print(f"Upload progress: {progress.percentage:.1f}% "
          f"({progress.bytes_uploaded}/{progress.total_bytes} bytes)")

# Upload with progress tracking
success = manager.upload_audio_file(
    file_path='/path/to/large_audio.wav',
    object_name='user_123/large_interview.wav',
    progress_callback=upload_progress_callback
)
```

## Error Handling

The enhanced integration provides comprehensive error handling:

```python
from src.minio_manager import (
    MinIOError, 
    MinIOConnectionError, 
    MinIOUploadError,
    MinIODownloadError
)

try:
    success = manager.upload_audio_file(file_path, object_name)
except MinIOConnectionError as e:
    print(f"Connection failed: {e}")
    # Handle connection issues
except MinIOUploadError as e:
    print(f"Upload failed: {e}")
    # Handle upload-specific issues
except MinIOError as e:
    print(f"General MinIO error: {e}")
    # Handle other MinIO issues
```

## Monitoring & Health Checks

### Health Status Monitoring

```python
# Get detailed health report
health_report = manager.get_health_status()

# Check if service is healthy
if health_report['connection_status'] == 'healthy':
    print("MinIO service is operational")
else:
    print("MinIO service needs attention")

# Monitor performance metrics
metrics = health_report['health_report']['metrics']
print(f"Total operations: {metrics['operations_total']}")
print(f"Success rate: {health_report['health_report']['success_rate']}%")
print(f"Average response time: {metrics['average_response_time']:.3f}s")
```

### Performance Metrics

The system automatically tracks:
- Operation success/failure rates
- Response times and performance trends
- Data transfer volumes (upload/download)
- Storage usage and growth patterns

## Testing

### Running Tests

```bash
# Run all tests
python tests/run_tests.py

# Run only unit tests
python tests/run_tests.py --unit

# Run only integration tests
python tests/run_tests.py --integration

# Run with verbose output
python tests/run_tests.py --verbose

# Run specific test pattern
python tests/run_tests.py --pattern "test_minio_manager.TestMinIOManager"
```

### Test Environment Setup

1. Copy test environment file:
   ```bash
   cp tests/.env.test .env.test
   ```

2. Configure test MinIO instance or use mocks

3. Run tests to verify functionality

## Security Considerations

### Production Security

1. **SSL/TLS Configuration**:
   ```bash
   MINIO_USE_SSL=true
   ```

2. **Access Control**:
   - Use strong, unique access keys
   - Implement bucket-level policies
   - Regular credential rotation

3. **Network Security**:
   - Use internal Docker networks
   - Implement firewall rules
   - Consider VPN access for management

### Data Protection

- Files are stored with user-specific metadata
- Automatic cleanup of old files
- Secure deletion capabilities
- Audit trail for all operations

## Troubleshooting

### Common Issues

1. **Connection Failures**:
   ```bash
   # Check MinIO service status
   docker-compose logs minio
   
   # Verify network connectivity
   docker-compose exec voxpersona ping minio
   ```

2. **Bucket Creation Issues**:
   ```bash
   # Manually create buckets if needed
   docker-compose exec minio mc mb local/voxpersona-audio
   ```

3. **Permission Errors**:
   ```bash
   # Check MinIO logs for access denied errors
   docker-compose logs minio | grep "Access Denied"
   ```

4. **Storage Issues**:
   ```bash
   # Check available disk space
   docker system df
   
   # Clean up old data if needed
   docker volume prune
   ```

### Health Check Commands

```bash
# Check MinIO health endpoint
curl http://localhost:9000/minio/health/ready

# Check bucket accessibility
curl -I http://localhost:9000/voxpersona-audio

# Monitor MinIO console
# Access: http://localhost:9001
```

## Performance Optimization

### Recommended Settings

1. **Retry Configuration**:
   ```bash
   MINIO_MAX_RETRIES=3
   MINIO_RETRY_BACKOFF=2.0
   ```

2. **Health Check Frequency**:
   ```bash
   MINIO_HEALTH_CHECK_INTERVAL=60  # seconds
   ```

3. **File Size Limits**:
   ```bash
   MINIO_MAX_FILE_SIZE=2147483648  # 2GB
   ```

### Performance Monitoring

The system provides detailed metrics for:
- Upload/download speeds
- Operation success rates
- Storage utilization
- Response time trends

## Migration from Previous Version

### Step-by-Step Migration

1. **Backup existing data** (if any)
2. **Update docker-compose.yml** with MinIO service
3. **Update environment variables**
4. **Replace old MinIO client usage** with new MinIOManager
5. **Test integration** with new health checks
6. **Deploy updated services**

### Code Migration

Replace old MinIO usage:

```python
# OLD: Direct minio client usage
from minio import Minio
client = Minio(endpoint, access_key, secret_key)
client.fput_object(bucket, object_name, file_path)

# NEW: Enhanced MinIOManager usage  
from src.minio_manager import get_minio_manager
manager = get_minio_manager()
success = manager.upload_audio_file(file_path, object_name, metadata)
```

## Support and Maintenance

### Regular Maintenance Tasks

1. **Monitor storage usage** and plan capacity
2. **Review health metrics** and performance trends  
3. **Clean up old files** based on retention policies
4. **Update MinIO version** regularly for security
5. **Test backup and recovery** procedures

### Getting Help

- Check application logs: `docker-compose logs voxpersona`
- Check MinIO logs: `docker-compose logs minio`
- Review health status via API
- Consult MinIO documentation for advanced configuration

## Conclusion

The enhanced MinIO integration provides:
- ✅ Robust, production-ready object storage
- ✅ Comprehensive error handling and recovery
- ✅ Performance monitoring and analytics
- ✅ Complete test coverage
- ✅ Security best practices
- ✅ Easy maintenance and troubleshooting

This implementation significantly improves VoxPersona's audio file management capabilities and provides a solid foundation for future enhancements.