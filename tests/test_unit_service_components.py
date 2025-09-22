"""
Unit Tests for Service Components

This module provides comprehensive testing of VoxPersona service components including:
- MinIO Manager service validation
- Analysis service component testing
- Handler service functionality
- Database service component testing
- Audio processing service validation
"""

import unittest
import sys
import os
import tempfile
import time
import io
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timedelta
from typing import Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tests.test_config import get_test_config


class TestMinIOManagerServiceValidation(unittest.TestCase):
    """Test MinIO Manager service component"""
    
    def setUp(self):
        """Setup test environment"""
        self.test_config = get_test_config()
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.minio_manager.Minio')
    def test_minio_manager_initialization(self, mock_minio_class):
        """Test MinIO manager initialization"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        from src.minio_manager import MinIOManager
        
        manager = MinIOManager()
        
        self.assertIsNotNone(manager.client)
        self.assertIsNotNone(manager.health_monitor)
        self.assertIsNotNone(manager.retry_handler)
    
    @patch('src.minio_manager.Minio')
    def test_minio_configuration_validation(self, mock_minio_class):
        """Test MinIO configuration validation"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        
        from src.minio_manager import MinIOManager, MinIOConnectionError
        
        # Test with missing configuration
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MinIOConnectionError):
                MinIOManager()
    
    @patch('src.minio_manager.Minio')
    def test_bucket_creation_validation(self, mock_minio_class):
        """Test bucket creation validation"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = False
        
        from src.minio_manager import MinIOManager
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'test',
            'MINIO_SECRET_KEY': 'test',
            'MINIO_BUCKET_NAME': 'test-bucket',
            'MINIO_AUDIO_BUCKET_NAME': 'test-audio'
        }):
            manager = MinIOManager()
            
            # Should attempt to create both buckets
            self.assertGreaterEqual(mock_client.make_bucket.call_count, 2)
    
    @patch('src.minio_manager.Minio')
    def test_health_monitoring_functionality(self, mock_minio_class):
        """Test health monitoring functionality"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        from src.minio_manager import MinIOManager
        
        with patch.dict(os.environ, {
            'MINIO_ENDPOINT': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'test',
            'MINIO_SECRET_KEY': 'test'
        }):
            manager = MinIOManager()
            
            # Test health check
            health_status = manager.health_monitor.health_check()
            self.assertIsInstance(health_status, bool)
            
            # Test metrics recording
            manager.health_monitor.record_operation('upload', True, 1.5, 1024)
            metrics = manager.health_monitor.get_health_report()
            
            self.assertIn('is_healthy', metrics)
            self.assertIn('metrics', metrics)
    
    @patch('src.minio_manager.Minio')
    def test_retry_mechanism_functionality(self, mock_minio_class):
        """Test retry mechanism functionality"""
        mock_client = Mock()
        mock_minio_class.return_value = mock_client
        mock_client.list_buckets.return_value = []
        mock_client.bucket_exists.return_value = True
        
        from src.minio_manager import RetryableMinIOOperation
        
        retry_handler = RetryableMinIOOperation(max_retries=3)
        
        # Test successful operation (no retries needed)
        def success_operation():
            return "success"
        
        result = retry_handler.execute_with_retry(success_operation)
        self.assertEqual(result, "success")
        
        # Test operation that fails then succeeds
        call_count = 0
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = retry_handler.execute_with_retry(flaky_operation)
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)


