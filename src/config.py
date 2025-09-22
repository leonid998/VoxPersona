import os
import sys
import logging
import warnings
from typing import Dict, List, Set
from dotenv import load_dotenv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
    load_dotenv: Callable[..., bool]
import tiktoken

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Load environment files with proper precedence
# First load .env, then .env.test if in testing environment
_ = load_dotenv(override=True)
if 'pytest' in sys.modules or os.getenv('IS_TESTING', '').lower() == 'true' or os.getenv('RUN_MODE', '').upper() == 'TEST':
    _ = load_dotenv('.env.test', override=True)

# Testing environment detection
def is_testing_environment() -> bool:
    """
    Detect if we're running in a testing environment.
    Uses multiple detection methods with priority order.
    """
    # Method 1: PyTest execution detection (High priority)
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True
    
    # Method 2: pytest module presence in sys.modules (Medium priority)
    if "pytest" in sys.modules:
        return True
    
    # Method 3: Custom IS_TESTING flag (Low priority)
    if os.getenv("IS_TESTING", "false").lower() == "true":
        return True
    
    # Method 4: RUN_MODE environment variable
    if os.getenv("RUN_MODE", "").upper() == "TEST":
        return True
    
    return False

IS_TESTING = is_testing_environment()

EMBEDDING_MODEL = None

# API key initialization functions
def get_openai_api_key() -> str | None:
    """Get OpenAI API key with testing fallback."""
    key = os.getenv("OPENAI_API_KEY")
    if not key and IS_TESTING:
        return "test_openai_key_12345"
    return key

