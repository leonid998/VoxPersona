"""
Environment Detection and Configuration System for VoxPersona

This module automatically detects the execution environment and provides
context-appropriate configuration and behavior adaptations.

Supported Environments:
- CI/CD (GitHub Actions, GitLab CI, Jenkins, etc.)
- Docker containers
- Test environments (pytest, unittest)
- Development (local development)
- Production (deployed applications)

Key Features:
- Automatic environment detection
- Environment-specific configuration
- Resource allocation optimization
- Path resolution with fallbacks
- Security context adaptation
"""

import os
import sys
import logging
import platform
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import tempfile
import pwd
import grp
from functools import lru_cache

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """Enumeration of supported environment types"""
    DEVELOPMENT = "development"
    TEST = "test"
    CI_CD = "ci_cd"
    DOCKER = "docker"
    PRODUCTION = "production"
    UNKNOWN = "unknown"


@dataclass
class EnvironmentInfo:
    """Comprehensive environment information"""
    env_type: EnvironmentType
    is_containerized: bool
    is_ci: bool
    is_test: bool
    has_write_permissions: bool
    temp_dir: Path
    user_info: Dict[str, Any]
    system_info: Dict[str, Any]
    python_info: Dict[str, Any]
    detected_indicators: List[str]
    confidence_score: float


