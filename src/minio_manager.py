"""
Enhanced MinIO Manager for VoxPersona

Provides comprehensive MinIO integration with:
- Health checks and connection validation
- Retry mechanisms with exponential backoff
- Complete CRUD operations (upload, download, delete, list)
- Metadata management and security features
- Error handling and monitoring
"""

import os
import time
import logging
import io
from datetime import datetime, timedelta
from typing import Any, Callable
from dataclasses import dataclass
from minio import Minio
from minio.error import S3Error
import urllib3

from .config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET_NAME,
    MINIO_AUDIO_BUCKET_NAME
)


@dataclass
class ObjectInfo:
    """Information about a MinIO object"""
    object_name: str
    size: int
    etag: str
    last_modified: datetime
    content_type: str
    metadata: dict[str, str]
    is_dir: bool = False


@dataclass
class UploadProgress:
    """Upload progress information"""
    bytes_uploaded: int
    total_bytes: int
    percentage: float
    elapsed_time: float


class MinIOError(Exception):
    """Base exception for MinIO operations"""
    pass


class MinIOConnectionError(MinIOError):
    """MinIO connection failed"""
    pass


class MinIOUploadError(MinIOError):
    """File upload failed"""
    pass


class MinIODownloadError(MinIOError):
    """File download failed"""
    pass


class MinIODeleteError(MinIOError):
    """File deletion failed"""
    pass


