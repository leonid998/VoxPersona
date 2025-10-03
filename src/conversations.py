"""
Модели данных для системы мультичатов в Telegram боте.
Принцип KISS - максимальная простота.
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class ConversationMessage:
    """
    Модель одного сообщения в чате.

    Attributes:
        timestamp: ISO timestamp сообщения
        message_id: ID сообщения в Telegram
        type: Тип сообщения - "user_question" или "bot_answer"
        text: Полный текст сообщения
        tokens: Количество токенов в сообщении
        sent_as: Как отправлено - "message" или "file"
        file_path: Путь к файлу если sent_as="file"
        search_type: Тип поиска - "fast" или "deep"
    """
    timestamp: str
    message_id: int
    type: str
    text: str
    tokens: int
    sent_as: Optional[str] = None
    file_path: Optional[str] = None
    search_type: Optional[str] = None


@dataclass
class ConversationMetadata:
    """
    Метаданные чата.

    Attributes:
        conversation_id: UUID чата
        user_id: ID пользователя Telegram
        username: Username пользователя
        title: Название чата (из первых слов вопроса, max 30 символов)
        created_at: ISO timestamp создания
        updated_at: ISO timestamp последнего сообщения
        is_active: True если это текущий активный чат
        message_count: Количество сообщений в чате
        total_tokens: Сумма токенов всех сообщений
    """
    conversation_id: str
    user_id: int
    username: str
    title: str
    created_at: str
    updated_at: str
    is_active: bool
    message_count: int
    total_tokens: int


@dataclass
class Conversation:
    """
    Полная структура чата.

    Attributes:
        metadata: Метаданные чата
        messages: Список всех сообщений в чате
    """
    metadata: ConversationMetadata
    messages: List[ConversationMessage]


def generate_chat_name(text: str, max_length: int = 30) -> str:
    """
    Генерирует название чата из первых слов текста.

    Логика (KISS):
    1. Удалить лишние пробелы
    2. Взять первые слова до max_length символов
    3. Если текст обрезан - добавить "..."
    4. Минимум 3 слова, максимум max_length символов

    Args:
        text: Исходный текст для генерации названия
        max_length: Максимальная длина названия

    Returns:
        str: Сгенерированное название чата

    Example:
        >>> generate_chat_name("Проанализируй интервью с клиентом из отеля Москва")
        'Проанализируй интервью с...'
    """
    # Удаляем лишние пробелы
    cleaned_text = ' '.join(text.split())

    # Если текст уже короткий - возвращаем как есть
    if len(cleaned_text) <= max_length:
        return cleaned_text

    # Разбиваем на слова
    words = cleaned_text.split()

    # Берем минимум 3 слова
    result_words = []
    current_length = 0

    for word in words:
        # Проверяем, не превысим ли мы длину (с учетом пробелов и "...")
        test_length = current_length + len(word) + (len(result_words) if result_words else 0) + 3

        if test_length > max_length and len(result_words) >= 3:
            break

        result_words.append(word)
        current_length += len(word)

    # Формируем результат
    result = ' '.join(result_words)

    # Добавляем "..." если текст был обрезан
    if len(result) < len(cleaned_text):
        result += "..."

    return result
