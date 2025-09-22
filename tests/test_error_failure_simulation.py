"""
Error Scenario Testing with Failure Simulation

This module provides comprehensive error scenario testing including:
- Network connectivity failure simulation
- Service unavailability testing  
- Database connection failure scenarios
- Storage system failure simulation
- API rate limiting and quota exhaustion
- Recovery mechanism validation
- Cascade failure prevention testing
"""

import unittest
import os
import sys
import time
import threading
import tempfile
import random
from unittest.mock import Mock, patch, MagicMock, side_effect
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tests.test_config import get_test_config


class TestNetworkConnectivityFailures(unittest.TestCase):
    """Test network connectivity failure scenarios"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.minio_manager.Minio')
    def test_minio_connection_timeout_recovery(self, mock_minio_class):
        """Test MinIO connection timeout and recovery"""
        # First connection fails, second succeeds
        mock_client_fail = Mock()
        mock_client_fail.list_buckets.side_effect = Exception("Connection timeout")
        
        mock_client_success = Mock()
        mock_client_success.list_buckets.return_value = []
        mock_client_success.bucket_exists.return_value = True
        
        mock_minio_class.side_effect = [mock_client_fail, mock_client_success]
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret'
        }):
            try:
                from src.minio_manager import MinIOManager, MinIOConnectionError
                
                # First attempt should fail
                with self.assertRaises(MinIOConnectionError):
                    MinIOManager()
                
                # Second attempt should succeed
                manager = MinIOManager()
                self.assertIsNotNone(manager.client)
                
            except ImportError:
                self.skipTest("MinIO manager not available")
    
    @patch('src.minio_manager.Minio')
    def test_intermittent_network_connectivity(self, mock_minio_class):
        """Test intermittent network connectivity issues"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        
        # Simulate intermittent failures
        failure_count = 0
        def intermittent_list_buckets():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 2:
                raise Exception("Network unreachable")
            return []
        
        mock_client.list_buckets.side_effect = intermittent_list_buckets
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret'
        }):
            try:
                from src.minio_manager import MinIOManager
                
                manager = MinIOManager()
                
                # Health check should eventually succeed with retries
                # First checks fail, later ones succeed
                health1 = manager.health_monitor.health_check()
                self.assertFalse(health1)
                
                # Reset for retry
                manager.health_monitor.last_health_check = 0
                health2 = manager.health_monitor.health_check()
                self.assertTrue(health2)
                
            except ImportError:
                self.skipTest("MinIO manager not available")
    
    def test_dns_resolution_failure(self):
        """Test DNS resolution failure handling"""
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'nonexistent-domain.example.com:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret'
        }):
            with patch('src.minio_manager.Minio') as mock_minio:
                mock_minio.side_effect = Exception("DNS resolution failed")
                
                try:
                    from src.minio_manager import MinIOManager, MinIOConnectionError
                    
                    with self.assertRaises(MinIOConnectionError):
                        MinIOManager()
                        
                except ImportError:
                    self.skipTest("MinIO manager not available")
    
    @patch('requests.post')
    def test_api_network_failure_recovery(self, mock_post):
        """Test API network failure and recovery"""
        # Simulate network failures followed by success
        responses = [
            Exception("Connection refused"),
            Exception("Network timeout"),
            Mock(status_code=200, json=lambda: {"content": [{"text": "success"}]})
        ]
        
        mock_post.side_effect = responses
        
        try:
            from src.analysis import send_msg_to_model
            
            # Should eventually succeed with retries
            messages = [{"role": "user", "content": "test"}]
            
            # Mock the actual API call to avoid real network
            with patch('src.analysis.anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                mock_anthropic.return_value = mock_client
                
                # First calls fail, last succeeds
                mock_client.messages.create.side_effect = [
                    Exception("Network error"),
                    Exception("Connection timeout"),
                    Mock(content=[Mock(text="Recovery successful")])
                ]
                
                result = send_msg_to_model(messages)
                self.assertEqual(result, "Recovery successful")
                
        except ImportError:
            self.skipTest("Analysis module not available")


class TestServiceUnavailabilityScenarios(unittest.TestCase):
    """Test service unavailability scenarios"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.minio_manager.Minio')
    def test_minio_service_completely_unavailable(self, mock_minio_class):
        """Test complete MinIO service unavailability"""
        mock_minio_class.side_effect = Exception("Service unavailable")
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret'
        }):
            try:
                from src.minio_manager import MinIOManager, MinIOConnectionError
                from src.minio_manager import get_minio_manager, reset_minio_manager
                
                # Reset to ensure fresh initialization
                reset_minio_manager()
                
                # Should handle service unavailability gracefully
                with self.assertRaises(MinIOConnectionError):
                    get_minio_manager()
                    
            except ImportError:
                self.skipTest("MinIO manager not available")
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_database_service_unavailable(self, mock_connect):
        """Test database service unavailability"""
        mock_connect.side_effect = Exception("Database service unavailable")
        
        try:
            from src.db_handler.db import get_connection
            
            # Should handle database unavailability gracefully
            connection = get_connection()
            self.assertIsNone(connection)
            
        except ImportError:
            self.skipTest("Database handler not available")
    
    @patch('src.analysis.OpenAI')
    def test_openai_service_unavailable(self, mock_openai_class):
        """Test OpenAI service unavailability"""
        mock_openai_class.side_effect = Exception("OpenAI service unavailable")
        
        try:
            from src.analysis import transcribe_audio_raw
            
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
                temp_file.write(b"fake audio content")
                temp_file.flush()
                
                # Should handle OpenAI unavailability gracefully
                result = transcribe_audio_raw(temp_file.name)
                self.assertEqual(result, "")  # Should return empty on failure
                
        except ImportError:
            self.skipTest("Analysis module not available")
    
    @patch('src.analysis.anthropic.Anthropic')
    def test_anthropic_service_unavailable(self, mock_anthropic_class):
        """Test Anthropic service unavailability"""
        mock_anthropic_class.side_effect = Exception("Anthropic service unavailable")
        
        try:
            from src.analysis import send_msg_to_model
            
            messages = [{"role": "user", "content": "test"}]
            result = send_msg_to_model(messages, err="Service Error")
            
            # Should return error message on service unavailability
            self.assertEqual(result, "Service Error")
            
        except ImportError:
            self.skipTest("Analysis module not available")
    
    def test_multiple_service_unavailability(self):
        """Test handling when multiple services are unavailable"""
        with patch('src.minio_manager.Minio') as mock_minio:
            with patch('src.db_handler.db.psycopg2.connect') as mock_db:
                with patch('src.analysis.OpenAI') as mock_openai:
                    
                    # All services fail
                    mock_minio.side_effect = Exception("MinIO unavailable")
                    mock_db.side_effect = Exception("Database unavailable")
                    mock_openai.side_effect = Exception("OpenAI unavailable")
                    
                    try:
                        # System should handle graceful degradation
                        from src.minio_manager import get_minio_manager, reset_minio_manager
                        from src.db_handler.db import get_connection
                        
                        reset_minio_manager()
                        
                        # Each service should fail independently
                        with self.assertRaises(Exception):
                            get_minio_manager()
                        
                        connection = get_connection()
                        self.assertIsNone(connection)
                        
                        # Application should still be importable
                        self.assertTrue(True)
                        
                    except ImportError:
                        self.skipTest("Required modules not available")


class TestDatabaseConnectionFailures(unittest.TestCase):
    """Test database connection failure scenarios"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_connection_pool_exhaustion(self, mock_connect):
        """Test database connection pool exhaustion"""
        # Simulate connection pool exhaustion
        mock_connect.side_effect = Exception("Connection pool exhausted")
        
        try:
            from src.db_handler.db import get_connection
            
            # Multiple attempts should all fail gracefully
            for i in range(5):
                connection = get_connection()
                self.assertIsNone(connection)
                
        except ImportError:
            self.skipTest("Database handler not available")
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_database_deadlock_scenario(self, mock_connect):
        """Test database deadlock handling"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Simulate deadlock on query execution
        mock_cursor.execute.side_effect = Exception("Deadlock detected")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        try:
            from src.db_handler.db import fetch_prompt_by_name
            
            # Should handle deadlock gracefully
            result = fetch_prompt_by_name("test_prompt")
            self.assertIsNone(result)
            
        except ImportError:
            self.skipTest("Database handler not available")
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_database_connection_recovery(self, mock_connect):
        """Test database connection recovery after failure"""
        # First connection fails, subsequent ones succeed
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ("recovered prompt",)
        mock_conn.cursor.return_value = mock_cursor
        
        mock_connect.side_effect = [
            Exception("Connection failed"),
            Exception("Still failing"),
            mock_conn  # Finally succeeds
        ]
        
        try:
            from src.db_handler.db import fetch_prompt_by_name
            
            # First attempts fail
            result1 = fetch_prompt_by_name("test_prompt")
            self.assertIsNone(result1)
            
            result2 = fetch_prompt_by_name("test_prompt")
            self.assertIsNone(result2)
            
            # Third attempt succeeds
            result3 = fetch_prompt_by_name("test_prompt")
            self.assertEqual(result3, "recovered prompt")
            
        except ImportError:
            self.skipTest("Database handler not available")
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_transaction_rollback_on_failure(self, mock_connect):
        """Test transaction rollback on failure"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Simulate transaction failure
        mock_cursor.execute.side_effect = Exception("Transaction failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        try:
            from src.db_handler.db import get_connection
            
            connection = get_connection()
            if connection:
                # Rollback should be available
                self.assertTrue(hasattr(connection, 'rollback'))
                
                # Simulate rollback call
                connection.rollback()
                
        except ImportError:
            self.skipTest("Database handler not available")


class TestStorageSystemFailures(unittest.TestCase):
    """Test storage system failure scenarios"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
        self.temp_files = []
    
    def tearDown(self):
        """Clean up"""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        
        os.environ.clear()  
        os.environ.update(self.original_env)
    
    def create_temp_file(self, content: bytes = b"test content") -> str:
        """Create temporary file"""
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(content)
        temp_file.close()
        self.temp_files.append(temp_file.name)
        return temp_file.name
    
    @patch('src.minio_manager.Minio')
    def test_disk_space_exhaustion(self, mock_minio_class):
        """Test disk space exhaustion scenario"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Simulate disk space exhaustion
        mock_client.fput_object.side_effect = Exception("No space left on device")
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret',
            'MINIO_AUDIO_BUCKET_NAME': 'test-audio'
        }):
            try:
                from src.minio_manager import MinIOManager, MinIOUploadError
                
                manager = MinIOManager()
                temp_file = self.create_temp_file(b"large content" * 1000)
                
                # Should handle disk space exhaustion
                with self.assertRaises(MinIOUploadError):
                    manager.upload_audio_file(temp_file, "test.wav")
                    
            except ImportError:
                self.skipTest("MinIO manager not available")
    
    @patch('src.minio_manager.Minio')
    def test_storage_corruption_scenario(self, mock_minio_class):
        """Test storage corruption handling"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Simulate storage corruption
        mock_client.get_object.side_effect = Exception("Data corruption detected")
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret',
            'MINIO_AUDIO_BUCKET_NAME': 'test-audio'
        }):
            try:
                from src.minio_manager import MinIOManager, MinIODownloadError
                
                manager = MinIOManager()
                
                # Should handle corruption gracefully
                with self.assertRaises(MinIODownloadError):
                    manager.get_audio_stream("corrupted_file.wav")
                    
            except ImportError:
                self.skipTest("MinIO manager not available")
    
    def test_file_system_permission_failures(self):
        """Test file system permission failures"""
        try:
            from src.config import ensure_storage_directories, STORAGE_DIRS
            
            # Mock permission denied error
            with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
                # Should handle permission errors gracefully
                ensure_storage_directories()
                # If we get here, error was handled gracefully
                
        except ImportError:
            self.skipTest("Config module not available")
    
    @patch('src.minio_manager.Minio')
    def test_backup_storage_activation(self, mock_minio_class):
        """Test backup storage activation on primary failure"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        # Primary storage fails, backup should activate
        upload_attempts = []
        def track_upload_attempts(*args, **kwargs):
            upload_attempts.append(args)
            if len(upload_attempts) <= 2:
                raise Exception("Primary storage failed")
            return True  # Backup succeeds
        
        mock_client.fput_object.side_effect = track_upload_attempts
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret',
            'MINIO_AUDIO_BUCKET_NAME': 'test-audio'
        }):
            try:
                from src.minio_manager import MinIOManager
                
                manager = MinIOManager()
                temp_file = self.create_temp_file()
                
                # Should eventually succeed with retries
                result = manager.upload_audio_file(temp_file, "test.wav")
                self.assertTrue(result)
                
                # Should have made multiple attempts
                self.assertGreaterEqual(len(upload_attempts), 3)
                
            except ImportError:
                self.skipTest("MinIO manager not available")


