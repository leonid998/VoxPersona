"""
Менеджер для работы с мультичатами.
Принцип KISS - максимальная простота, минимум зависимостей.

Структура хранения:
/home/voxpersona_user/VoxPersona/conversations/
└── user_{user_id}/
    ├── index.json  # Список всех чатов
    ├── {conversation_id}.json  # Чат 1
    └── {conversation_id}.json  # Чат 2
"""

import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from dataclasses import asdict

from conversations import (
    ConversationMessage,
    ConversationMetadata,
    Conversation,
    generate_chat_name
)
from config import CONVERSATIONS_DIR

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Менеджер для работы с мультичатами.

    Реализует CRUD операции, управление активным чатом,
    работу с сообщениями и индексом.
    """

    def __init__(self, base_dir: str | Path):
        """
        Инициализирует менеджер чатов.

        Args:
            base_dir: Базовая директория для хранения чатов
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ConversationManager initialized with base_dir: {self.base_dir}")

    # ========== Вспомогательные функции ==========

    def ensure_user_directory(self, user_id: int) -> Path:
        """
        Создает директорию пользователя если не существует.

        Args:
            user_id: ID пользователя Telegram

        Returns:
            Path: Путь к директории пользователя
        """
        user_dir = self.base_dir / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def conversation_exists(self, user_id: int, conversation_id: str) -> bool:
        """
        Проверяет существование чата.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата

        Returns:
            bool: True если чат существует
        """
        user_dir = self.ensure_user_directory(user_id)
        conversation_file = user_dir / f"{conversation_id}.json"
        return conversation_file.exists()

    # ========== Работа с индексом ==========

    def load_index(self, user_id: int) -> dict:
        """
        Загружает index.json пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            dict: Данные индекса или пустой шаблон
        """
        user_dir = self.ensure_user_directory(user_id)
        index_file = user_dir / "index.json"

        if not index_file.exists():
            # Создаем пустой индекс
            empty_index = {
                "user_id": user_id,
                "username": "",
                "last_active_conversation_id": None,
                "conversations": [],
                "next_chat_number": 1  # Счетчик для автоинкремента номеров чатов
            }
            return empty_index

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
                # Добавляем next_chat_number если его нет (обратная совместимость)
                if "next_chat_number" not in index_data:
                    index_data["next_chat_number"] = 1
                return index_data
        except Exception as e:
            logger.error(f"Failed to load index for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "username": "",
                "last_active_conversation_id": None,
                "conversations": [],
                "next_chat_number": 1
            }

    def save_index(self, user_id: int, index_data: dict) -> bool:
        """
        Сохраняет index.json пользователя.

        Args:
            user_id: ID пользователя
            index_data: Данные индекса

        Returns:
            bool: True если сохранение успешно
        """
        user_dir = self.ensure_user_directory(user_id)
        index_file = user_dir / "index.json"
        temp_file = user_dir / "index.json.tmp"

        try:
            # Atomic write: сначала в temp файл
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)

            # Потом переименовываем
            temp_file.replace(index_file)
            return True
        except Exception as e:
            logger.error(f"Failed to save index for user {user_id}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            return False

    def list_conversations(self, user_id: int) -> List[ConversationMetadata]:
        """
        Возвращает список всех чатов пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            List[ConversationMetadata]: Список метаданных чатов
        """
        index_data = self.load_index(user_id)
        conversations = []

        for conv_dict in index_data.get("conversations", []):
            try:
                metadata = ConversationMetadata(**conv_dict)
                conversations.append(metadata)
            except Exception as e:
                logger.error(f"Failed to parse conversation metadata: {e}")
                continue

        return conversations

    # ========== CRUD операции ==========

    def create_conversation(
        self,
        user_id: int,
        username: str,
        first_question: str = "Новый чат"
    ) -> str:
        """
        Создает новый чат.

        Args:
            user_id: ID пользователя Telegram
            username: Username пользователя
            first_question: Первый вопрос для генерации названия

        Returns:
            str: UUID нового чата
        """
        # 1. Генерируем UUID
        conversation_id = str(uuid.uuid4())

        # 2. Загружаем индекс и получаем следующий номер чата
        index_data = self.load_index(user_id)
        chat_number = index_data.get("next_chat_number", 1)

        # 3. Создаем ConversationMetadata с постоянным номером
        now = datetime.now().isoformat()
        chat_name = generate_chat_name(first_question)

        metadata = ConversationMetadata(
            conversation_id=conversation_id,
            user_id=user_id,
            username=username,
            title=chat_name,
            created_at=now,
            updated_at=now,
            is_active=True,
            message_count=0,
            total_tokens=0,
            chat_number=chat_number
        )

        # 4. Создаем Conversation с пустым списком сообщений
        conversation = Conversation(
            metadata=metadata,
            messages=[]
        )

        # 5. Обновляем все старые чаты: is_active=False
        for conv_dict in index_data.get("conversations", []):
            conv_dict["is_active"] = False

        # 6. Сохраняем новый чат
        if not self.save_conversation(conversation):
            logger.error(f"Failed to save new conversation {conversation_id}")
            raise RuntimeError("Failed to save new conversation")

        # 7. Обновляем index.json и инкрементируем счетчик
        index_data["username"] = username
        index_data["last_active_conversation_id"] = conversation_id
        index_data["conversations"].append(asdict(metadata))
        index_data["next_chat_number"] = chat_number + 1  # Инкрементируем счетчик

        if not self.save_index(user_id, index_data):
            logger.error(f"Failed to save index for user {user_id}")
            raise RuntimeError("Failed to save index")

        logger.info(f"Created conversation {conversation_id} for user {user_id}")
        return conversation_id

    def load_conversation(self, user_id: int, conversation_id: str) -> Optional[Conversation]:
        """
        Загружает чат по ID.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата

        Returns:
            Optional[Conversation]: Объект чата или None
        """
        user_dir = self.ensure_user_directory(user_id)
        conversation_file = user_dir / f"{conversation_id}.json"

        if not conversation_file.exists():
            logger.warning(f"Conversation {conversation_id} not found for user {user_id}")
            return None

        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Десериализуем metadata
            metadata = ConversationMetadata(**data["metadata"])

            # Десериализуем messages
            messages = [ConversationMessage(**msg) for msg in data.get("messages", [])]

            return Conversation(metadata=metadata, messages=messages)
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            return None

    def save_conversation(self, conversation: Conversation) -> bool:
        """
        Сохраняет чат.

        Args:
            conversation: Объект чата

        Returns:
            bool: True если сохранение успешно
        """
        user_id = conversation.metadata.user_id
        conversation_id = conversation.metadata.conversation_id

        user_dir = self.ensure_user_directory(user_id)
        conversation_file = user_dir / f"{conversation_id}.json"
        temp_file = user_dir / f"{conversation_id}.json.tmp"

        try:
            # Atomic write: сначала в temp файл
            data = asdict(conversation)
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Потом переименовываем
            temp_file.replace(conversation_file)

            # Обновляем metadata в index.json
            index_data = self.load_index(user_id)
            for i, conv_dict in enumerate(index_data["conversations"]):
                if conv_dict["conversation_id"] == conversation_id:
                    index_data["conversations"][i] = asdict(conversation.metadata)
                    break

            self.save_index(user_id, index_data)
            return True
        except Exception as e:
            logger.error(f"Failed to save conversation {conversation_id}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            return False

    def delete_conversation(self, user_id: int, conversation_id: str) -> bool:
        """
        Удаляет чат.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата

        Returns:
            bool: True если удаление успешно
        """
        user_dir = self.ensure_user_directory(user_id)
        conversation_file = user_dir / f"{conversation_id}.json"

        try:
            # 1. Удаляем файл чата
            if conversation_file.exists():
                conversation_file.unlink()

            # 2. Удаляем из index.json
            index_data = self.load_index(user_id)
            index_data["conversations"] = [
                c for c in index_data["conversations"]
                if c["conversation_id"] != conversation_id
            ]

            # 3. Если это был активный чат - находим другой или создаем новый
            if index_data["last_active_conversation_id"] == conversation_id:
                if index_data["conversations"]:
                    # Берем первый доступный чат
                    index_data["last_active_conversation_id"] = \
                        index_data["conversations"][0]["conversation_id"]
                    index_data["conversations"][0]["is_active"] = True
                    # Сохраняем индекс только если есть другие чаты
                    self.save_index(user_id, index_data)
                else:
                    # Сохраняем индекс с пустым списком чатов
                    index_data["last_active_conversation_id"] = None
                    self.save_index(user_id, index_data)

                    # Создаем новый чат (он сам сохранит индекс)
                    username = index_data.get("username", "")
                    new_id = self.create_conversation(user_id, username)
            else:
                # Если удаляемый чат не активный, просто сохраняем индекс
                self.save_index(user_id, index_data)
            logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False

    # ========== Управление активным чатом ==========

    def get_active_conversation_id(self, user_id: int) -> Optional[str]:
        """
        Возвращает ID активного чата.

        Args:
            user_id: ID пользователя

        Returns:
            Optional[str]: UUID активного чата или None
        """
        index_data = self.load_index(user_id)
        return index_data.get("last_active_conversation_id")

    def set_active_conversation(self, user_id: int, conversation_id: str) -> bool:
        """
        Устанавливает чат как активный.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата

        Returns:
            bool: True если операция успешна
        """
        if not self.conversation_exists(user_id, conversation_id):
            logger.warning(f"Cannot set active: conversation {conversation_id} not found")
            return False

        try:
            # 1. Загружаем индекс
            index_data = self.load_index(user_id)

            # 2. У всех чатов is_active=False
            for conv_dict in index_data["conversations"]:
                conv_dict["is_active"] = False

            # 3. У выбранного is_active=True
            for conv_dict in index_data["conversations"]:
                if conv_dict["conversation_id"] == conversation_id:
                    conv_dict["is_active"] = True
                    break

            # 4. Обновляем last_active_conversation_id
            index_data["last_active_conversation_id"] = conversation_id

            # 5. Сохраняем изменения
            return self.save_index(user_id, index_data)
        except Exception as e:
            logger.error(f"Failed to set active conversation {conversation_id}: {e}")
            return False

    # ========== Работа с сообщениями ==========

    def add_message(
        self,
        user_id: int,
        conversation_id: str,
        message: ConversationMessage
    ) -> bool:
        """
        Добавляет сообщение в чат.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата
            message: Объект сообщения

        Returns:
            bool: True если добавление успешно
        """
        # 1. Загружаем чат
        conversation = self.load_conversation(user_id, conversation_id)
        if not conversation:
            logger.error(f"Cannot add message: conversation {conversation_id} not found")
            return False

        try:
            # 2. Добавляем сообщение
            conversation.messages.append(message)

            # 3. Обновляем metadata
            conversation.metadata.message_count = len(conversation.messages)
            conversation.metadata.total_tokens += message.tokens
            conversation.metadata.updated_at = datetime.now().isoformat()

            # 4. Сохраняем чат
            if not self.save_conversation(conversation):
                return False

            # 5. Обновляем last_active_conversation_id в индексе
            index_data = self.load_index(user_id)
            index_data["last_active_conversation_id"] = conversation_id
            self.save_index(user_id, index_data)

            return True
        except Exception as e:
            logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
            return False

    def get_messages(
        self,
        user_id: int,
        conversation_id: str,
        limit: int = 20
    ) -> List[ConversationMessage]:
        """
        Возвращает последние N сообщений из чата.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата
            limit: Количество последних сообщений

        Returns:
            List[ConversationMessage]: Список сообщений
        """
        conversation = self.load_conversation(user_id, conversation_id)
        if not conversation:
            logger.warning(f"Cannot get messages: conversation {conversation_id} not found")
            return []

        # Возвращаем последние limit сообщений
        return conversation.messages[-limit:] if len(conversation.messages) > limit \
            else conversation.messages


# Singleton instance
conversation_manager = ConversationManager(CONVERSATIONS_DIR)
