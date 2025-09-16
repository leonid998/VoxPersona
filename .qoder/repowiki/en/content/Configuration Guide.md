# Configuration Guide

<cite>
**Referenced Files in This Document**   
- [config.py](file://src/config.py#L1-L93)
- [.env.template](file://.env.template#L1-L45)
- [SETUP.md](file://SETUP.md#L76-L131)
- [docker-compose.yml](file://docker-compose.yml#L1-L37)
- [analysis.py](file://src/analysis.py#L170-L425)
- [README.md](file://README.md#L1-L223)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Configuration Parameters in config.py](#configuration-parameters-in-configpy)
3. [Environment Variables and .env File](#environment-variables-and-env-file)
4. [Multi-Environment Configuration](#multi-environment-configuration)
5. [Model and API Configuration](#model-and-api-configuration)
6. [MinIO and Storage Settings](#minio-and-storage-settings)
7. [Runtime Settings and Feature Flags](#runtime-settings-and-feature-flags)
8. [Best Practices for Securing Credentials](#best-practices-for-securing-credentials)
9. [Customizing Analysis Behavior](#customizing-analysis-behavior)
10. [Common Misconfigurations and Debugging](#common-misconfigurations-and-debugging)

## Introduction
The VoxPersona platform is an AI-powered voice analysis system that leverages large language models (LLMs) for transcription, content analysis, and report generation. Central to its operation is a robust configuration system based on environment variables and runtime settings. This guide provides a comprehensive overview of the configuration framework, focusing on the `config.py` file, `.env` template, and related components. It explains how to properly set up API keys, database connections, model parameters, and feature flags across different deployment environments.

**Section sources**
- [README.md](file://README.md#L1-L223)

## Configuration Parameters in config.py
The `src/config.py` file serves as the central configuration module, loading environment variables and defining global settings used throughout the application.

### API Keys and Authentication
The configuration file retrieves API credentials for external services:
- **OpenAI**: `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- **Anthropic (Claude)**: `ANTHROPIC_API_KEY` through `ANTHROPIC_API_KEY_7`
- **Telegram Bot**: `TELEGRAM_BOT_TOKEN`, `SESSION_NAME`
- **Telegram API**: `API_ID`, `API_HASH`

These keys are loaded via `os.getenv()` from the environment, ensuring sensitive data is not hardcoded.

### Database Configuration
Database settings are dynamically assigned based on the `RUN_MODE`:
```python
if RUN_MODE == "TEST":
    DB_CONFIG = {
        "dbname": os.getenv("TEST_DB_NAME"),
        "user": os.getenv("TEST_DB_USER"),
        "password": os.getenv("TEST_DB_PASSWORD"),
        "host": os.getenv("TEST_DB_HOST"),  
        "port": os.getenv("TEST_DB_PORT"),       
    }
else:
    DB_CONFIG = {
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),  
        "port": os.getenv("DB_PORT"),     
    }
```

### Model and Processing Settings
- `TRANSCRIBATION_MODEL_NAME`: Specifies the Whisper model for audio transcription
- `REPORT_MODEL_NAME`: Defines the LLM (e.g., `claude-3-7-sonnet-20250219`) used for analysis
- Token encoding via `tiktoken` for accurate token counting

### Global State Management
The configuration defines shared data structures:
- `processed_texts`: Cache for processed text by user ID
- `user_states`: Track conversation state per user
- `authorized_users`: Set of authorized Telegram user IDs
- `active_menus`: Manage active menu states

**Section sources**
- [config.py](file://src/config.py#L1-L93)

## Environment Variables and .env File
The `.env.template` file provides a blueprint for configuring the application.

### Required Environment Variables
| Variable | Purpose | Example |
|--------|--------|--------|
| `ANTHROPIC_API_KEY` | Primary Anthropic API key | `sk-ant-api03-...` |
| `OPENAI_API_KEY` | OpenAI API key for Whisper | `sk-your_openai_key_here` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | `123456789:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `API_ID` | Telegram API ID | `1234567` |
| `API_HASH` | Telegram API hash | `your_telegram_api_hash_here` |
| `PASSWORD` | Bot access password | `your_bot_access_password_here` |

### Optional Variables
- Multiple Anthropic keys (`ANTHROPIC_API_KEY_2` to `_7`) for load balancing
- MinIO storage configuration for audio and document storage
- VseGPT API key (optional)

### Setup Process
1. Copy `.env.template` to `.env`
2. Fill in required values
3. Keep `.env` out of version control

```env
# Database Configuration
DB_NAME=bot_db
DB_USER=voxpersona_user
DB_PASSWORD=your_secure_password_here

# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-your_anthropic_key_here
OPENAI_API_KEY=sk-your_openai_key_here
TELEGRAM_BOT_TOKEN=123456789:your_telegram_bot_token_here

# Telegram API
API_ID=your_telegram_api_id_here
API_HASH=your_telegram_api_hash_here

# Bot Configuration
PASSWORD=your_bot_access_password_here
```

**Section sources**
- [.env.template](file://.env.template#L1-L45)
- [SETUP.md](file://SETUP.md#L76-L131)

## Multi-Environment Configuration
The system supports different configurations for development, testing, and production environments through the `RUN_MODE` variable.

### Environment Modes
- **PROD (Production)**: Uses primary database and production credentials
- **TEST**: Uses test database and test-specific credentials

### Conditional Configuration
```python
RUN_MODE = os.getenv("RUN_MODE")

if RUN_MODE == "TEST":
    DB_CONFIG = { /* test database settings */ }
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_TEST_NAME")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_TEST")
else:
    DB_CONFIG = { /* production database settings */ }
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```

### Docker Environment Mapping
The `docker-compose.yml` file maps environment variables:
```yaml
environment:
  - API_ID=${API_ID}
  - API_HASH=${API_HASH}
  - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - DB_NAME=${DB_NAME:-bot_db}
  - RUN_MODE=${RUN_MODE:-PROD}
```

This allows environment-specific `.env` files to be used in different deployment contexts.

**Section sources**
- [config.py](file://src/config.py#L38-L70)
- [docker-compose.yml](file://docker-compose.yml#L1-L37)

## Model and API Configuration
The configuration system enables flexible integration with multiple LLM providers and API services.

### LLM Provider Configuration
The system supports multiple LLM providers:
- **Anthropic Claude**: Primary analysis model
- **OpenAI Whisper**: Audio transcription service

```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
TRANSCRIBATION_MODEL_NAME = os.getenv("TRANSCRIBATION_MODEL_NAME")     # Whisper
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")      # Claude
REPORT_MODEL_NAME = os.getenv("REPORT_MODEL_NAME")
```

### Load Balancing Across Multiple Keys
The system can utilize up to seven Anthropic API keys for rate limit management:
```python
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_KEY_2 = os.getenv("ANTHROPIC_API_KEY_2")
...
ANTHROPIC_API_KEY_7 = os.getenv("ANTHROPIC_API_KEY_7")
```

This enables parallel processing with rate limit awareness in `analysis.py`:
```python
token_limits_per_min = [80000, 20000, 20000, 20000, 20000, 20000, 20000]
req_limits_per_min =   [2000,   50,    50,    50,    50,   50,   50]
```

### Model Parameters
- **Temperature**: Hardcoded to 0.1 in `send_msg_to_model()` for consistent, deterministic responses
- **Max Tokens**: Configurable via `max_tokens` parameter (default: 20000)
- **Token Encoding**: Uses `tiktoken` with fallback to `cl100k_base` encoding

**Section sources**
- [config.py](file://src/config.py#L1-L93)
- [analysis.py](file://src/analysis.py#L399-L425)

## MinIO and Storage Settings
The configuration includes settings for MinIO object storage integration.

### MinIO Configuration Variables
- `MINIO_ENDPOINT`: MinIO server URL
- `MINIO_ACCESS_KEY`: Access key for authentication
- `MINIO_SECRET_KEY`: Secret key for authentication
- `MINIO_BUCKET_NAME`: Main bucket name
- `MINIO_AUDIO_BUCKET_NAME`: Audio-specific bucket (default: `voxpersona-audio`)

### Directory Structure
The system uses predefined storage directories:
```python
STORAGE_DIRS = {
    "audio": "/root/Vox/VoxPersona/audio_files",
    "text_without_roles": "/root/Vox/VoxPersona/text_with_roles",
    "text_with_roles": "/root/Vox/VoxPersona/text_without_roles"
}
```

### RAG Index Storage
```python
RAG_INDEX_DIR = "/app/rag_indices"
os.makedirs(RAG_INDEX_DIR, exist_ok=True)
```

This ensures persistent storage of vector indices when deployed with Docker volumes.

**Section sources**
- [config.py](file://src/config.py#L60-L75)

## Runtime Settings and Feature Flags
The configuration includes various runtime settings and feature flags.

### Feature Flags
- `RUN_MODE`: Controls environment-specific behavior (PROD/TEST)
- Multiple Anthropic keys act as a load balancing feature flag
- Optional MinIO and VseGPT integrations

### Global State Management
The configuration defines shared state objects:
```python
processed_texts: dict[int, str] = {}
user_states: dict[int, dict] = {}
authorized_users = set()  
active_menus: dict[int, list[int]] = {}
```

These enable persistent user session tracking across the application.

### Validation and Error Handling
The system validates critical configuration at startup:
```python
if not all([OPENAI_API_KEY, ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("Не все ключи (OPENAI_API_KEY, VSEGPT_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH) заданы!")
```

This prevents startup with incomplete configuration.

**Section sources**
- [config.py](file://src/config.py#L70-L93)

## Best Practices for Securing Credentials
Proper credential management is critical for system security.

### Environment Isolation
- Use separate `.env` files for different environments
- Never commit `.env` files to version control
- Use different API keys for development and production

### Access Controls
- Restrict access to the `.env` file (chmod 600)
- Use role-based access for database credentials
- Rotate API keys periodically
- Use dedicated service accounts for MinIO

### Secure Deployment
- Store `.env` files outside web root
- Use Docker secrets for production deployments
- Implement monitoring for unauthorized access attempts
- Regularly audit credential usage

### Credential Validation
The system performs startup validation:
```python
if not all([OPENAI_API_KEY, ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("Critical API keys are missing!")
```

This fails fast on misconfiguration, preventing insecure operation.

**Section sources**
- [config.py](file://src/config.py#L70-L75)
- [README.md](file://README.md#L1-L223)

## Customizing Analysis Behavior
The configuration system enables customization of analysis workflows.

### Switching LLM Providers
While Anthropic is primary, the system could be extended to support other providers by:
1. Adding new API key variables
2. Modifying `send_msg_to_model()` to route based on configuration
3. Implementing provider-specific error handling

### Adjusting RAG Retrieval
The `generate_db_answer()` function allows customization of retrieval behavior:
```python
def generate_db_answer(query: str, db_index, k: int=15, verbose: bool=True):
```
- `k`: Number of relevant chunks to retrieve (adjust for precision/recall trade-off)
- `verbose`: Enable/disable debug logging of retrieved chunks

### Model Parameter Tuning
Although temperature is currently hardcoded, it could be made configurable:
```python
model_args = {
    "model": model,
    "max_tokens": max_tokens,
    "temperature": float(os.getenv("MODEL_TEMPERATURE", "0.1")),
    "messages": messages
}
```

### Parallel Processing Configuration
The system supports parallel analysis with configurable rate limits:
```python
token_limits_per_min = [80000, 20000, 20000, 20000, 20000, 20000, 20000]
req_limits_per_min =   [2000,   50,    50,    50,    50,   50,   50]
```

These can be adjusted based on API rate limits and performance requirements.

**Section sources**
- [analysis.py](file://src/analysis.py#L170-L200)
- [analysis.py](file://src/analysis.py#L300-L338)

## Common Misconfigurations and Debugging
Understanding common configuration issues is essential for smooth operation.

### Missing Required Variables
**Symptom**: Application fails to start with "Critical API keys are missing!" error
**Solution**: Ensure all required variables are set in `.env`:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `API_ID`
- `API_HASH`

### Incorrect Database Configuration
**Symptom**: Database connection errors
**Solution**: Verify:
- Database is running
- Host, port, and credentials match
- Database name exists
- For Docker, ensure network connectivity between containers

### Model Name Mismatch
**Symptom**: "Model not found" errors
**Solution**: Verify model names match provider specifications:
- `TRANSCRIBATION_MODEL_NAME=whisper-1`
- `REPORT_MODEL_NAME=claude-3-7-sonnet-20250219`

### Rate Limit Issues
**Symptom**: 429 errors from Anthropic API
**Solution**:
- Implement proper rate limiting in `extract_from_chunk_parallel()`
- Use multiple API keys for load distribution
- Monitor token usage and adjust `token_limits_per_min`

### Debugging Techniques
1. **Enable Verbose Logging**: Set `verbose=True` in `generate_db_answer()`
2. **Check Environment Variables**: Use `printenv` or logging to verify values
3. **Test API Connectivity**: Use curl to test API endpoints independently
4. **Review Docker Logs**: `docker-compose logs -f voxpersona`

```python
if verbose:
    logging.info(f"Token counts - System: {system_tokens}, Docs: {docs_tokens}, Query: {query_tokens}")
```

**Section sources**
- [config.py](file://src/config.py#L70-L75)
- [analysis.py](file://src/analysis.py#L170-L200)
- [analysis.py](file://src/analysis.py#L197-L231)