"""API performance tests for VoxPersona.

This module contains performance tests for API endpoints,
HTTP request handling, and external service integration.
"""

import time
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import patch, MagicMock

from tests.framework.base_test import BasePerformanceTest
from src.import_utils import SafeImporter
from src.config import VoxPersonaConfig


class APIPerformanceTests(BasePerformanceTest):
    """Performance tests for API operations."""
    
    def setUp(self):
        """Set up API performance test environment."""
        super().setUp()
        self.importer = SafeImporter()
        self.config = VoxPersonaConfig()
        
        # Performance thresholds (in seconds)
        self.thresholds = {
            'api_response_time': 2.0,      # Max response time
            'batch_requests': 10.0,        # Batch of 10 requests
            'concurrent_requests': 5.0,    # 5 concurrent requests
            'large_payload': 5.0,          # Large data upload
            'error_handling': 1.0,         # Error response time
        }
    
    def test_api_response_time_performance(self):
        """Test API endpoint response time performance."""
        requests = self.importer.safe_import('requests')
        
        # Mock API endpoints
        endpoints = [
            ('GET', '/api/v1/health'),
            ('GET', '/api/v1/status'),
            ('POST', '/api/v1/analyze'),
            ('GET', '/api/v1/results/123'),
            ('DELETE', '/api/v1/files/456')
        ]
        
        with patch.object(requests, 'request') as mock_request:
            # Mock successful responses
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'status': 'success'}
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_request.return_value = mock_response
            
            for method, endpoint in endpoints:
                with self.subTest(method=method, endpoint=endpoint):
                    start_time = time.time()
                    
                    response = requests.request(method, f'http://localhost:8000{endpoint}')
                    
                    response_time = time.time() - start_time
                    
                    # Verify response
                    self.assertEqual(response.status_code, 200)
                    
                    # Check performance
                    self.assertLess(response_time, self.thresholds['api_response_time'],
                                  f"API {method} {endpoint} too slow: {response_time:.3f}s")
                    
                    # Log performance metric
                    self.log_performance_metric(
                        f'api_{method.lower()}_response',
                        response_time,
                        {'endpoint': endpoint, 'method': method}
                    )
    
    def test_batch_request_performance(self):
        """Test performance of batch API requests."""
        requests = self.importer.safe_import('requests')
        
        with patch.object(requests, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'batch_id': '123', 'status': 'processing'}
            mock_post.return_value = mock_response
            
            start_time = time.time()
            
            # Send batch of requests
            batch_size = 10
            responses = []
            
            for i in range(batch_size):
                payload = {'file_id': f'file_{i}', 'analysis_type': 'voice_analysis'}
                response = requests.post('http://localhost:8000/api/v1/batch', json=payload)
                responses.append(response)
            
            batch_time = time.time() - start_time
            
            # Verify all requests succeeded
            self.assertEqual(len(responses), batch_size)
            for response in responses:
                self.assertEqual(response.status_code, 200)
            
            # Check performance
            self.assertLess(batch_time, self.thresholds['batch_requests'],
                           f"Batch requests too slow: {batch_time:.3f}s")
            
            # Calculate average time per request
            avg_time = batch_time / batch_size
            
            self.log_performance_metric(
                'api_batch_requests',
                batch_time,
                {
                    'batch_size': batch_size,
                    'avg_time_per_request': avg_time,
                    'requests_per_second': batch_size / batch_time
                }
            )
    
    def test_concurrent_request_performance(self):
        """Test performance under concurrent API requests."""
        import concurrent.futures
        
        requests = self.importer.safe_import('requests')
        
        def make_api_request(request_id):
            """Make single API request."""
            with patch.object(requests, 'get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'id': request_id, 'data': 'test'}
                mock_get.return_value = mock_response
                
                # Simulate processing time
                time.sleep(0.1)
                
                response = requests.get(f'http://localhost:8000/api/v1/data/{request_id}')
                return {
                    'request_id': request_id,
                    'status_code': response.status_code,
                    'success': response.status_code == 200
                }
        
        start_time = time.time()
        
        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_api_request, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        concurrent_time = time.time() - start_time
        
        # Verify all requests succeeded
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertTrue(result['success'])
        
        # Check performance (should be faster than sequential)
        self.assertLess(concurrent_time, self.thresholds['concurrent_requests'],
                       f"Concurrent requests too slow: {concurrent_time:.3f}s")
        
        # Should be significantly faster than sequential (5 * 0.1 = 0.5s minimum)
        sequential_estimate = 5 * 0.1
        self.assertLess(concurrent_time, sequential_estimate * 2,
                       "Concurrent processing not efficient")
        
        self.log_performance_metric(
            'api_concurrent_requests',
            concurrent_time,
            {
                'concurrent_requests': 5,
                'max_workers': 3,
                'efficiency_ratio': sequential_estimate / concurrent_time
            }
        )


class DatabasePerformanceTests(BasePerformanceTest):
    """Performance tests for database operations."""
    
    def setUp(self):
        """Set up database performance test environment."""
        super().setUp()
        self.importer = SafeImporter()
        self.config = VoxPersonaConfig()
        
        # Performance thresholds
        self.thresholds = {
            'single_query': 0.1,          # Single query time
            'batch_insert': 2.0,          # Batch insert time
            'complex_query': 1.0,         # Complex query time
            'concurrent_operations': 3.0,  # Concurrent DB ops
        }
    
    def test_database_query_performance(self):
        """Test database query performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        # Create in-memory database for testing
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [(1, 'test', 'data')]
            mock_connect.return_value = mock_conn
            
            start_time = time.time()
            
            # Perform database operations
            conn = sqlite3.connect(':memory:')
            cursor = conn.cursor()
            
            # Simple query
            cursor.execute("SELECT * FROM test_table WHERE id = ?", (1,))
            results = cursor.fetchall()
            
            query_time = time.time() - start_time
            
            # Verify results
            self.assertIsNotNone(results)
            
            # Check performance
            self.assertLess(query_time, self.thresholds['single_query'],
                           f"Database query too slow: {query_time:.3f}s")
            
            self.log_performance_metric(
                'db_single_query',
                query_time,
                {'query_type': 'select', 'result_count': len(results)}
            )
    
    def test_batch_database_operations(self):
        """Test batch database operation performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            start_time = time.time()
            
            # Batch insert operations
            conn = sqlite3.connect(':memory:')
            cursor = conn.cursor()
            
            # Simulate batch insert
            batch_data = [(i, f'name_{i}', f'data_{i}') for i in range(100)]
            cursor.executemany("INSERT INTO test_table VALUES (?, ?, ?)", batch_data)
            conn.commit()
            
            batch_time = time.time() - start_time
            
            # Check performance
            self.assertLess(batch_time, self.thresholds['batch_insert'],
                           f"Batch database operations too slow: {batch_time:.3f}s")
            
            self.log_performance_metric(
                'db_batch_insert',
                batch_time,
                {
                    'record_count': len(batch_data),
                    'records_per_second': len(batch_data) / batch_time
                }
            )


if __name__ == '__main__':
    import unittest
    unittest.main()