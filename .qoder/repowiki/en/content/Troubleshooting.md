# Troubleshooting

<cite>
**Referenced Files in This Document**   
- [docker-compose.yml](file://docker-compose.yml)
- [Dockerfile](file://Dockerfile)
- [src/main.py](file://src/main.py)
- [src/config.py](file://src/config.py)
- [src/utils.py](file://src/utils.py)
- [src/handlers.py](file://src/handlers.py)
- [src/audio_utils.py](file://src/audio_utils.py)
- [src/analysis.py](file://src/analysis.py)
- [src/db_handler/db.py](file://src/db_handler/db.py)
- [src/run_analysis.py](file://src/run_analysis.py)
- [src/storage.py](file://src/storage.py)
</cite>

## Table of Contents
1. [Deployment Issues](#deployment-issues)
2. [Configuration Problems](#configuration-problems)
3. [Audio Processing Errors](#audio-processing-errors)
4. [Analysis Failures](#analysis-failures)
5. [Database Issues](#database-issues)
6. [Utility Functions for Debugging](#utility-functions-for-debugging)

## Deployment Issues

### Container Fails to Start
When the VoxPersona container fails to start, check the following diagnostic steps:

1. **Inspect container logs**:
```bash
docker-compose logs voxpersona
```

2. **Verify container status**:
```bash
docker-compose ps
```

3. **Check Docker resource allocation**:
```bash
docker stats
```

Common causes include:
- Insufficient memory (container requires up to 10GB as defined in docker-compose.yml)
- Missing dependencies in the Docker image
- Port conflicts on port 5432 (PostgreSQL)

**Solution**: 
- Ensure host machine has sufficient RAM (8GB+ recommended)
- Verify no other PostgreSQL instance is running on port 5432
- Rebuild the container with `docker-compose build --no-cache voxpersona`

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L1-L70)
- [Dockerfile](file://Dockerfile#L1-L67)

### Port Conflicts
The application uses PostgreSQL on port 5432 by default.

**Diagnostic steps**:
```bash
# Check if port 5432 is already in use
netstat -an | grep 5432
# or on Linux
lsof -i :5432
```

**Solution**:
- Stop the conflicting service
- Or modify the port mapping in docker-compose.yml:
```yaml
ports:
  - "5433:5432"  # Map host port 5433 to container port 5432
```

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L58-L60)

## Configuration Problems

### Missing API Keys
The system requires several API keys to function properly.

**Diagnostic steps**:
1. Check environment variables in the container:
```bash
docker exec voxpersona_app env | grep -E "(ANTHROPIC|OPENAI|TELEGRAM)"
```

2. Verify .env file exists and is properly formatted:
```bash
ls -la .env
cat .env | grep -v "^#" | grep -v "^$"
```

Required keys include:
- ANTHROPIC_API_KEY
- OPENAI_API_KEY
- TELEGRAM_BOT_TOKEN
- API_ID and API_HASH

**Solution**:
1. Create .env file from template:
```bash
cp .env.template .env
```

2. Populate all required fields and restart:
```bash
docker-compose down && docker-compose up -d
```

**Section sources**
- [src/config.py](file://src/config.py#L30-L45)
- [docker-compose.yml](file://docker-compose.yml#L10-L35)

### Incorrect .env Setup
The application validates essential configuration at startup.

**Diagnostic steps**:
1. Check for configuration error messages:
```bash
docker-compose logs voxpersona | grep "Не все ключи"
```

2. Verify file permissions:
```bash
chmod 600 .env
```

**Common issues**:
- Missing required environment variables
- Incorrect variable names in .env file
- Special characters in passwords not properly escaped

**Solution**:
Ensure .env file contains all required variables as specified in the documentation. The application will raise a ValueError if essential keys are missing.

**Section sources**
- [src/config.py](file://src/config.py#L85-L88)

## Audio Processing Errors

### Transcription Errors
Transcription failures can occur due to various reasons.

**Diagnostic steps**:
1. Check audio processing logs:
```bash
docker-compose logs voxpersona | grep -i "transcribe"
```

2. Verify audio file format compatibility.

**Common causes**:
- Unsupported audio formats
- Corrupted audio files
- Audio files exceeding size limits (50MB)

**Solution**:
- Convert audio to supported formats (MP3, WAV, M4A, OGG)
- Use ffmpeg to repair or convert files:
```bash
ffmpeg -i input.corrupted.mp3 -c:a libmp3lame output.mp3
```

**Section sources**
- [src/audio_utils.py](file://src/audio_utils.py)
- [src/analysis.py](file://src/analysis.py)

### Format Incompatibilities
The system relies on ffmpeg for audio processing.

**Diagnostic steps**:
1. Verify ffmpeg installation in container:
```bash
docker exec voxpersona_app ffmpeg -version
```

2. Test audio conversion:
```bash
docker exec voxpersona_app ffmpeg -i test.mp3 -f null -
```

**Solution**:
Ensure ffmpeg is properly installed in the Docker image. The Dockerfile includes ffmpeg installation:
```dockerfile
RUN apt-get update && apt-get install -y ffmpeg
```

If issues persist, rebuild the image to ensure ffmpeg is correctly installed.

**Section sources**
- [Dockerfile](file://Dockerfile#L4-L8)

## Analysis Failures

### LLM Timeouts
Large language model requests may timeout under certain conditions.

**Diagnostic steps**:
1. Monitor analysis logs:
```bash
docker-compose logs voxpersona | grep -i "timeout\|error"
```

2. Check network connectivity from container:
```bash
docker exec voxpersona_app curl -I https://api.anthropic.com
```

**Common causes**:
- Network connectivity issues
- API rate limiting
- Overloaded LLM services

**Solution**:
- Implement retry logic with exponential backoff
- Use multiple API keys for load balancing (up to 7 Anthropic keys supported)
- Reduce request frequency

The system supports multiple Anthropic API keys for load distribution:
```yaml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - ANTHROPIC_API_KEY_2=${ANTHROPIC_API_KEY_2:-}
  # ... up to ANTHROPIC_API_KEY_7
```

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L18-L24)
- [src/analysis.py](file://src/analysis.py)

### Malformed Prompts
Prompt formatting issues can cause analysis failures.

**Diagnostic steps**:
1. Check prompt loading logs:
```bash
docker-compose logs voxpersona | grep -i "prompt\|load"
```

2. Verify prompt files exist and are readable:
```bash
docker exec voxpersona_app ls -la /app/prompts/
```

**Solution**:
- Ensure prompt files are properly formatted
- Verify file encoding is UTF-8
- Check file permissions within the container

The system loads prompts from two directories:
- `/app/prompts/` - General prompts
- `/app/prompts-by-scenario/` - Scenario-specific prompts

**Section sources**
- [src/main.py](file://src/main.py#L1-L96)
- [Dockerfile](file://Dockerfile#L60-L63)

## Database Issues

### Connection Errors
Database connectivity problems are common during startup.

**Diagnostic steps**:
1. Check PostgreSQL container status:
```bash
docker-compose ps postgres
```

2. Verify database logs:
```bash
docker-compose logs postgres
```

3. Test database connectivity:
```bash
docker exec voxpersona_postgres pg_isready -U voxpersona_user -d bot_db
```

**Common causes**:
- Incorrect database credentials
- Database not fully initialized
- Volume permission issues

**Solution**:
1. Verify database credentials in .env file
2. Wait for PostgreSQL to fully initialize
3. Reset database if necessary:
```bash
docker-compose down -v && docker-compose up -d
```

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L40-L56)
- [src/config.py](file://src/config.py#L47-L65)

### Schema Mismatches
Schema issues can occur when database structure doesn't match application expectations.

**Diagnostic steps**:
1. Check database schema:
```bash
docker exec -i voxpersona_postgres psql -U voxpersona_user -d bot_db -c "\dt"
```

2. Verify table structures:
```bash
docker exec -i voxpersona_postgres psql -U voxpersona_user -d bot_db -c "\d audit"
```

**Solution**:
1. Initialize database with proper schema:
```bash
docker exec -i voxpersona_postgres psql -U voxpersona_user -d bot_db < sql_scripts/create_tables.sql
```

2. Or enable automatic initialization by uncommenting the volume mount in docker-compose.yml:
```yaml
volumes:
  - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L52-L54)
- [src/db_handler/db.py](file://src/db_handler/db.py)

## Utility Functions for Debugging

The system provides several utility functions to aid in debugging.

### RAG Index Management
The RAG persistence module handles saving and loading of retrieval indices.

```python
from rag_persistence import save_rag_indices, load_rag_indices
```

**Diagnostic usage**:
```bash
# Check if RAG indices are being saved
ls -la rag_indices/
# Verify file modification times correspond to expected save intervals
```

The system automatically saves RAG indices every 15 minutes via `periodic_save_rags()` function.

**Section sources**
- [src/main.py](file://src/main.py#L15-L30)
- [src/rag_persistence.py](file://src/rag_persistence.py)

### Logging and Monitoring
Comprehensive logging is implemented throughout the application.

**Key log locations**:
- Application logs: `/app/logs/` (mounted to ./logs on host)
- Docker container logs: `docker-compose logs`
- Error tracking: All exceptions are logged with full context

**Log monitoring command**:
```bash
docker-compose logs -f voxpersona | grep -i "error\|warning\|exception"
```

**Section sources**
- [src/main.py](file://src/main.py#L4-L6)
- [src/config.py](file://src/config.py#L5-L6)

### State Tracking
The system maintains several global state dictionaries for debugging:

```python
# In config.py
processed_texts: dict[int, str] = {}     # Processed text cache
user_states: dict[int, dict] = {}        # User interaction states
authorized_users = set()                # Authorized user IDs
active_menus: dict[int, list[int]] = {} # Active menu messages
```

These can be inspected during debugging to understand application state.

**Section sources**
- [src/config.py](file://src/config.py#L70-L73)