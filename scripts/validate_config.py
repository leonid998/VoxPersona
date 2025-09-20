#!/usr/bin/env python3
"""
Configuration Validator for VoxPersona

This script validates configuration files and environment setup
to ensure they follow best practices and are compatible with
the enhanced systems.

Usage:
    python scripts/validate_config.py [file1] [file2] ...
    
Return codes:
    0: All validations passed
    1: Validation failures found
    2: Script error
"""

import sys
import os
import logging
import yaml
import json
from pathlib import Path
from typing import List, Dict, Set, Any, Optional
import argparse
import re
from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates configuration files and environment setup"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        
        # Required configuration keys
        self.required_keys = {
            'OPENAI_API_KEY',
            'ANTHROPIC_API_KEY', 
            'TELEGRAM_BOT_TOKEN',
            'API_ID',
            'API_HASH'
        }
        
        # Recommended configuration keys
        self.recommended_keys = {
            'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT',
            'MINIO_ENDPOINT', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY',
            'REPORT_MODEL_NAME', 'TRANSCRIBATION_MODEL_NAME'
        }
        
        # Environment-specific keys
        self.env_specific_keys = {
            'test': {
                'TEST_DB_NAME', 'TEST_DB_USER', 'TEST_DB_PASSWORD',
                'TELEGRAM_BOT_TOKEN_TEST', 'MINIO_BUCKET_TEST_NAME'
            },
            'production': {
                'DB_PASSWORD', 'MINIO_SECRET_KEY', 'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 'TELEGRAM_BOT_TOKEN'
            }
        }
        
        # Security patterns to check
        self.security_patterns = [
            (r'password\s*=\s*["\'][^"\']{1,8}["\']', 'Weak password detected'),
            (r'secret\s*=\s*["\']admin["\']', 'Default secret detected'),
            (r'key\s*=\s*["\']test["\']', 'Test key in production config'),
            (r'token\s*=\s*["\'][^"\']{1,20}["\']', 'Potentially weak token'),
        ]
    
    def validate_env_file(self, file_path: Path) -> bool:
        """Validate a .env file"""
        try:
            # Load the .env file
            load_dotenv(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse environment variables
            env_vars = {}
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
            
            # Validate required keys
            missing_required = self.required_keys - env_vars.keys()
            if missing_required:
                for key in missing_required:
                    self.issues.append(f"{file_path}: Missing required key: {key}")
            
            # Validate recommended keys
            missing_recommended = self.recommended_keys - env_vars.keys()
            if missing_recommended:
                for key in missing_recommended:
                    self.warnings.append(f"{file_path}: Missing recommended key: {key}")
            
            # Check for empty values in required keys
            for key in self.required_keys:
                if key in env_vars and not env_vars[key]:
                    self.issues.append(f"{file_path}: Required key {key} is empty")
            
            # Security checks
            self._check_security_patterns(content, file_path)
            
            # Environment-specific validation
            self._validate_environment_config(env_vars, file_path)
            
            # Format validation
            self._validate_env_format(content, file_path)
            
            return len([issue for issue in self.issues if str(file_path) in issue]) == 0
            
        except Exception as e:
            self.issues.append(f"{file_path}: Failed to validate env file - {e}")
            return False
    
    def validate_config_py(self, file_path: Path) -> bool:
        """Validate the config.py file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for enhanced systems usage
            if 'from environment import' not in content and 'import environment' not in content:
                self.warnings.append(
                    f"{file_path}: Consider using enhanced environment detection system"
                )
            
            if 'from path_manager import' not in content and 'import path_manager' not in content:
                self.warnings.append(
                    f"{file_path}: Consider using enhanced path management system"
                )
            
            if 'from error_recovery import' not in content and 'import error_recovery' not in content:
                self.warnings.append(
                    f"{file_path}: Consider using enhanced error recovery system"
                )
            
            # Check for hardcoded paths
            hardcoded_patterns = [
                r'/root/[^"\']*',
                r'/home/[^"\']*',
                r'C:\\[^"\']*',
                r'/tmp/[^"\']*'
            ]
            
            for pattern in hardcoded_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    self.warnings.append(
                        f"{file_path}: Hardcoded path found: {match}. "
                        "Consider using path_manager for environment-aware paths."
                    )
            
            # Check for proper configuration loading
            if 'get_config_value' not in content and 'os.getenv' in content:
                self.warnings.append(
                    f"{file_path}: Direct os.getenv usage found. "
                    "Consider using get_config_value() for better error handling."
                )
            
            # Check for validation functions
            if 'validate_configuration' not in content:
                self.warnings.append(
                    f"{file_path}: No configuration validation function found. "
                    "Consider adding validate_configuration() function."
                )
            
            return len([issue for issue in self.issues if str(file_path) in issue]) == 0
            
        except Exception as e:
            self.issues.append(f"{file_path}: Failed to validate config.py - {e}")
            return False
    
    def validate_docker_compose(self, file_path: Path) -> bool:
        """Validate docker-compose.yml file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                compose_data = yaml.safe_load(f)
            
            # Check for required services
            services = compose_data.get('services', {})
            
            expected_services = {'app', 'postgres', 'minio'}
            missing_services = expected_services - set(services.keys())
            if missing_services:
                for service in missing_services:
                    self.warnings.append(f"{file_path}: Missing service: {service}")
            
            # Check app service configuration
            if 'app' in services:
                app_service = services['app']
                
                # Check for environment variables
                if 'environment' not in app_service and 'env_file' not in app_service:
                    self.issues.append(
                        f"{file_path}: App service missing environment configuration"
                    )
                
                # Check for volumes
                if 'volumes' not in app_service:
                    self.warnings.append(
                        f"{file_path}: App service missing volume mounts"
                    )
                
                # Check for proper dependency setup
                depends_on = app_service.get('depends_on', [])
                if 'postgres' not in depends_on or 'minio' not in depends_on:
                    self.warnings.append(
                        f"{file_path}: App service missing proper dependencies"
                    )
            
            # Check for security issues
            for service_name, service_config in services.items():
                # Check for default passwords
                env_vars = service_config.get('environment', {})
                if isinstance(env_vars, list):
                    env_vars = {item.split('=')[0]: item.split('=', 1)[1] 
                               for item in env_vars if '=' in item}
                
                for key, value in env_vars.items():
                    if 'PASSWORD' in key.upper() and value in ['password', 'admin', 'root']:
                        self.issues.append(
                            f"{file_path}: Default password found in {service_name}: {key}"
                        )
            
            return len([issue for issue in self.issues if str(file_path) in issue]) == 0
            
        except yaml.YAMLError as e:
            self.issues.append(f"{file_path}: Invalid YAML - {e}")
            return False
        except Exception as e:
            self.issues.append(f"{file_path}: Failed to validate docker-compose - {e}")
            return False
    
    def _check_security_patterns(self, content: str, file_path: Path):
        """Check for security issues in configuration"""
        for pattern, message in self.security_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                self.issues.append(f"{file_path}: {message}")
        
        # Check for exposed secrets
        if 'sk-' in content and 'OPENAI_API_KEY' in content:
            self.issues.append(f"{file_path}: Potential OpenAI API key exposed in config")
        
        if 'ANTHROPIC_API_KEY' in content and len(re.findall(r'sk-ant-[a-zA-Z0-9\-_]{40,}', content)) > 0:
            self.issues.append(f"{file_path}: Potential Anthropic API key exposed in config")
    
    def _validate_environment_config(self, env_vars: Dict[str, str], file_path: Path):
        """Validate environment-specific configuration"""
        run_mode = env_vars.get('RUN_MODE', 'PRODUCTION').upper()
        
        if run_mode == 'TEST':
            # Validate test environment
            missing_test_keys = self.env_specific_keys['test'] - env_vars.keys()
            if missing_test_keys:
                for key in missing_test_keys:
                    self.warnings.append(
                        f"{file_path}: Missing test environment key: {key}"
                    )
        
        elif run_mode == 'PRODUCTION':
            # Validate production environment
            missing_prod_keys = self.env_specific_keys['production'] - env_vars.keys()
            if missing_prod_keys:
                for key in missing_prod_keys:
                    self.issues.append(
                        f"{file_path}: Missing production environment key: {key}"
                    )
            
            # Check for test values in production
            test_indicators = ['test', 'localhost', 'admin', 'password', 'debug']
            for key, value in env_vars.items():
                if any(indicator in value.lower() for indicator in test_indicators):
                    if key in ['DB_HOST', 'MINIO_ENDPOINT']:
                        continue  # localhost might be valid in containerized production
                    self.warnings.append(
                        f"{file_path}: Potential test value in production: {key}={value}"
                    )
    
    def _validate_env_format(self, content: str, file_path: Path):
        """Validate .env file format"""
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' not in line:
                self.issues.append(f"{file_path}:{i}: Invalid format - missing '='")
                continue
            
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Validate key format
            if not re.match(r'^[A-Z_][A-Z0-9_]*$', key):
                self.warnings.append(
                    f"{file_path}:{i}: Key '{key}' should use UPPER_CASE format"
                )
            
            # Check for unquoted values with spaces
            if ' ' in value and not (value.startswith('"') and value.endswith('"')):
                self.warnings.append(
                    f"{file_path}:{i}: Value with spaces should be quoted: {key}"
                )
    
    def get_results(self) -> tuple:
        """Get validation results"""
        return self.issues, self.warnings


def validate_files(file_paths: List[Path]) -> bool:
    """Validate multiple configuration files"""
    validator = ConfigValidator()
    all_passed = True
    
    for file_path in file_paths:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            all_passed = False
            continue
        
        logger.info(f"Validating: {file_path}")
        
        if file_path.name.endswith('.env') or file_path.name == '.env.example':
            passed = validator.validate_env_file(file_path)
        elif file_path.name == 'config.py':
            passed = validator.validate_config_py(file_path)
        elif file_path.name == 'docker-compose.yml':
            passed = validator.validate_docker_compose(file_path)
        else:
            logger.warning(f"Unknown configuration file type: {file_path}")
            continue
        
        if not passed:
            all_passed = False
    
    # Report results
    issues, warnings = validator.get_results()
    
    if issues:
        logger.error(f"Found {len(issues)} configuration issues:")
        for issue in issues:
            logger.error(f"  ❌ {issue}")
    
    if warnings:
        logger.warning(f"Found {len(warnings)} configuration warnings:")
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
    
    if not issues and not warnings:
        logger.info("✅ All configuration files are valid!")
    elif not issues:
        logger.info("✅ No critical configuration issues found (warnings present)")
    
    return all_passed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate VoxPersona configuration")
    parser.add_argument('files', nargs='*', help='Configuration files to validate')
    parser.add_argument('--all', action='store_true',
                       help='Validate all configuration files')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine files to validate
    if args.all:
        file_paths = []
        config_files = [
            '.env', '.env.example', 'src/config.py', 'docker-compose.yml'
        ]
        for config_file in config_files:
            file_path = project_root / config_file
            if file_path.exists():
                file_paths.append(file_path)
    elif args.files:
        file_paths = [Path(f) for f in args.files]
    else:
        # Default: validate common config files
        file_paths = []
        default_files = ['.env', 'src/config.py', 'docker-compose.yml']
        for config_file in default_files:
            file_path = project_root / config_file
            if file_path.exists():
                file_paths.append(file_path)
    
    if not file_paths:
        logger.warning("No configuration files found to validate")
        return 0
    
    try:
        success = validate_files(file_paths)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Configuration validation script error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())