def get_anthropic_api_key() -> str | None:
    """Get Anthropic API key with testing fallback."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key and IS_TESTING:
        return "test_anthropic_key_12345"
    return key

def get_api_id() -> str | None:
    """Get API ID with testing fallback."""
    api_id = os.getenv("API_ID")
    if not api_id and IS_TESTING:
        return "test_api_id"
    return api_id

def get_api_hash() -> str | None:
    """Get API hash with testing fallback."""
    api_hash = os.getenv("API_HASH")
    if not api_hash and IS_TESTING:
        return "test_api_hash"
    return api_hash

# Initialize API configuration
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_API_KEY = get_openai_api_key()
TRANSCRIPTION_MODEL_NAME = os.getenv("TRANSCRIBATION_MODEL_NAME")     # Whisper

ANTHROPIC_API_KEY = get_anthropic_api_key()
ANTHROPIC_API_KEY_2 = os.getenv("ANTHROPIC_API_KEY_2")
ANTHROPIC_API_KEY_3 = os.getenv("ANTHROPIC_API_KEY_3")
ANTHROPIC_API_KEY_4 = os.getenv("ANTHROPIC_API_KEY_4")
ANTHROPIC_API_KEY_5 = os.getenv("ANTHROPIC_API_KEY_5")
ANTHROPIC_API_KEY_6 = os.getenv("ANTHROPIC_API_KEY_6")
ANTHROPIC_API_KEY_7 = os.getenv("ANTHROPIC_API_KEY_7")
REPORT_MODEL_NAME = os.getenv("REPORT_MODEL_NAME")

API_ID = get_api_id()
API_HASH = get_api_hash()
PASSWORD = os.getenv("PASSWORD")

RUN_MODE = os.getenv("RUN_MODE")

# Database configuration function to avoid constant redefinition
def get_db_config() -> dict[str, str | None]:
    """Get database configuration based on environment."""
    if IS_TESTING or RUN_MODE == "TEST":
        return {
            "dbname": os.getenv("TEST_DB_NAME", "voxpersona_test"),
            "user": os.getenv("TEST_DB_USER", "test_user"),
            "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
            "host": os.getenv("TEST_DB_HOST", "localhost"),  
            "port": os.getenv("TEST_DB_PORT", "5432"),       
        }
    else:
        return {
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST"),  
            "port": os.getenv("DB_PORT"),     
        }

# Initialize DB_CONFIG as a constant
DB_CONFIG = get_db_config()

# Configuration variables initialization with proper handling
def get_minio_bucket_name() -> str | None:
    """Get MinIO bucket name based on environment."""
    if IS_TESTING or RUN_MODE == "TEST":
        return os.getenv("MINIO_BUCKET_TEST_NAME", os.getenv("MINIO_BUCKET_NAME", "test-bucket"))
    else:
        return os.getenv("MINIO_BUCKET_NAME")

def get_telegram_bot_token() -> str | None:
    """Get Telegram bot token based on environment."""
    if IS_TESTING or RUN_MODE == "TEST":
        return os.getenv("TELEGRAM_BOT_TOKEN_TEST", os.getenv("TELEGRAM_BOT_TOKEN", "test_token"))
    else:
        return os.getenv("TELEGRAM_BOT_TOKEN")

def get_session_name() -> str | None:
    """Get session name based on environment."""
    if IS_TESTING or RUN_MODE == "TEST":
        return os.getenv("SESSION_BOT_NAME_TEST", os.getenv("SESSION_BOT_NAME", "test_session"))
    else:
        return os.getenv("SESSION_BOT_NAME")

# Initialize configuration constants
MINIO_BUCKET_NAME = get_minio_bucket_name()
TELEGRAM_BOT_TOKEN = get_telegram_bot_token()
SESSION_NAME = get_session_name()

# MinIO Configuration with test defaults
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000" if IS_TESTING else None)
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "test_access" if IS_TESTING else None)
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "test_secret" if IS_TESTING else None)
MINIO_AUDIO_BUCKET_NAME = os.getenv("MINIO_AUDIO_BUCKET_NAME", "test-audio-bucket" if IS_TESTING else "voxpersona-audio")

# MinIO Health Check Configuration
MINIO_HEALTH_CHECK_INTERVAL = int(os.getenv("MINIO_HEALTH_CHECK_INTERVAL", "60"))
MINIO_MAX_RETRIES = int(os.getenv("MINIO_MAX_RETRIES", "3"))
MINIO_RETRY_BACKOFF = float(os.getenv("MINIO_RETRY_BACKOFF", "2.0"))

# Storage Configuration
MINIO_MAX_FILE_SIZE = int(os.getenv("MINIO_MAX_FILE_SIZE", "2147483648"))  # 2GB
MINIO_CLEANUP_DAYS = int(os.getenv("MINIO_CLEANUP_DAYS", "30"))
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"


if not IS_TESTING:
    # Production environment requires all API keys
    missing_keys = []
    if not OPENAI_API_KEY: missing_keys.append("OPENAI_API_KEY")
    if not ANTHROPIC_API_KEY: missing_keys.append("ANTHROPIC_API_KEY")
    if not TELEGRAM_BOT_TOKEN: missing_keys.append("TELEGRAM_BOT_TOKEN")
    if not API_ID: missing_keys.append("API_ID")
    if not API_HASH: missing_keys.append("API_HASH")
    
    if missing_keys:
        raise ValueError(f"Missing required API keys in production: {', '.join(missing_keys)}")
else:
    logging.info("Running in testing environment - using test API key defaults")



# Глобальные словари/сеты
processed_texts: Dict[int, str] = {}
user_states: Dict[int, Dict[str, object]] = {}
authorized_users: Set[int] = set()  
active_menus: Dict[int, List[int]] = {}

# Директории хранения (deferred creation pattern)
STORAGE_DIRS = {
    "audio": "/root/Vox/VoxPersona/audio_files",
    "text_without_roles": "/root/Vox/VoxPersona/text_with_roles", 
    "text_with_roles": "/root/Vox/VoxPersona/text_without_roles"
}

def ensure_storage_directories():
    """
    Create storage directories if they don't exist.
    This function is called on-demand instead of at import time.
    """
    for directory_name, path in STORAGE_DIRS.items():
        try:
            os.makedirs(path, exist_ok=True)
            logging.debug(f"Ensured directory exists: {path}")
        except Exception as e:
            logging.error(f"Failed to create directory {path}: {e}")
            # Graceful degradation - continue with other directories
            continue

PROMPTS_DIR = "/root/Vox/VoxPersona/prompts"

# Каталог для сохранения RAG индексов (deferred creation)
RAG_INDEX_DIR = "/app/rag_indices"

def ensure_rag_directory():
    """
    Create RAG index directory if it doesn't exist.
    This function is called on-demand instead of at import time.
    """
    try:
        os.makedirs(RAG_INDEX_DIR, exist_ok=True)
        logging.debug(f"Ensured RAG directory exists: {RAG_INDEX_DIR}")
        return True
    except Exception as e:
        logging.error(f"Failed to create RAG directory {RAG_INDEX_DIR}: {e}")
        return False

# Initialize encoding with fallback
def get_tiktoken_encoding():
    """Get tiktoken encoding with fallback."""
    try:
        # Only initialize encoder if model name is available
        if REPORT_MODEL_NAME:
            return tiktoken.encoding_for_model(REPORT_MODEL_NAME)
        else:
            return tiktoken.get_encoding("cl100k_base")
    except (KeyError, AttributeError):
        return tiktoken.get_encoding("cl100k_base")

ENC = get_tiktoken_encoding()
