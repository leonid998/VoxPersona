import os
import sys
import logging
import warnings
from dotenv import load_dotenv
import tiktoken

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Load environment files with proper precedence
# First load .env, then .env.test if in testing environment
load_dotenv(override=True)
if 'pytest' in sys.modules or os.getenv('IS_TESTING', '').lower() == 'true' or os.getenv('RUN_MODE', '').upper() == 'TEST':
    load_dotenv('.env.test', override=True)

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

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
TRANSCRIBATION_MODEL_NAME = os.getenv("TRANSCRIBATION_MODEL_NAME")     # Whisper

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")      # Claude
ANTHROPIC_API_KEY_2 = os.getenv("ANTHROPIC_API_KEY_2")
ANTHROPIC_API_KEY_3 = os.getenv("ANTHROPIC_API_KEY_3")
ANTHROPIC_API_KEY_4 = os.getenv("ANTHROPIC_API_KEY_4")
ANTHROPIC_API_KEY_5 = os.getenv("ANTHROPIC_API_KEY_5")
ANTHROPIC_API_KEY_6 = os.getenv("ANTHROPIC_API_KEY_6")
ANTHROPIC_API_KEY_7 = os.getenv("ANTHROPIC_API_KEY_7")
REPORT_MODEL_NAME = os.getenv("REPORT_MODEL_NAME")

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PASSWORD = os.getenv("PASSWORD")

RUN_MODE = os.getenv("RUN_MODE")

# Use unified testing detection for configuration
if IS_TESTING or RUN_MODE == "TEST":
    DB_CONFIG = {
        "dbname": os.getenv("TEST_DB_NAME", "voxpersona_test"),
        "user": os.getenv("TEST_DB_USER", "test_user"),
        "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
        "host": os.getenv("TEST_DB_HOST", "localhost"),  
        "port": os.getenv("TEST_DB_PORT", "5432"),       
    }
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_TEST_NAME", os.getenv("MINIO_BUCKET_NAME", "test-bucket"))
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_TEST", os.getenv("TELEGRAM_BOT_TOKEN", "test_token"))
    SESSION_NAME = os.getenv("SESSION_BOT_NAME_TEST", os.getenv("SESSION_BOT_NAME", "test_session"))
else:
    DB_CONFIG = {
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),  
        "port": os.getenv("DB_PORT"),     
    }
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    SESSION_NAME = os.getenv("SESSION_BOT_NAME")

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

# Enhanced API key validation with testing awareness
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
    # Testing environment - use defaults if keys are missing
    if not OPENAI_API_KEY:
        OPENAI_API_KEY = "test_openai_key_12345"
    if not ANTHROPIC_API_KEY:
        ANTHROPIC_API_KEY = "test_anthropic_key_12345"
    if not TELEGRAM_BOT_TOKEN:
        TELEGRAM_BOT_TOKEN = "123456789:test_telegram_bot_token"
    if not API_ID:
        API_ID = "test_api_id"
    if not API_HASH:
        API_HASH = "test_api_hash"
    
    logging.info("Running in testing environment - using test API key defaults")

# Глобальные словари/сеты
processed_texts: dict[int, str] = {}
user_states: dict[int, dict] = {}
authorized_users = set()  
active_menus: dict[int, list[int]] = {}

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

try:
    # Only initialize encoder if model name is available
    if REPORT_MODEL_NAME:
        ENC = tiktoken.encoding_for_model(REPORT_MODEL_NAME)
    else:
        ENC = tiktoken.get_encoding("cl100k_base")
except (KeyError, AttributeError):
    ENC = tiktoken.get_encoding("cl100k_base")
