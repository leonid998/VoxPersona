import os
import shutil
from langchain_community.vectorstores import FAISS

from config import RAG_INDEX_DIR
from storage import safe_filename
from utils import get_embedding_model, CustomSentenceTransformerEmbeddings


def save_rag_indices(rags: dict) -> None:
    """Persist FAISS indices to disk."""
    for name, index in rags.items():
        # Skip objects that do not support local saving
        if not hasattr(index, "save_local"):
            continue
        path = os.path.join(RAG_INDEX_DIR, safe_filename(name))
        shutil.rmtree(path, ignore_errors=True)
        index.save_local(path)


def load_rag_indices() -> dict:
    """Load FAISS indices from disk."""
    import logging
    logging.info(f"🔍 Сканирование директории {RAG_INDEX_DIR} для загрузки FAISS индексов...")

    model = get_embedding_model()
    embeddings = CustomSentenceTransformerEmbeddings(model)
    rags = {}

    if not os.path.exists(RAG_INDEX_DIR):
        logging.warning(f"⚠️  Директория {RAG_INDEX_DIR} не существует!")
        return rags

    found_dirs = [d for d in os.listdir(RAG_INDEX_DIR) if os.path.isdir(os.path.join(RAG_INDEX_DIR, d))]
    logging.info(f"📁 Найдено директорий: {found_dirs}")

    for name in found_dirs:
        path = os.path.join(RAG_INDEX_DIR, name)
        try:
            logging.info(f"⏳ Загрузка FAISS индекса {name} из {path}...")
            rags[name] = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
            logging.info(f"✅ Индекс {name} успешно загружен")
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки индекса {name}: {e}")
            continue

    if rags:
        logging.info(f"✅ Всего загружено FAISS индексов с диска: {len(rags)} ({list(rags.keys())})")
    else:
        logging.warning("⚠️  Ни одного FAISS индекса не загружено!")

    return rags
