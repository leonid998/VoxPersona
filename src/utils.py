import time
import threading
from pyrogram import Client
from pyrogram.types import Message
from io import StringIO
from langchain.embeddings.base import Embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import logging
from datamodels import spinner_chars, OPENAI_AUDIO_EXTS
from config import EMBEDDING_MODEL, ENC


def get_embedding_model():
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        logging.info("Загружаем локальную модель эмбеддингов BAAI/bge-m3...")
        EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2', device='cpu') #SentenceTransformer('BAAI/bge-m3', device='cpu') #SentenceTransformer('all-MiniLM-L6-v2', device='cpu')  
    return EMBEDDING_MODEL

class CustomSentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model):
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
        return embedding.tolist()

def openai_audio_filter(_, __, m: Message) -> bool:
    """
    Возвращает True, если сообщение содержит аудиофайл или голосовое сообщение,
    либо документ с именем, оканчивающимся на один из поддерживаемых Whisper форматов.
    """
    # 1) Если это голосовое (voice) или "обычное" аудио (audio) — сразу True
    if m.voice or m.audio:
        return True

    # 2) Если это документ с файлом, проверяем расширение
    if m.document and m.document.file_name:
        file_name = m.document.file_name.lower()
        return any(file_name.endswith(ext) for ext in OPENAI_AUDIO_EXTS)

    return False

def run_loading_animation(chat_id: int, msg_id: int, stop_event: threading.Event, app: Client):
    """
    Фоновая анимация "спиннера", пока stop_event не завершится.
    """
    idx = 0
    while not stop_event.is_set():
        sp = spinner_chars[idx % len(spinner_chars)]
        try:
            app.send_chat_action(chat_id, msg_id, f"⏳ Обработка... {sp}")
        except:
            pass
        idx += 1
        time.sleep(0.5)

def sort_tuples_by_second_item(tuple_list):
    # Используем метод sorted() с параметром key
    return sorted(tuple_list, key=lambda x: x[1])

def count_tokens(text: str) -> int:
    return len(ENC.encode(text)) + 10

def split_markdown_text(markdown_text, chunk_size=800, chunk_overlap=100): 
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    return text_splitter.split_text(markdown_text)

def split_and_send_long_text(text: str, chat_id: int, app: Client, chunk_size: int = 4096, parse_mode: str = None):
    """
    Для отправки длинных результатов, разбитых на части по 4096 символов.
    """
    for i in range(0, len(text), chunk_size):
        app.send_message(chat_id, text[i:i+chunk_size], parse_mode=parse_mode)

def clean_text(text: str) -> str:
    """Удаляет ведущие # внутри текста, чтобы не мешали разделению чанков."""
    cleaned_lines = []
    for line in text.splitlines():
        if line.strip().startswith('#'):
            cleaned_lines.append(line.lstrip('#').strip())
        else:
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)

def grouped_reports_to_string(grouped_reports):
    output = StringIO()
    
    for transcription_id, texts in grouped_reports.items():
        output.write(f"# Чанк transcription_id {transcription_id}\n\n")
        output.write("\n\n".join(texts))
        output.write("\n\n" + "="*100 + "\n\n")
    
    result = output.getvalue()
    output.close()
    
    return result