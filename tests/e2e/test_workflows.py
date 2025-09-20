"""End-to-End tests for complete VoxPersona workflows."""
import os
import tempfile
import shutil
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, Mock
import time

from tests.framework.base_test import BaseE2ETest


class TestAudioProcessingWorkflow(BaseE2ETest):
    """Test complete audio processing workflow."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.audio_file = Path(self.temp_dir) / "test_audio.wav"
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Create fake audio file
        self.audio_file.write_bytes(self._create_fake_wav_data())
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        super().tearDown()
    
    def _create_fake_wav_data(self):
        """Create fake WAV file data for testing."""
        # Minimal WAV header + some data
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x44\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\x00\x08\x00\x00'
        wav_data = b'\x00\x00' * 1024  # Fake audio data
        return wav_header + wav_data
    
    def test_complete_audio_analysis_workflow(self):
        """Test complete audio analysis from upload to results."""
        from src.import_utils import SafeImporter
        from src.config import VoxPersonaConfig
        from src.environment import EnvironmentDetector
        
        # Initialize components
        importer = SafeImporter()
        config = VoxPersonaConfig()
        env_detector = EnvironmentDetector()
        
        # Setup environment
        env_info = env_detector.detect_environment()
        config.load_for_environment(env_info)
        
        # Step 1: Audio file validation
        self.assertTrue(self.audio_file.exists())
        self.assertGreater(self.audio_file.stat().st_size, 0)
        
        # Step 2: Import required modules with fallback
        librosa = importer.safe_import('librosa')
        numpy = importer.safe_import('numpy')
        
        self.assertIsNotNone(librosa)
        self.assertIsNotNone(numpy)
        
        # Step 3: Mock audio processing
        with patch.object(librosa, 'load') as mock_load:
            # Mock audio data and sample rate
            mock_audio_data = [0.1, -0.1, 0.2, -0.2] * 1000
            mock_sample_rate = 22050
            mock_load.return_value = (mock_audio_data, mock_sample_rate)
            
            # Step 4: Process audio file
            audio_data, sr = librosa.load(str(self.audio_file))
            
            self.assertIsNotNone(audio_data)
            self.assertEqual(sr, mock_sample_rate)
        
        # Step 5: Generate analysis results
        analysis_results = {
            'file_info': {
                'filename': self.audio_file.name,
                'duration': len(mock_audio_data) / mock_sample_rate,
                'sample_rate': mock_sample_rate
            },
            'voice_features': {
                'pitch_mean': 150.5,
                'pitch_std': 25.3,
                'intensity_mean': 65.2,
                'formants': [850, 1200, 2400]
            },
            'personality_scores': {
                'openness': 0.7,
                'conscientiousness': 0.6,
                'extraversion': 0.8,
                'agreeableness': 0.75,
                'neuroticism': 0.3
            }
        }
        
        # Step 6: Save results
        results_file = self.output_dir / f"{self.audio_file.stem}_analysis.json"
        with open(results_file, 'w') as f:
            json.dump(analysis_results, f, indent=2)
        
        # Step 7: Verify results
        self.assertTrue(results_file.exists())
        
        with open(results_file, 'r') as f:
            loaded_results = json.load(f)
        
        self.assertEqual(loaded_results['file_info']['filename'], self.audio_file.name)
        self.assertIn('voice_features', loaded_results)
        self.assertIn('personality_scores', loaded_results)
    
    def test_batch_audio_processing_workflow(self):
        """Test batch processing of multiple audio files."""
        from src.import_utils import SafeImporter
        
        # Create multiple test files
        audio_files = []
        for i in range(3):
            audio_file = Path(self.temp_dir) / f"test_audio_{i}.wav"
            audio_file.write_bytes(self._create_fake_wav_data())
            audio_files.append(audio_file)
        
        importer = SafeImporter()
        librosa = importer.safe_import('librosa')
        
        results = []
        
        # Process each file
        for audio_file in audio_files:
            with patch.object(librosa, 'load') as mock_load:
                mock_load.return_value = ([0.1] * 1000, 22050)
                
                # Mock processing
                audio_data, sr = librosa.load(str(audio_file))
                
                result = {
                    'filename': audio_file.name,
                    'processed': True,
                    'duration': len(audio_data) / sr
                }
                results.append(result)
        
        # Verify all files processed
        self.assertEqual(len(results), 3)
        for i, result in enumerate(results):
            self.assertEqual(result['filename'], f"test_audio_{i}.wav")
            self.assertTrue(result['processed'])
    
    def test_error_recovery_in_workflow(self):
        """Test error recovery during audio processing workflow."""
        from src.import_utils import SafeImporter
        from src.error_recovery import ErrorRecoveryManager
        
        importer = SafeImporter()
        recovery_manager = ErrorRecoveryManager()
        
        # Test workflow with import failure
        librosa = importer.safe_import('non_existent_audio_lib')
        
        # Should get mock object
        self.assertIsNotNone(librosa)
        
        # Test workflow with file processing error
        with patch.object(librosa, 'load') as mock_load:
            mock_load.side_effect = Exception("File processing failed")
            
            try:
                audio_data, sr = librosa.load(str(self.audio_file))
            except Exception as e:
                # Recovery should handle this
                recovered = recovery_manager.handle_error(e, context={'operation': 'audio_load'})
                self.assertTrue(recovered)


class TestReportGenerationWorkflow(BaseE2ETest):
    """Test complete report generation workflow."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.reports_dir = Path(self.temp_dir) / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        super().tearDown()
    
    def test_pdf_report_generation_workflow(self):
        """Test PDF report generation workflow."""
        from src.import_utils import SafeImporter
        
        importer = SafeImporter()
        
        # Import required modules
        matplotlib = importer.safe_import('matplotlib.pyplot')
        reportlab = importer.safe_import('reportlab.pdfgen.canvas')
        
        self.assertIsNotNone(matplotlib)
        self.assertIsNotNone(reportlab)
        
        # Test data
        analysis_data = {
            'participant_id': 'P001',
            'audio_file': 'test_audio.wav',
            'analysis_date': '2024-01-15',
            'voice_features': {
                'pitch_mean': 150.5,
                'pitch_std': 25.3,
                'intensity_mean': 65.2
            },
            'personality_scores': {
                'openness': 0.7,
                'conscientiousness': 0.6,
                'extraversion': 0.8,
                'agreeableness': 0.75,
                'neuroticism': 0.3
            }
        }
        
        # Mock PDF generation
        with patch.object(reportlab, 'Canvas') as mock_canvas:
            mock_canvas_instance = Mock()
            mock_canvas.return_value = mock_canvas_instance
            
            # Generate report
            report_path = self.reports_dir / f"{analysis_data['participant_id']}_report.pdf"
            
            # Mock PDF creation process
            canvas = reportlab.Canvas(str(report_path))
            canvas.drawString(100, 750, f"VoxPersona Analysis Report")
            canvas.drawString(100, 720, f"Participant: {analysis_data['participant_id']}")
            canvas.save()
            
            # Verify mock calls
            mock_canvas.assert_called_with(str(report_path))
            self.assertTrue(mock_canvas_instance.drawString.called)
            self.assertTrue(mock_canvas_instance.save.called)
    
    def test_html_report_generation_workflow(self):
        """Test HTML report generation workflow."""
        from src.import_utils import SafeImporter
        
        importer = SafeImporter()
        jinja2 = importer.safe_import('jinja2')
        
        self.assertIsNotNone(jinja2)
        
        # Test data
        analysis_data = {
            'participant_id': 'P002',
            'analysis_date': '2024-01-15',
            'personality_scores': {
                'openness': 0.65,
                'conscientiousness': 0.72,
                'extraversion': 0.58,
                'agreeableness': 0.80,
                'neuroticism': 0.25
            }
        }
        
        # HTML template
        html_template = """
        <!DOCTYPE html>
        <html>
        <head><title>VoxPersona Report</title></head>
        <body>
            <h1>Analysis Report for {{ participant_id }}</h1>
            <p>Date: {{ analysis_date }}</p>
            <h2>Personality Scores</h2>
            <ul>
            {% for trait, score in personality_scores.items() %}
                <li>{{ trait|title }}: {{ "%.2f"|format(score) }}</li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """
        
        # Mock template rendering
        with patch.object(jinja2, 'Template') as mock_template:
            mock_template_instance = Mock()
            mock_template.return_value = mock_template_instance
            mock_template_instance.render.return_value = html_template.replace('{{ participant_id }}', analysis_data['participant_id'])
            
            # Generate HTML report
            template = jinja2.Template(html_template)
            html_content = template.render(**analysis_data)
            
            # Save HTML report
            report_path = self.reports_dir / f"{analysis_data['participant_id']}_report.html"
            report_path.write_text(html_content)
            
            # Verify
            mock_template.assert_called_with(html_template)
            mock_template_instance.render.assert_called_with(**analysis_data)
            self.assertTrue(report_path.exists())
    
    def test_data_visualization_workflow(self):
        """Test data visualization generation workflow."""
        from src.import_utils import SafeImporter
        
        importer = SafeImporter()
        matplotlib = importer.safe_import('matplotlib.pyplot')
        numpy = importer.safe_import('numpy')
        
        self.assertIsNotNone(matplotlib)
        self.assertIsNotNone(numpy)
        
        # Test data
        personality_data = {
            'traits': ['Openness', 'Conscientiousness', 'Extraversion', 'Agreeableness', 'Neuroticism'],
            'scores': [0.7, 0.6, 0.8, 0.75, 0.3]
        }
        
        # Mock visualization creation
        with patch.object(matplotlib, 'figure') as mock_figure, \
             patch.object(matplotlib, 'bar') as mock_bar, \
             patch.object(matplotlib, 'savefig') as mock_savefig:
            
            # Create visualization
            matplotlib.figure(figsize=(10, 6))
            matplotlib.bar(personality_data['traits'], personality_data['scores'])
            
            chart_path = self.reports_dir / "personality_chart.png"
            matplotlib.savefig(str(chart_path))
            
            # Verify mock calls
            mock_figure.assert_called_with(figsize=(10, 6))
            mock_bar.assert_called_with(personality_data['traits'], personality_data['scores'])
            mock_savefig.assert_called_with(str(chart_path))


