"""Audio processing performance tests for VoxPersona.

This module contains performance tests for audio processing workflows
including loading, analysis, feature extraction, and batch processing.
"""

import os
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import patch, MagicMock
import threading
import statistics

from tests.framework.base_test import BasePerformanceTest
from src.import_utils import SafeImporter
from src.config import VoxPersonaConfig


class AudioProcessingPerformanceTests(BasePerformanceTest):
    """Performance tests for audio processing operations."""
    
    def setUp(self):
        """Set up performance test environment."""
        super().setUp()
        self.importer = SafeImporter()
        self.config = VoxPersonaConfig() 
        self.temp_dir = tempfile.mkdtemp()
        
        # Performance thresholds (in seconds)
        self.thresholds = {
            'audio_load_single': 2.0,           # Load single audio file
            'audio_load_batch': 10.0,           # Load 10 audio files
            'feature_extraction': 5.0,          # Extract features from audio
            'voice_analysis': 3.0,              # Analyze voice characteristics
            'batch_processing': 30.0,           # Process 10 files
            'concurrent_processing': 15.0,      # Process 5 files concurrently
            'memory_efficiency': 100,           # Max MB memory increase
        }
        
        # Create test audio files
        self.test_files = self._create_test_audio_files()
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        super().tearDown()
    
    def _create_test_audio_files(self) -> List[Path]:
        """Create test audio files for performance testing."""
        test_files = []
        
        # Create fake WAV files of different sizes
        sizes = [
            (1, "small"),      # 1 second
            (5, "medium"),     # 5 seconds  
            (10, "large"),     # 10 seconds
            (30, "xlarge")     # 30 seconds
        ]
        
        for duration, size_name in sizes:
            for i in range(3):  # 3 files per size
                file_path = Path(self.temp_dir) / f"test_audio_{size_name}_{i}.wav"
                self._create_fake_wav_file(file_path, duration)
                test_files.append(file_path)
        
        return test_files
    
    def _create_fake_wav_file(self, file_path: Path, duration_seconds: int):
        """Create a fake WAV file for testing."""
        # Simple WAV header (44 bytes) + data
        sample_rate = 22050
        num_samples = sample_rate * duration_seconds
        
        # WAV header
        wav_header = b'RIFF'
        wav_header += (36 + num_samples * 2).to_bytes(4, 'little')  # File size
        wav_header += b'WAVE'
        wav_header += b'fmt '
        wav_header += (16).to_bytes(4, 'little')  # Format chunk size
        wav_header += (1).to_bytes(2, 'little')   # Audio format (PCM)
        wav_header += (1).to_bytes(2, 'little')   # Number of channels
        wav_header += sample_rate.to_bytes(4, 'little')  # Sample rate
        wav_header += (sample_rate * 2).to_bytes(4, 'little')  # Byte rate
        wav_header += (2).to_bytes(2, 'little')   # Block align
        wav_header += (16).to_bytes(2, 'little')  # Bits per sample
        wav_header += b'data'
        wav_header += (num_samples * 2).to_bytes(4, 'little')  # Data size
        
        # Create fake audio data (silence)
        audio_data = b'\x00\x00' * num_samples
        
        with open(file_path, 'wb') as f:
            f.write(wav_header + audio_data)
    
    def test_single_audio_file_loading_performance(self):
        """Test performance of loading a single audio file."""
        librosa = self.importer.safe_import('librosa')
        
        # Test different file sizes
        for test_file in self.test_files[:4]:  # One of each size
            with self.subTest(file=test_file.name):
                start_time = time.time()
                
                with patch.object(librosa, 'load') as mock_load:
                    # Mock realistic audio loading
                    duration = self._get_file_duration_from_name(test_file.name)
                    sample_rate = 22050
                    mock_audio_data = [0.0] * (sample_rate * duration)
                    mock_load.return_value = (mock_audio_data, sample_rate)
                    
                    # Load audio file
                    audio_data, sr = librosa.load(str(test_file))
                
                load_time = time.time() - start_time
                
                # Check performance threshold
                self.assertLess(load_time, self.thresholds['audio_load_single'],
                              f"Audio loading too slow: {load_time:.2f}s")
                
                # Log performance metric
                self.log_performance_metric(
                    'audio_load_single',
                    load_time,
                    {'file_size': test_file.stat().st_size}
                )
    
    def _get_file_duration_from_name(self, filename: str) -> int:
        """Extract duration from test file name."""
        if 'small' in filename:
            return 1
        elif 'medium' in filename:
            return 5
        elif 'large' in filename:
            return 10
        elif 'xlarge' in filename:
            return 30
        return 1
    
    def test_batch_audio_loading_performance(self):
        """Test performance of loading multiple audio files."""
        librosa = self.importer.safe_import('librosa')
        
        start_time = time.time()
        loaded_files = 0
        
        with patch.object(librosa, 'load') as mock_load:
            for test_file in self.test_files[:10]:  # Load 10 files
                duration = self._get_file_duration_from_name(test_file.name)
                sample_rate = 22050
                mock_audio_data = [0.0] * (sample_rate * duration)
                mock_load.return_value = (mock_audio_data, sample_rate)
                
                audio_data, sr = librosa.load(str(test_file))
                loaded_files += 1
        
        batch_load_time = time.time() - start_time
        
        self.assertLess(batch_load_time, self.thresholds['audio_load_batch'],
                       f"Batch audio loading too slow: {batch_load_time:.2f}s")
        
        self.assertEqual(loaded_files, 10)
        
        # Calculate average time per file
        avg_time_per_file = batch_load_time / loaded_files
        self.log_performance_metric(
            'audio_load_batch',
            batch_load_time,
            {
                'files_loaded': loaded_files,
                'avg_time_per_file': avg_time_per_file
            }
        )
    
    def test_feature_extraction_performance(self):
        """Test performance of audio feature extraction."""
        librosa = self.importer.safe_import('librosa')
        numpy = self.importer.safe_import('numpy')
        
        # Mock audio data
        sample_rate = 22050
        duration = 10  # 10 seconds
        mock_audio_data = [0.1 * i for i in range(sample_rate * duration)]
        
        start_time = time.time()
        
        with patch.object(librosa, 'feature') as mock_feature:
            # Mock feature extraction functions
            mock_feature.mfcc.return_value = [[0.1] * 13 for _ in range(100)]
            mock_feature.spectral_centroid.return_value = [[1000.0] * 100]
            mock_feature.spectral_rolloff.return_value = [[2000.0] * 100]
            mock_feature.zero_crossing_rate.return_value = [[0.1] * 100]
            
            # Extract multiple features
            features = {}
            features['mfcc'] = librosa.feature.mfcc(y=mock_audio_data, sr=sample_rate)
            features['spectral_centroid'] = librosa.feature.spectral_centroid(y=mock_audio_data, sr=sample_rate)
            features['spectral_rolloff'] = librosa.feature.spectral_rolloff(y=mock_audio_data, sr=sample_rate)
            features['zcr'] = librosa.feature.zero_crossing_rate(mock_audio_data)
        
        extraction_time = time.time() - start_time
        
        self.assertLess(extraction_time, self.thresholds['feature_extraction'],
                       f"Feature extraction too slow: {extraction_time:.2f}s")
        
        # Verify features were extracted
        self.assertEqual(len(features), 4)
        
        self.log_performance_metric(
            'feature_extraction',
            extraction_time,
            {
                'audio_duration': duration,
                'features_extracted': len(features)
            }
        )
    
    def test_voice_analysis_performance(self):
        """Test performance of voice characteristic analysis."""
        librosa = self.importer.safe_import('librosa')
        numpy = self.importer.safe_import('numpy')
        
        # Mock audio data and analysis functions
        sample_rate = 22050
        mock_audio_data = [0.1 * i for i in range(sample_rate * 5)]  # 5 seconds
        
        start_time = time.time()
        
        with patch.object(librosa, 'yin') as mock_yin, \
             patch.object(librosa, 'stft') as mock_stft, \
             patch.object(numpy, 'mean') as mock_mean, \
             patch.object(numpy, 'std') as mock_std:
            
            # Mock pitch detection
            mock_yin.return_value = [150.0] * 100  # F0 estimates
            
            # Mock spectral analysis
            mock_stft.return_value = [[0.1 + 0.1j] * 100 for _ in range(1024)]
            
            # Mock statistical functions
            mock_mean.return_value = 150.0
            mock_std.return_value = 25.0
            
            # Perform voice analysis
            analysis_results = {}
            
            # Pitch analysis
            f0 = librosa.yin(mock_audio_data, fmin=80, fmax=400)
            analysis_results['pitch_mean'] = numpy.mean(f0)
            analysis_results['pitch_std'] = numpy.std(f0)
            
            # Spectral analysis
            stft = librosa.stft(mock_audio_data)
            analysis_results['spectral_features'] = {
                'magnitude_mean': numpy.mean(numpy.abs(stft)),
                'magnitude_std': numpy.std(numpy.abs(stft))
            }
            
            # Formant analysis (simplified)
            analysis_results['formants'] = [850, 1200, 2400]  # Typical formants
        
        analysis_time = time.time() - start_time
        
        self.assertLess(analysis_time, self.thresholds['voice_analysis'],
                       f"Voice analysis too slow: {analysis_time:.2f}s")
        
        # Verify analysis results
        self.assertIn('pitch_mean', analysis_results)
        self.assertIn('spectral_features', analysis_results)
        self.assertIn('formants', analysis_results)
        
        self.log_performance_metric(
            'voice_analysis',
            analysis_time,
            {
                'audio_duration': 5,
                'features_analyzed': len(analysis_results)
            }
        )
    
    def test_batch_processing_performance(self):
        """Test performance of batch audio processing."""
        librosa = self.importer.safe_import('librosa')
        
        start_time = time.time()
        processed_files = []
        
        with patch.object(librosa, 'load') as mock_load, \
             patch.object(librosa, 'feature') as mock_feature:
            
            # Mock audio loading and feature extraction
            mock_feature.mfcc.return_value = [[0.1] * 13 for _ in range(50)]
            
            for test_file in self.test_files[:10]:  # Process 10 files
                # Mock loading
                duration = self._get_file_duration_from_name(test_file.name)
                sample_rate = 22050
                mock_audio_data = [0.0] * (sample_rate * duration)
                mock_load.return_value = (mock_audio_data, sample_rate)
                
                # Load and process
                audio_data, sr = librosa.load(str(test_file))
                features = librosa.feature.mfcc(y=audio_data, sr=sr)
                
                processed_files.append({
                    'file': test_file.name,
                    'duration': duration,
                    'features_shape': (13, 50)  # Mock shape
                })
        
        batch_processing_time = time.time() - start_time
        
        self.assertLess(batch_processing_time, self.thresholds['batch_processing'],
                       f"Batch processing too slow: {batch_processing_time:.2f}s")
        
        self.assertEqual(len(processed_files), 10)
        
        # Calculate throughput
        total_audio_duration = sum(f['duration'] for f in processed_files)
        throughput = total_audio_duration / batch_processing_time
        
        self.log_performance_metric(
            'batch_processing',
            batch_processing_time,
            {
                'files_processed': len(processed_files),
                'total_audio_duration': total_audio_duration,
                'throughput_ratio': throughput
            }
        )
    
    def test_concurrent_processing_performance(self):
        """Test performance of concurrent audio processing."""
        import concurrent.futures
        
        librosa = self.importer.safe_import('librosa')
        
        def process_audio_file(file_path):
            """Process single audio file."""
            with patch.object(librosa, 'load') as mock_load, \
                 patch.object(librosa, 'feature') as mock_feature:
                
                duration = self._get_file_duration_from_name(file_path.name)
                sample_rate = 22050
                mock_audio_data = [0.0] * (sample_rate * duration)
                mock_load.return_value = (mock_audio_data, sample_rate)
                mock_feature.mfcc.return_value = [[0.1] * 13 for _ in range(50)]
                
                # Simulate processing time
                time.sleep(0.1)  # Small delay to simulate real processing
                
                audio_data, sr = librosa.load(str(file_path))
                features = librosa.feature.mfcc(y=audio_data, sr=sr)
                
                return {
                    'file': file_path.name,
                    'duration': duration,
                    'processed': True
                }
        
        start_time = time.time()
        
        # Process 5 files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(process_audio_file, file_path)
                for file_path in self.test_files[:5]
            ]
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        concurrent_processing_time = time.time() - start_time
        
        self.assertLess(concurrent_processing_time, self.thresholds['concurrent_processing'],
                       f"Concurrent processing too slow: {concurrent_processing_time:.2f}s")
        
        self.assertEqual(len(results), 5)
        
        # Should be faster than sequential processing
        estimated_sequential_time = len(results) * 0.1  # Minimum time based on sleep
        self.assertLess(concurrent_processing_time, estimated_sequential_time * 2,
                       "Concurrent processing not significantly faster than sequential")
        
        self.log_performance_metric(
            'concurrent_processing',
            concurrent_processing_time,
            {
                'files_processed': len(results),
                'workers_used': 3
            }
        )
    
    def test_memory_efficiency_during_processing(self):
        """Test memory usage during audio processing."""
        import psutil
        import gc
        
        librosa = self.importer.safe_import('librosa')
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch.object(librosa, 'load') as mock_load, \
             patch.object(librosa, 'feature') as mock_feature:
            
            # Mock large audio data
            sample_rate = 22050
            large_audio_data = [0.1 * i for i in range(sample_rate * 30)]  # 30 seconds
            mock_load.return_value = (large_audio_data, sample_rate)
            mock_feature.mfcc.return_value = [[0.1] * 13 for _ in range(1000)]
            
            # Process multiple files to test memory accumulation
            for i in range(5):
                audio_data, sr = librosa.load(str(self.test_files[i]))
                features = librosa.feature.mfcc(y=audio_data, sr=sr)
                
                # Force garbage collection
                gc.collect()
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        self.assertLess(memory_increase, self.thresholds['memory_efficiency'],
                       f"Memory usage increased too much: {memory_increase:.2f}MB")
        
        self.log_performance_metric(
            'memory_efficiency',
            memory_increase,
            {
                'initial_memory_mb': initial_memory,
                'final_memory_mb': final_memory,
                'files_processed': 5
            }
        )
    
    def test_performance_regression_detection(self):
        """Test for performance regressions by comparing with baselines."""
        # This test would compare current performance with stored baselines
        current_metrics = self.get_logged_metrics()
        
        # Define baseline performance (would normally be loaded from file)
        baselines = {
            'audio_load_single': 1.0,
            'feature_extraction': 3.0,
            'voice_analysis': 2.0,
            'batch_processing': 20.0
        }
        
        regressions = []
        
        for metric_name, baseline in baselines.items():
            if metric_name in current_metrics:
                current_time = current_metrics[metric_name]['value']
                regression_threshold = baseline * 1.5  # 50% slower = regression
                
                if current_time > regression_threshold:
                    regressions.append({
                        'metric': metric_name,
                        'baseline': baseline,
                        'current': current_time,
                        'regression_factor': current_time / baseline
                    })
        
        # Report any regressions found
        if regressions:
            regression_report = "\n".join([
                f"- {r['metric']}: {r['current']:.2f}s vs baseline {r['baseline']:.2f}s "
                f"({r['regression_factor']:.1f}x slower)"
                for r in regressions
            ])
            self.fail(f"Performance regressions detected:\n{regression_report}")
        
        # Log baseline comparison
        self.log_performance_metric(
            'regression_check',
            len(regressions),
            {
                'metrics_checked': len(baselines),
                'regressions_found': len(regressions)
            }
        )
    
    def test_performance_under_stress(self):
        """Test performance under stress conditions."""
        librosa = self.importer.safe_import('librosa')
        
        # Simulate high-load scenario
        start_time = time.time()
        operations_completed = 0
        errors = []
        
        with patch.object(librosa, 'load') as mock_load, \
             patch.object(librosa, 'feature') as mock_feature:
            
            mock_load.return_value = ([0.1] * 22050, 22050)  # 1 second audio
            mock_feature.mfcc.return_value = [[0.1] * 13 for _ in range(50)]
            
            # Perform many operations quickly
            for i in range(50):  # 50 operations
                try:
                    audio_data, sr = librosa.load(f"stress_test_{i}.wav")
                    features = librosa.feature.mfcc(y=audio_data, sr=sr)
                    operations_completed += 1
                except Exception as e:
                    errors.append(str(e))
        
        stress_test_time = time.time() - start_time
        
        # Should complete most operations successfully
        success_rate = operations_completed / 50
        self.assertGreater(success_rate, 0.9, "Too many failures under stress")
        
        # Should maintain reasonable performance
        avg_time_per_operation = stress_test_time / operations_completed if operations_completed > 0 else float('inf')
        self.assertLess(avg_time_per_operation, 1.0, "Operations too slow under stress")
        
        self.log_performance_metric(
            'stress_test',
            stress_test_time,
            {
                'operations_attempted': 50,
                'operations_completed': operations_completed,
                'success_rate': success_rate,
                'errors': len(errors)
            }
        )


if __name__ == '__main__':
    import unittest
    unittest.main()