class EnvironmentDetector:
    """
    Detects and analyzes the current execution environment
    """
    
    def __init__(self):
        self._cached_info: Optional[EnvironmentInfo] = None
        self._detection_rules = self._initialize_detection_rules()
    
    def _initialize_detection_rules(self) -> Dict[EnvironmentType, List[Tuple[str, callable]]]:
        """Initialize environment detection rules"""
        return {
            EnvironmentType.CI_CD: [
                ("ci_env_vars", self._check_ci_env_vars),
                ("ci_user_context", self._check_ci_user_context),
                ("ci_filesystem", self._check_ci_filesystem),
            ],
            EnvironmentType.DOCKER: [
                ("dockerenv_file", self._check_dockerenv_file),
                ("docker_env_vars", self._check_docker_env_vars),
                ("docker_cgroups", self._check_docker_cgroups),
            ],
            EnvironmentType.TEST: [
                ("test_frameworks", self._check_test_frameworks),
                ("test_env_vars", self._check_test_env_vars),
                ("test_argv", self._check_test_argv),
            ],
            EnvironmentType.PRODUCTION: [
                ("prod_env_vars", self._check_prod_env_vars),
                ("prod_user_context", self._check_prod_user_context),
                ("prod_paths", self._check_prod_paths),
            ],
            EnvironmentType.DEVELOPMENT: [
                ("dev_user_context", self._check_dev_user_context),
                ("dev_paths", self._check_dev_paths),
                ("dev_tools", self._check_dev_tools),
            ]
        }
    
    @lru_cache(maxsize=1)
    def detect_environment(self) -> EnvironmentInfo:
        """
        Detect the current environment with caching
        
        Returns:
            EnvironmentInfo with detected environment details
        """
        if self._cached_info:
            return self._cached_info
        
        logger.info("Starting environment detection...")
        
        # Collect basic system information
        system_info = self._get_system_info()
        user_info = self._get_user_info()
        python_info = self._get_python_info()
        
        # Run detection rules for each environment type
        detection_results = {}
        all_indicators = []
        
        for env_type, rules in self._detection_rules.items():
            score = 0.0
            indicators = []
            
            for rule_name, rule_func in rules:
                try:
                    result = rule_func()
                    if result:
                        score += 1.0
                        indicators.append(rule_name)
                        logger.debug(f"Environment indicator '{rule_name}' positive for {env_type.value}")
                except Exception as e:
                    logger.warning(f"Error running detection rule '{rule_name}': {e}")
            
            # Normalize score by number of rules
            normalized_score = score / len(rules) if rules else 0.0
            detection_results[env_type] = (normalized_score, indicators)
            all_indicators.extend(indicators)
        
        # Determine the most likely environment
        best_env, (best_score, best_indicators) = max(
            detection_results.items(),
            key=lambda x: x[1][0]
        )
        
        # If no environment has a good score, mark as unknown
        if best_score < 0.3:
            best_env = EnvironmentType.UNKNOWN
            best_score = 0.0
            best_indicators = []
        
        # Create environment info
        env_info = EnvironmentInfo(
            env_type=best_env,
            is_containerized=self._is_containerized(),
            is_ci=self._is_ci_environment(),
            is_test=self._is_test_environment(),
            has_write_permissions=self._check_write_permissions(),
            temp_dir=self._get_safe_temp_dir(),
            user_info=user_info,
            system_info=system_info,
            python_info=python_info,
            detected_indicators=list(set(all_indicators)),
            confidence_score=best_score
        )
        
        self._cached_info = env_info
        logger.info(f"Environment detected: {best_env.value} (confidence: {best_score:.2f})")
        
        return env_info
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return {
            'platform': platform.platform(),
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'hostname': platform.node(),
            'cwd': os.getcwd(),
            'argv': sys.argv,
            'executable': sys.executable,
        }
    
    def _get_user_info(self) -> Dict[str, Any]:
        """Get user and permissions information"""
        try:
            user_info = {
                'uid': os.getuid(),
                'gid': os.getgid(),
                'username': pwd.getpwuid(os.getuid()).pw_name,
                'home_dir': os.path.expanduser('~'),
                'groups': [grp.getgrgid(gid).gr_name for gid in os.getgroups()],
            }
        except (AttributeError, KeyError, OSError):
            # Fallback for Windows or restricted environments
            user_info = {
                'uid': os.getuid() if hasattr(os, 'getuid') else None,
                'gid': os.getgid() if hasattr(os, 'getgid') else None,
                'username': os.environ.get('USER', os.environ.get('USERNAME', 'unknown')),
                'home_dir': os.path.expanduser('~'),
                'groups': [],
            }
        
        return user_info
    
    def _get_python_info(self) -> Dict[str, Any]:
        """Get Python environment information"""
        return {
            'version': sys.version,
            'version_info': sys.version_info,
            'executable': sys.executable,
            'path': sys.path[:5],  # First 5 paths to avoid huge output
            'modules': list(sys.modules.keys())[:20],  # First 20 modules
            'prefix': sys.prefix,
            'base_prefix': getattr(sys, 'base_prefix', sys.prefix),
            'in_virtualenv': sys.prefix != getattr(sys, 'base_prefix', sys.prefix),
        }
    
    # Detection rule implementations
    def _check_ci_env_vars(self) -> bool:
        """Check for CI/CD environment variables"""
        ci_vars = [
            'CI', 'CONTINUOUS_INTEGRATION', 'BUILD_NUMBER',
            'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_URL',
            'TRAVIS', 'CIRCLECI', 'BITBUCKET_BUILD_NUMBER',
            'AZURE_HTTP_USER_AGENT', 'TEAMCITY_VERSION'
        ]
        return any(os.environ.get(var) for var in ci_vars)
    
    def _check_ci_user_context(self) -> bool:
        """Check if running in CI user context"""
        ci_users = ['runner', 'build', 'jenkins', 'travis', 'circleci', 'vsts']
        current_user = os.environ.get('USER', os.environ.get('USERNAME', '')).lower()
        return any(ci_user in current_user for ci_user in ci_users)
    
    def _check_ci_filesystem(self) -> bool:
        """Check for CI-specific filesystem characteristics"""
        ci_paths = ['/github', '/builds', '/home/runner', '/opt/buildagent']
        cwd = os.getcwd()
        return any(ci_path in cwd for ci_path in ci_paths)
    
    def _check_dockerenv_file(self) -> bool:
        """Check for Docker environment file"""
        return os.path.exists('/.dockerenv')
    
    def _check_docker_env_vars(self) -> bool:
        """Check for Docker-specific environment variables"""
        docker_vars = ['DOCKER_CONTAINER', 'CONTAINER', 'KUBERNETES_SERVICE_HOST']
        return any(os.environ.get(var) for var in docker_vars)
    
    def _check_docker_cgroups(self) -> bool:
        """Check cgroups for Docker indicators"""
        try:
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                return 'docker' in content or 'containerd' in content
        except (OSError, IOError):
            return False
    
    def _check_test_frameworks(self) -> bool:
        """Check if test frameworks are loaded"""
        test_modules = ['pytest', 'unittest', 'nose', 'testtools']
        return any(module in sys.modules for module in test_modules)
    
    def _check_test_env_vars(self) -> bool:
        """Check for test-specific environment variables"""
        return os.environ.get('RUN_MODE') == 'TEST' or os.environ.get('PYTEST_CURRENT_TEST') is not None
    
    def _check_test_argv(self) -> bool:
        """Check command line arguments for test indicators"""
        if not sys.argv:
            return False
        test_indicators = ['test', 'pytest', 'unittest']
        return any(indicator in sys.argv[0].lower() for indicator in test_indicators)
    
    def _check_prod_env_vars(self) -> bool:
        """Check for production environment variables"""
        prod_vars = ['PRODUCTION', 'PROD', 'NODE_ENV']
        return any(os.environ.get(var, '').lower() in ['production', 'prod'] for var in prod_vars)
    
    def _check_prod_user_context(self) -> bool:
        """Check if running as production user"""
        prod_users = ['www-data', 'nginx', 'apache', 'app', 'service']
        current_user = os.environ.get('USER', os.environ.get('USERNAME', '')).lower()
        return current_user in prod_users
    
    def _check_prod_paths(self) -> bool:
        """Check for production-typical paths"""
        prod_paths = ['/var/www', '/opt/app', '/usr/local/app', '/app']
        cwd = os.getcwd()
        return any(prod_path in cwd for prod_path in prod_paths)
    
    def _check_dev_user_context(self) -> bool:
        """Check if running in development user context"""
        # Not a system user, not CI user, has home directory
        user_info = self._get_user_info()
        username = user_info.get('username', '').lower()
        
        # Skip if it's a system/service user
        system_users = ['root', 'www-data', 'nginx', 'runner', 'build']
        if username in system_users:
            return False
        
        # Check if home directory exists and is writable
        home_dir = user_info.get('home_dir')
        if home_dir and os.path.exists(home_dir):
            try:
                return os.access(home_dir, os.W_OK)
            except OSError:
                pass
        
        return False
    
    def _check_dev_paths(self) -> bool:
        """Check for development-typical paths"""
        dev_indicators = ['Projects', 'Development', 'Code', 'src', 'dev', 'workspace']
        cwd = os.getcwd()
        return any(indicator in cwd for indicator in dev_indicators)
    
    def _check_dev_tools(self) -> bool:
        """Check for development tools presence"""
        # Check if git is available and we're in a git repo
        try:
            import subprocess
            result = subprocess.run(['git', 'rev-parse', '--git-dir'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _is_containerized(self) -> bool:
        """Check if running in any kind of container"""
        return (self._check_dockerenv_file() or 
                self._check_docker_env_vars() or 
                self._check_docker_cgroups())
    
    def _is_ci_environment(self) -> bool:
        """Check if running in CI/CD"""
        return (self._check_ci_env_vars() or 
                self._check_ci_user_context() or 
                self._check_ci_filesystem())
    
    def _is_test_environment(self) -> bool:
        """Check if running in test environment"""
        return (self._check_test_frameworks() or 
                self._check_test_env_vars() or 
                self._check_test_argv())
    
    def _check_write_permissions(self) -> bool:
        """Check if we have write permissions in current directory"""
        try:
            test_file = Path.cwd() / '.write_test'
            test_file.touch()
            test_file.unlink()
            return True
        except (OSError, IOError, PermissionError):
            return False
    
    def _get_safe_temp_dir(self) -> Path:
        """Get a safe temporary directory for the current environment"""
        temp_candidates = [
            Path(tempfile.gettempdir()),
            Path('/tmp'),
            Path.cwd() / 'tmp',
            Path.home() / 'tmp' if Path.home().exists() else None,
        ]
        
        for temp_dir in temp_candidates:
            if temp_dir and temp_dir.exists():
                try:
                    # Test write access
                    test_file = temp_dir / f'.test_{os.getpid()}'
                    test_file.touch()
                    test_file.unlink()
                    return temp_dir
                except (OSError, IOError, PermissionError):
                    continue
        
        # Fallback to current directory
        return Path.cwd()


# Global detector instance
_detector = EnvironmentDetector()


def get_environment() -> EnvironmentInfo:
    """Get current environment information"""
    return _detector.detect_environment()


def is_development() -> bool:
    """Check if running in development environment"""
    return get_environment().env_type == EnvironmentType.DEVELOPMENT


def is_production() -> bool:
    """Check if running in production environment"""
    return get_environment().env_type == EnvironmentType.PRODUCTION


def is_test() -> bool:
    """Check if running in test environment"""
    return get_environment().is_test


def is_ci() -> bool:
    """Check if running in CI/CD environment"""
    return get_environment().is_ci


def is_docker() -> bool:
    """Check if running in Docker container"""
    return get_environment().is_containerized


def get_safe_temp_dir() -> Path:
    """Get safe temporary directory for current environment"""
    return get_environment().temp_dir


def has_write_permissions() -> bool:
    """Check if current environment has write permissions"""
    return get_environment().has_write_permissions


def get_environment_summary() -> str:
    """Get a human-readable summary of the current environment"""
    env = get_environment()
    
    summary = [
        f"Environment: {env.env_type.value}",
        f"Confidence: {env.confidence_score:.2f}",
        f"Containerized: {env.is_containerized}",
        f"CI/CD: {env.is_ci}",
        f"Test: {env.is_test}",
        f"Write Permissions: {env.has_write_permissions}",
        f"User: {env.user_info.get('username', 'unknown')}",
        f"System: {env.system_info.get('system', 'unknown')}",
        f"Python: {env.python_info.get('version_info', 'unknown')}",
    ]
    
    if env.detected_indicators:
        summary.append(f"Indicators: {', '.join(env.detected_indicators)}")
    
    return '\n'.join(summary)


if __name__ == "__main__":
    # When run directly, show environment information
    print("VoxPersona Environment Detection")
    print("=" * 40)
    print(get_environment_summary())