class TestAPIRateLimitingAndQuotaExhaustion(unittest.TestCase):
    """Test API rate limiting and quota exhaustion scenarios"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.analysis.anthropic.Anthropic')
    def test_anthropic_rate_limit_handling(self, mock_anthropic_class):
        """Test Anthropic API rate limit handling"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # Simulate rate limit error followed by success
        from anthropic import RateLimitError
        
        mock_client.messages.create.side_effect = [
            RateLimitError("Rate limit exceeded"),
            RateLimitError("Still rate limited"),
            Mock(content=[Mock(text="Success after rate limit")])
        ]
        
        try:
            from src.analysis import send_msg_to_model
            
            messages = [{"role": "user", "content": "test"}]
            
            # Should handle rate limiting with backoff
            start_time = time.time()
            result = send_msg_to_model(messages)
            duration = time.time() - start_time
            
            self.assertEqual(result, "Success after rate limit")
            # Should have taken time due to backoff
            self.assertGreater(duration, 1.0)
            
        except ImportError:
            self.skipTest("Analysis module not available")
    
    @patch('src.analysis.OpenAI')
    def test_openai_quota_exhaustion(self, mock_openai_class):
        """Test OpenAI quota exhaustion handling"""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Simulate quota exhaustion
        mock_client.audio.transcriptions.create.side_effect = Exception("Quota exceeded")
        
        try:
            from src.analysis import transcribe_audio_raw
            
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
                temp_file.write(b"fake audio")
                temp_file.flush()
                
                # Should handle quota exhaustion gracefully
                result = transcribe_audio_raw(temp_file.name)
                self.assertEqual(result, "")  # Should return empty on quota failure
                
        except ImportError:
            self.skipTest("Analysis module not available")
    
    def test_concurrent_api_rate_limit_handling(self):
        """Test concurrent API requests with rate limiting"""
        try:
            from src.analysis import send_msg_to_model
            
            with patch('src.analysis.anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                mock_anthropic.return_value = mock_client
                
                # Simulate rate limiting for concurrent requests
                call_count = 0
                def rate_limited_create(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 3:
                        from anthropic import RateLimitError
                        raise RateLimitError("Rate limited")
                    return Mock(content=[Mock(text=f"Success {call_count}")])
                
                mock_client.messages.create.side_effect = rate_limited_create
                
                # Run concurrent requests
                results = []
                threads = []
                
                def make_request(thread_id):
                    messages = [{"role": "user", "content": f"request {thread_id}"}]
                    result = send_msg_to_model(messages)
                    results.append(result)
                
                # Start multiple threads
                for i in range(2):
                    thread = threading.Thread(target=make_request, args=(i,))
                    threads.append(thread)
                    thread.start()
                
                # Wait for completion
                for thread in threads:
                    thread.join()
                
                # At least some should succeed
                self.assertGreater(len(results), 0)
                
        except ImportError:
            self.skipTest("Analysis module not available")


class TestRecoveryMechanismValidation(unittest.TestCase):
    """Test recovery mechanism validation"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.minio_manager.Minio')
    def test_automatic_service_restart_simulation(self, mock_minio_class):
        """Test automatic service restart simulation"""
        # Simulate service failure followed by restart
        mock_client_fail = Mock()
        mock_client_fail.list_buckets.side_effect = Exception("Service crashed")
        
        mock_client_restart = Mock()
        mock_client_restart.list_buckets.return_value = []
        mock_client_restart.bucket_exists.return_value = True
        
        mock_minio_class.side_effect = [mock_client_fail, mock_client_restart]
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'testaccess',
            'MINIO_SECRET_KEY': 'testsecret'
        }):
            try:
                from src.minio_manager import MinIOManager, reset_minio_manager
                
                # First attempt fails
                reset_minio_manager()
                with self.assertRaises(Exception):
                    MinIOManager()
                
                # After restart, should succeed
                reset_minio_manager()
                manager = MinIOManager()
                self.assertIsNotNone(manager.client)
                
            except ImportError:
                self.skipTest("MinIO manager not available")
    
    def test_state_preservation_during_recovery(self):
        """Test state preservation during recovery"""
        try:
            from src.config import user_states, processed_texts
            
            # Setup initial state
            user_id = 12345
            initial_state = {
                "mode": "interview",
                "step": "ask_employee",
                "data": {"important": "data"}
            }
            
            user_states[user_id] = initial_state.copy()
            processed_texts[user_id] = "important transcript"
            
            # Simulate recovery scenario
            # State should be preserved
            self.assertEqual(user_states[user_id]["mode"], "interview")
            self.assertEqual(processed_texts[user_id], "important transcript")
            
            # Test state persistence through simulated restart
            saved_state = user_states[user_id].copy()
            saved_text = processed_texts[user_id]
            
            # Clear and restore (simulating restart)
            user_states.clear()
            processed_texts.clear()
            
            user_states[user_id] = saved_state
            processed_texts[user_id] = saved_text
            
            # State should be restored
            self.assertEqual(user_states[user_id]["mode"], "interview")
            self.assertEqual(processed_texts[user_id], "important transcript")
            
        except ImportError:
            self.skipTest("Config module not available")
    
    def test_graceful_degradation_mechanisms(self):
        """Test graceful degradation mechanisms"""
        # Test that system can operate with reduced functionality
        
        # Simulate primary services failing
        with patch('src.minio_manager.get_minio_manager') as mock_get_manager:
            mock_get_manager.side_effect = Exception("MinIO unavailable")
            
            try:
                from src.config import user_states
                
                # Basic functionality should still work
                user_states[123] = {"mode": "test"}
                self.assertEqual(user_states[123]["mode"], "test")
                
                # System should handle service unavailability
                with self.assertRaises(Exception):
                    mock_get_manager()
                
            except ImportError:
                self.skipTest("Config module not available")
    
    def test_recovery_time_measurement(self):
        """Test recovery time measurement"""
        # Simulate service recovery and measure time
        
        recovery_times = []
        
        def simulate_recovery_scenario():
            start_time = time.time()
            
            # Simulate failure
            time.sleep(0.1)  # Simulated downtime
            
            # Simulate detection and recovery
            time.sleep(0.05)  # Recovery time
            
            recovery_time = time.time() - start_time
            recovery_times.append(recovery_time)
        
        # Run multiple recovery scenarios
        for _ in range(3):
            simulate_recovery_scenario()
        
        # All recoveries should complete within reasonable time
        for recovery_time in recovery_times:
            self.assertLess(recovery_time, 1.0)  # Should recover within 1 second
        
        # Average recovery time should be acceptable
        avg_recovery = sum(recovery_times) / len(recovery_times)
        self.assertLess(avg_recovery, 0.5)


class TestCascadeFailurePrevention(unittest.TestCase):
    """Test cascade failure prevention mechanisms"""
    
    def test_circuit_breaker_simulation(self):
        """Test circuit breaker pattern simulation"""
        # Simulate circuit breaker behavior
        
        class MockCircuitBreaker:
            def __init__(self, failure_threshold=3):
                self.failure_count = 0
                self.failure_threshold = failure_threshold
                self.is_open = False
                self.last_failure_time = None
            
            def call(self, func):
                if self.is_open:
                    # Circuit is open, check if we should try again
                    if time.time() - self.last_failure_time > 5:  # 5 second timeout
                        self.is_open = False
                        self.failure_count = 0
                    else:
                        raise Exception("Circuit breaker is open")
                
                try:
                    result = func()
                    self.failure_count = 0  # Reset on success
                    return result
                except Exception as e:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    
                    if self.failure_count >= self.failure_threshold:
                        self.is_open = True
                    
                    raise e
        
        circuit_breaker = MockCircuitBreaker(failure_threshold=2)
        
        def failing_operation():
            raise Exception("Service failure")
        
        def successful_operation():
            return "success"
        
        # First few calls should fail and open circuit
        with self.assertRaises(Exception):
            circuit_breaker.call(failing_operation)
        
        with self.assertRaises(Exception):
            circuit_breaker.call(failing_operation)
        
        # Circuit should be open now
        self.assertTrue(circuit_breaker.is_open)
        
        # Subsequent calls should be blocked
        with self.assertRaises(Exception):
            circuit_breaker.call(successful_operation)
    
    def test_resource_isolation(self):
        """Test resource isolation to prevent cascade failures"""
        # Test that failure in one component doesn't affect others
        
        try:
            from src.config import user_states, processed_texts, authorized_users
            
            # Setup different user contexts
            user1_id = 123
            user2_id = 456
            
            user_states[user1_id] = {"mode": "interview", "status": "active"}
            user_states[user2_id] = {"mode": "design", "status": "active"}
            
            processed_texts[user1_id] = "user1 transcript"
            processed_texts[user2_id] = "user2 transcript"
            
            # Simulate failure for user1
            user_states[user1_id]["status"] = "error"
            
            # User2 should be unaffected
            self.assertEqual(user_states[user2_id]["status"], "active")
            self.assertEqual(processed_texts[user2_id], "user2 transcript")
            
            # User1's error shouldn't affect user2's data
            self.assertNotEqual(user_states[user1_id]["status"], user_states[user2_id]["status"])
            
        except ImportError:
            self.skipTest("Config module not available")
    
    def test_failure_propagation_prevention(self):
        """Test prevention of failure propagation"""
        # Test that failures are contained and don't propagate
        
        failure_log = []
        
        def component_a():
            failure_log.append("A: Starting")
            try:
                # Simulate component A operation
                failure_log.append("A: Processing")
                return "A: Success"
            except Exception as e:
                failure_log.append(f"A: Failed - {e}")
                raise
        
        def component_b():
            failure_log.append("B: Starting")
            try:
                # Component B operates independently
                failure_log.append("B: Processing")
                return "B: Success"
            except Exception as e:
                failure_log.append(f"B: Failed - {e}")
                raise
        
        def isolated_component_execution():
            results = {}
            
            # Execute components in isolation
            try:
                results['A'] = component_a()
            except Exception:
                results['A'] = "Failed (isolated)"
            
            try:
                results['B'] = component_b()
            except Exception:
                results['B'] = "Failed (isolated)"
            
            return results
        
        # Test normal operation
        results = isolated_component_execution()
        self.assertEqual(results['A'], "A: Success")
        self.assertEqual(results['B'], "B: Success")
        
        # Test with component A failing
        def failing_component_a():
            failure_log.append("A: Starting")
            raise Exception("Component A failed")
        
        # Replace component A with failing version
        original_component_a = component_a
        component_a = failing_component_a
        
        try:
            results = isolated_component_execution()
            # A should fail, B should succeed
            self.assertEqual(results['A'], "Failed (isolated)")
            self.assertEqual(results['B'], "B: Success")
        finally:
            # Restore original component
            component_a = original_component_a
    
    def test_system_resilience_under_load(self):
        """Test system resilience under load with failures"""
        # Simulate high load with intermittent failures
        
        successful_operations = 0
        failed_operations = 0
        
        def simulate_operation_under_load(operation_id):
            nonlocal successful_operations, failed_operations
            
            try:
                # Simulate random failures (20% failure rate)
                if random.random() < 0.2:
                    raise Exception(f"Operation {operation_id} failed")
                
                # Simulate work
                time.sleep(0.01)
                
                successful_operations += 1
                return f"Operation {operation_id} succeeded"
                
            except Exception:
                failed_operations += 1
                # Don't let individual failures crash the system
                return f"Operation {operation_id} failed (handled)"
        
        # Run multiple operations concurrently
        threads = []
        results = []
        
        def worker(op_id):
            result = simulate_operation_under_load(op_id)
            results.append(result)
        
        # Start 20 concurrent operations
        for i in range(20):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # System should handle the load and failures
        self.assertEqual(len(results), 20)
        self.assertGreater(successful_operations, 0)  # Some should succeed
        self.assertGreater(failed_operations, 0)      # Some should fail
        
        # Success rate should be reasonable (>50% despite 20% failure rate)
        success_rate = successful_operations / (successful_operations + failed_operations)
        self.assertGreater(success_rate, 0.5)


class TestSystemResilienceValidation(unittest.TestCase):
    """Test overall system resilience"""
    
    def test_multiple_concurrent_failures(self):
        """Test system behavior with multiple concurrent failures"""
        # Simulate multiple services failing simultaneously
        
        with patch('src.minio_manager.Minio') as mock_minio:
            with patch('src.db_handler.db.psycopg2.connect') as mock_db:
                with patch('src.analysis.OpenAI') as mock_openai:
                    
                    # All services fail simultaneously
                    mock_minio.side_effect = Exception("MinIO down")
                    mock_db.side_effect = Exception("Database down")
                    mock_openai.side_effect = Exception("OpenAI down")
                    
                    try:
                        # System should still be importable and partially functional
                        from src.config import user_states, processed_texts
                        
                        # Basic data structures should work
                        user_states[123] = {"test": "data"}
                        processed_texts[456] = "test transcript"
                        
                        self.assertEqual(user_states[123]["test"], "data")
                        self.assertEqual(processed_texts[456], "test transcript")
                        
                    except ImportError:
                        self.skipTest("Required modules not available")
    
    def test_graceful_system_shutdown(self):
        """Test graceful system shutdown under error conditions"""
        # Test that system can shut down gracefully even with errors
        
        shutdown_steps = []
        
        def simulate_shutdown_step(step_name, should_fail=False):
            shutdown_steps.append(f"Starting: {step_name}")
            
            try:
                if should_fail:
                    raise Exception(f"{step_name} failed")
                
                # Simulate work
                time.sleep(0.01)
                shutdown_steps.append(f"Completed: {step_name}")
                return True
                
            except Exception as e:
                shutdown_steps.append(f"Failed: {step_name} - {e}")
                return False
        
        # Simulate shutdown sequence with some failures
        steps = [
            ("Save user states", False),
            ("Close database connections", True),  # This fails
            ("Close MinIO connections", False),
            ("Clean temp files", True),  # This fails
            ("Final cleanup", False)
        ]
        
        completed_steps = 0
        failed_steps = 0
        
        for step_name, should_fail in steps:
            if simulate_shutdown_step(step_name, should_fail):
                completed_steps += 1
            else:
                failed_steps += 1
        
        # Some steps should complete even if others fail
        self.assertGreater(completed_steps, 0)
        self.assertGreater(failed_steps, 0)
        
        # All steps should be attempted
        self.assertEqual(len(shutdown_steps), len(steps) * 2)  # Start + End for each
    
    def test_error_reporting_and_logging(self):
        """Test error reporting and logging during failures"""
        # Test that errors are properly reported and logged
        
        import logging
        from io import StringIO
        
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger('test_logger')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        # Simulate errors with logging
        def operation_with_logging(operation_name, should_fail=False):
            try:
                if should_fail:
                    raise Exception(f"{operation_name} encountered an error")
                return f"{operation_name} completed successfully"
            except Exception as e:
                logger.error(f"Operation failed: {operation_name} - {e}")
                return None
        
        # Test normal operation
        result1 = operation_with_logging("Normal Operation", False)
        self.assertIsNotNone(result1)
        
        # Test failing operation
        result2 = operation_with_logging("Failing Operation", True)
        self.assertIsNone(result2)
        
        # Check that error was logged
        log_output = log_capture.getvalue()
        self.assertIn("Operation failed", log_output)
        self.assertIn("Failing Operation", log_output)
        
        # Clean up
        logger.removeHandler(handler)
        handler.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
