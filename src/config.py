import os
import logging
import warnings
from dotenv import load_dotenv
import tiktoken

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

load_dotenv(override=True)

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

# Проверяем, что все ключи заданы
if not all([OPENAI_API_KEY, ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("Не все ключи (OPENAI_API_KEY, VSEGPT_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH) заданы!")

# Глобальные словари/сеты
processed_texts: dict[int, str] = {}
user_states: dict[int, dict] = {}
authorized_users = set()  
active_menus: dict[int, list[int]] = {}

# Директории хранения
STORAGE_DIRS = {
    "audio": "/root/Vox/VoxPersona/audio_files",
    "text_without_roles": "/root/Vox/VoxPersona/text_with_roles",
    "text_with_roles": "/root/Vox/VoxPersona/text_without_roles"
}

# Создаём папки при необходимости
for fold in STORAGE_DIRS.values():
    os.makedirs(fold, exist_ok=True)

PROMPTS_DIR = "/root/Vox/VoxPersona/prompts"

try:
    ENC = tiktoken.encoding_for_model(REPORT_MODEL_NAME)
except KeyError:
    ENC = tiktoken.get_encoding("cl100k_base")
