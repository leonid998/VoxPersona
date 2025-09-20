import os
import logging
import warnings
from dotenv import load_dotenv
import tiktoken
from pathlib import Path

# Import our enhanced systems
try:
    from environment import get_environment, EnvironmentType, is_test, is_ci, is_docker
    from path_manager import get_path, PathType, get_temp_path
    from error_recovery import with_recovery, recover_from_error
    ENHANCED_SYSTEMS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Enhanced systems not available, using fallbacks: {e}")
    ENHANCED_SYSTEMS_AVAILABLE = False
    
    # Create fallback functions
    def get_environment():
        class MockEnv:
            env_type = "development"
        return MockEnv()
    
    def is_test():
        return os.getenv('RUN_MODE') == 'TEST'
    
    def is_ci():
        return bool(os.getenv('CI'))
    
    def is_docker():
        return os.path.exists('/.dockerenv')
    
    def get_path(path_type, create_dirs=True):
        return Path.cwd()
    
    def get_temp_path(suffix=""):
        return Path("/tmp") / suffix if os.name == 'posix' else Path.cwd() / "tmp" / suffix
    
    def with_recovery(context=None):
        def decorator(func):
            return func
        return decorator
    
    def recover_from_error(error, context=None):
        return None

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Load environment variables
load_dotenv(override=True)

# Get environment information
if ENHANCED_SYSTEMS_AVAILABLE:
    environment = get_environment()
    logging.info(f"Detected environment: {environment.env_type.value if hasattr(environment.env_type, 'value') else environment.env_type}")
else:
    environment = get_environment()  # This will be our mock
    logging.info("Using fallback environment detection")

# Safe configuration loading with recovery
@with_recovery({'operation': 'load_config_value'})
def get_config_value(key: str, default=None, required=False):
    """Safely load configuration value with fallbacks"""
    value = os.getenv(key, default)
    
    if required and not value:
        error_msg = f"Required configuration {key} not found"
        logging.error(error_msg)
        
        # Try recovery
        recovery_result = recover_from_error(
            ValueError(error_msg),
            {'config_key': key, 'default_value': default, 'required': required}
        )
        
        if recovery_result:
            logging.info(f"Configuration {key} recovered: {recovery_result}")
            return recovery_result
        elif not required:
            return default
        else:
            raise ValueError(error_msg)
    
    return value

EMBEDDING_MODEL = None

# API Configuration with fallbacks
OPENAI_BASE_URL = get_config_value("OPENAI_BASE_URL")
OPENAI_API_KEY = get_config_value("OPENAI_API_KEY", required=True)
TRANSCRIBATION_MODEL_NAME = get_config_value("TRANSCRIBATION_MODEL_NAME", "whisper-1")

# Anthropic API keys with fallbacks
ANTHROPIC_API_KEY = get_config_value("ANTHROPIC_API_KEY", required=True)
ANTHROPIC_API_KEY_2 = get_config_value("ANTHROPIC_API_KEY_2")
ANTHROPIC_API_KEY_3 = get_config_value("ANTHROPIC_API_KEY_3")
ANTHROPIC_API_KEY_4 = get_config_value("ANTHROPIC_API_KEY_4")
ANTHROPIC_API_KEY_5 = get_config_value("ANTHROPIC_API_KEY_5")
ANTHROPIC_API_KEY_6 = get_config_value("ANTHROPIC_API_KEY_6")
ANTHROPIC_API_KEY_7 = get_config_value("ANTHROPIC_API_KEY_7")
REPORT_MODEL_NAME = get_config_value("REPORT_MODEL_NAME", "claude-3-sonnet-20240229")

# Telegram configuration
API_ID = get_config_value("API_ID", required=True)
API_HASH = get_config_value("API_HASH", required=True)
PASSWORD = get_config_value("PASSWORD")

# Environment detection
RUN_MODE = get_config_value("RUN_MODE", "PRODUCTION")

# Database configuration with environment-aware fallbacks
@with_recovery({'operation': 'database_config'})
def get_database_config():
    """Get database configuration based on environment"""
    if RUN_MODE == "TEST" or is_test():
        return {
            "dbname": get_config_value("TEST_DB_NAME", "voxpersona_test"),
            "user": get_config_value("TEST_DB_USER", "test_user"),
            "password": get_config_value("TEST_DB_PASSWORD", "test_password"),
            "host": get_config_value("TEST_DB_HOST", "localhost"),  
            "port": get_config_value("TEST_DB_PORT", "5432"),       
        }
    else:
        return {
            "dbname": get_config_value("DB_NAME", "voxpersona"),
            "user": get_config_value("DB_USER", "voxpersona_user"),
            "password": get_config_value("DB_PASSWORD", required=True),
            "host": get_config_value("DB_HOST", "localhost"),  
            "port": get_config_value("DB_PORT", "5432"),     
        }

