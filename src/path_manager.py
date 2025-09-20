"""
Path Management System for VoxPersona

This module provides intelligent path resolution with environment-aware fallbacks
and permission handling. It ensures the application works reliably across different
execution contexts (CI/CD, Docker, local development, production).

Key Features:
- Environment-aware path resolution
- Automatic fallback mechanisms
- Permission-safe directory creation
- Temporary path management
- Path validation and sanitization
- Cross-platform compatibility
"""

import os
import sys
import logging
import tempfile
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import shutil
import stat
from functools import lru_cache

from environment import get_environment, EnvironmentType

logger = logging.getLogger(__name__)


class PathType(Enum):
    """Types of paths used by VoxPersona"""
    AUDIO_STORAGE = "audio_storage"
    TEXT_STORAGE = "text_storage" 
    RAG_INDICES = "rag_indices"
    PROMPTS = "prompts"
    TEMP = "temporary"
    LOGS = "logs"
    CONFIG = "config"
    DATABASE = "database"


@dataclass
class PathConfig:
    """Configuration for a specific path type"""
    primary_path: Path
    fallback_paths: List[Path]
    create_if_missing: bool = True
    require_write_access: bool = True
    require_read_access: bool = True
    is_temporary: bool = False
    cleanup_on_exit: bool = False


class PathResolutionError(Exception):
    """Exception raised when path resolution fails"""
    def __init__(self, message: str, path_type: PathType, attempted_paths: List[Path]):
        super().__init__(message)
        self.path_type = path_type
        self.attempted_paths = attempted_paths


