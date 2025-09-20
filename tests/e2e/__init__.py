"""End-to-End tests package for VoxPersona.

This package contains end-to-end tests that verify complete
user workflows and system integration scenarios.
"""

from .test_workflows import (
    TestAudioProcessingWorkflow,
    TestReportGenerationWorkflow, 
    TestSystemIntegrationWorkflow
)

__all__ = [
    'TestAudioProcessingWorkflow',
    'TestReportGenerationWorkflow',
    'TestSystemIntegrationWorkflow'
]