"""
Unit and Integration Tests for MinIO Manager

Tests the enhanced MinIO integration functionality including:
- Connection and health checks
- Upload, download, delete operations
- Error handling and retry mechanisms
- Metadata management
"""

import unittest
import tempfile
import os
import time
import io
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.minio_manager import (
    MinIOManager, 
    MinIOError, 
    MinIOConnectionError, 
    MinIOUploadError,
    MinIODownloadError,
    MinIODeleteError,
    RetryableMinIOOperation,
    MinIOHealthMonitor,
    ObjectInfo,
    get_minio_manager,
    reset_minio_manager
)


class TestRetryableMinIOOperation(unittest.TestCase):
    """Test retry mechanism functionality"""
    
    def setUp(self):
        self.retry_handler = RetryableMinIOOperation(max_retries=3, backoff_factor=1.0)
    
    def test_successful_operation_no_retry(self):
        """Test successful operation without retries"""
        def successful_operation():
            return "success"
        
        result = self.retry_handler.execute_with_retry(successful_operation)
        self.assertEqual(result, "success")
    
    def test_operation_succeeds_after_retries(self):
        """Test operation that succeeds after some failures"""
        call_count = 0
        
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = self.retry_handler.execute_with_retry(flaky_operation)
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
    
    def test_operation_fails_after_max_retries(self):
        """Test operation that fails after max retries"""
        call_count = 0
        
        def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")
        
        with self.assertRaises(MinIOError):
            self.retry_handler.execute_with_retry(always_failing_operation)
        
        self.assertEqual(call_count, 4)  # initial + 3 retries


class TestMinIOHealthMonitor(unittest.TestCase):
    """Test health monitoring functionality"""
    
    def setUp(self):
        self.mock_client = Mock()
        self.health_monitor = MinIOHealthMonitor(self.mock_client)
    
    def test_health_check_success(self):
        """Test successful health check"""
        self.mock_client.list_buckets.return_value = []
        
        result = self.health_monitor.health_check()
        
        self.assertTrue(result)
        self.assertTrue(self.health_monitor.is_healthy)
        self.assertGreater(self.health_monitor.last_health_check, 0)
    
    def test_health_check_failure(self):
        """Test failed health check"""
        self.mock_client.list_buckets.side_effect = Exception("Connection failed")
        
        result = self.health_monitor.health_check()
        
        self.assertFalse(result)
        self.assertFalse(self.health_monitor.is_healthy)
    
    def test_health_check_caching(self):
        """Test health check result caching"""
        self.mock_client.list_buckets.return_value = []
        
        # First health check
        result1 = self.health_monitor.health_check()
        call_count_1 = self.mock_client.list_buckets.call_count
        
        # Second health check (should be cached)
        result2 = self.health_monitor.health_check()
        call_count_2 = self.mock_client.list_buckets.call_count
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertEqual(call_count_1, call_count_2)  # No additional call
    
    def test_record_operation_metrics(self):
        """Test operation metrics recording"""
        self.health_monitor.record_operation('upload', True, 1.5, 1024)
        self.health_monitor.record_operation('download', False, 2.0, 0)
        
        metrics = self.health_monitor.metrics
        
        self.assertEqual(metrics['operations_total'], 2)
        self.assertEqual(metrics['operations_successful'], 1)
        self.assertEqual(metrics['operations_failed'], 1)
        self.assertEqual(metrics['total_bytes_uploaded'], 1024)
        self.assertEqual(metrics['total_bytes_downloaded'], 0)
    
    def test_health_report_generation(self):
        """Test health report generation"""
        self.health_monitor.is_healthy = True
        self.health_monitor.record_operation('upload', True, 1.0, 500)
        self.health_monitor.record_operation('upload', False, 2.0, 0)
        
        report = self.health_monitor.get_health_report()
        
        self.assertTrue(report['is_healthy'])
        self.assertEqual(report['success_rate'], 50.0)
        self.assertIn('metrics', report)


