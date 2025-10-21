"""
Модели данных для системы мультичатов в Telegram боте.
Принцип KISS - максимальная простота.

Миграция с dataclass на Pydantic BaseModel для валидации данных.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime


class ConversationMessage(BaseModel):
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
    timestamp: str = Field(..., description="ISO timestamp сообщения")
    message_id: int = Field(..., gt=0, description="Telegram message ID")
    type: str = Field(..., pattern="^(user_question|bot_answer)$", description="Тип сообщения")
    text: str = Field(..., min_length=1, description="Текст сообщения")
    tokens: int = Field(..., ge=0, description="Количество токенов")
    sent_as: Optional[str] = Field(None, pattern="^(message|file)$", description="Способ отправки")
    file_path: Optional[str] = Field(None, description="Путь к файлу")
    search_type: Optional[str] = Field(None, pattern="^(fast|deep)$", description="Тип поиска")

    model_config = ConfigDict(extra='ignore')

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Валидирует ISO timestamp формат."""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError('Invalid ISO timestamp format')


class ConversationMetadata(BaseModel):
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
        chat_number: Уникальный постоянный номер чата (не пересчитывается при удалении других чатов)
    """
    conversation_id: str = Field(..., description="UUID чата")
    user_id: int = Field(..., gt=0, description="Telegram user ID")
    username: str = Field(..., min_length=1, description="Telegram username")
    title: str = Field(..., min_length=1, max_length=50, description="Название чата")
    created_at: str = Field(..., description="ISO timestamp создания")
    updated_at: str = Field(..., description="ISO timestamp обновления")
    is_active: bool = Field(..., description="Активный чат или нет")
    message_count: int = Field(..., ge=0, description="Количество сообщений")
    total_tokens: int = Field(..., ge=0, description="Сумма токенов")
    chat_number: int = Field(default=0, ge=0, description="Постоянный номер чата")

    model_config = ConfigDict(extra='ignore')

    @field_validator('created_at', 'updated_at')
    @classmethod
    def validate_timestamps(cls, v: str) -> str:
        """Валидирует ISO timestamp формат для дат."""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError('Invalid ISO timestamp format')

    @field_validator('conversation_id')
    @classmethod
    def validate_conversation_id(cls, v: str) -> str:
        """Валидирует формат UUID."""
        if len(v) != 36:
            raise ValueError('conversation_id must be a valid UUID')
        return v


class Conversation(BaseModel):
    """
    Полная структура чата.

    Attributes:
        metadata: Метаданные чата
        messages: Список всех сообщений в чате
    """
    metadata: ConversationMetadata = Field(..., description="Метаданные чата")
    messages: List[ConversationMessage] = Field(default_factory=list, description="Список сообщений")

    model_config = ConfigDict(extra='ignore')


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
