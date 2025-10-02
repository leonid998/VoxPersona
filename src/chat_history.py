"""
Модуль для управления историей чатов пользователей.
Реализует сохранение, загрузку и анализ истории сообщений.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from .config import CHAT_HISTORY_DIR
from .constants import HISTORY_FILE_EXTENSION, INDEX_FILE_NAME
from .utils import count_tokens


@dataclass
class Message:
    """Модель сообщения в истории чата."""
    timestamp: str
    message_id: int
    type: str  # "user_question" | "bot_answer"
    text: str
    tokens: int
    sent_as: Optional[str] = None  # "message" | "file" (только для bot_answer)
    file_path: Optional[str] = None  # путь к файлу (если sent_as = "file")
    search_type: Optional[str] = None  # "fast" | "deep" (только для bot_answer)


@dataclass
class DayStats:
    """Статистика за день."""
    total_questions: int = 0
    total_answers: int = 0
    fast_searches: int = 0
    deep_searches: int = 0
    total_tokens: int = 0
    files_sent: int = 0


@dataclass
class DayHistory:
    """История за один день."""
    user_id: int
    username: str
    date: str
    messages: List[Message]
    stats: DayStats


class ChatHistoryManager:
    """Менеджер для работы с историей чатов."""

    def __init__(self):
        self.history_dir = Path(CHAT_HISTORY_DIR)
        self.ensure_history_directory()

    def ensure_history_directory(self) -> None:
        """Создает директорию истории если она не существует."""
        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            logging.debug(f"History directory ensured: {self.history_dir}")
        except Exception as e:
            logging.error(f"Failed to create history directory {self.history_dir}: {e}")
            raise

    def ensure_user_directory(self, user_id: int) -> Path:
        """Создает директорию пользователя если она не существует."""
        user_dir = self.history_dir / f"user_{user_id}"
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            return user_dir
        except Exception as e:
            logging.error(f"Failed to create user directory {user_dir}: {e}")
            raise

    def get_today_filename(self) -> str:
        """Возвращает имя файла для сегодняшней даты."""
        today = date.today().isoformat()
        return f"{today}{HISTORY_FILE_EXTENSION}"

    def get_date_filename(self, target_date: date) -> str:
        """Возвращает имя файла для указанной даты."""
        return f"{target_date.isoformat()}{HISTORY_FILE_EXTENSION}"

    def load_day_history(self, user_id: int, target_date: Optional[date] = None) -> Optional[DayHistory]:
        """Загружает историю за указанный день."""
        if target_date is None:
            target_date = date.today()
        
        user_dir = self.ensure_user_directory(user_id)
        filename = self.get_date_filename(target_date)
        file_path = user_dir / filename

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Конвертируем данные в объекты
            messages = [Message(**msg) for msg in data['messages']]
            stats = DayStats(**data['stats'])
            
            return DayHistory(
                user_id=data['user_id'],
                username=data['username'],
                date=data['date'],
                messages=messages,
                stats=stats
            )
        except Exception as e:
            logging.error(f"Failed to load day history for user {user_id}, date {target_date}: {e}")
            return None

    def save_day_history(self, day_history: DayHistory) -> bool:
        """Сохраняет историю за день."""
        user_dir = self.ensure_user_directory(day_history.user_id)
        filename = self.get_date_filename(date.fromisoformat(day_history.date))
        file_path = user_dir / filename

        try:
            # Конвертируем в dict для JSON сериализации
            data = asdict(day_history)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logging.debug(f"Saved day history for user {day_history.user_id}, date {day_history.date}")
            return True
        except Exception as e:
            logging.error(f"Failed to save day history: {e}")
            return False

    def save_message_to_history(
        self, 
        user_id: int, 
        username: str, 
        message_id: int,
        message_type: str, 
        text: str,
        sent_as: Optional[str] = None,
        file_path: Optional[str] = None,
        search_type: Optional[str] = None
    ) -> bool:
        """Сохраняет сообщение в историю."""
        try:
            # Загружаем или создаем историю за сегодня
            today = date.today()
            day_history = self.load_day_history(user_id, today)
            
            if day_history is None:
                day_history = DayHistory(
                    user_id=user_id,
                    username=username,
                    date=today.isoformat(),
                    messages=[],
                    stats=DayStats()
                )

            # Создаем новое сообщение
            message = Message(
                timestamp=datetime.now().isoformat(),
                message_id=message_id,
                type=message_type,
                text=text,
                tokens=count_tokens(text),
                sent_as=sent_as,
                file_path=file_path,
                search_type=search_type
            )

            # Добавляем сообщение
            day_history.messages.append(message)

            # Обновляем статистику
            self._update_stats(day_history.stats, message)

            # Сохраняем
            return self.save_day_history(day_history)

        except Exception as e:
            logging.error(f"Failed to save message to history: {e}")
            return False

    def _update_stats(self, stats: DayStats, message: Message) -> None:
        """Обновляет статистику дня."""
        stats.total_tokens += message.tokens

        if message.type == "user_question":
            stats.total_questions += 1
        elif message.type == "bot_answer":
            stats.total_answers += 1
            
            if message.sent_as == "file":
                stats.files_sent += 1
            
            if message.search_type == "fast":
                stats.fast_searches += 1
            elif message.search_type == "deep":
                stats.deep_searches += 1

    def get_user_stats(self, user_id: int, days_back: int = 30) -> Dict[str, Any]:
        """Возвращает статистику пользователя за указанное количество дней."""
        stats = {
            "total_questions": 0,
            "total_answers": 0,
            "fast_searches": 0,
            "deep_searches": 0,
            "total_tokens": 0,
            "files_sent": 0,
            "days_active": 0
        }

        user_dir = self.ensure_user_directory(user_id)
        if not user_dir.exists():
            return stats

        current_date = date.today()
        for i in range(days_back):
            check_date = date.fromordinal(current_date.toordinal() - i)
            day_history = self.load_day_history(user_id, check_date)
            
            if day_history and day_history.messages:
                stats["days_active"] += 1
                stats["total_questions"] += day_history.stats.total_questions
                stats["total_answers"] += day_history.stats.total_answers
                stats["fast_searches"] += day_history.stats.fast_searches
                stats["deep_searches"] += day_history.stats.deep_searches
                stats["total_tokens"] += day_history.stats.total_tokens
                stats["files_sent"] += day_history.stats.files_sent

        return stats

    def format_day_history_for_display(self, user_id: int, target_date: Optional[date] = None) -> str:
        """Форматирует историю дня для отображения пользователю."""
        if target_date is None:
            target_date = date.today()

        day_history = self.load_day_history(user_id, target_date)
        
        if not day_history or not day_history.messages:
            return f"📊 История за {target_date.strftime('%d.%m.%Y')}\n\nНет сообщений за этот день."

        # Заголовок
        result = f"📊 История за {target_date.strftime('%d.%m.%Y')}\n\n"
        
        # Статистика
        stats = day_history.stats
        result += f"🤔 Вопросы: {stats.total_questions}\n"
        result += f"🤖 Ответы: {stats.total_answers}\n"
        result += f"⚡ Быстрых поисков: {stats.fast_searches}\n"
        result += f"🔍 Глубоких поисков: {stats.deep_searches}\n"
        result += f"📝 Токенов использовано: {stats.total_tokens:,}\n"
        result += f"📎 Файлов отправлено: {stats.files_sent}\n\n"

        # Последние 5 сообщений
        result += "**Последние сообщения:**\n\n"
        recent_messages = day_history.messages[-5:] if len(day_history.messages) > 5 else day_history.messages
        
        for msg in recent_messages:
            timestamp = datetime.fromisoformat(msg.timestamp).strftime('%H:%M')
            
            if msg.type == "user_question":
                preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
                result += f"👤 {timestamp}: {preview}\n"
            else:
                preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
                search_icon = "⚡" if msg.search_type == "fast" else "🔍" if msg.search_type == "deep" else "🤖"
                file_icon = "📎" if msg.sent_as == "file" else ""
                result += f"{search_icon} {timestamp}: {preview} {file_icon}\n"
            
            result += "\n"

        return result

    def format_user_stats_for_display(self, user_id: int) -> str:
        """Форматирует статистику пользователя для отображения."""
        stats = self.get_user_stats(user_id)
        
        result = "📈 **Ваша статистика (за 30 дней):**\n\n"
        result += f"📅 Активных дней: {stats['days_active']}\n"
        result += f"🤔 Всего вопросов: {stats['total_questions']:,}\n"
        result += f"🤖 Всего ответов: {stats['total_answers']:,}\n"
        result += f"⚡ Быстрых поисков: {stats['fast_searches']:,}\n"
        result += f"🔍 Глубоких поисков: {stats['deep_searches']:,}\n"
        result += f"📝 Всего токенов: {stats['total_tokens']:,}\n"
        result += f"📎 Сохраненных файлов: {stats['files_sent']:,}\n\n"
        
        # Добавляем некоторую аналитику
        if stats['total_questions'] > 0:
            avg_tokens_per_question = stats['total_tokens'] / stats['total_questions']
            result += f"💡 Средняя длина вопроса: {avg_tokens_per_question:.1f} токенов\n"
        
        if stats['total_answers'] > 0:
            deep_search_ratio = (stats['deep_searches'] / stats['total_answers']) * 100
            result += f"🎯 Глубоких поисков: {deep_search_ratio:.1f}%\n"

        return result


# Создаем глобальный экземпляр менеджера
chat_history_manager = ChatHistoryManager()