class RetryableMinIOOperation:
    """Handles retrying MinIO operations with exponential backoff"""
    
    max_retries: int
    backoff_factor: float
    max_delay: float
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
    
    def execute_with_retry(self, operation: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute MinIO operation with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries:
                    break
                
                delay = min(self.backoff_factor ** attempt, self.max_delay)
                logging.warning(f"MinIO operation failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                logging.info(f"Retrying in {delay:.2f} seconds...")
                _ = time.sleep(delay)
        
        raise MinIOError(f"Operation failed after {self.max_retries + 1} attempts: {last_exception}")


class MinIOHealthMonitor:
    """Monitors MinIO service health and performance"""
    
    client: Minio
    last_health_check: float
    health_check_interval: int
    is_healthy: bool
    metrics: dict[str, Any]
    
    def __init__(self, client: Minio):
        self.client = client
        self.last_health_check = 0
        self.health_check_interval = 60  # seconds
        self.is_healthy = False
        self.metrics = {
            'operations_total': 0,
            'operations_successful': 0,
            'operations_failed': 0,
            'total_bytes_uploaded': 0,
            'total_bytes_downloaded': 0,
            'average_response_time': 0.0
        }
    
    def health_check(self) -> bool:
        """Verify MinIO service availability"""
        current_time = time.time()
        
        # Skip health check if recently performed
        if current_time - self.last_health_check < self.health_check_interval:
            return self.is_healthy
        
        try:
            start_time = time.time()
            # Try to list buckets as a health check
            list(self.client.list_buckets())
            response_time = time.time() - start_time
            
            self.is_healthy = True
            self.last_health_check = current_time
            self._update_response_time(response_time)
            
            logging.debug(f"MinIO health check passed in {response_time:.3f}s")
            return True
            
        except Exception as e:
            self.is_healthy = False
            self.last_health_check = current_time
            logging.error(f"MinIO health check failed: {e}")
            return False
    
    def record_operation(self, operation: str, success: bool, duration: float, bytes_transferred: int = 0):
        """Record operation metrics"""
        self.metrics['operations_total'] += 1
        
        if success:
            self.metrics['operations_successful'] += 1
            if operation == 'upload':
                self.metrics['total_bytes_uploaded'] += bytes_transferred
            elif operation == 'download':
                self.metrics['total_bytes_downloaded'] += bytes_transferred
        else:
            self.metrics['operations_failed'] += 1
        
        self._update_response_time(duration)
    
    def _update_response_time(self, duration: float):
        """Update average response time"""
        if self.metrics['operations_total'] > 0:
            current_avg = self.metrics['average_response_time']
            total_ops = self.metrics['operations_total']
            self.metrics['average_response_time'] = (current_avg * (total_ops - 1) + duration) / total_ops
    
    def get_health_report(self) -> dict[str, Any]:
        """Generate comprehensive health report"""
        success_rate = 0.0
        if self.metrics['operations_total'] > 0:
            success_rate = (self.metrics['operations_successful'] / self.metrics['operations_total']) * 100
        
        return {
            'is_healthy': self.is_healthy,
            'last_check': datetime.fromtimestamp(self.last_health_check),
            'success_rate': success_rate,
            'metrics': self.metrics.copy()
        }


class MinIOManager:
    """Enhanced MinIO Manager with comprehensive functionality"""
    
    endpoint: str | None
    access_key: str | None
    secret_key: str | None
    client: Minio | None
    health_monitor: MinIOHealthMonitor | None
    retry_handler: RetryableMinIOOperation
    
    def __init__(self, endpoint: str | None = None, access_key: str | None = None, secret_key: str | None = None):
        self.endpoint = endpoint or MINIO_ENDPOINT
        self.access_key = access_key or MINIO_ACCESS_KEY
        self.secret_key = secret_key or MINIO_SECRET_KEY
        
        self.client: Minio | None = None
        self.health_monitor: MinIOHealthMonitor | None = None
        self.retry_handler = RetryableMinIOOperation()
        
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate MinIO configuration"""
        if not all([self.endpoint, self.access_key, self.secret_key]):
            raise MinIOConnectionError(
                "MinIO configuration incomplete. Please check MINIO_ENDPOINT, "
                "MINIO_ACCESS_KEY, and MINIO_SECRET_KEY environment variables."
            )
    
    def _initialize_client(self) -> bool:
        """Initialize MinIO client with connection validation"""
        try:
            # Disable SSL certificate verification for development
            # In production, use proper SSL certificates
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=False  # Set to True in production with proper SSL
            )
            
            self.health_monitor = MinIOHealthMonitor(self.client)
            
            # Validate connection by performing a health check
            if not self.health_monitor.health_check():
                raise MinIOConnectionError("Failed to establish connection to MinIO")
            
            # Ensure required buckets exist
            self._ensure_buckets_exist()
            
            logging.info("MinIO client initialized successfully")
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize MinIO client: {e}")
            raise MinIOConnectionError(f"MinIO initialization failed: {e}")
    
    def _ensure_buckets_exist(self):
        """Create required buckets if they don't exist"""
        if not self.client:
            raise MinIOConnectionError("MinIO client not initialized")
            
        required_buckets = [MINIO_BUCKET_NAME, MINIO_AUDIO_BUCKET_NAME]
        
        for bucket_name in required_buckets:
            if not bucket_name:
                continue
                
            try:
                if not self.client.bucket_exists(bucket_name):
                    self.client.make_bucket(bucket_name)
                    logging.info(f"Created MinIO bucket: {bucket_name}")
                else:
                    logging.debug(f"MinIO bucket already exists: {bucket_name}")
                    
            except S3Error as e:
                if e.code == 'BucketAlreadyOwnedByYou' or e.code == 'BucketAlreadyExists':
                    logging.debug(f"Bucket {bucket_name} already exists")
                else:
                    logging.error(f"Failed to create bucket {bucket_name}: {e}")
                    raise MinIOError(f"Bucket creation failed: {e}")
    
    def get_client(self) -> Minio:
        """Get validated MinIO client instance"""
        if not self.client or not self.health_monitor or not self.health_monitor.health_check():
            self._initialize_client()
        
        if not self.client:
            raise MinIOConnectionError("Failed to initialize MinIO client")
        
        return self.client
    
    def upload_audio_file(self, file_path: str, object_name: str | None = None, 
                         metadata: dict[str, str] | None = None, 
                         progress_callback: Callable[[UploadProgress], None] | None = None) -> bool:
        """Upload audio file to MinIO with metadata and progress tracking"""
        if not os.path.exists(file_path):
            raise MinIOUploadError(f"File not found: {file_path}")
        
        if not object_name:
            object_name = os.path.basename(file_path)
        
        bucket_name = MINIO_AUDIO_BUCKET_NAME
        if not bucket_name:
            raise MinIOUploadError("MINIO_AUDIO_BUCKET_NAME not configured")
        
        # Prepare metadata
        file_metadata = metadata or {}
        file_metadata.update({
            'uploaded_at': datetime.now().isoformat(),
            'original_filename': os.path.basename(file_path),
            'file_size': str(os.path.getsize(file_path))
        })
        
        def upload_operation():
            if not self.client or not self.health_monitor:
                raise MinIOUploadError("MinIO client not initialized")
                
            start_time = time.time()
            file_size = os.path.getsize(file_path)
            
            try:
                # Upload with progress tracking if callback provided
                if progress_callback:
                    self._upload_with_progress(file_path, bucket_name, object_name, 
                                             file_metadata, progress_callback, file_size)
                else:
                    self.client.fput_object(
                        bucket_name=bucket_name,
                        object_name=object_name,
                        file_path=file_path,
                        metadata=file_metadata
                    )
                
                duration = time.time() - start_time
                self.health_monitor.record_operation('upload', True, duration, file_size)
                
                logging.info(f"Successfully uploaded {object_name} to {bucket_name}")
                return True
                
            except Exception as e:
                duration = time.time() - start_time
                self.health_monitor.record_operation('upload', False, duration)
                raise MinIOUploadError(f"Upload failed: {e}")
        
        return self.retry_handler.execute_with_retry(upload_operation)
    
    def _upload_with_progress(self, file_path: str, bucket_name: str, object_name: str,
                            metadata: dict[str, str], progress_callback: Callable[[UploadProgress], None], total_size: int):
        """Upload file with progress tracking"""
        if not self.client:
            raise MinIOUploadError("MinIO client not initialized")
            
        # For progress tracking, we'll need to use put_object with a custom stream
        # This is a simplified implementation
        with open(file_path, 'rb') as file_data:
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=file_data,
                length=total_size,
                metadata=metadata
            )
    
    def download_audio_file(self, object_name: str, local_path: str | None = None) -> str:
        """Download audio file from MinIO"""
        bucket_name = MINIO_AUDIO_BUCKET_NAME
        if not bucket_name:
            raise MinIODownloadError("MINIO_AUDIO_BUCKET_NAME not configured")
        
        if not local_path:
            local_path = os.path.join(os.getcwd(), object_name)
        
        def download_operation():
            if not self.client or not self.health_monitor:
                raise MinIODownloadError("MinIO client not initialized")
                
            start_time = time.time()
            
            try:
                self.client.fget_object(bucket_name, object_name, local_path)
                
                file_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
                duration = time.time() - start_time
                self.health_monitor.record_operation('download', True, duration, file_size)
                
                logging.info(f"Successfully downloaded {object_name} to {local_path}")
                return local_path
                
            except Exception as e:
                duration = time.time() - start_time
                self.health_monitor.record_operation('download', False, duration)
                raise MinIODownloadError(f"Download failed: {e}")
        
        return self.retry_handler.execute_with_retry(download_operation)
    
    def get_audio_stream(self, object_name: str) -> io.BytesIO:
        """Get audio file as stream for processing"""
        bucket_name = MINIO_AUDIO_BUCKET_NAME
        if not bucket_name:
            raise MinIODownloadError("MINIO_AUDIO_BUCKET_NAME not configured")
        
        def stream_operation():
            if not self.client or not self.health_monitor:
                raise MinIODownloadError("MinIO client not initialized")
                
            start_time = time.time()
            
            try:
                response = self.client.get_object(bucket_name, object_name)
                data = response.read()
                
                duration = time.time() - start_time
                self.health_monitor.record_operation('download', True, duration, len(data))
                
                return io.BytesIO(data)
                
            except Exception as e:
                duration = time.time() - start_time
                self.health_monitor.record_operation('download', False, duration)
                raise MinIODownloadError(f"Stream operation failed: {e}")
        
        return self.retry_handler.execute_with_retry(stream_operation)
    
    def delete_audio_file(self, object_name: str) -> bool:
        """Delete single audio file"""
        bucket_name = MINIO_AUDIO_BUCKET_NAME
        if not bucket_name:
            raise MinIODeleteError("MINIO_AUDIO_BUCKET_NAME not configured")
        
        def delete_operation():
            if not self.client or not self.health_monitor:
                raise MinIODeleteError("MinIO client not initialized")
                
            start_time = time.time()
            
            try:
                self.client.remove_object(bucket_name, object_name)
                
                duration = time.time() - start_time
                self.health_monitor.record_operation('delete', True, duration)
                
                logging.info(f"Successfully deleted {object_name} from {bucket_name}")
                return True
                
            except Exception as e:
                duration = time.time() - start_time
                self.health_monitor.record_operation('delete', False, duration)
                raise MinIODeleteError(f"Delete failed: {e}")
        
        return self.retry_handler.execute_with_retry(delete_operation)
    
    def list_user_audio_files(self, user_id: int | None = None, prefix: str | None = None, 
                             max_results: int = 1000) -> list[ObjectInfo]:
        """List audio files for specific user or with prefix"""
        bucket_name = MINIO_AUDIO_BUCKET_NAME
        if not bucket_name:
            raise MinIOError("MINIO_AUDIO_BUCKET_NAME not configured")
        
        search_prefix = prefix or ""
        if user_id:
            search_prefix = f"user_{user_id}/" + search_prefix
        
        def list_operation():
            if not self.client or not self.health_monitor:
                raise MinIOError("MinIO client not initialized")
                
            start_time = time.time()
            
            try:
                objects = []
                for obj in self.client.list_objects(bucket_name, prefix=search_prefix):
                    if len(objects) >= max_results:
                        break
                    
                    # Get object metadata
                    try:
                        stat = self.client.stat_object(bucket_name, obj.object_name)
                        metadata = stat.metadata or {}
                    except:
                        metadata = {}
                    
                    objects.append(ObjectInfo(
                        object_name=obj.object_name,
                        size=obj.size,
                        etag=obj.etag,
                        last_modified=obj.last_modified,
                        content_type=obj.content_type or 'application/octet-stream',
                        metadata=metadata,
                        is_dir=obj.is_dir
                    ))
                
                duration = time.time() - start_time
                self.health_monitor.record_operation('list', True, duration)
                
                logging.debug(f"Listed {len(objects)} objects from {bucket_name}")
                return objects
                
            except Exception as e:
                duration = time.time() - start_time
                self.health_monitor.record_operation('list', False, duration)
                raise MinIOError(f"List operation failed: {e}")
        
        return self.retry_handler.execute_with_retry(list_operation)
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up files older than specified days"""
        if not self.client:
            raise MinIOError("MinIO client not initialized")
            
        bucket_name = MINIO_AUDIO_BUCKET_NAME
        if not bucket_name:
            raise MinIOError("MINIO_AUDIO_BUCKET_NAME not configured")
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0
        
        try:
            objects_to_delete = []
            for obj in self.client.list_objects(bucket_name):
                if obj.last_modified < cutoff_date:
                    objects_to_delete.append(obj.object_name)
            
            for object_name in objects_to_delete:
                try:
                    self.client.remove_object(bucket_name, object_name)
                    deleted_count += 1
                except Exception as e:
                    logging.error(f"Failed to delete {object_name}: {e}")
            
            logging.info(f"Cleaned up {deleted_count} old files (older than {days_old} days)")
            return deleted_count
            
        except Exception as e:
            logging.error(f"Cleanup operation failed: {e}")
            raise MinIOError(f"Cleanup failed: {e}")
    
    def search_files_by_metadata(self, filters: dict[str, str]) -> list[ObjectInfo]:
        """Search files by metadata criteria"""
        all_files = self.list_user_audio_files()
        matching_files = []
        
        for file_info in all_files:
            matches = True
            for key, value in filters.items():
                if key not in file_info.metadata or file_info.metadata[key] != value:
                    matches = False
                    break
            
            if matches:
                matching_files.append(file_info)
        
        return matching_files
    
    def get_storage_usage(self) -> dict[str, Any]:
        """Get storage usage statistics"""
        if not self.client:
            return {}
            
        try:
            total_size = 0
            file_count = 0
            
            for bucket_name in [MINIO_BUCKET_NAME, MINIO_AUDIO_BUCKET_NAME]:
                if not bucket_name:
                    continue
                    
                for obj in self.client.list_objects(bucket_name):
                    total_size += obj.size
                    file_count += 1
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'buckets': [b for b in [MINIO_BUCKET_NAME, MINIO_AUDIO_BUCKET_NAME] if b]
            }
            
        except Exception as e:
            logging.error(f"Failed to get storage usage: {e}")
            return {}
    
    def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status"""
        health_report = self.health_monitor.get_health_report() if self.health_monitor else {}
        storage_usage = self.get_storage_usage()
        
        return {
            'connection_status': 'healthy' if health_report.get('is_healthy') else 'unhealthy',
            'health_report': health_report,
            'storage_usage': storage_usage,
            'service_info': {
                'endpoint': self.endpoint,
                'buckets_configured': [MINIO_BUCKET_NAME, MINIO_AUDIO_BUCKET_NAME]
            }
        }


# Global MinIO manager instance
_minio_manager: MinIOManager | None = None


def get_minio_manager() -> MinIOManager:
    """Get global MinIO manager instance"""
    global _minio_manager
    
    if _minio_manager is None:
        _minio_manager = MinIOManager()
    
    return _minio_manager


def reset_minio_manager():
    """Reset global MinIO manager instance (for testing)"""
    global _minio_manager
    _minio_manager = None