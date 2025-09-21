import os
import sys
import logging
import warnings
from dotenv import load_dotenv
import tiktoken

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

load_dotenv(override=True)

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

if RUN_MODE == "TEST":
    DB_CONFIG = {
        "dbname": os.getenv("TEST_DB_NAME"),
        "user": os.getenv("TEST_DB_USER"),
        "password": os.getenv("TEST_DB_PASSWORD"),
        "host": os.getenv("TEST_DB_HOST"),  
        "port": os.getenv("TEST_DB_PORT"),       
    }
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_TEST_NAME")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_TEST")
    SESSION_NAME = os.getenv("SESSION_BOT_NAME_TEST")
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

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_AUDIO_BUCKET_NAME = os.getenv("MINIO_AUDIO_BUCKET_NAME", "voxpersona-audio")

# MinIO Health Check Configuration
MINIO_HEALTH_CHECK_INTERVAL = int(os.getenv("MINIO_HEALTH_CHECK_INTERVAL", "60"))
MINIO_MAX_RETRIES = int(os.getenv("MINIO_MAX_RETRIES", "3"))
MINIO_RETRY_BACKOFF = float(os.getenv("MINIO_RETRY_BACKOFF", "2.0"))

# Storage Configuration
MINIO_MAX_FILE_SIZE = int(os.getenv("MINIO_MAX_FILE_SIZE", "2147483648"))  # 2GB
MINIO_CLEANUP_DAYS = int(os.getenv("MINIO_CLEANUP_DAYS", "30"))
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"

# Conditional API key validation - skip during testing, enforce in production
if not IS_TESTING:
    if not all([OPENAI_API_KEY, ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH]):
        missing_keys = []
        if not OPENAI_API_KEY: missing_keys.append("OPENAI_API_KEY")
        if not ANTHROPIC_API_KEY: missing_keys.append("ANTHROPIC_API_KEY")
        if not TELEGRAM_BOT_TOKEN: missing_keys.append("TELEGRAM_BOT_TOKEN")
        if not API_ID: missing_keys.append("API_ID")
        if not API_HASH: missing_keys.append("API_HASH")
        raise ValueError(f"Missing required API keys in production: {', '.join(missing_keys)}")
else:
    logging.info("Running in testing environment - skipping API key validation")

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