DB_CONFIG = get_database_config()

# MinIO configuration with fallbacks
MINIO_ENDPOINT = get_config_value("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = get_config_value("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = get_config_value("MINIO_SECRET_KEY", "minioadmin")
MINIO_AUDIO_BUCKET_NAME = get_config_value("MINIO_AUDIO_BUCKET_NAME", "voxpersona-audio")

# MinIO Health Check Configuration
MINIO_HEALTH_CHECK_INTERVAL = int(get_config_value("MINIO_HEALTH_CHECK_INTERVAL", "60"))
MINIO_MAX_RETRIES = int(get_config_value("MINIO_MAX_RETRIES", "3"))
MINIO_RETRY_BACKOFF = float(get_config_value("MINIO_RETRY_BACKOFF", "2.0"))

# Storage Configuration
MINIO_MAX_FILE_SIZE = int(get_config_value("MINIO_MAX_FILE_SIZE", "2147483648"))  # 2GB
MINIO_CLEANUP_DAYS = int(get_config_value("MINIO_CLEANUP_DAYS", "30"))
MINIO_USE_SSL = get_config_value("MINIO_USE_SSL", "false").lower() == "true"

# Validate critical configuration
@with_recovery({'operation': 'config_validation'})
def validate_configuration():
    """Validate that all required configuration is present"""
    required_configs = {
        'OPENAI_API_KEY': OPENAI_API_KEY,
        'ANTHROPIC_API_KEY': ANTHROPIC_API_KEY,
        'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
        'API_ID': API_ID,
        'API_HASH': API_HASH
    }
    
    missing_configs = [key for key, value in required_configs.items() if not value]
    
    if missing_configs:
        error_msg = f"Missing required configuration keys: {', '.join(missing_configs)}"
        logging.error(error_msg)
        
        # Try recovery
        recovery_result = recover_from_error(
            ValueError(error_msg),
            {'missing_configs': missing_configs, 'operation': 'config_validation'}
        )
        
        if not recovery_result:
            raise ValueError(error_msg)
    
    logging.info("Configuration validation successful")
    return True

# Perform validation on module load
try:
    validate_configuration()
except Exception as e:
    logging.warning(f"Configuration validation failed: {e}")
    if not (is_test() or is_ci()):
        # In production, this should be a hard error
        raise

# Global state dictionaries
processed_texts: dict[int, str] = {}
user_states: dict[int, dict] = {}
authorized_users = set()  
active_menus: dict[int, list[int]] = {}

# Dynamic storage directories based on environment
@with_recovery({'operation': 'storage_dirs_setup'})
def get_storage_directories():
    """Get storage directories based on current environment"""
    if ENHANCED_SYSTEMS_AVAILABLE:
        try:
            return {
                "audio": str(get_path(PathType.AUDIO_STORAGE)),
                "text_without_roles": str(get_path(PathType.TEXT_STORAGE) / "without_roles"),
                "text_with_roles": str(get_path(PathType.TEXT_STORAGE) / "with_roles")
            }
        except Exception as e:
            logging.warning(f"Could not use enhanced path management: {e}")
    
    # Fallback to original hardcoded paths or environment-based paths
    if is_docker():
        base_path = "/app"
    elif is_ci():
        base_path = "/tmp/voxpersona"
    elif is_test():
        base_path = str(get_temp_path("voxpersona_test"))
    else:
        base_path = str(Path.cwd())
    
    return {
        "audio": f"{base_path}/audio_files",
        "text_without_roles": f"{base_path}/text_without_roles",
        "text_with_roles": f"{base_path}/text_with_roles"
    }

STORAGE_DIRS = get_storage_directories()

# Create directories with error recovery
@with_recovery({'operation': 'create_storage_dirs'})
def create_storage_directories():
    """Create storage directories with proper error handling"""
    for name, path in STORAGE_DIRS.items():
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            logging.debug(f"Created storage directory {name}: {path}")
        except Exception as e:
            logging.warning(f"Could not create storage directory {name} at {path}: {e}")
            
            # Try recovery
            recovery_result = recover_from_error(e, {
                'operation': 'create_directory',
                'path': path,
                'directory_type': name
            })
            
            if recovery_result:
                STORAGE_DIRS[name] = recovery_result
                logging.info(f"Storage directory {name} recovered to: {recovery_result}")

create_storage_directories()

# Dynamic prompts directory based on environment
@with_recovery({'operation': 'prompts_dir_setup'})
def get_prompts_directory():
    """Get prompts directory based on current environment"""
    if ENHANCED_SYSTEMS_AVAILABLE:
        try:
            return str(get_path(PathType.PROMPTS, create_dirs=False))
        except Exception as e:
            logging.warning(f"Could not use enhanced path management for prompts: {e}")
    
    # Fallback search for prompts directory
    candidates = [
        Path.cwd() / "prompts",
        Path.cwd() / "prompts-by-scenario", 
        Path(__file__).parent.parent / "prompts",
        Path("/app/prompts") if is_docker() else Path.cwd() / "prompts",
        Path("/root/Vox/VoxPersona/prompts")  # Original hardcoded path
    ]
    
    for candidate in candidates:
        if candidate.exists():
            logging.info(f"Found prompts directory: {candidate}")
            return str(candidate)
    
    # If no prompts directory found, create one
    default_prompts = Path.cwd() / "prompts"
    default_prompts.mkdir(parents=True, exist_ok=True)
    logging.warning(f"No prompts directory found, created: {default_prompts}")
    return str(default_prompts)

PROMPTS_DIR = get_prompts_directory()

# Dynamic RAG index directory with environment awareness
@with_recovery({'operation': 'rag_index_dir_setup'})
def get_rag_index_directory():
    """Get RAG index directory based on current environment"""
    if ENHANCED_SYSTEMS_AVAILABLE:
        try:
            return str(get_path(PathType.RAG_INDICES))
        except Exception as e:
            logging.warning(f"Could not use enhanced path management for RAG indices: {e}")
    
    # Environment-based fallbacks
    if is_docker():
        rag_dir = Path("/app/rag_indices")
    elif is_ci():
        rag_dir = Path("/tmp/voxpersona_rag_indices")
    elif is_test():
        rag_dir = get_temp_path("test_rag_indices")
    else:
        rag_dir = Path.cwd() / "rag_indices"
    
    # Ensure directory exists
    try:
        rag_dir.mkdir(parents=True, exist_ok=True)
        logging.debug(f"RAG index directory: {rag_dir}")
        return str(rag_dir)
    except Exception as e:
        logging.error(f"Could not create RAG index directory {rag_dir}: {e}")
        # Ultimate fallback
        fallback_dir = get_temp_path("rag_fallback")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        logging.warning(f"Using fallback RAG directory: {fallback_dir}")
        return str(fallback_dir)

RAG_INDEX_DIR = get_rag_index_directory()

# Initialize tiktoken encoder with error recovery
@with_recovery({'operation': 'tiktoken_initialization'})
def initialize_tiktoken_encoder():
    """Initialize tiktoken encoder with fallbacks"""
    try:
        return tiktoken.encoding_for_model(REPORT_MODEL_NAME or "claude-3-sonnet-20240229")
    except KeyError:
        logging.warning(f"Could not find encoding for model {REPORT_MODEL_NAME}, using default")
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        logging.error(f"Error initializing tiktoken encoder: {e}")
        # Try recovery
        recovery_result = recover_from_error(e, {
            'operation': 'tiktoken_init',
            'model_name': REPORT_MODEL_NAME
        })
        if recovery_result:
            return recovery_result
        # Final fallback
        return tiktoken.get_encoding("cl100k_base")

ENC = initialize_tiktoken_encoder()

# Log configuration summary
logging.info(f"VoxPersona Configuration Summary:")
logging.info(f"  Environment: {environment.env_type if hasattr(environment, 'env_type') else 'unknown'}")
logging.info(f"  Run Mode: {RUN_MODE}")
logging.info(f"  Enhanced Systems: {ENHANCED_SYSTEMS_AVAILABLE}")
logging.info(f"  Storage Dirs: {len(STORAGE_DIRS)} configured")
logging.info(f"  Prompts Dir: {PROMPTS_DIR}")
logging.info(f"  RAG Index Dir: {RAG_INDEX_DIR}")
logging.info(f"  Database: {DB_CONFIG.get('host', 'unknown')}:{DB_CONFIG.get('port', 'unknown')}")
