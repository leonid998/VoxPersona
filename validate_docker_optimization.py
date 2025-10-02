#!/usr/bin/env python3
"""
VoxPersona Docker Build Validation Script
Validates optimized Docker build performance and functionality

This script tests the Docker build optimization implementation by:
1. Measuring build times for different scenarios
2. Validating layer caching effectiveness
3. Testing application functionality
4. Generating performance reports
"""

import subprocess
import time
import json
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime
import tempfile


class DockerBuildValidator:
    """Validates Docker build optimizations and measures performance"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = os.path.abspath(project_path)
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "project_path": self.project_path,
            "tests": {}
        }
        
    def run_command(self, cmd: List[str], capture_output: bool = True) -> Dict:
        """Run shell command and measure execution time"""
        print(f"Running: {' '.join(cmd)}")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=capture_output,
                text=True,
                cwd=self.project_path,
                timeout=1800  # 30 minute timeout
            )
            end_time = time.time()
            
            return {
                "success": result.returncode == 0,
                "duration": end_time - start_time,
                "stdout": result.stdout if capture_output else "",
                "stderr": result.stderr if capture_output else "",
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": 1800,
                "stdout": "",
                "stderr": "Command timed out after 30 minutes",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }
    
    def check_buildkit_enabled(self) -> bool:
        """Check if BuildKit is enabled"""
        result = self.run_command(["docker", "version", "--format", "json"])
        if not result["success"]:
            return False
            
        try:
            version_info = json.loads(result["stdout"])
            # Check for BuildKit in Docker info
            info_result = self.run_command(["docker", "info", "--format", "json"])
            if info_result["success"]:
                info = json.loads(info_result["stdout"])
                return info.get("ClientInfo", {}).get("BuildkitVersion", "") != ""
        except:
            pass
        
        # Fallback: check environment variable
        return os.environ.get("DOCKER_BUILDKIT", "0") == "1"
    
    def test_clean_build(self) -> Dict:
        """Test clean build from scratch (no cache)"""
        print("\n=== Testing Clean Build (No Cache) ===")
        
        # Remove existing image
        self.run_command(["docker", "rmi", "voxpersona:latest"], capture_output=False)
        
        # Clear build cache
        self.run_command(["docker", "builder", "prune", "-f"], capture_output=False)
        
        # Build without cache
        result = self.run_command([
            "docker", "build", 
            "--no-cache", 
            "--tag", "voxpersona:latest",
            "."
        ])
        
        return {
            "test_name": "clean_build",
            "description": "Full build from scratch without cache",
            "success": result["success"],
            "build_time": result["duration"],
            "error": result["stderr"] if not result["success"] else None
        }
    
    def test_incremental_build(self) -> Dict:
        """Test incremental build with cache (code change simulation)"""
        print("\n=== Testing Incremental Build (With Cache) ===")
        
        # Create a temporary file to simulate code change
        temp_file = os.path.join(self.project_path, "src", "temp_test_file.py")
        with open(temp_file, "w") as f:
            f.write(f"# Temporary test file created at {datetime.now()}\n")
        
        try:
            # Build with cache
            result = self.run_command([
                "docker", "build", 
                "--tag", "voxpersona:latest",
                "."
            ])
            
            return {
                "test_name": "incremental_build",
                "description": "Build with existing cache after code change",
                "success": result["success"],
                "build_time": result["duration"],
                "error": result["stderr"] if not result["success"] else None
            }
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_requirements_change_build(self) -> Dict:
        """Test build after requirements.txt change"""
        print("\n=== Testing Requirements Change Build ===")
        
        requirements_path = os.path.join(self.project_path, "requirements.txt")
        backup_path = requirements_path + ".backup"
        
        try:
            # Backup original requirements
            with open(requirements_path, "r") as f:
                original_content = f.read()
            
            with open(backup_path, "w") as f:
                f.write(original_content)
            
            # Add a comment to requirements.txt to simulate change
            with open(requirements_path, "a") as f:
                f.write(f"\n# Test comment added at {datetime.now()}\n")
            
            # Build after requirements change
            result = self.run_command([
                "docker", "build", 
                "--tag", "voxpersona:latest",
                "."
            ])
            
            return {
                "test_name": "requirements_change_build",
                "description": "Build after requirements.txt modification",
                "success": result["success"],
                "build_time": result["duration"],
                "error": result["stderr"] if not result["success"] else None
            }
        finally:
            # Restore original requirements
            if os.path.exists(backup_path):
                with open(backup_path, "r") as f:
                    original_content = f.read()
                
                with open(requirements_path, "w") as f:
                    f.write(original_content)
                
                os.remove(backup_path)
    
    def test_container_functionality(self) -> Dict:
        """Test if the built container starts and functions correctly"""
        print("\n=== Testing Container Functionality ===")
        
        # Stop any existing container
        self.run_command(["docker", "stop", "voxpersona_test"], capture_output=False)
        self.run_command(["docker", "rm", "voxpersona_test"], capture_output=False)
        
        try:
            # Start container in test mode
            start_result = self.run_command([
                "docker", "run", 
                "--name", "voxpersona_test",
                "--detach",
                "--env", "RUN_MODE=TEST",
                "voxpersona:latest"
            ])
            
            if not start_result["success"]:
                return {
                    "test_name": "container_functionality",
                    "description": "Container startup and basic functionality test",
                    "success": False,
                    "error": f"Failed to start container: {start_result['stderr']}"
                }
            
            # Wait a moment for container to initialize
            time.sleep(10)
            
            # Check if container is running
            status_result = self.run_command([
                "docker", "ps", 
                "--filter", "name=voxpersona_test",
                "--format", "{{.Status}}"
            ])
            
            # Check container logs for any immediate errors
            logs_result = self.run_command([
                "docker", "logs", "voxpersona_test"
            ])
            
            container_running = "Up" in status_result["stdout"]
            no_critical_errors = "Error" not in logs_result["stdout"] and "Traceback" not in logs_result["stdout"]
            
            return {
                "test_name": "container_functionality",
                "description": "Container startup and basic functionality test",
                "success": container_running and no_critical_errors,
                "container_running": container_running,
                "logs_clean": no_critical_errors,
                "logs_sample": logs_result["stdout"][-500:] if logs_result["stdout"] else ""
            }
        
        finally:
            # Clean up test container
            self.run_command(["docker", "stop", "voxpersona_test"], capture_output=False)
            self.run_command(["docker", "rm", "voxpersona_test"], capture_output=False)
    
    def get_image_info(self) -> Dict:
        """Get information about the built image"""
        print("\n=== Collecting Image Information ===")
        
        # Get image size
        size_result = self.run_command([
            "docker", "images", 
            "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}",
            "voxpersona:latest"
        ])
        
        # Get image layers
        history_result = self.run_command([
            "docker", "history", 
            "--format", "table {{.CreatedBy}}\t{{.Size}}",
            "voxpersona:latest"
        ])
        
        return {
            "image_size_info": size_result["stdout"] if size_result["success"] else "N/A",
            "layer_history": history_result["stdout"] if history_result["success"] else "N/A"
        }
    
    def run_all_tests(self) -> Dict:
        """Run all validation tests"""
        print("VoxPersona Docker Build Validation")
        print("=" * 50)
        
        # Check prerequisites
        buildkit_enabled = self.check_buildkit_enabled()
        print(f"BuildKit enabled: {buildkit_enabled}")
        
        if not buildkit_enabled:
            print("WARNING: BuildKit is not enabled. Performance optimizations may not be effective.")
            print("Enable BuildKit by setting DOCKER_BUILDKIT=1 environment variable")
        
        # Run tests
        self.results["buildkit_enabled"] = buildkit_enabled
        
        # Test 1: Clean build
        self.results["tests"]["clean_build"] = self.test_clean_build()
        
        # Test 2: Incremental build
        self.results["tests"]["incremental_build"] = self.test_incremental_build()
        
        # Test 3: Requirements change build
        self.results["tests"]["requirements_change"] = self.test_requirements_change_build()
        
        # Test 4: Container functionality
        self.results["tests"]["functionality"] = self.test_container_functionality()
        
        # Get image information
        self.results["image_info"] = self.get_image_info()
        
        return self.results
    
    def generate_report(self) -> str:
        """Generate a human-readable performance report"""
        report = []
        report.append("VoxPersona Docker Build Optimization Report")
        report.append("=" * 60)
        report.append(f"Generated: {self.results['timestamp']}")
        report.append(f"BuildKit Enabled: {self.results.get('buildkit_enabled', 'Unknown')}")
        report.append("")
        
        # Performance summary
        tests = self.results.get("tests", {})
        
        if "clean_build" in tests:
            clean_time = tests["clean_build"]["build_time"]
            report.append(f"Clean Build Time: {clean_time:.1f} seconds ({clean_time/60:.1f} minutes)")
        
        if "incremental_build" in tests:
            incremental_time = tests["incremental_build"]["build_time"]
            report.append(f"Incremental Build Time: {incremental_time:.1f} seconds")
            
            if "clean_build" in tests:
                clean_time = tests["clean_build"]["build_time"]
                improvement = ((clean_time - incremental_time) / clean_time) * 100
                report.append(f"Cache Improvement: {improvement:.1f}% faster")
        
        if "requirements_change" in tests:
            req_time = tests["requirements_change"]["build_time"]
            report.append(f"Requirements Change Build Time: {req_time:.1f} seconds")
        
        report.append("")
        
        # Test results
        report.append("Test Results:")
        for test_name, test_result in tests.items():
            status = "PASS" if test_result.get("success", False) else "FAIL"
            report.append(f"  {test_name}: {status}")
            if not test_result.get("success", False) and test_result.get("error"):
                report.append(f"    Error: {test_result['error'][:100]}...")
        
        # Image information
        if "image_info" in self.results:
            report.append("")
            report.append("Image Information:")
            image_info = self.results["image_info"]["image_size_info"]
            if image_info and "N/A" not in image_info:
                lines = image_info.split("\n")
                for line in lines[:3]:  # First few lines
                    if line.strip():
                        report.append(f"  {line}")
        
        return "\n".join(report)
    
    def save_results(self, filename: str = "docker_build_validation.json"):
        """Save detailed results to JSON file"""
        filepath = os.path.join(self.project_path, filename)
        with open(filepath, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"Detailed results saved to: {filepath}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate VoxPersona Docker build optimizations")
    parser.add_argument("--project-path", default=".", help="Path to VoxPersona project")
    parser.add_argument("--output", default="docker_build_validation.json", help="Output file for results")
    parser.add_argument("--report-only", action="store_true", help="Generate report from existing results")
    
    args = parser.parse_args()
    
    validator = DockerBuildValidator(args.project_path)
    
    if args.report_only and os.path.exists(args.output):
        # Load existing results
        with open(args.output, "r") as f:
            validator.results = json.load(f)
    else:
        # Run validation tests
        validator.run_all_tests()
        validator.save_results(args.output)
    
    # Generate and display report
    print("\n" + "=" * 60)
    print(validator.generate_report())
    print("=" * 60)
    
    # Exit with error code if any tests failed
    tests = validator.results.get("tests", {})
    failed_tests = [name for name, result in tests.items() if not result.get("success", False)]
    
    if failed_tests:
        print(f"\nFailed tests: {', '.join(failed_tests)}")
        sys.exit(1)
    else:
        print("\nAll tests passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()