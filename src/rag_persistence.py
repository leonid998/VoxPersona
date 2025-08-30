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
    model = get_embedding_model()
    embeddings = CustomSentenceTransformerEmbeddings(model)
    rags = {}

    for name in os.listdir(RAG_INDEX_DIR):
        path = os.path.join(RAG_INDEX_DIR, name)
        if not os.path.isdir(path):
            continue
        try:
            rags[name] = FAISS.load_local(path, embeddings)
        except Exception:
            continue

    return rags