class TestAnalysisServiceComponents(unittest.TestCase):
    """Test analysis service components"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.analysis.OpenAI')
    def test_transcription_service_validation(self, mock_openai):
        """Test transcription service validation"""
        # Mock OpenAI client and response
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        mock_response = Mock()
        mock_response.text = "transcribed text"
        mock_client.audio.transcriptions.create.return_value = mock_response
        
        with patch('src.analysis.AudioSegment') as mock_audio:
            mock_segment = Mock()
            mock_segment.__len__ = Mock(return_value=60000)  # 1 minute
            mock_segment.__getitem__ = Mock(return_value=mock_segment)
            mock_audio.from_file.return_value = mock_segment
            
            # Mock export
            mock_segment.export = Mock()
            
            from src.analysis import transcribe_audio_raw
            
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
                result = transcribe_audio_raw(temp_file.name)
                self.assertIsInstance(result, str)
    
    @patch('src.analysis.anthropic.Anthropic')
    def test_analysis_service_validation(self, mock_anthropic):
        """Test analysis service validation"""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "analysis result"
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        
        from src.analysis import send_msg_to_model
        
        messages = [{"role": "user", "content": "test message"}]
        result = send_msg_to_model(messages)
        
        self.assertEqual(result, "analysis result")
        mock_client.messages.create.assert_called_once()
    
    def test_token_counting_functionality(self):
        """Test token counting functionality"""
        from src.utils import count_tokens
        
        test_text = "This is a test message for token counting."
        token_count = count_tokens(test_text)
        
        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)
    
    @patch('src.analysis.anthropic.Anthropic')
    def test_error_handling_in_analysis(self, mock_anthropic):
        """Test error handling in analysis service"""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Error")
        
        from src.analysis import send_msg_to_model
        
        messages = [{"role": "user", "content": "test message"}]
        result = send_msg_to_model(messages, err="Test Error")
        
        self.assertEqual(result, "Test Error")


class TestHandlerServiceComponents(unittest.TestCase):
    """Test handler service components"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dirs = []
    
    def tearDown(self):
        """Clean up temporary directories"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
    
    def create_temp_dir(self) -> str:
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def test_user_state_management(self):
        """Test user state management functionality"""
        from src.config import user_states
        
        # Clear user states
        user_states.clear()
        
        # Test state creation
        user_id = 12345
        user_states[user_id] = {
            "mode": "interview",
            "step": "ask_employee",
            "data": {}
        }
        
        self.assertIn(user_id, user_states)
        self.assertEqual(user_states[user_id]["mode"], "interview")
        
        # Test state modification
        user_states[user_id]["step"] = "confirm_data"
        self.assertEqual(user_states[user_id]["step"], "confirm_data")
    
    def test_processed_texts_management(self):
        """Test processed texts management"""
        from src.config import processed_texts
        
        # Clear processed texts
        processed_texts.clear()
        
        # Test text storage
        user_id = 12345
        test_text = "This is a test transcription"
        processed_texts[user_id] = test_text
        
        self.assertIn(user_id, processed_texts)
        self.assertEqual(processed_texts[user_id], test_text)
    
    def test_authorization_management(self):
        """Test authorization management"""
        from src.config import authorized_users
        
        # Test user authorization
        user_id = 12345
        authorized_users.add(user_id)
        
        self.assertIn(user_id, authorized_users)
        
        # Test user deauthorization
        authorized_users.remove(user_id)
        self.assertNotIn(user_id, authorized_users)
    
    def test_menu_management(self):
        """Test menu management functionality"""
        from src.config import active_menus
        
        # Clear active menus
        active_menus.clear()
        
        # Test menu registration
        user_id = 12345
        message_id = 67890
        active_menus[user_id] = [message_id]
        
        self.assertIn(user_id, active_menus)
        self.assertIn(message_id, active_menus[user_id])


class TestDatabaseServiceComponents(unittest.TestCase):
    """Test database service components"""
    
    def setUp(self):
        """Setup test environment"""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore environment"""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_database_connection_validation(self, mock_connect):
        """Test database connection validation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        from src.db_handler.db import get_connection
        
        connection = get_connection()
        self.assertIsNotNone(connection)
        mock_connect.assert_called_once()
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_prompt_fetching_functionality(self, mock_connect):
        """Test prompt fetching functionality"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ("test prompt content",)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        from src.db_handler.db import fetch_prompt_by_name
        
        result = fetch_prompt_by_name("test_prompt")
        self.assertEqual(result, "test prompt content")
    
    @patch('src.db_handler.db.psycopg2.connect')
    def test_database_error_handling(self, mock_connect):
        """Test database error handling"""
        mock_connect.side_effect = Exception("Connection failed")
        
        from src.db_handler.db import get_connection
        
        # Should handle connection errors gracefully
        connection = get_connection()
        self.assertIsNone(connection)


