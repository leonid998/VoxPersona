
from pyrogram.types import Message
from datetime import datetime
import os

from analysis import transcribe_audio

def extract_audio_filename(message: Message) -> str:
    """
    Извлекает имя аудиофайла из сообщения.
    Если имя файла отсутствует, генерирует уникальное имя на основе времени.
    """
    if message.audio and message.audio.file_name:
        # Если это аудиофайл и у него есть имя
        return message.audio.file_name
    elif message.voice:
        # Для голосовых сообщений имя файла обычно отсутствует, поэтому генерируем уникальное имя
        current_time = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        return f"voice_{current_time}.ogg"
    
    elif message.document and message.document.file_name:
        return message.document.file_name
    else:
        # Если тип файла неизвестен, генерируем имя по умолчанию
        current_time = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        return f"audio_{current_time}.mp3"
    
def define_audio_file_params(message: Message) -> int:
    """
    Возвращает размер файла в байтах для голосового/аудио/документ-с-музыкой.
    """
    if message.voice:
        return message.voice.file_size

    if message.audio:
        return message.audio.file_size

    if message.document:
        return message.document.file_size
    
    raise ValueError("Сообщение не содержит аудио или войс")
    
def transcribe_audio_and_save(downloaded_path: str, chat_id: int, processed_texts: dict[int, str]):
    """
    Выполняет транскрибацию и сохраняет результат в processed_texts[chat_id].
    Без расстановки ролей — только «сырое» распознавание.
    """
    raw_text = transcribe_audio(downloaded_path)
    processed_texts[chat_id] = raw_text
    return raw_text