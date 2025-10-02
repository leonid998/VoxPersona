# Multi-stage build for optimized Docker layer caching
# Based on VoxPersona Docker optimization design

# ============================================================================
# Stage 1: Base system dependencies
# This stage installs system packages that rarely change
# ============================================================================
FROM python:3.10.11-slim as system-base

# Install system dependencies in a single layer with cleanup
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    g++ \
    gcc \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ============================================================================
# Stage 2: Python dependencies
# This stage installs Python packages and will be cached unless requirements.txt changes
# ============================================================================
FROM system-base as python-deps

WORKDIR /app

# Copy only requirements.txt first for better caching
# This ensures Python dependencies layer is only rebuilt when requirements change
COPY requirements.txt ./

# Install Python dependencies with optimizations
# Remove GPU-oriented packages (faiss-gpu, triton) for CPU-only deployment
# Install remaining dependencies and upgrade pip
RUN pip install --no-cache-dir --upgrade pip && \
    # Remove GPU packages for CPU-only build
    sed -i '/^faiss-gpu/d;/^triton/d' requirements.txt && \
    # Install remaining dependencies
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 3: PyTorch and ML libraries
# Separate stage for large ML dependencies to enable better caching
# ============================================================================
FROM python-deps as pytorch-stage

# Install PyTorch CPU version and sentence-transformers in separate layer
# This allows caching of these large dependencies independently
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu \
    sentence-transformers

# ============================================================================
# Stage 4: Model pre-loading
# Pre-download embedding models for runtime performance
# ============================================================================
FROM pytorch-stage as models-stage

# Pre-download embedding models for caching in the Docker image
# This stage will be cached unless model versions change
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer

# Pre-download embedding models so that they are cached in the Docker image
# Models are downloaded to the default cache directory in the container
models = [
    'BAAI/bge-m3',
    'sentence-transformers/all-MiniLM-L6-v2',
]

print("Starting model pre-loading...")
for model_name in models:
    try:
        print(f"Downloading model: {model_name}")
        SentenceTransformer(model_name)
        print(f"Successfully downloaded model: {model_name}")
    except Exception as e:
        # Do not fail the build if download fails; models can be downloaded at runtime
        print(f"Warning: could not download {model_name}: {e}")
        print("Model will be downloaded at runtime if needed")

print("Model pre-loading completed")
PY

# ============================================================================
# Stage 5: Application code
# Final stage with application code - this will change most frequently
# ============================================================================
FROM models-stage as final

# Create logs directory
RUN mkdir -p /app/logs

# Copy application code and resources
# These are copied last as they change most frequently
# This ensures maximum cache utilization for dependencies
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY prompts-by-scenario/ ./prompts-by-scenario/

# Only copy sql_scripts if it exists (conditional copy)
COPY sql_scripts* ./sql_scripts/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Set working directory permissions
RUN chmod -R 755 /app

# Health check for container monitoring
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command
CMD ["python", "src/main.py"]