class TestAudioProcessingServiceComponents(unittest.TestCase):
    """Test audio processing service components"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_files = []
    
    def tearDown(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def create_temp_file(self, content: bytes = b"fake audio content") -> str:
        """Create temporary file"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.write(content)
        temp_file.close()
        self.temp_files.append(temp_file.name)
        return temp_file.name
    
    def test_audio_file_validation(self):
        """Test audio file validation functionality"""
        from src.audio_utils import define_audio_file_params
        
        # Mock Pyrogram message with audio
        mock_message = Mock()
        mock_message.audio = Mock()
        mock_message.audio.file_size = 1024
        mock_message.voice = None
        mock_message.document = None
        
        file_size = define_audio_file_params(mock_message)
        self.assertEqual(file_size, 1024)
    
    def test_audio_filename_extraction(self):
        """Test audio filename extraction"""
        from src.audio_utils import extract_audio_filename
        
        # Mock message with voice
        mock_message = Mock()
        mock_message.voice = Mock()
        mock_message.voice.file_unique_id = "unique123"
        mock_message.audio = None
        mock_message.document = None
        
        filename = extract_audio_filename(mock_message)
        self.assertIn("unique123", filename)
        self.assertTrue(filename.endswith(".ogg"))
    
    def test_audio_size_validation(self):
        """Test audio size validation"""
        from src.validators import check_audio_file_size
        
        # Mock app for testing
        mock_app = Mock()
        
        # Test valid file size
        try:
            check_audio_file_size(1024, 2048, 123, mock_app)
        except ValueError:
            self.fail("Should not raise exception for valid file size")
        
        # Test invalid file size
        with self.assertRaises(ValueError):
            check_audio_file_size(2048, 1024, 123, mock_app)
    
    @patch('src.audio_utils.transcribe_audio')
    def test_transcription_and_save_functionality(self, mock_transcribe):
        """Test transcription and save functionality"""
        mock_transcribe.return_value = "transcribed text"
        
        from src.audio_utils import transcribe_audio_and_save
        from src.config import processed_texts
        
        temp_file = self.create_temp_file()
        user_id = 123
        
        result = transcribe_audio_and_save(temp_file, user_id, processed_texts)
        
        self.assertEqual(result, "transcribed text")
        self.assertIn(user_id, processed_texts)
        self.assertEqual(processed_texts[user_id], "transcribed text")


class TestStorageServiceComponents(unittest.TestCase):
    """Test storage service components"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dirs = []
    
    def tearDown(self):
        """Clean up temporary directories"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
    
    def create_temp_dir(self) -> str:
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def test_safe_filename_generation(self):
        """Test safe filename generation"""
        from src.storage import safe_filename
        
        # Test various problematic filenames
        test_cases = [
            ("file with spaces.txt", "file_with_spaces.txt"),
            ("file/with/slashes.txt", "file_with_slashes.txt"),
            ("file<>with:chars.txt", "file__with_chars.txt"),
            ("файл.txt", "файл.txt"),  # Unicode should be preserved
        ]
        
        for original, expected_pattern in test_cases:
            with self.subTest(filename=original):
                safe_name = safe_filename(original)
                self.assertIsInstance(safe_name, str)
                self.assertNotIn("/", safe_name)
                self.assertNotIn("\\", safe_name)
    
    def test_file_finding_functionality(self):
        """Test file finding functionality"""
        from src.storage import find_real_filename
        
        temp_dir = self.create_temp_dir()
        
        # Create test file
        test_filename = "test_file.txt"
        test_path = os.path.join(temp_dir, test_filename)
        with open(test_path, 'w') as f:
            f.write("test content")
        
        # Test finding existing file
        found_file = find_real_filename(temp_dir, test_filename)
        self.assertEqual(found_file, test_filename)
        
        # Test finding non-existent file
        not_found = find_real_filename(temp_dir, "nonexistent.txt")
        self.assertIsNone(not_found)
    
    def test_temporary_file_cleanup(self):
        """Test temporary file cleanup functionality"""
        from src.storage import delete_tmp_params
        
        # Create temporary file
        temp_file = self.create_temp_file()
        temp_dir = os.path.dirname(temp_file)
        
        # Mock message and app
        mock_msg = Mock()
        mock_msg.id = 123
        mock_app = Mock()
        
        # Test cleanup
        delete_tmp_params(mock_msg, temp_file, temp_dir, 456, mock_app)
        
        # File should be cleaned up
        self.assertFalse(os.path.exists(temp_file))
    
    def create_temp_file(self, content: str = "test content") -> str:
        """Create temporary file"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name


class TestServiceIntegrationValidation(unittest.TestCase):
    """Test service integration validation"""
    
    def test_service_dependency_chain(self):
        """Test service dependency chain validation"""
        # Test that services can be imported in correct order
        import_order = [
            'src.config',
            'src.minio_manager',
            'src.analysis',
            'src.handlers'
        ]
        
        imported_modules = []
        
        for module_name in import_order:
            try:
                module = __import__(module_name, fromlist=[''])
                imported_modules.append(module_name)
                self.assertIsNotNone(module)
            except ImportError as e:
                self.fail(f"Failed to import {module_name} in service chain: {e}")
        
        self.assertEqual(len(imported_modules), len(import_order))
    
    def test_service_communication_interfaces(self):
        """Test service communication interfaces"""
        try:
            # Test that services can communicate
            from src.minio_manager import get_minio_manager
            from src.config import processed_texts, user_states
            
            # Services should be accessible
            self.assertIsNotNone(get_minio_manager)
            self.assertIsInstance(processed_texts, dict)
            self.assertIsInstance(user_states, dict)
            
        except ImportError as e:
            self.fail(f"Service communication interface failed: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)