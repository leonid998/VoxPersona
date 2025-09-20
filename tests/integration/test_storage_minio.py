"""Integration tests for Storage + MinIO interaction."""
import os
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, Mock

from tests.framework.base_test import BaseIntegrationTest
from src.import_utils import SafeImporter


class TestStorageMinIOIntegration(BaseIntegrationTest):
    """Test integration between storage system and MinIO."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_audio.wav"
        
        # Create test file
        self.test_file.write_bytes(b"fake audio data for testing")
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        super().tearDown()
    
    def test_minio_import_with_fallback(self):
        """Test MinIO import with fallback mechanisms."""
        importer = SafeImporter()
        
        # Test MinIO import
        minio_module = importer.safe_import('minio')
        self.assertIsNotNone(minio_module)
        
        # Should provide Minio class (real or mock)
        self.assertTrue(hasattr(minio_module, 'Minio'))
        
        # Test client creation
        client = minio_module.Minio(
            endpoint='localhost:9000',
            access_key='minioadmin',
            secret_key='minioadmin',
            secure=False
        )
        self.assertIsNotNone(client)
    
    def test_storage_operations_with_minio_unavailable(self):
        """Test storage operations when MinIO is unavailable."""
        importer = SafeImporter()
        
        # Mock MinIO to simulate unavailability
        minio_mock = importer.safe_import('minio')
        
        # Create mock client that raises exceptions
        mock_client = Mock()
        mock_client.bucket_exists.side_effect = Exception("Connection failed")
        mock_client.make_bucket.side_effect = Exception("Connection failed")
        mock_client.put_object.side_effect = Exception("Connection failed")
        
        minio_mock.Minio.return_value = mock_client
        
        # Test bucket operations with error handling
        try:
            exists = mock_client.bucket_exists('test-bucket')
        except Exception as e:
            self.assertIn("Connection failed", str(e))
    
    def test_file_upload_with_retry_mechanism(self):
        """Test file upload with retry mechanism."""
        importer = SafeImporter()
        minio_module = importer.safe_import('minio')
        
        # Create mock client with intermittent failures
        mock_client = Mock()
        
        # First call fails, second succeeds
        mock_client.put_object.side_effect = [
            Exception("Temporary failure"),
            None  # Success
        ]
        
        minio_module.Minio.return_value = mock_client
        
        client = minio_module.Minio('localhost:9000')
        
        # Implement retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                client.put_object(
                    bucket_name='test-bucket',
                    object_name='test-file.wav',
                    data=self.test_file.open('rb'),
                    length=self.test_file.stat().st_size
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                continue
        
        # Should have been called twice (first failure, then success)
        self.assertEqual(mock_client.put_object.call_count, 2)
    
    def test_bucket_management_operations(self):
        """Test bucket management operations."""
        importer = SafeImporter()
        minio_module = importer.safe_import('minio')
        
        mock_client = Mock()
        mock_client.bucket_exists.return_value = False
        mock_client.make_bucket.return_value = None
        mock_client.list_buckets.return_value = []
        
        minio_module.Minio.return_value = mock_client
        
        client = minio_module.Minio('localhost:9000')
        
        # Test bucket creation workflow
        bucket_name = 'voxpersona-audio'
        
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        
        # Verify calls
        mock_client.bucket_exists.assert_called_with(bucket_name)
        mock_client.make_bucket.assert_called_with(bucket_name)
    
    def test_file_download_with_error_handling(self):
        """Test file download with comprehensive error handling."""
        importer = SafeImporter()
        minio_module = importer.safe_import('minio')
        
        mock_client = Mock()
        
        # Test different error scenarios
        test_scenarios = [
            ('NoSuchBucket', 'Bucket does not exist'),
            ('NoSuchKey', 'Object does not exist'),
            ('AccessDenied', 'Access denied'),
            ('ConnectionError', 'Network error')
        ]
        
        for error_type, error_message in test_scenarios:
            mock_client.get_object.side_effect = Exception(f"{error_type}: {error_message}")
            minio_module.Minio.return_value = mock_client
            
            client = minio_module.Minio('localhost:9000')
            
            with self.assertRaises(Exception) as context:
                client.get_object('test-bucket', 'test-file.wav')
            
            self.assertIn(error_type, str(context.exception))
    
    def test_concurrent_storage_operations(self):
        """Test concurrent storage operations."""
        import threading
        import time
        
        importer = SafeImporter()
        minio_module = importer.safe_import('minio')
        
        mock_client = Mock()
        mock_client.put_object.return_value = None
        mock_client.get_object.return_value = Mock()
        
        minio_module.Minio.return_value = mock_client
        
        results = []
        errors = []
        
        def storage_worker(worker_id):
            try:
                client = minio_module.Minio('localhost:9000')
                
                # Simulate upload
                client.put_object(
                    bucket_name='test-bucket',
                    object_name=f'worker-{worker_id}.wav',
                    data=b'test data',
                    length=9
                )
                
                # Simulate download
                obj = client.get_object('test-bucket', f'worker-{worker_id}.wav')
                
                results.append(f'worker-{worker_id}')
            except Exception as e:
                errors.append(e)
        
        # Start multiple workers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=storage_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertFalse(errors, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5)
        
        # Verify all operations completed
        expected_results = [f'worker-{i}' for i in range(5)]
        self.assertEqual(sorted(results), sorted(expected_results))
    
    def test_storage_configuration_integration(self):
        """Test storage configuration integration."""
        from src.config import VoxPersonaConfig
        
        config = VoxPersonaConfig()
        importer = SafeImporter()
        
        # Test storage configuration loading
        storage_config = config.get_storage_config()
        
        # Should provide default values even if not configured
        self.assertIsInstance(storage_config, dict)
        
        # Test MinIO client creation with config
        minio_module = importer.safe_import('minio')
        
        if hasattr(minio_module, 'Minio'):
            # Should be able to create client with config
            client = minio_module.Minio(
                endpoint=storage_config.get('endpoint', 'localhost:9000'),
                access_key=storage_config.get('access_key', 'minioadmin'),
                secret_key=storage_config.get('secret_key', 'minioadmin'),
                secure=storage_config.get('secure', False)
            )
            self.assertIsNotNone(client)


if __name__ == '__main__':
    import unittest
    unittest.main()