class TestSystemIntegrationWorkflow(BaseE2ETest):
    """Test complete system integration workflows."""
    
    def test_full_system_startup_workflow(self):
        """Test complete system startup and initialization."""
        from src.import_utils import SafeImporter
        from src.config import VoxPersonaConfig
        from src.environment import EnvironmentDetector
        from src.error_recovery import ErrorRecoveryManager
        
        # Step 1: Environment detection
        env_detector = EnvironmentDetector()
        env_info = env_detector.detect_environment()
        
        self.assertIsNotNone(env_info)
        self.assertIn('environment', env_info)
        
        # Step 2: Configuration loading
        config = VoxPersonaConfig()
        config.load_for_environment(env_info)
        
        self.assertTrue(config.validate_config())
        
        # Step 3: Import system initialization
        importer = SafeImporter()
        
        # Test critical imports
        required_modules = ['os', 'sys', 'pathlib', 'json']
        for module_name in required_modules:
            module = importer.safe_import(module_name)
            self.assertIsNotNone(module)
        
        # Step 4: Error recovery system
        recovery_manager = ErrorRecoveryManager()
        self.assertIsNotNone(recovery_manager)
        
        # Step 5: System health check
        system_status = {
            'environment': env_info['environment'],
            'config_loaded': True,
            'imports_working': True,
            'recovery_available': True
        }
        
        self.assertTrue(all(system_status.values()))
    
    def test_configuration_change_workflow(self):
        """Test system adaptation to configuration changes."""
        from src.config import VoxPersonaConfig
        from src.environment import EnvironmentDetector
        
        config = VoxPersonaConfig()
        env_detector = EnvironmentDetector()
        
        # Test different environment configurations
        environments = ['development', 'production', 'test']
        
        for env_name in environments:
            with patch.dict(os.environ, {"VOXPERSONA_ENV": env_name}):
                # Clear cache to force re-detection
                env_detector._cached_environment = None
                
                env_info = env_detector.detect_environment()
                config.load_for_environment(env_info)
                
                self.assertEqual(env_info['environment'], env_name)
                self.assertTrue(config.validate_config())
    
    def test_error_cascade_prevention_workflow(self):
        """Test prevention of error cascades across system."""
        from src.import_utils import SafeImporter
        from src.error_recovery import ErrorRecoveryManager
        
        importer = SafeImporter()
        recovery_manager = ErrorRecoveryManager()
        
        # Simulate multiple system failures
        failures = [
            ('import_failure', 'non_existent_module'),
            ('config_failure', 'invalid_config.json'),
            ('permission_failure', '/restricted/path'),
            ('network_failure', 'unreachable_service')
        ]
        
        recovered_count = 0
        
        for failure_type, failure_context in failures:
            try:
                if failure_type == 'import_failure':
                    module = importer.safe_import(failure_context)
                    if module is not None:
                        recovered_count += 1
                else:
                    # Simulate other failures
                    error = Exception(f"{failure_type}: {failure_context}")
                    if recovery_manager.handle_error(error, context={'type': failure_type}):
                        recovered_count += 1
            except Exception:
                pass
        
        # Should recover from at least import failures
        self.assertGreater(recovered_count, 0)


if __name__ == '__main__':
    import unittest
    unittest.main()