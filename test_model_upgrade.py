#!/usr/bin/env python3
"""
VoxPersona Model Upgrade Testing Framework
=========================================

This module provides comprehensive testing for the Anthropic Claude Sonnet 4 (20250514) model upgrade.
Includes API connection tests, functionality tests, and integration tests for validation.
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import sys
import os

# Add src directory to path to import project modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.analysis import (
    send_msg_to_model, 
    assign_roles, 
    classify_query,
    send_msg_to_model_async
)
from src.config import ANTHROPIC_API_KEY, REPORT_MODEL_NAME
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('model_upgrade_tests.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Test result data structure."""
    name: str
    passed: bool
    duration: float
    details: str
    error: Optional[str] = None

@dataclass
class TestSuite:
    """Test suite configuration."""
    name: str
    description: str
    tests: List[str]
    success_criteria: Dict[str, Any]

class ModelUpgradeTestFramework:
    """Main testing framework class for model upgrade validation."""
    
    def __init__(self):
        """Initialize test framework."""
        self.test_results: List[TestResult] = []
        self.model_name = REPORT_MODEL_NAME or "claude-sonnet-4-20250514"
        self.api_key = ANTHROPIC_API_KEY
        self.test_suites = self._initialize_test_suites()
        
    def _initialize_test_suites(self) -> List[TestSuite]:
        """Initialize all test suites."""
        return [
            TestSuite(
                name="API Connection Tests",
                description="Verify API connectivity and model availability",
                tests=["test_api_connection", "test_basic_response"],
                success_criteria={"min_success_rate": 1.0, "max_response_time": 30.0}
            ),
            TestSuite(
                name="Functionality Tests", 
                description="Test core functionality with new model",
                tests=["test_role_assignment", "test_query_classification", "test_json_parsing"],
                success_criteria={"min_success_rate": 0.95, "max_response_time": 30.0}
            ),
            TestSuite(
                name="Integration Tests",
                description="Test full workflow integration",
                tests=["test_full_analysis_workflow", "test_concurrent_requests"],
                success_criteria={"min_success_rate": 0.90, "max_response_time": 60.0}
            ),
            TestSuite(
                name="Performance Tests",
                description="Validate performance metrics",
                tests=["test_response_time", "test_token_handling"],
                success_criteria={"min_success_rate": 0.95, "max_response_time": 30.0}
            )
        ]
    
    # API Connection Tests
    async def test_api_connection(self) -> TestResult:
        """Test basic API connection to new model."""
        start_time = time.time()
        
        try:
            simple_message = [{"role": "user", "content": "test"}]
            response = send_msg_to_model(
                messages=simple_message,
                model=self.model_name,
                api_key=self.api_key,
                max_tokens=100
            )
            
            duration = time.time() - start_time
            
            if response and "ERROR" not in response:
                return TestResult(
                    name="API Connection Test",
                    passed=True,
                    duration=duration,
                    details=f"Successfully connected to {self.model_name}. Response length: {len(response)} chars"
                )
            else:
                return TestResult(
                    name="API Connection Test",
                    passed=False,
                    duration=duration,
                    details="API connection failed",
                    error=response
                )
                
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="API Connection Test",
                passed=False,
                duration=duration,
                details="Exception during API connection test",
                error=str(e)
            )
    
    async def test_basic_response(self) -> TestResult:
        """Test basic response quality from new model."""
        start_time = time.time()
        
        try:
            test_prompt = "Ответь одним словом: какой цвет получается при смешивании красного и синего?"
            messages = [{"role": "user", "content": test_prompt}]
            
            response = send_msg_to_model(
                messages=messages,
                model=self.model_name,
                api_key=self.api_key,
                max_tokens=50
            )
            
            duration = time.time() - start_time
            
            # Check if response is reasonable
            is_valid = (
                response and 
                "ERROR" not in response and 
                len(response.strip()) > 0 and
                len(response.strip()) < 100
            )
            
            return TestResult(
                name="Basic Response Test",
                passed=is_valid,
                duration=duration,
                details=f"Response: '{response}' (length: {len(response)})" if is_valid else "Invalid response",
                error=None if is_valid else f"Invalid response: {response}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Basic Response Test", 
                passed=False,
                duration=duration,
                details="Exception during basic response test",
                error=str(e)
            )
    
    # Functionality Tests
    async def test_role_assignment(self) -> TestResult:
        """Test role assignment functionality."""
        start_time = time.time()
        
        test_dialogue = """
        Человек 1: Здравствуйте, я хотел бы забронировать номер.
        Человек 2: Конечно, на какие даты?
        Человек 1: С 15 по 20 января.
        Человек 2: Прекрасно, у нас есть свободные номера.
        """
        
        try:
            result = assign_roles(test_dialogue)
            duration = time.time() - start_time
            
            # Check if roles were assigned
            has_roles = "клиент" in result.lower() or "сотрудник" in result.lower()
            
            return TestResult(
                name="Role Assignment Test",
                passed=has_roles,
                duration=duration,
                details=f"Roles detected: {has_roles}. Result length: {len(result)}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Role Assignment Test",
                passed=False,
                duration=duration,
                details="Exception during role assignment test",
                error=str(e)
            )
    
    async def test_query_classification(self) -> TestResult:
        """Test query classification functionality.""" 
        start_time = time.time()
        
        test_query = "Найди информацию о качестве обслуживания в ресторанах"
        
        try:
            result = classify_query(test_query)
            duration = time.time() - start_time
            
            # Check if classification returned valid result
            is_valid = result and result != "Не определено"
            
            return TestResult(
                name="Query Classification Test",
                passed=is_valid,
                duration=duration,
                details=f"Classification result: {result}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Query Classification Test",
                passed=False,
                duration=duration,
                details="Exception during query classification test",
                error=str(e)
            )
    
    async def test_json_parsing(self) -> TestResult:
        """Test JSON response parsing capability."""
        start_time = time.time()
        
        try:
            json_prompt = """
            Верни ответ в формате JSON со следующей структурой:
            {
                "status": "success",
                "message": "тестовое сообщение",
                "data": {"key": "value"}
            }
            """
            
            messages = [{"role": "user", "content": json_prompt}]
            response = send_msg_to_model(
                messages=messages,
                model=self.model_name,
                api_key=self.api_key,
                max_tokens=200
            )
            
            duration = time.time() - start_time
            
            # Try to parse JSON
            try:
                # Extract JSON from response (might be wrapped in markdown)
                json_str = response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0].strip()
                
                parsed_json = json.loads(json_str)
                is_valid = isinstance(parsed_json, dict) and "status" in parsed_json
                
                return TestResult(
                    name="JSON Parsing Test",
                    passed=is_valid,
                    duration=duration,
                    details=f"JSON parsed successfully: {parsed_json}"
                )
                
            except json.JSONDecodeError:
                return TestResult(
                    name="JSON Parsing Test",
                    passed=False,
                    duration=duration,
                    details="Failed to parse JSON response",
                    error=f"Invalid JSON: {response}"
                )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="JSON Parsing Test",
                passed=False,
                duration=duration,
                details="Exception during JSON parsing test",
                error=str(e)
            )
    
    # Integration Tests
    async def test_full_analysis_workflow(self) -> TestResult:
        """Test full analysis workflow with new model."""
        start_time = time.time()
        
        try:
            # Simulate a complex analysis workflow
            test_text = """
            Клиент: Добрый день, я недоволен качеством номера.
            Сотрудник: Извините, что именно вас не устраивает?
            Клиент: Номер не был убран, а завтрак был холодным.
            Сотрудник: Мы обязательно это исправим и предложим компенсацию.
            """
            
            # Step 1: Assign roles
            with_roles = assign_roles(test_text)
            
            # Step 2: Classify the content
            classification = classify_query("анализ качества обслуживания")
            
            duration = time.time() - start_time
            
            # Check workflow completion
            workflow_success = (
                len(with_roles) > len(test_text) and
                classification and classification != "Не определено"
            )
            
            return TestResult(
                name="Full Analysis Workflow Test",
                passed=workflow_success,
                duration=duration,
                details=f"Workflow completed. Roles assigned: {len(with_roles)} chars, Classification: {classification}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Full Analysis Workflow Test",
                passed=False,
                duration=duration,
                details="Exception during workflow test",
                error=str(e)
            )
    
    async def test_concurrent_requests(self) -> TestResult:
        """Test concurrent request handling."""
        start_time = time.time()
        
        try:
            async def single_request(session, message_id):
                """Single async request."""
                messages = [{"role": "user", "content": f"Тест #{message_id}: ответь числом {message_id}"}]
                return await send_msg_to_model_async(
                    session=session,
                    messages=messages,
                    system="Отвечай кратко",
                    model=self.model_name,
                    api_key=self.api_key
                )
            
            # Create 3 concurrent requests
            async with aiohttp.ClientSession() as session:
                tasks = [single_request(session, i) for i in range(1, 4)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            duration = time.time() - start_time
            
            # Check success rate
            successful_results = [r for r in results if isinstance(r, str) and "ERROR" not in r]
            success_rate = len(successful_results) / len(tasks)
            
            return TestResult(
                name="Concurrent Requests Test",
                passed=success_rate >= 0.66,  # At least 2/3 should succeed
                duration=duration,
                details=f"Success rate: {success_rate:.2%} ({len(successful_results)}/{len(tasks)})"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Concurrent Requests Test",
                passed=False,
                duration=duration,
                details="Exception during concurrent requests test",
                error=str(e)
            )
    
    # Performance Tests
    async def test_response_time(self) -> TestResult:
        """Test response time performance."""
        start_time = time.time()
        
        try:
            messages = [{"role": "user", "content": "Опиши погоду одним предложением"}]
            
            response_start = time.time()
            response = send_msg_to_model(
                messages=messages,
                model=self.model_name,
                api_key=self.api_key,
                max_tokens=100
            )
            response_time = time.time() - response_start
            
            duration = time.time() - start_time
            
            # Response should be under 30 seconds
            is_fast_enough = response_time < 30.0
            has_response = response and "ERROR" not in response
            
            return TestResult(
                name="Response Time Test",
                passed=is_fast_enough and has_response,
                duration=duration,
                details=f"Response time: {response_time:.2f}s, Response received: {has_response}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Response Time Test",
                passed=False,
                duration=duration,
                details="Exception during response time test",
                error=str(e)
            )
    
    async def test_token_handling(self) -> TestResult:
        """Test token handling with different message sizes."""
        start_time = time.time()
        
        try:
            # Test with different token sizes
            test_cases = [
                ("Short message", "Привет"),
                ("Medium message", "Расскажи о преимуществах отелей " * 10),
                ("Long message", "Подробно опиши процесс анализа качества обслуживания " * 20)
            ]
            
            results = []
            for case_name, message in test_cases:
                try:
                    messages = [{"role": "user", "content": message}]
                    response = send_msg_to_model(
                        messages=messages,
                        model=self.model_name,
                        api_key=self.api_key,
                        max_tokens=200
                    )
                    results.append(response and "ERROR" not in response)
                except Exception:
                    results.append(False)
            
            duration = time.time() - start_time
            success_rate = sum(results) / len(results)
            
            return TestResult(
                name="Token Handling Test",
                passed=success_rate >= 0.66,
                duration=duration,
                details=f"Success rate across different message sizes: {success_rate:.2%}"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name="Token Handling Test",
                passed=False,
                duration=duration,
                details="Exception during token handling test",
                error=str(e)
            )
    
    async def run_test_suite(self, suite: TestSuite) -> Dict[str, Any]:
        """Run a complete test suite."""
        logger.info(f"Running test suite: {suite.name}")
        logger.info(f"Description: {suite.description}")
        
        suite_results = []
        
        for test_name in suite.tests:
            test_method = getattr(self, test_name)
            logger.info(f"Running test: {test_name}")
            
            try:
                result = await test_method()
                suite_results.append(result)
                self.test_results.append(result)
                
                status = "PASSED" if result.passed else "FAILED"
                logger.info(f"Test {test_name}: {status} ({result.duration:.2f}s)")
                if result.error:
                    logger.error(f"Error: {result.error}")
                
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                error_result = TestResult(
                    name=test_name,
                    passed=False,
                    duration=0.0,
                    details="Test execution failed",
                    error=str(e)
                )
                suite_results.append(error_result)
                self.test_results.append(error_result)
        
        # Calculate suite metrics
        passed_tests = sum(1 for result in suite_results if result.passed)
        total_tests = len(suite_results)
        success_rate = passed_tests / total_tests if total_tests > 0 else 0
        avg_response_time = sum(result.duration for result in suite_results) / total_tests if total_tests > 0 else 0
        
        # Check success criteria
        meets_criteria = (
            success_rate >= suite.success_criteria.get("min_success_rate", 1.0) and
            avg_response_time <= suite.success_criteria.get("max_response_time", 30.0)
        )
        
        suite_summary = {
            "name": suite.name,
            "description": suite.description,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "meets_criteria": meets_criteria,
            "results": suite_results
        }
        
        logger.info(f"Suite {suite.name} completed:")
        logger.info(f"  Success rate: {success_rate:.2%}")
        logger.info(f"  Average response time: {avg_response_time:.2f}s")
        logger.info(f"  Meets criteria: {meets_criteria}")
        
        return suite_summary
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites and return comprehensive results."""
        logger.info("Starting VoxPersona Model Upgrade Testing Framework")
        logger.info(f"Testing model: {self.model_name}")
        logger.info("=" * 80)
        
        overall_start_time = time.time()
        suite_summaries = []
        
        for suite in self.test_suites:
            try:
                summary = await self.run_test_suite(suite)
                suite_summaries.append(summary)
            except Exception as e:
                logger.error(f"Test suite {suite.name} failed: {e}")
                suite_summaries.append({
                    "name": suite.name,
                    "description": suite.description,
                    "error": str(e),
                    "meets_criteria": False
                })
        
        overall_duration = time.time() - overall_start_time
        
        # Calculate overall metrics
        total_tests = sum(summary.get("total_tests", 0) for summary in suite_summaries)
        total_passed = sum(summary.get("passed_tests", 0) for summary in suite_summaries)
        overall_success_rate = total_passed / total_tests if total_tests > 0 else 0
        suites_passing_criteria = sum(1 for summary in suite_summaries if summary.get("meets_criteria", False))
        
        final_results = {
            "model_name": self.model_name,
            "test_start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_duration": overall_duration,
            "total_test_suites": len(self.test_suites),
            "suites_passing_criteria": suites_passing_criteria,
            "total_tests": total_tests,
            "total_passed": total_passed,
            "overall_success_rate": overall_success_rate,
            "upgrade_recommended": suites_passing_criteria >= 3 and overall_success_rate >= 0.85,
            "suite_summaries": suite_summaries
        }
        
        # Log final results
        logger.info("=" * 80)
        logger.info("MODEL UPGRADE TESTING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Overall Success Rate: {overall_success_rate:.2%}")
        logger.info(f"Test Suites Passing Criteria: {suites_passing_criteria}/{len(self.test_suites)}")
        logger.info(f"Total Duration: {overall_duration:.2f}s")
        logger.info(f"Upgrade Recommended: {'YES' if final_results['upgrade_recommended'] else 'NO'}")
        
        return final_results

# Main execution function
async def main():
    """Main function to run the test framework."""
    framework = ModelUpgradeTestFramework()
    results = await framework.run_all_tests()
    
    # Save results to file
    with open('model_upgrade_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    logger.info("Test results saved to: model_upgrade_test_results.json")
    return results

if __name__ == "__main__":
    asyncio.run(main())