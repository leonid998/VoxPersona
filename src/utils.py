import time
import threading
import os
import asyncio
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from io import StringIO
from typing import Optional
from langchain.embeddings.base import Embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
from datamodels import spinner_chars, OPENAI_AUDIO_EXTS
from config import ENC, TELEGRAM_MESSAGE_THRESHOLD, PREVIEW_TEXT_LENGTH, EMBEDDING_MODEL
from constants import ERROR_FILE_SEND_FAILED
from datetime import datetime

# Условный импорт для sentence_transformers
try:
    from sentence_transformers import SentenceTransformer
    _sentence_transformers_available = True
except ImportError:
    _sentence_transformers_available = False
    SentenceTransformer = None
    if not os.getenv('CI'):
        logging.warning("sentence_transformers не установлен. Некоторые функции могут быть недоступны.")

def has_sentence_transformers() -> bool:
    """Проверяет доступность библиотеки sentence_transformers."""
    return _sentence_transformers_available


def get_embedding_model():
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        if not has_sentence_transformers():
            logging.error("sentence_transformers не установлен, модель эмбеддингов недоступна")
            return None
        logging.info("Загружаем локальную модель эмбеддингов BAAI/bge-m3...")
        # Проверяем, что SentenceTransformer доступен перед использованием
        if SentenceTransformer is not None:
            EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')  # pyright: ignore[reportConstantRedefinition]  
    return EMBEDDING_MODEL

class CustomSentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model):
        super().__init__()
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
        _ = time.sleep(0.5)

def sort_tuples_by_second_item(tuple_list):
    # Используем метод sorted() с параметром key
    return sorted(tuple_list, key=lambda x: x[1])

def count_tokens(text: str) -> int:
    return len(ENC.encode(text)) + 10

def split_markdown_text(markdown_text, chunk_size=800, chunk_overlap=100): 
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n", 
            "\n", 
            " ", 
            ""
        ]
    )
    return text_splitter.split_text(markdown_text)

def split_and_send_long_text(text: str, chat_id: int, app: Client, chunk_size: int = 4096, parse_mode: str | None = None):
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


async def get_username_from_chat(chat_id: int, app: Optional[Client] = None) -> str:
    """Получает username пользователя из чата."""
    try:
        if app:
            chat = await app.get_chat(chat_id)
            return chat.username or f"user_{chat_id}"
        return f"user_{chat_id}"
    except Exception as e:
        logging.error(f"Failed to get username for chat_id {chat_id}: {e}")
        return f"user_{chat_id}"


def create_preview_text(text: str, length: int = PREVIEW_TEXT_LENGTH) -> str:
    """Создает превью текста заданной длины."""
    if len(text) <= length:
        return text
    
    # Ищем последний пробел в пределах длины
    preview = text[:length]
    last_space = preview.rfind(' ')
    
    if last_space > length * 0.8:  # Если пробел не слишком близко к началу
        preview = preview[:last_space]
    
    return preview + "..."










def _save_to_history_sync(
    user_id: int,
    username: str,
    message_id: int,
    message_type: str,
    text: str,
    sent_as: Optional[str] = None,
    file_path: Optional[str] = None,
    search_type: Optional[str] = None
) -> None:
    """Синхронно сохраняет сообщение в историю."""
    try:
        from chat_history import chat_history_manager
        success = chat_history_manager.save_message_to_history(
            user_id=user_id,
            username=username,
            message_id=message_id,
            message_type=message_type,
            text=text,
            sent_as=sent_as,
            file_path=file_path,
            search_type=search_type
        )

        if not success:
            logging.error(f"Failed to save message to history: user_id={user_id}")

    except Exception as e:
        logging.error(f"Error saving to history: {e}")


def _save_to_conversation_sync(
    user_id: int,
    conversation_id: str,
    message_id: int,
    message_type: str,
    text: str,
    sent_as: Optional[str] = None,
    file_path: Optional[str] = None,
    search_type: Optional[str] = None
) -> None:
    """Синхронно сохраняет сообщение в мультичат."""
    try:
        from conversation_manager import conversation_manager
        from conversations import ConversationMessage

        # Создаем объект сообщения
        message = ConversationMessage(
            timestamp=datetime.now().isoformat(),
            message_id=message_id,
            type=message_type,
            text=text,
            tokens=count_tokens(text),
            sent_as=sent_as,
            file_path=file_path,
            search_type=search_type
        )

        # Сохраняем в conversation
        success = conversation_manager.add_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message
        )

        if not success:
            logging.error(f"Failed to save message to conversation: user_id={user_id}, conversation_id={conversation_id}")

    except Exception as e:
        logging.error(f"Error saving to conversation: {e}")