class PathManager:
    """
    Manages path resolution with environment-aware fallbacks
    """
    
    def __init__(self):
        self.environment = get_environment()
        self._resolved_paths: Dict[PathType, Path] = {}
        self._temp_dirs: List[Path] = []
        self._path_configs = self._initialize_path_configs()
    
    def _initialize_path_configs(self) -> Dict[PathType, PathConfig]:
        """Initialize path configurations based on environment"""
        env_type = self.environment.env_type
        is_containerized = self.environment.is_containerized
        has_write_perms = self.environment.has_write_permissions
        
        configs = {}
        
        # Audio storage paths
        if env_type == EnvironmentType.TEST:
            configs[PathType.AUDIO_STORAGE] = PathConfig(
                primary_path=self.environment.temp_dir / "test_audio",
                fallback_paths=[
                    Path(tempfile.gettempdir()) / "voxpersona_test_audio",
                    Path.cwd() / "tmp" / "audio"
                ],
                is_temporary=True,
                cleanup_on_exit=True
            )
        elif env_type == EnvironmentType.CI_CD:
            configs[PathType.AUDIO_STORAGE] = PathConfig(
                primary_path=Path("/tmp/voxpersona_audio"),
                fallback_paths=[
                    self.environment.temp_dir / "audio",
                    Path.cwd() / "tmp" / "audio"
                ],
                is_temporary=True
            )
        elif is_containerized:
            configs[PathType.AUDIO_STORAGE] = PathConfig(
                primary_path=Path("/app/audio_files"),
                fallback_paths=[
                    Path("/tmp/audio_files"),
                    Path.cwd() / "audio_files"
                ]
            )
        else:
            # Development or production
            configs[PathType.AUDIO_STORAGE] = PathConfig(
                primary_path=Path.cwd() / "audio_files",
                fallback_paths=[
                    Path.home() / "VoxPersona" / "audio_files" if Path.home().exists() else Path.cwd() / "audio_files",
                    self.environment.temp_dir / "audio_files"
                ]
            )
        
        # Text storage paths
        if env_type == EnvironmentType.TEST:
            configs[PathType.TEXT_STORAGE] = PathConfig(
                primary_path=self.environment.temp_dir / "test_text",
                fallback_paths=[
                    Path(tempfile.gettempdir()) / "voxpersona_test_text",
                    Path.cwd() / "tmp" / "text"
                ],
                is_temporary=True,
                cleanup_on_exit=True
            )
        elif env_type == EnvironmentType.CI_CD:
            configs[PathType.TEXT_STORAGE] = PathConfig(
                primary_path=Path("/tmp/voxpersona_text"),
                fallback_paths=[
                    self.environment.temp_dir / "text",
                    Path.cwd() / "tmp" / "text"
                ],
                is_temporary=True
            )
        elif is_containerized:
            configs[PathType.TEXT_STORAGE] = PathConfig(
                primary_path=Path("/app/text_files"),
                fallback_paths=[
                    Path("/tmp/text_files"),
                    Path.cwd() / "text_files"
                ]
            )
        else:
            configs[PathType.TEXT_STORAGE] = PathConfig(
                primary_path=Path.cwd() / "text_files",
                fallback_paths=[
                    Path.home() / "VoxPersona" / "text_files" if Path.home().exists() else Path.cwd() / "text_files",
                    self.environment.temp_dir / "text_files"
                ]
            )
        
        # RAG indices paths
        if env_type == EnvironmentType.TEST:
            configs[PathType.RAG_INDICES] = PathConfig(
                primary_path=self.environment.temp_dir / "test_rag_indices",
                fallback_paths=[
                    Path(tempfile.gettempdir()) / "voxpersona_test_rag",
                    Path.cwd() / "tmp" / "rag_indices"
                ],
                is_temporary=True,
                cleanup_on_exit=True
            )
        elif env_type == EnvironmentType.CI_CD:
            configs[PathType.RAG_INDICES] = PathConfig(
                primary_path=Path("/tmp/voxpersona_rag"),
                fallback_paths=[
                    self.environment.temp_dir / "rag_indices",
                    Path.cwd() / "tmp" / "rag_indices"
                ],
                is_temporary=True
            )
        elif is_containerized:
            configs[PathType.RAG_INDICES] = PathConfig(
                primary_path=Path("/app/rag_indices"),
                fallback_paths=[
                    Path("/tmp/rag_indices"),
                    Path.cwd() / "rag_indices"
                ]
            )
        else:
            configs[PathType.RAG_INDICES] = PathConfig(
                primary_path=Path.cwd() / "rag_indices",
                fallback_paths=[
                    Path.home() / "VoxPersona" / "rag_indices" if Path.home().exists() else Path.cwd() / "rag_indices",
                    self.environment.temp_dir / "rag_indices"
                ]
            )
        
        # Prompts paths (read-only)
        prompts_candidates = [
            Path.cwd() / "prompts",
            Path.cwd() / "prompts-by-scenario",
            Path(__file__).parent.parent / "prompts",
            Path("/app/prompts") if is_containerized else Path.cwd() / "prompts"
        ]
        
        configs[PathType.PROMPTS] = PathConfig(
            primary_path=prompts_candidates[0],
            fallback_paths=prompts_candidates[1:],
            create_if_missing=False,
            require_write_access=False
        )
        
        # Temporary paths
        configs[PathType.TEMP] = PathConfig(
            primary_path=self.environment.temp_dir / "voxpersona_temp",
            fallback_paths=[
                Path(tempfile.gettempdir()) / "voxpersona",
                Path.cwd() / "tmp"
            ],
            is_temporary=True,
            cleanup_on_exit=True
        )
        
        # Log paths
        if env_type in [EnvironmentType.TEST, EnvironmentType.CI_CD]:
            configs[PathType.LOGS] = PathConfig(
                primary_path=self.environment.temp_dir / "logs",
                fallback_paths=[
                    Path("/tmp/voxpersona_logs"),
                    Path.cwd() / "tmp" / "logs"
                ],
                is_temporary=True
            )
        elif is_containerized:
            configs[PathType.LOGS] = PathConfig(
                primary_path=Path("/app/logs"),
                fallback_paths=[
                    Path("/tmp/logs"),
                    Path.cwd() / "logs"
                ]
            )
        else:
            configs[PathType.LOGS] = PathConfig(
                primary_path=Path.cwd() / "logs",
                fallback_paths=[
                    Path.home() / "VoxPersona" / "logs" if Path.home().exists() else Path.cwd() / "logs",
                    self.environment.temp_dir / "logs"
                ]
            )
        
        return configs
    
    def get_path(self, path_type: PathType, create_dirs: bool = True) -> Path:
        """
        Get a resolved path for the given path type
        
        Args:
            path_type: Type of path to resolve
            create_dirs: Whether to create directories if they don't exist
            
        Returns:
            Resolved Path object
            
        Raises:
            PathResolutionError: If path cannot be resolved
        """
        # Return cached path if available
        if path_type in self._resolved_paths:
            return self._resolved_paths[path_type]
        
        config = self._path_configs.get(path_type)
        if not config:
            raise PathResolutionError(
                f"No configuration found for path type: {path_type}",
                path_type,
                []
            )
        
        # Try primary path first, then fallbacks
        all_paths = [config.primary_path] + config.fallback_paths
        attempted_paths = []
        
        for path in all_paths:
            attempted_paths.append(path)
            
            try:
                resolved_path = self._try_resolve_path(path, config, create_dirs)
                if resolved_path:
                    self._resolved_paths[path_type] = resolved_path
                    logger.info(f"Resolved {path_type.value} to: {resolved_path}")
                    
                    # Track temporary directories for cleanup
                    if config.is_temporary and resolved_path not in self._temp_dirs:
                        self._temp_dirs.append(resolved_path)
                    
                    return resolved_path
                    
            except Exception as e:
                logger.debug(f"Failed to resolve {path_type.value} to {path}: {e}")
                continue
        
        # All paths failed
        raise PathResolutionError(
            f"Could not resolve path for {path_type.value} after trying {len(attempted_paths)} locations",
            path_type,
            attempted_paths
        )
    
    def _try_resolve_path(self, path: Path, config: PathConfig, create_dirs: bool) -> Optional[Path]:
        """
        Try to resolve a single path according to its configuration
        
        Returns:
            Resolved Path if successful, None if failed
        """
        try:
            # Expand and resolve the path
            resolved_path = path.expanduser().resolve()
            
            # Check if path exists
            if resolved_path.exists():
                # Path exists, check permissions
                if config.require_read_access and not os.access(resolved_path, os.R_OK):
                    logger.debug(f"Path {resolved_path} exists but lacks read access")
                    return None
                
                if config.require_write_access and not os.access(resolved_path, os.W_OK):
                    logger.debug(f"Path {resolved_path} exists but lacks write access")
                    return None
                
                return resolved_path
            
            # Path doesn't exist
            if not config.create_if_missing:
                if not create_dirs:
                    return None
                logger.debug(f"Path {resolved_path} doesn't exist and creation not allowed")
                return None
            
            if create_dirs:
                # Try to create the directory
                self._create_directory_safely(resolved_path)
                
                # Verify creation and permissions
                if (resolved_path.exists() and
                    (not config.require_read_access or os.access(resolved_path, os.R_OK)) and
                    (not config.require_write_access or os.access(resolved_path, os.W_OK))):
                    return resolved_path
            
            return None
            
        except Exception as e:
            logger.debug(f"Exception resolving path {path}: {e}")
            return None
    
    def _create_directory_safely(self, path: Path):
        """
        Safely create a directory with appropriate permissions
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            # Set appropriate permissions (readable/writable by owner, readable by group)
            if os.name == 'posix':  # Unix-like systems
                os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
            
            logger.debug(f"Created directory: {path}")
            
        except (OSError, PermissionError) as e:
            logger.debug(f"Failed to create directory {path}: {e}")
            raise
    
    def get_temp_path(self, suffix: str = "") -> Path:
        """
        Get a temporary path with optional suffix
        
        Args:
            suffix: Optional suffix for the temporary path
            
        Returns:
            Path to temporary location
        """
        temp_base = self.get_path(PathType.TEMP)
        
        if suffix:
            temp_path = temp_base / suffix
            temp_path.mkdir(parents=True, exist_ok=True)
            return temp_path
        
        return temp_base
    
    def cleanup_temp_dirs(self):
        """Clean up temporary directories created during this session"""
        for temp_dir in self._temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
        
        self._temp_dirs.clear()
    
    def validate_path(self, path: Union[str, Path]) -> Tuple[bool, str]:
        """
        Validate a path for security and accessibility
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            path_obj = Path(path).resolve()
            
            # Check for path traversal attempts
            if '..' in str(path):
                return False, "Path traversal not allowed"
            
            # Check if path is within allowed boundaries
            cwd = Path.cwd().resolve()
            temp_dir = self.environment.temp_dir.resolve()
            
            # Allow paths under current directory or temp directory
            try:
                path_obj.relative_to(cwd)
                return True, ""
            except ValueError:
                try:
                    path_obj.relative_to(temp_dir)
                    return True, ""
                except ValueError:
                    return False, "Path outside allowed boundaries"
                    
        except Exception as e:
            return False, f"Path validation error: {e}"
    
    def get_safe_filename(self, filename: str) -> str:
        """
        Get a safe filename by removing/replacing problematic characters
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace problematic characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        safe_filename = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # Ensure filename is not empty and doesn't start with a dot
        if not safe_filename or safe_filename.startswith('.'):
            safe_filename = f"file_{safe_filename}"
        
        # Limit length
        if len(safe_filename) > 255:
            safe_filename = safe_filename[:255]
        
        return safe_filename
    
    def get_path_info(self, path_type: PathType) -> Dict[str, any]:
        """Get diagnostic information about a path type"""
        try:
            resolved_path = self.get_path(path_type, create_dirs=False)
            config = self._path_configs[path_type]
            
            return {
                'path_type': path_type.value,
                'resolved_path': str(resolved_path),
                'exists': resolved_path.exists(),
                'is_directory': resolved_path.is_dir() if resolved_path.exists() else False,
                'readable': os.access(resolved_path, os.R_OK) if resolved_path.exists() else False,
                'writable': os.access(resolved_path, os.W_OK) if resolved_path.exists() else False,
                'is_temporary': config.is_temporary,
                'cleanup_on_exit': config.cleanup_on_exit,
                'primary_path': str(config.primary_path),
                'fallback_paths': [str(p) for p in config.fallback_paths]
            }
        except Exception as e:
            return {
                'path_type': path_type.value,
                'error': str(e),
                'resolved_path': None
            }


# Global path manager instance
_path_manager = PathManager()


def get_path_manager() -> PathManager:
    """Get the global path manager instance"""
    return _path_manager


def get_path(path_type: PathType, create_dirs: bool = True) -> Path:
    """Convenience function to get a path"""
    return _path_manager.get_path(path_type, create_dirs)


def get_temp_path(suffix: str = "") -> Path:
    """Convenience function to get a temporary path"""
    return _path_manager.get_temp_path(suffix)


def cleanup_temp_dirs():
    """Convenience function to clean up temporary directories"""
    _path_manager.cleanup_temp_dirs()


def validate_path(path: Union[str, Path]) -> Tuple[bool, str]:
    """Convenience function to validate a path"""
    return _path_manager.validate_path(path)


def get_safe_filename(filename: str) -> str:
    """Convenience function to get a safe filename"""
    return _path_manager.get_safe_filename(filename)


# Register cleanup function for application exit
import atexit
atexit.register(cleanup_temp_dirs)


if __name__ == "__main__":
    # When run directly, show path information
    print("VoxPersona Path Management")
    print("=" * 40)
    
    path_manager = get_path_manager()
    
    for path_type in PathType:
        info = path_manager.get_path_info(path_type)
        print(f"\n{path_type.value.upper()}:")
        for key, value in info.items():
            if key != 'path_type':
                print(f"  {key}: {value}")