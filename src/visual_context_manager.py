"""
Модуль для минимизации старых сообщений бота.

Обеспечивает визуальную очистку экрана через минимизацию сообщений до символа "·".
Простой утилитный класс без бизнес-логики.

Создано: 2025-01-04
Рефакторинг: 2025-01-04 (упрощение до минимального API)
"""

import logging
from typing import Dict, List
from pyrogram import Client
from pyrogram.errors import MessageIdInvalid

logger = logging.getLogger(__name__)


class VisualContextManager:
    """
    Утилитный класс для минимизации старых сообщений бота.

    Простой API:
    - track_message() - запомнить ID отправленного сообщения
    - minimize_messages() - минимизировать все сообщения контекста до "·"

    Используется для визуальной очистки экрана при переключении контекстов.
    """

    # Структура: {chat_id: {context: [msg_ids]}}
    # context = "system" или conversation_id
    _tracked_messages: Dict[int, Dict[str, List[int]]] = {}

    @classmethod
    def track_message(cls, chat_id: int, context: str, message_id: int) -> None:
        """
        Трекает ID отправленного сообщения бота для последующей минимизации.

        Args:
            chat_id: ID чата Telegram
            context: Контекст сообщения ("system" или conversation_id)
            message_id: ID сообщения для трекинга
        """
        if chat_id not in cls._tracked_messages:
            cls._tracked_messages[chat_id] = {}

        if context not in cls._tracked_messages[chat_id]:
            cls._tracked_messages[chat_id][context] = []

        cls._tracked_messages[chat_id][context].append(message_id)
        logger.info(f"Tracked message {message_id} in context '{context}' for chat {chat_id}")

    @classmethod
    async def minimize_messages(
        cls,
        chat_id: int,
        app: Client,
        context: str
    ) -> int:
        """
        Минимизирует все сообщения указанного контекста до символа "·".

        Args:
            chat_id: ID чата
            app: Pyrogram клиент
            context: Контекст для минимизации ("system" или conversation_id)

        Returns:
            Количество успешно минимизированных сообщений
        """
        # Получаем список сообщений для минимизации
        message_ids = cls._tracked_messages.get(chat_id, {}).get(context, [])

        if not message_ids:
            logger.info(f"No messages to minimize for context '{context}' in chat {chat_id}")
            return 0

        minimized_count = 0

        for msg_id in message_ids:
            try:
                logger.debug(f"Attempting to minimize message {msg_id} in chat {chat_id}")
                await app.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text="·",
                    reply_markup=None  # Явно удаляем InlineKeyboardMarkup
                )
                minimized_count += 1
                logger.debug(f"Successfully minimized message {msg_id} in chat {chat_id}")

            except MessageIdInvalid:
                logger.debug(f"Message {msg_id} not found (already deleted?)")
            except Exception as e:
                logger.warning(f"Failed to minimize message {msg_id}: {type(e).__name__}: {e}")

        # Очищаем список после минимизации
        if chat_id in cls._tracked_messages and context in cls._tracked_messages[chat_id]:
            cls._tracked_messages[chat_id][context] = []

        logger.info(f"Minimized {minimized_count}/{len(message_ids)} messages for context '{context}' in chat {chat_id}")
        return minimized_count

    @classmethod
    def clear_tracked_messages(cls, chat_id: int, context: str) -> None:
        """
        Очищает отслеживаемые сообщения для контекста без минимизации.

        Args:
            chat_id: ID чата
            context: Контекст для очистки
        """
        if chat_id in cls._tracked_messages and context in cls._tracked_messages[chat_id]:
            cls._tracked_messages[chat_id][context] = []
            logger.debug(f"Cleared tracked messages for context '{context}' in chat {chat_id}")