async def smart_send_text_unified(
    text: str,
    chat_id: int,
    app: Client,
    username: Optional[str] = None,
    question: str = "",
    search_type: str = "fast",
    parse_mode: Optional[ParseMode] = None,
    conversation_id: Optional[str] = None
) -> bool:
    """
    Единая async функция для умной отправки текста.
    Автоматически выбирает между сообщением и файлом на основе длины текста.

    Args:
        text: Текст для отправки
        chat_id: ID чата
        app: Pyrogram клиент
        username: Имя пользователя (если None, будет получено автоматически)
        question: Исходный вопрос пользователя
        search_type: Тип поиска ("fast" или "deep")
        parse_mode: Режим парсинга для сообщений
        conversation_id: ID мультичата (если None, сохранение в conversations не выполняется)

    Returns:
        bool: True если отправка успешна
    """
    try:
        # Получаем username если не предоставлен
        if username is None:
            username = await get_username_from_chat(chat_id, app)

        # Удаляем префикс @ если есть
        username = username.lstrip('@')

        # Определяем способ отправки на основе длины текста
        if len(text) <= TELEGRAM_MESSAGE_THRESHOLD:
            # Короткое сообщение - отправляем как обычное сообщение
            try:
                sent_message = app.send_message(chat_id, text, parse_mode=parse_mode)

                # Синхронно сохраняем в историю
                _save_to_history_sync(
                    chat_id, username, sent_message.id, "bot_answer", text,
                    sent_as="message", search_type=search_type
                )

                # Синхронно сохраняем в conversations (если передан conversation_id)
                if conversation_id:
                    _save_to_conversation_sync(
                        chat_id, conversation_id, sent_message.id, "bot_answer", text,
                        sent_as="message", search_type=search_type
                    )

                logging.info(f"Message sent to {chat_id}, length: {len(text)} chars")
                return True

            except Exception as e:
                logging.error(f"Failed to send message: {e}")
                return False

        else:
            # Длинное сообщение - отправляем как MD файл
            try:
                # Создаем и отправляем превью
                preview = create_preview_text(text)
                preview_message = f"📄 **Ваш отчет готов!**\n\n{preview}\n\n📎 Полный отчет отправлен файлом."

                try:
                    app.send_message(chat_id, preview_message, parse_mode=parse_mode)
                except Exception as e:
                    logging.error(f"Failed to send preview: {e}")
                    # Продолжаем без превью

                # Сохраняем MD файл
                from md_storage import md_storage_manager
                file_path = md_storage_manager.save_md_report(
                    content=text,
                    user_id=chat_id,
                    username=username,
                    question=question,
                    search_type=search_type
                )

                if not file_path:
                    logging.error("Failed to save MD report, falling back to split send")
                    # Fallback к обычной отправке
                    split_and_send_long_text(text, chat_id, app, parse_mode=parse_mode)
                    return True

                # Отправляем файл
                try:
                    sent_file_msg = app.send_document(
                        chat_id,
                        file_path,
                        caption=f"🔍 Результат {search_type} поиска\n📝 Токенов: {count_tokens(text):,}"
                    )

                    # Синхронно сохраняем в историю
                    _save_to_history_sync(
                        chat_id, username, sent_file_msg.id, "bot_answer", text,
                        sent_as="file", file_path=file_path, search_type=search_type
                    )

                    # Синхронно сохраняем в conversations (если передан conversation_id)
                    if conversation_id:
                        _save_to_conversation_sync(
                            chat_id, conversation_id, sent_file_msg.id, "bot_answer", text,
                            sent_as="file", file_path=file_path, search_type=search_type
                        )

                    logging.info(f"File sent to {chat_id}, path: {file_path}")
                    return True

                except Exception as e:
                    logging.error(f"Failed to send file: {e}")

                    # Отправляем сообщение об ошибке
                    try:
                        app.send_message(chat_id, ERROR_FILE_SEND_FAILED)
                    except:
                        pass

                    # Fallback к обычной отправке
                    split_and_send_long_text(text, chat_id, app, parse_mode=parse_mode)
                    return True

            except Exception as e:
                logging.error(f"Failed to send as file: {e}")
                # Fallback к обычной отправке
                split_and_send_long_text(text, chat_id, app, parse_mode=parse_mode)
                return True

    except Exception as e:
        logging.error(f"Smart send unified failed: {e}")
        # Последний fallback
        try:
            split_and_send_long_text(text, chat_id, app, parse_mode=parse_mode)
            return True
        except:
            return False