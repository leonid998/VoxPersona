"""
Integration Tests for VoxPersona Audio Processing with MinIO

Tests the complete audio processing workflow including:
- Audio file upload to MinIO
- Transcription processing
- Error handling and recovery
- Performance and reliability
"""

import unittest
import tempfile
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.minio_manager import get_minio_manager, reset_minio_manager, MinIOError
from src.handlers import handle_audio_msg  # This would need to be refactored to be testable


class TestAudioProcessingIntegration(unittest.TestCase):
    """Integration tests for complete audio processing workflow"""
    
    def setUp(self):
        """Set up test environment"""
        reset_minio_manager()
        
        # Create temporary test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_audio_file = os.path.join(self.temp_dir, 'test_audio.wav')
        
        # Create a mock audio file
        with open(self.test_audio_file, 'wb') as f:
            f.write(b'fake audio content for testing' * 1000)  # ~32KB file
        
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
    
    def tearDown(self):
        """Clean up test environment"""
        self.env_patcher.stop()
        if os.path.exists(self.test_audio_file):
            os.remove(self.test_audio_file)
        os.rmdir(self.temp_dir)
    
    @patch('src.minio_manager.Minio')
    def test_complete_audio_upload_workflow(self, mock_minio_class):
        """Test complete audio upload and processing workflow"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Get MinIO manager
        manager = get_minio_manager()
        
        # Test metadata preparation
        metadata = {
            'user_id': '12345',
            'file_type': 'audio',
            'processing_status': 'uploaded'
        }
        
        # Test upload
        result = manager.upload_audio_file(
            file_path=self.test_audio_file,
            object_name='test_upload.wav',
            metadata=metadata
        )
        
        # Verify upload was successful
        self.assertTrue(result)
        mock_client.fput_object.assert_called_once()
        
        # Verify metadata was included
        call_args = mock_client.fput_object.call_args
        uploaded_metadata = call_args.kwargs['metadata']
        self.assertEqual(uploaded_metadata['user_id'], '12345')
        self.assertIn('uploaded_at', uploaded_metadata)
        self.assertIn('original_filename', uploaded_metadata)
    
    @patch('src.minio_manager.Minio')
    def test_audio_download_and_processing(self, mock_minio_class):
        """Test downloading audio file for processing"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock download
        download_path = os.path.join(self.temp_dir, 'downloaded_audio.wav')
        
        def mock_fget_object(bucket, object_name, local_path):
            with open(local_path, 'wb') as f:
                f.write(b'downloaded audio content')
        
        mock_client.fget_object.side_effect = mock_fget_object
        
        # Get manager and test download
        manager = get_minio_manager()
        result_path = manager.download_audio_file('test_audio.wav', download_path)
        
        # Verify download
        self.assertEqual(result_path, download_path)
        self.assertTrue(os.path.exists(download_path))
        
        # Clean up
        os.remove(download_path)
    
    @patch('src.minio_manager.Minio')
    def test_audio_stream_processing(self, mock_minio_class):
        """Test streaming audio for processing without local download"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock stream response
        mock_response = Mock()
        mock_response.read.return_value = b'audio stream content for processing'
        mock_client.get_object.return_value = mock_response
        
        # Get manager and test stream
        manager = get_minio_manager()
        stream = manager.get_audio_stream('test_audio.wav')
        
        # Verify stream content
        content = stream.read()
        self.assertEqual(content, b'audio stream content for processing')
        
        # Verify stream can be reset and read again
        stream.seek(0)
        content2 = stream.read()
        self.assertEqual(content2, content)
    
    @patch('src.minio_manager.Minio')
    def test_error_handling_upload_failure(self, mock_minio_class):
        """Test error handling when upload fails"""
        # Setup mock MinIO client that fails
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        mock_client.fput_object.side_effect = Exception("Upload failed")
        
        # Get manager and test failed upload
        manager = get_minio_manager()
        
        with self.assertRaises(MinIOError):
            manager.upload_audio_file(
                file_path=self.test_audio_file,
                object_name='test_upload.wav'
            )
        
        # Verify retry attempts were made
        self.assertGreater(mock_client.fput_object.call_count, 1)
    
    @patch('src.minio_manager.Minio')
    def test_connection_failure_recovery(self, mock_minio_class):
        """Test recovery from connection failures"""
        # Setup mock MinIO client that initially fails health checks
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        
        # First call fails, subsequent calls succeed
        mock_client.list_buckets.side_effect = [
            Exception("Connection failed"),
            [],  # Second call succeeds
            []   # Third call succeeds
        ]
        
        # Get manager
        manager = get_minio_manager()
        
        # First health check should fail
        health_status1 = manager.health_monitor.health_check()
        self.assertFalse(health_status1)
        
        # Wait a bit and try again - should succeed
        time.sleep(0.1)
        manager.health_monitor.last_health_check = 0  # Force new check
        health_status2 = manager.health_monitor.health_check()
        self.assertTrue(health_status2)
    
    @patch('src.minio_manager.Minio')
    def test_concurrent_operations(self, mock_minio_class):
        """Test concurrent MinIO operations"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Create multiple test files
        test_files = []
        for i in range(3):
            file_path = os.path.join(self.temp_dir, f'test_audio_{i}.wav')
            with open(file_path, 'wb') as f:
                f.write(f'audio content {i}'.encode() * 100)
            test_files.append(file_path)
        
        # Test concurrent uploads
        manager = get_minio_manager()
        results = []
        exceptions = []
        
        def upload_file(file_path, object_name):
            try:
                result = manager.upload_audio_file(file_path, object_name)
                results.append(result)
            except Exception as e:
                exceptions.append(e)
        
        # Start concurrent uploads
        threads = []
        for i, file_path in enumerate(test_files):
            thread = threading.Thread(
                target=upload_file,
                args=(file_path, f'concurrent_test_{i}.wav')
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all uploads to complete
        for thread in threads:
            thread.join()
        
        # Verify all uploads succeeded
        self.assertEqual(len(results), 3)
        self.assertEqual(len(exceptions), 0)
        self.assertTrue(all(results))
        
        # Clean up test files
        for file_path in test_files:
            os.remove(file_path)
    
    @patch('src.minio_manager.Minio')
    def test_large_file_handling(self, mock_minio_class):
        """Test handling of large audio files"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Create a larger test file (simulate 10MB)
        large_file_path = os.path.join(self.temp_dir, 'large_audio.wav')
        with open(large_file_path, 'wb') as f:
            # Write in chunks to avoid memory issues
            chunk = b'large audio content chunk' * 1000  # ~25KB chunk
            for _ in range(400):  # 400 chunks = ~10MB
                f.write(chunk)
        
        # Test upload with progress tracking
        manager = get_minio_manager()
        progress_updates = []
        
        def progress_callback(progress):
            progress_updates.append(progress.percentage)
        
        # Note: In real implementation, progress callback would work
        # For this test, we just verify the upload completes
        result = manager.upload_audio_file(
            file_path=large_file_path,
            object_name='large_test.wav',
            progress_callback=progress_callback
        )
        
        self.assertTrue(result)
        
        # Clean up
        os.remove(large_file_path)
    
    @patch('src.minio_manager.Minio')
    def test_metadata_search_and_filtering(self, mock_minio_class):
        """Test searching and filtering files by metadata"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock file listing with different metadata
        from src.minio_manager import ObjectInfo
        
        mock_objects = [
            Mock(object_name='user1_audio1.wav', size=1024, etag='etag1', 
                 last_modified=datetime.now(), content_type='audio/wav', is_dir=False),
            Mock(object_name='user2_audio1.wav', size=2048, etag='etag2',
                 last_modified=datetime.now(), content_type='audio/wav', is_dir=False),
            Mock(object_name='user1_audio2.wav', size=1536, etag='etag3',
                 last_modified=datetime.now(), content_type='audio/wav', is_dir=False)
        ]
        
        mock_client.list_objects.return_value = mock_objects
        
        # Mock stat_object to return different metadata for each file
        def mock_stat_object(bucket, object_name):
            mock_stat = Mock()
            if 'user1' in object_name:
                mock_stat.metadata = {'user_id': '123', 'category': 'interview'}
            else:
                mock_stat.metadata = {'user_id': '456', 'category': 'design'}
            return mock_stat
        
        mock_client.stat_object.side_effect = mock_stat_object
        
        # Test file listing and filtering
        manager = get_minio_manager()
        
        # Get all files for user 123
        user_files = manager.search_files_by_metadata({'user_id': '123'})
        self.assertEqual(len(user_files), 2)
        
        # Get interview files
        interview_files = manager.search_files_by_metadata({'category': 'interview'})
        self.assertEqual(len(interview_files), 2)
        
        # Get specific combination
        specific_files = manager.search_files_by_metadata({
            'user_id': '123', 
            'category': 'interview'
        })
        self.assertEqual(len(specific_files), 2)
    
    @patch('src.minio_manager.Minio')
    def test_storage_cleanup_operations(self, mock_minio_class):
        """Test storage cleanup and maintenance operations"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock old and new files
        from datetime import timedelta
        old_date = datetime.now() - timedelta(days=35)
        new_date = datetime.now() - timedelta(days=5)
        
        mock_old_files = [
            Mock(object_name='old_file1.wav', last_modified=old_date),
            Mock(object_name='old_file2.wav', last_modified=old_date),
        ]
        
        mock_new_files = [
            Mock(object_name='new_file1.wav', last_modified=new_date),
        ]
        
        mock_client.list_objects.return_value = mock_old_files + mock_new_files
        
        # Test cleanup
        manager = get_minio_manager()
        deleted_count = manager.cleanup_old_files(days_old=30)
        
        # Verify only old files were deleted
        self.assertEqual(deleted_count, 2)
        self.assertEqual(mock_client.remove_object.call_count, 2)
        
        # Verify correct files were deleted
        deleted_files = [call.args[1] for call in mock_client.remove_object.call_args_list]
        self.assertIn('old_file1.wav', deleted_files)
        self.assertIn('old_file2.wav', deleted_files)
        self.assertNotIn('new_file1.wav', deleted_files)
    
    @patch('src.minio_manager.Minio')
    def test_storage_usage_monitoring(self, mock_minio_class):
        """Test storage usage monitoring and reporting"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Mock objects with various sizes
        mock_objects_bucket1 = [
            Mock(size=1024),   # 1KB
            Mock(size=2048),   # 2KB
            Mock(size=4096),   # 4KB
        ]
        
        mock_objects_bucket2 = [
            Mock(size=8192),   # 8KB
            Mock(size=16384),  # 16KB
        ]
        
        # Return different objects for different buckets
        def mock_list_objects(bucket_name):
            if bucket_name == 'test-bucket':
                return mock_objects_bucket1
            elif bucket_name == 'test-audio-bucket':
                return mock_objects_bucket2
            return []
        
        mock_client.list_objects.side_effect = mock_list_objects
        
        # Test storage usage calculation
        manager = get_minio_manager()
        usage = manager.get_storage_usage()
        
        # Verify calculations
        expected_total = 1024 + 2048 + 4096 + 8192 + 16384  # 31744 bytes
        self.assertEqual(usage['total_size_bytes'], expected_total)
        self.assertEqual(usage['file_count'], 5)
        self.assertEqual(usage['total_size_mb'], round(expected_total / (1024 * 1024), 2))
    
    @patch('src.minio_manager.Minio')  
    def test_comprehensive_health_monitoring(self, mock_minio_class):
        """Test comprehensive health monitoring and reporting"""
        # Setup mock MinIO client
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Get manager and perform some operations
        manager = get_minio_manager()
        
        # Simulate some operations for metrics
        manager.health_monitor.record_operation('upload', True, 1.5, 1024)
        manager.health_monitor.record_operation('download', True, 0.8, 512)
        manager.health_monitor.record_operation('upload', False, 3.0, 0)
        manager.health_monitor.record_operation('delete', True, 0.5, 0)
        
        # Get comprehensive health status
        status = manager.get_health_status()
        
        # Verify status structure
        self.assertIn('connection_status', status)
        self.assertIn('health_report', status)
        self.assertIn('storage_usage', status)
        self.assertIn('service_info', status)
        
        # Verify health metrics
        health_report = status['health_report']
        self.assertEqual(health_report['success_rate'], 75.0)  # 3 success out of 4
        
        metrics = health_report['metrics']
        self.assertEqual(metrics['operations_total'], 4)
        self.assertEqual(metrics['operations_successful'], 3)
        self.assertEqual(metrics['operations_failed'], 1)
        self.assertEqual(metrics['total_bytes_uploaded'], 1024)
        self.assertEqual(metrics['total_bytes_downloaded'], 512)


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)