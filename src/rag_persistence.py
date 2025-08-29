import os
import shutil
from langchain_community.vectorstores import FAISS

from config import RAG_INDEX_DIR
from storage import safe_filename


def save_rag_indices(rags: dict) -> None:
    """Persist FAISS indices to disk."""
    for name, index in rags.items():
        # Skip objects that do not support local saving
        if not hasattr(index, "save_local"):
            continue
        path = os.path.join(RAG_INDEX_DIR, safe_filename(name))
        shutil.rmtree(path, ignore_errors=True)
        index.save_local(path)
