# Installation and Setup

<cite>
**Referenced Files in This Document**   
- [SETUP.md](file://SETUP.md)
- [DEPLOYMENT_GUIDE.md](file://DEPLOYMENT_GUIDE.md)
- [README.md](file://README.md)
- [.env.template](file://.env.template)
- [docker-compose.yml](file://docker-compose.yml)
- [src/db_handler/fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py)
</cite>

## Table of Contents
1. [Prerequisites](#prerequisites)  
2. [Obtain API Keys](#obtain-api-keys)  
3. [Environment Configuration](#environment-configuration)  
4. [Docker Setup and Service Initialization](#docker-setup-and-service-initialization)  
5. [Database Initialization](#database-initialization)  
6. [Populate Prompts Table](#populate-prompts-table)  
7. [Verification and Testing](#verification-and-testing)  
8. [Troubleshooting Common Issues](#troubleshooting-common-issues)  
9. [Platform-Specific Notes](#platform-specific-notes)  

## Prerequisites

Before installing and running the VoxPersona application, ensure that your system meets the following prerequisites.

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows 10/11 with WSL2 or Docker Desktop
- **RAM**: Minimum 4GB, recommended 8GB or more for stable operation
- **CPU**: Multi-core processor, recommended 4+ cores
- **Disk Space**: 10GB+ free space (for Docker images, logs, and data)
- **Internet Connection**: Stable connection required for API calls and dependency downloads

### Software Dependencies
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Git**: For cloning the repository
- **Python 3.10+**: Required only for local development (not mandatory for Docker deployment)

**Section sources**
- [README.md](file://README.md#L25-L45)
- [SETUP.md](file://SETUP.md#L4-L20)

## Obtain API Keys

VoxPersona relies on several third-party APIs to function. You must obtain valid API keys and configure them in the `.env` file.

### 1. Anthropic Claude API
1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in to your account
3. Navigate to the "API Keys" section
4. Click "Create Key"
5. Copy the generated key (starts with `sk-ant-`)

**Note**: For improved performance and rate limit handling, it is recommended to provide up to 7 Anthropic API keys (`ANTHROPIC_API_KEY` through `ANTHROPIC_API_KEY_7`).

### 2. OpenAI API
1. Visit [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Go to "API keys"
4. Click "Create new secret key"
5. Copy the key (starts with `sk-`)

### 3. Telegram Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send the command `/newbot`
3. Follow the prompts to name and create your bot
4. Receive the bot token in the format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### 4. Telegram API ID and Hash
1. Visit [my.telegram.org](https://my.telegram.org)
2. Log in using your phone number
3. Go to "API development tools"
4. Create a new application
5. Note down the `API ID` (integer) and `API Hash` (string)

**Section sources**
- [SETUP.md](file://SETUP.md#L24-L80)
- [README.md](file://README.md#L75-L100)

## Environment Configuration

Proper environment configuration is essential for the application to run correctly.

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/VoxPersona.git
cd VoxPersona
```

### Step 2: Create and Edit the .env File
```bash
cp .env.template .env
# Edit using your preferred editor
nano .env
```

### Step 3: Configure .env Variables

The `.env` file contains environment variables used by Docker and the application. Below are the required fields:

```env
# Database Configuration
DB_NAME=bot_db
DB_USER=voxpersona_user
DB_PASSWORD=your_secure_password_here

# API Keys
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
TELEGRAM_BOT_TOKEN=123456789:your_telegram_bot_token_here

# Telegram API
API_ID=your_telegram_api_id_here
API_HASH=your_telegram_api_hash_here

# Bot Configuration
PASSWORD=your_bot_access_password_here
```

**Optional (for performance and scalability):**
```env
ANTHROPIC_API_KEY_2=your_second_key_here
ANTHROPIC_API_KEY_3=your_third_key_here
# ... up to ANTHROPIC_API_KEY_7
```

**Section sources**
- [.env.template](file://.env.template#L1-L45)
- [SETUP.md](file://SETUP.md#L85-L120)

## Docker Setup and Service Initialization

The application uses Docker Compose for container orchestration.

### Step 1: Build and Start Services
```bash
# Build and start all services in detached mode
docker-compose up -d

# Verify container status
docker-compose ps

# Monitor logs
docker-compose logs -f voxpersona
```

### Step 2: Inspect docker-compose.yml
The `docker-compose.yml` file defines two main services:
- `voxpersona`: The main application container
- `postgres`: PostgreSQL database container

Key configurations:
- The `voxpersona` service depends on `postgres`
- Database credentials are passed via environment variables
- Logs and RAG indices are mounted as persistent volumes

```yaml
version: '3.8'
services:
  voxpersona:
    build: .
    container_name: voxpersona_app
    restart: unless-stopped
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      # ... other env vars
    depends_on:
      - postgres
    volumes:
      - ./logs:/app/logs
      - ./rag_indices:/app/rag_indices
  postgres:
    image: postgres:14
    container_name: voxpersona_postgres
    environment:
      - POSTGRES_DB=${DB_NAME}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
volumes:
  postgres_data:
```

**Section sources**
- [docker-compose.yml](file://docker-compose.yml#L1-L70)
- [SETUP.md](file://SETUP.md#L125-L140)

## Database Initialization

After starting the containers, initialize the PostgreSQL schema.

### Step 1: Run Schema Script (if available)
If you have a SQL schema file (e.g., `sql_scripts/create_tables.sql`), execute it:

```bash
# Run schema creation script
docker exec -i voxpersona_postgres psql -U voxpersona_user -d bot_db < sql_scripts/create_tables.sql
```

Alternatively, ensure the schema is created during the first run via application logic.

### Step 2: Verify Database Connection
```bash
# Check if PostgreSQL is ready
docker exec voxpersona_postgres pg_isready -U voxpersona_user -d bot_db

# Access PostgreSQL shell
docker exec -it voxpersona_postgres psql -U voxpersona_user -d bot_db
```

**Section sources**
- [README.md](file://README.md#L170-L180)
- [SETUP.md](file://SETUP.md#L145-L155)

## Populate Prompts Table

The `fill_prompts_table.py` script populates the `prompts` table with prompt files from the `prompts-by-scenario` directory.

### Step 1: Run the Script
```bash
# Execute the script inside the container
docker exec voxpersona_app python src/db_handler/fill_prompts_table.py
```

### Step 2: Understand Script Logic

The script performs the following:
- Traverses the `prompts-by-scenario` directory
- Maps folder names to scenario, report type, building, and part names via `mapping_*` dictionaries in `datamodels.py`
- Inserts or retrieves scenario, report type, and building records
- Creates prompt entries and links them to appropriate scenarios and buildings

Key functions:
- `get_or_create_scenario()`: Ensures unique scenarios
- `get_or_create_report_type()`: Manages report types per scenario
- `get_or_create_prompt()`: Prevents duplicate prompts
- `create_prompts_buildings()`: Establishes prompt-to-building relationships

```python
def main():
    connection = psycopg2.connect(**DB_CONFIG)
    cursor = connection.cursor()

    for scenario_entry in os.scandir(BASE_DIR):
        if scenario_entry.is_dir():
            scenario_name = mapping_scenario_names[scenario_entry.name]
            scenario_id = get_or_create_scenario(cursor, scenario_name)

            for report_type_entry in os.scandir(scenario_entry.path):
                if report_type_entry.is_dir():
                    report_type_name = mapping_report_type_names[report_type_entry.name]
                    report_type_id = get_or_create_report_type(cursor, report_type_name, scenario_id)
                    process_folder(cursor, report_type_entry.path, report_type_id, None)
    connection.commit()
    cursor.close()
    connection.close()
```

**Section sources**
- [src/db_handler/fill_prompts_table.py](file://src/db_handler/fill_prompts_table.py#L1-L228)
- [SETUP.md](file://SETUP.md#L160-L170)

## Verification and Testing

After setup, verify that the system is functioning correctly.

### Step 1: Check Application Logs
```bash
docker-compose logs voxpersona | grep -i "started\|ready\|error"
```

### Step 2: Test Telegram Bot
1. Open Telegram and search for your bot
2. Send `/start`
3. Confirm the bot responds appropriately

### Step 3: Upload Test Audio
1. Send a supported audio file (MP3, WAV, M4A, OGG, up to 50MB)
2. Select an analysis scenario
3. Verify receipt of a structured report

**Section sources**
- [SETUP.md](file://SETUP.md#L175-L190)
- [README.md](file://README.md#L200-L210)

## Troubleshooting Common Issues

### Issue: Container Fails to Start
```bash
# Check logs
docker-compose logs voxpersona

# Validate configuration
docker-compose config

# Rebuild image
docker-compose build --no-cache voxpersona
```

### Issue: API Key Errors
```bash
# Verify environment variables in container
docker exec voxpersona_app env | grep -E "(ANTHROPIC|OPENAI|TELEGRAM)"

# Ensure keys are valid and active
```

### Issue: Database Unavailable
```bash
# Check PostgreSQL status
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### Issue: Insufficient Memory
```bash
# Monitor resource usage
docker stats

# Adjust memory limits in docker-compose.yml
# Change: memory: 10G → memory: 4G (if needed)
```

**Section sources**
- [SETUP.md](file://SETUP.md#L195-L240)

## Platform-Specific Notes

### Windows
- Use **Docker Desktop for Windows** with WSL2 backend
- Ensure file path mappings in `docker-compose.yml` are correct
- Git line endings should be set to LF to avoid script execution issues

### macOS
- Install Docker Desktop from official site
- Allocate at least 8GB RAM in Docker settings
- Use native terminal or iTerm2 for best compatibility

### Linux
- Install Docker and Docker Compose via package manager
- Add user to `docker` group to avoid `sudo` usage:
  ```bash
  sudo usermod -aG docker $USER
  ```
- Ensure sufficient ulimit and sysctl settings for production use

**Section sources**
- [SETUP.md](file://SETUP.md#L10-L20)
- [README.md](file://README.md#L45-L50)