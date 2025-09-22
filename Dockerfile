FROM python:3.10.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    g++ \
    gcc \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем requirements из исходников
COPY requirements.txt ./
# Обновляем pip и устанавливаем зависимости.
# Перед установкой удаляем GPU‑ориентированные пакеты из requirements.txt,
# чтобы контейнер строился на CPU‑версии библиотек. Это исключает
# faiss-gpu и triton, которые требуют CUDA, в то время как код VoxPersona
# использует faiss-cpu и CPU‑вариант sentence‑transformers.
# Также устанавливаем PyTorch (CPU‑версия) и sentence-transformers,
# и заранее скачиваем модели для кэширования в образе.
RUN pip install --no-cache-dir --upgrade pip && \
    # удалить строки с GPU пакетами (faiss-gpu и triton)
    sed -i '/^faiss-gpu/d;/^triton/d' requirements.txt && \
    # установить оставшиеся зависимости
    pip install --no-cache-dir -r requirements.txt && \
    # установить PyTorch CPU версию и sentence-transformers
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu sentence-transformers && \
    # создать директорию для логов
    mkdir -p /app/logs && \
    # предварительно скачать модели для кэширования
    python - <<'PY'
from sentence_transformers import SentenceTransformer

# Pre-download embedding models so that they are cached in the Docker image.
models = [
    'BAAI/bge-m3',
    'sentence-transformers/all-MiniLM-L6-v2',
]
for model_name in models:
    try:
        SentenceTransformer(model_name)
        print(f'Downloaded model: {model_name}')
    except Exception as e:
        # Do not fail the build if download fails; models can be downloaded at runtime.
        print(f'Warning: could not download {model_name}: {e}')
PY

# Копируем исходный код и остальные папки
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY prompts-by-scenario/ ./prompts-by-scenario/
COPY sql_scripts/ ./sql_scripts/



ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]
