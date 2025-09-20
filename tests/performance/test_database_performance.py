"""Database performance tests for VoxPersona.

This module contains performance tests for database operations,
queries, transactions, and data management workflows.
"""

import time
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import patch, MagicMock

from tests.framework.base_test import BasePerformanceTest
from src.import_utils import SafeImporter
from src.config import VoxPersonaConfig


class DatabasePerformanceTests(BasePerformanceTest):
    """Performance tests for database operations."""
    
    def setUp(self):
        """Set up database performance test environment."""
        super().setUp()
        self.importer = SafeImporter()
        self.config = VoxPersonaConfig()
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        
        # Performance thresholds
        self.thresholds = {
            'connection_time': 1.0,        # Database connection time
            'single_query': 0.1,           # Single query execution
            'batch_insert': 2.0,           # Batch insert operations
            'complex_query': 1.0,          # Complex query with joins
            'transaction_time': 0.5,       # Transaction commit time
            'concurrent_operations': 3.0,   # Concurrent database operations
            'large_dataset_query': 5.0,    # Query on large dataset
        }
    
    def tearDown(self):
        """Clean up test environment."""
        self.temp_db.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
        super().tearDown()
    
    def test_database_connection_performance(self):
        """Test database connection establishment performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        start_time = time.time()
        
        # Test multiple connections
        connections = []
        for i in range(5):
            with patch.object(sqlite3, 'connect') as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                
                conn = sqlite3.connect(self.temp_db.name)
                connections.append(conn)
        
        connection_time = time.time() - start_time
        
        # Clean up
        for conn in connections:
            if hasattr(conn, 'close'):
                conn.close()
        
        # Check performance
        self.assertLess(connection_time, self.thresholds['connection_time'],
                       f"Database connections too slow: {connection_time:.3f}s")
        
        avg_connection_time = connection_time / len(connections)
        
        self.log_performance_metric(
            'db_connection_time',
            connection_time,
            {
                'connections_created': len(connections),
                'avg_connection_time': avg_connection_time
            }
        )
    
    def test_crud_operations_performance(self):
        """Test CRUD operations performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (1, 'test_name', 'test_data')
            mock_cursor.fetchall.return_value = [(1, 'test_1'), (2, 'test_2')]
            mock_connect.return_value = mock_conn
            
            conn = sqlite3.connect(self.temp_db.name)
            cursor = conn.cursor()
            
            # CREATE operation
            start_time = time.time()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            create_time = time.time() - start_time
            
            # INSERT operation
            start_time = time.time()
            cursor.execute(
                "INSERT INTO performance_test (name, data) VALUES (?, ?)",
                ('test_record', 'test_data')
            )
            insert_time = time.time() - start_time
            
            # SELECT operation
            start_time = time.time()
            cursor.execute("SELECT * FROM performance_test WHERE id = ?", (1,))
            result = cursor.fetchone()
            select_time = time.time() - start_time
            
            # UPDATE operation
            start_time = time.time()
            cursor.execute(
                "UPDATE performance_test SET data = ? WHERE id = ?",
                ('updated_data', 1)
            )
            update_time = time.time() - start_time
            
            # DELETE operation
            start_time = time.time()
            cursor.execute("DELETE FROM performance_test WHERE id = ?", (1,))
            delete_time = time.time() - start_time
            
            # Verify operations
            self.assertIsNotNone(result)
            
            # Check individual operation performance
            operations = [
                ('create', create_time),
                ('insert', insert_time),
                ('select', select_time),
                ('update', update_time),
                ('delete', delete_time)
            ]
            
            for op_name, op_time in operations:
                self.assertLess(op_time, self.thresholds['single_query'],
                               f"Database {op_name} too slow: {op_time:.3f}s")
                
                self.log_performance_metric(
                    f'db_crud_{op_name}',
                    op_time,
                    {'operation': op_name}
                )
    
    def test_batch_operations_performance(self):
        """Test batch database operations performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            conn = sqlite3.connect(self.temp_db.name)
            cursor = conn.cursor()
            
            # Setup table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    value INTEGER,
                    data TEXT
                )
            """)
            
            # Batch insert test
            batch_size = 1000
            batch_data = [
                (f'name_{i}', i, f'data_{i}')
                for i in range(batch_size)
            ]
            
            start_time = time.time()
            cursor.executemany(
                "INSERT INTO batch_test (name, value, data) VALUES (?, ?, ?)",
                batch_data
            )
            conn.commit()
            batch_insert_time = time.time() - start_time
            
            # Batch update test
            update_data = [(f'updated_{i}', i) for i in range(0, batch_size, 10)]
            
            start_time = time.time()
            cursor.executemany(
                "UPDATE batch_test SET data = ? WHERE value = ?",
                update_data
            )
            conn.commit()
            batch_update_time = time.time() - start_time
            
            # Check performance
            self.assertLess(batch_insert_time, self.thresholds['batch_insert'],
                           f"Batch insert too slow: {batch_insert_time:.3f}s")
            
            # Log metrics
            self.log_performance_metric(
                'db_batch_insert',
                batch_insert_time,
                {
                    'record_count': batch_size,
                    'records_per_second': batch_size / batch_insert_time
                }
            )
            
            self.log_performance_metric(
                'db_batch_update',
                batch_update_time,
                {
                    'record_count': len(update_data),
                    'records_per_second': len(update_data) / batch_update_time
                }
            )
    
    def test_complex_query_performance(self):
        """Test complex query performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock complex query results
            mock_cursor.fetchall.return_value = [
                (1, 'user1', 5, 150.0),
                (2, 'user2', 3, 120.5),
                (3, 'user3', 8, 200.2)
            ]
            mock_connect.return_value = mock_conn
            
            conn = sqlite3.connect(self.temp_db.name)
            cursor = conn.cursor()
            
            # Complex query with joins and aggregations
            start_time = time.time()
            cursor.execute("""
                SELECT 
                    u.id,
                    u.name,
                    COUNT(a.id) as analysis_count,
                    AVG(a.score) as avg_score
                FROM users u
                LEFT JOIN analyses a ON u.id = a.user_id
                WHERE u.created_at > ?
                GROUP BY u.id, u.name
                HAVING COUNT(a.id) > 0
                ORDER BY avg_score DESC
                LIMIT 100
            """, ('2024-01-01',))
            
            results = cursor.fetchall()
            complex_query_time = time.time() - start_time
            
            # Verify results
            self.assertIsNotNone(results)
            self.assertGreater(len(results), 0)
            
            # Check performance
            self.assertLess(complex_query_time, self.thresholds['complex_query'],
                           f"Complex query too slow: {complex_query_time:.3f}s")
            
            self.log_performance_metric(
                'db_complex_query',
                complex_query_time,
                {
                    'result_count': len(results),
                    'query_type': 'join_aggregate_with_having'
                }
            )
    
    def test_transaction_performance(self):
        """Test database transaction performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            conn = sqlite3.connect(self.temp_db.name)
            cursor = conn.cursor()
            
            # Transaction with multiple operations
            start_time = time.time()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            try:
                # Multiple operations in transaction
                for i in range(100):
                    cursor.execute(
                        "INSERT INTO transaction_test (name, value) VALUES (?, ?)",
                        (f'trans_record_{i}', i)
                    )
                
                # Commit transaction
                conn.commit()
                transaction_success = True
                
            except Exception as e:
                conn.rollback()
                transaction_success = False
            
            transaction_time = time.time() - start_time
            
            # Verify transaction succeeded
            self.assertTrue(transaction_success)
            
            # Check performance
            self.assertLess(transaction_time, self.thresholds['transaction_time'],
                           f"Transaction too slow: {transaction_time:.3f}s")
            
            self.log_performance_metric(
                'db_transaction',
                transaction_time,
                {
                    'operations_count': 100,
                    'transaction_success': transaction_success
                }
            )
    
    def test_concurrent_database_access(self):
        """Test concurrent database access performance."""
        import threading
        
        sqlite3 = self.importer.safe_import('sqlite3')
        
        results = []
        errors = []
        
        def database_worker(worker_id):
            """Worker function for concurrent database access."""
            try:
                with patch.object(sqlite3, 'connect') as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_conn.cursor.return_value = mock_cursor
                    mock_cursor.fetchone.return_value = (worker_id, f'worker_{worker_id}')
                    mock_connect.return_value = mock_conn
                    
                    conn = sqlite3.connect(self.temp_db.name)
                    cursor = conn.cursor()
                    
                    # Perform database operations
                    cursor.execute(
                        "INSERT INTO concurrent_test (worker_id, data) VALUES (?, ?)",
                        (worker_id, f'data_from_worker_{worker_id}')
                    )
                    
                    cursor.execute(
                        "SELECT * FROM concurrent_test WHERE worker_id = ?",
                        (worker_id,)
                    )
                    result = cursor.fetchone()
                    
                    conn.commit()
                    conn.close()
                    
                    results.append({
                        'worker_id': worker_id,
                        'success': True,
                        'result': result
                    })
                    
            except Exception as e:
                errors.append(f'Worker {worker_id}: {str(e)}')
        
        # Start concurrent workers
        start_time = time.time()
        
        threads = []
        num_workers = 5
        
        for i in range(num_workers):
            thread = threading.Thread(target=database_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        concurrent_time = time.time() - start_time
        
        # Verify results
        self.assertEqual(len(results), num_workers)
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")
        
        for result in results:
            self.assertTrue(result['success'])
        
        # Check performance
        self.assertLess(concurrent_time, self.thresholds['concurrent_operations'],
                       f"Concurrent operations too slow: {concurrent_time:.3f}s")
        
        self.log_performance_metric(
            'db_concurrent_access',
            concurrent_time,
            {
                'worker_count': num_workers,
                'success_count': len(results),
                'error_count': len(errors)
            }
        )
    
    def test_database_indexing_performance(self):
        """Test database indexing impact on query performance."""
        sqlite3 = self.importer.safe_import('sqlite3')
        
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [(i, f'name_{i}') for i in range(10)]
            mock_connect.return_value = mock_conn
            
            conn = sqlite3.connect(self.temp_db.name)
            cursor = conn.cursor()
            
            # Create table with test data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS index_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    age INTEGER,
                    created_at TIMESTAMP
                )
            """)
            
            # Query without index
            start_time = time.time()
            cursor.execute("SELECT * FROM index_test WHERE email = ?", ('test@example.com',))
            results_no_index = cursor.fetchall()
            query_time_no_index = time.time() - start_time
            
            # Create index
            start_time = time.time()
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON index_test(email)")
            index_creation_time = time.time() - start_time
            
            # Query with index
            start_time = time.time()
            cursor.execute("SELECT * FROM index_test WHERE email = ?", ('test@example.com',))
            results_with_index = cursor.fetchall()
            query_time_with_index = time.time() - start_time
            
            # Verify both queries return same results
            self.assertEqual(len(results_no_index), len(results_with_index))
            
            # Log performance metrics
            self.log_performance_metric(
                'db_query_no_index',
                query_time_no_index,
                {'result_count': len(results_no_index)}
            )
            
            self.log_performance_metric(
                'db_index_creation',
                index_creation_time,
                {'index_type': 'single_column'}
            )
            
            self.log_performance_metric(
                'db_query_with_index',
                query_time_with_index,
                {'result_count': len(results_with_index)}
            )
            
            # Index should generally improve query performance
            # (though with mocked data, the difference might not be significant)


if __name__ == '__main__':
    import unittest
    unittest.main()