class TestMinIOManager(unittest.TestCase):
    """Test MinIO Manager functionality"""
    
    def setUp(self):
        # Reset global manager instance
        reset_minio_manager()
        
        # Mock environment variables
        self.env_patcher = patch.multiple(
            'src.config',
            MINIO_ENDPOINT='localhost:9000',
            MINIO_ACCESS_KEY='test_access',
            MINIO_SECRET_KEY='test_secret',
            MINIO_BUCKET_NAME='test-bucket',
            MINIO_AUDIO_BUCKET_NAME='test-audio-bucket'
        )
        self.env_patcher.start()
        
        # Create temporary test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, 'test_audio.wav')
        with open(self.test_file_path, 'wb') as f:
            f.write(b'fake audio content for testing')
    
    def tearDown(self):
        self.env_patcher.stop()
        # Clean up temporary files
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        os.rmdir(self.temp_dir)
    
    @patch('src.minio_manager.Minio')
    def test_manager_initialization_success(self, mock_minio_class):
        """Test successful MinIO manager initialization"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        manager = MinIOManager()
        
        self.assertIsNotNone(manager.client)
        self.assertIsNotNone(manager.health_monitor)
        mock_minio_class.assert_called_once()
    
    @patch('src.minio_manager.Minio')
    def test_manager_initialization_failure(self, mock_minio_class):
        """Test MinIO manager initialization failure"""
        mock_minio_class.side_effect = Exception("Connection failed")
        
        with self.assertRaises(MinIOConnectionError):
            MinIOManager()
    
    @patch('src.minio_manager.Minio')
    def test_bucket_creation(self, mock_minio_class):
        """Test automatic bucket creation"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = False
        
        manager = MinIOManager()
        
        # Verify buckets were created
        expected_calls = 2  # test-bucket and test-audio-bucket
        self.assertEqual(mock_client.make_bucket.call_count, expected_calls)
    
    @patch('src.minio_manager.Minio')
    def test_upload_audio_file_success(self, mock_minio_class):
        """Test successful audio file upload"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        manager = MinIOManager()
        
        # Test upload
        result = manager.upload_audio_file(
            file_path=self.test_file_path,
            object_name='test_audio.wav',
            metadata={'user_id': '123'}
        )
        
        self.assertTrue(result)
        mock_client.fput_object.assert_called_once()
        
        # Verify metadata was included
        call_args = mock_client.fput_object.call_args
        self.assertIn('metadata', call_args.kwargs)
        metadata = call_args.kwargs['metadata']
        self.assertEqual(metadata['user_id'], '123')
        self.assertIn('uploaded_at', metadata)
    
    @patch('src.minio_manager.Minio')
    def test_upload_file_not_found(self, mock_minio_class):
        """Test upload with non-existent file"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        manager = MinIOManager()
        
        with self.assertRaises(MinIOUploadError):
            manager.upload_audio_file('/non/existent/file.wav')
    
    @patch('src.minio_manager.Minio')
    def test_download_audio_file_success(self, mock_minio_class):
        """Test successful audio file download"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        manager = MinIOManager()
        
        download_path = os.path.join(self.temp_dir, 'downloaded_audio.wav')
        
        # Mock the download to create the file
        def mock_fget_object(bucket, object_name, local_path):
            with open(local_path, 'wb') as f:
                f.write(b'downloaded content')
        
        mock_client.fget_object.side_effect = mock_fget_object
        
        result = manager.download_audio_file('test_audio.wav', download_path)
        
        self.assertEqual(result, download_path)
        self.assertTrue(os.path.exists(download_path))
        mock_client.fget_object.assert_called_once()
        
        # Clean up
        os.remove(download_path)
    
    @patch('src.minio_manager.Minio')
    def test_get_audio_stream_success(self, mock_minio_class):
        """Test successful audio stream retrieval"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock response object
        mock_response = Mock()
        mock_response.read.return_value = b'audio stream content'
        mock_client.get_object.return_value = mock_response
        
        manager = MinIOManager()
        
        stream = manager.get_audio_stream('test_audio.wav')
        
        self.assertIsInstance(stream, io.BytesIO)
        self.assertEqual(stream.read(), b'audio stream content')
        mock_client.get_object.assert_called_once()
    
    @patch('src.minio_manager.Minio')
    def test_delete_audio_file_success(self, mock_minio_class):
        """Test successful audio file deletion"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        manager = MinIOManager()
        
        result = manager.delete_audio_file('test_audio.wav')
        
        self.assertTrue(result)
        mock_client.remove_object.assert_called_once()
    
    @patch('src.minio_manager.Minio')
    def test_list_user_audio_files(self, mock_minio_class):
        """Test listing user audio files"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock object list
        mock_object = Mock()
        mock_object.object_name = 'user_123/audio1.wav'
        mock_object.size = 1024
        mock_object.etag = 'etag123'
        mock_object.last_modified = datetime.now()
        mock_object.content_type = 'audio/wav'
        mock_object.is_dir = False
        
        mock_client.list_objects.return_value = [mock_object]
        
        # Mock stat_object for metadata
        mock_stat = Mock()
        mock_stat.metadata = {'user_id': '123'}
        mock_client.stat_object.return_value = mock_stat
        
        manager = MinIOManager()
        
        files = manager.list_user_audio_files(user_id=123)
        
        self.assertEqual(len(files), 1)
        self.assertIsInstance(files[0], ObjectInfo)
        self.assertEqual(files[0].object_name, 'user_123/audio1.wav')
        self.assertEqual(files[0].metadata['user_id'], '123')
    
    @patch('src.minio_manager.Minio')
    def test_cleanup_old_files(self, mock_minio_class):
        """Test cleanup of old files"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock old and new objects
        old_object = Mock()
        old_object.object_name = 'old_file.wav'
        old_object.last_modified = datetime.now() - timedelta(days=35)
        
        new_object = Mock()
        new_object.object_name = 'new_file.wav'
        new_object.last_modified = datetime.now() - timedelta(days=5)
        
        mock_client.list_objects.return_value = [old_object, new_object]
        
        manager = MinIOManager()
        
        deleted_count = manager.cleanup_old_files(days_old=30)
        
        self.assertEqual(deleted_count, 1)
        mock_client.remove_object.assert_called_once_with(
            'test-audio-bucket', 'old_file.wav'
        )
    
    @patch('src.minio_manager.Minio')
    def test_get_storage_usage(self, mock_minio_class):
        """Test storage usage calculation"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock objects with sizes
        object1 = Mock()
        object1.size = 1024
        object2 = Mock()
        object2.size = 2048
        
        mock_client.list_objects.return_value = [object1, object2]
        
        manager = MinIOManager()
        
        usage = manager.get_storage_usage()
        
        self.assertEqual(usage['total_size_bytes'], 3072)
        self.assertEqual(usage['file_count'], 4)  # 2 objects × 2 buckets
        self.assertIn('buckets', usage)
    
    @patch('src.minio_manager.Minio')
    def test_health_status_report(self, mock_minio_class):
        """Test comprehensive health status report"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        manager = MinIOManager()
        
        status = manager.get_health_status()
        
        self.assertIn('connection_status', status)
        self.assertIn('health_report', status)
        self.assertIn('storage_usage', status)
        self.assertIn('service_info', status)


class TestMinIOManagerIntegration(unittest.TestCase):
    """Integration tests for MinIO Manager"""
    
    def setUp(self):
        reset_minio_manager()
    
    def test_global_manager_singleton(self):
        """Test global manager singleton pattern"""
        manager1 = get_minio_manager()
        manager2 = get_minio_manager()
        
        self.assertIs(manager1, manager2)
    
    @patch('src.minio_manager.MinIOManager')
    def test_manager_retry_on_failure(self, mock_manager_class):
        """Test manager retry behavior on failure"""
        # First initialization fails
        mock_manager_class.side_effect = [
            MinIOConnectionError("Connection failed"),
            Mock()  # Second attempt succeeds
        ]
        
        with patch('src.minio_manager._minio_manager', None):
            try:
                get_minio_manager()
                self.fail("Expected MinIOConnectionError")
            except MinIOConnectionError:
                pass
            
            # Reset and try again
            reset_minio_manager()
            manager = get_minio_manager()
            self.assertIsNotNone(manager)


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)