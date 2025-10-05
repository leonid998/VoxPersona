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

    def _cleanup_temp_files(self, temp_files: List[Path]) -> None:
        """
        Удаляет временные файлы при откате транзакции.

        Args:
            temp_files: Список путей к временным файлам
        """
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

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
                metadata = ConversationMetadata.model_validate(conv_dict)
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
        index_data["conversations"].append(metadata.model_dump())
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
            metadata = ConversationMetadata.model_validate(data.get("metadata", {}))

            # Десериализуем messages
            messages = [ConversationMessage.model_validate(msg) for msg in data.get("messages", [])]

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
            data = {"schema_version": "1.0", "metadata": conversation.metadata.model_dump(), "messages": [msg.model_dump() for msg in conversation.messages]}
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Потом переименовываем
            temp_file.replace(conversation_file)

            # Обновляем metadata в index.json
            index_data = self.load_index(user_id)
            for i, conv_dict in enumerate(index_data["conversations"]):
                if conv_dict["conversation_id"] == conversation_id:
                    index_data["conversations"][i] = conversation.metadata.model_dump()
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
        Удаляет чат и все связанные MD файлы.

        Args:
            user_id: ID пользователя
            conversation_id: UUID чата

        Returns:
            bool: True если удаление успешно
        """
        user_dir = self.ensure_user_directory(user_id)
        conversation_file = user_dir / f"{conversation_id}.json"

        try:
            # 1. СНАЧАЛА загружаем чат чтобы получить file_path для MD файлов
            conversation = self.load_conversation(user_id, conversation_id)

            md_files_deleted = 0
            if conversation:
                # 2. Собираем все MD файлы из сообщений
                md_files_to_delete = [
                    msg.file_path
                    for msg in conversation.messages
                    if msg.file_path and msg.sent_as == "file"
                ]

                # 3. Удаляем MD файлы
                for file_path in md_files_to_delete:
                    try:
                        full_path = Path(file_path)
                        if full_path.exists():
                            full_path.unlink()
                            md_files_deleted += 1
                            logger.info(f"Deleted MD file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete MD file {file_path}: {e}")

                if md_files_deleted > 0:
                    logger.info(f"Deleted {md_files_deleted} MD files for conversation {conversation_id}")

            # 4. Удаляем файл чата
            if conversation_file.exists():
                conversation_file.unlink()

            # 5. Удаляем из index.json
            index_data = self.load_index(user_id)
            index_data["conversations"] = [
                c for c in index_data["conversations"]
                if c["conversation_id"] != conversation_id
            ]

            # 6. Если это был активный чат - находим другой или создаем новый
            if index_data["last_active_conversation_id"] == conversation_id:
                if index_data["conversations"]:
                    # Берем первый доступный чат
                    index_data["last_active_conversation_id"] =                         index_data["conversations"][0]["conversation_id"]
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
        Добавляет сообщение в чат с транзакционной гарантией.

        Использует двухфазный commit для атомарности:
        1. Подготовка изменений во временные файлы
        2. Атомарное переименование всех файлов
        3. Откат при любой ошибке

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

        user_dir = self.ensure_user_directory(user_id)

        # Пути к основным файлам
        conversation_file = user_dir / f"{conversation_id}.json"
        index_file = user_dir / "index.json"

        # Пути к временным файлам
        conv_temp = user_dir / f"{conversation_id}.json.tmp"
        index_temp = user_dir / "index.json.tmp"

        temp_files = [conv_temp, index_temp]

        try:
            # 2. Подготавливаем изменения в conversation
            conversation.messages.append(message)
            conversation.metadata.message_count = len(conversation.messages)
            conversation.metadata.total_tokens += message.tokens
            conversation.metadata.updated_at = datetime.now().isoformat()

            # 3. Подготавливаем изменения в index
            index_data = self.load_index(user_id)
            index_data["last_active_conversation_id"] = conversation_id

            # Обновляем metadata в списке чатов
            for i, conv_dict in enumerate(index_data["conversations"]):
                if conv_dict["conversation_id"] == conversation_id:
                    index_data["conversations"][i] = conversation.metadata.model_dump()
                    break

            # 4. Записываем ВСЕ изменения во временные файлы
            with open(conv_temp, 'w', encoding='utf-8') as f:
                json.dump({"schema_version": "1.0", "metadata": conversation.metadata.model_dump(), "messages": [msg.model_dump() for msg in conversation.messages]}, f, ensure_ascii=False, indent=2)

            with open(index_temp, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)

            # 5. АТОМАРНО переименовываем ВСЕ файлы
            conv_temp.replace(conversation_file)
            index_temp.replace(index_file)

            logger.info(f"Message added to conversation {conversation_id} (transactional)")
            return True

        except Exception as e:
            # 6. При любой ошибке - откатываем все временные файлы
            logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
            self._cleanup_temp_files(temp_files)
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

    # ========== Статистические функции ==========

    def get_user_stats(self, user_id: int, days_back: int = 30) -> dict:
        """
        Возвращает агрегированную статистику пользователя.

        Args:
            user_id: ID пользователя
            days_back: Количество дней для анализа (не используется, сохранен для совместимости)

        Returns:
            dict: Словарь со статистикой
        """
        stats = {
            "total_questions": 0,
            "total_answers": 0,
            "fast_searches": 0,
            "deep_searches": 0,
            "total_tokens": 0,
            "files_sent": 0,
            "conversations_count": 0,
            "total_messages": 0
        }

        # Получаем все чаты пользователя
        conversations = self.list_conversations(user_id)
        stats["conversations_count"] = len(conversations)

        if not conversations:
            return stats

        # Фильтруем по дате если нужно (опционально)
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()

        # Загружаем каждый чат и считаем статистику
        for conv_metadata in conversations:
            conversation = self.load_conversation(user_id, conv_metadata.conversation_id)
            if not conversation:
                continue

            for message in conversation.messages:
                # Проверяем дату сообщения (опционально)
                if message.timestamp < cutoff_date:
                    continue

                stats["total_messages"] += 1
                stats["total_tokens"] += message.tokens

                if message.type == "user_question":
                    stats["total_questions"] += 1
                elif message.type == "bot_answer":
                    stats["total_answers"] += 1

                    if message.sent_as == "file":
                        stats["files_sent"] += 1

                    if message.search_type == "fast":
                        stats["fast_searches"] += 1
                    elif message.search_type == "deep":
                        stats["deep_searches"] += 1

        return stats

    def format_user_stats_for_display(self, user_id: int) -> str:
        """
        Форматирует статистику пользователя для отображения.

        Args:
            user_id: ID пользователя

        Returns:
            str: Отформатированная строка со статистикой
        """
        stats = self.get_user_stats(user_id)

        result = "📈 **Ваша статистика (за 30 дней):**\n\n"
        result += f"💬 Всего чатов: {stats['conversations_count']}\n"
        result += f"📝 Всего сообщений: {stats['total_messages']:,}\n"
        result += f"🤔 Всего вопросов: {stats['total_questions']:,}\n"
        result += f"🤖 Всего ответов: {stats['total_answers']:,}\n"
        result += f"⚡ Быстрых поисков: {stats['fast_searches']:,}\n"
        result += f"🔍 Глубоких поисков: {stats['deep_searches']:,}\n"
        result += f"📝 Всего токенов: {stats['total_tokens']:,}\n"
        result += f"📎 Сохраненных файлов: {stats['files_sent']:,}\n\n"

        # Добавляем аналитику
        if stats['total_questions'] > 0:
            avg_tokens_per_question = stats['total_tokens'] / stats['total_questions']
            result += f"💡 Средняя длина вопроса: {avg_tokens_per_question:.1f} токенов\n"

        if stats['total_answers'] > 0:
            deep_search_ratio = (stats['deep_searches'] / stats['total_answers']) * 100
            result += f"🎯 Глубоких поисков: {deep_search_ratio:.1f}%\n"

        return result


# Singleton instance
conversation_manager = ConversationManager(CONVERSATIONS_DIR)
