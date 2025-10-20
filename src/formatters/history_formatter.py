"""
Форматтер для истории чатов VoxPersona
"""
from typing import List, Dict, Any
from formatters.base_formatter import BaseFormatter


class HistoryFormatter(BaseFormatter):
    """Форматирование истории чатов в Markdown для .txt файлов"""

    def format(self, messages: List[Dict[str, Any]], conversation: Any) -> str:
        """
        Генерация Markdown файла с полной историей чата.

        Args:
            messages: Список сообщений из БД
            conversation: Объект Conversation с метаданными

        Returns:
            Markdown-форматированная строка для сохранения в .txt
        """
        # Заголовок
        title = conversation.metadata.title if hasattr(conversation, 'metadata') else "Без названия"
        md = f"# 📜 История чата: {self.escape_markdown(title)}\n\n"

        # Метаданные
        if hasattr(conversation, 'metadata'):
            created_at = self.format_timestamp(conversation.metadata.created_at)
            md += f"**Создан:** {created_at}\n"
            md += f"**Сообщений:** {conversation.metadata.message_count}\n"

            if hasattr(conversation.metadata, 'total_tokens'):
                md += f"**Токенов:** {conversation.metadata.total_tokens:,}\n"

        md += f"\n{self.heavy_separator}\n\n"

        # Сообщения
        for idx, msg in enumerate(messages, 1):
            timestamp = self.format_timestamp(msg.timestamp) if hasattr(msg, 'timestamp') else "Нет данных"

            # Определяем роль
            if hasattr(msg, 'type'):
                role = "👤 Пользователь" if msg.type == "user_question" else "🤖 Ассистент"
            else:
                role = "👤 Отправитель"

            # Текст сообщения
            text = msg.text if hasattr(msg, 'text') else ""

            md += f"## {idx}. {role}\n\n"
            md += f"**Время:** {timestamp}\n\n"
            md += f"{text}\n\n"
            md += f"{self.line_separator}\n\n"

        return md

    def format_inline_preview(self, messages: List[Dict[str, Any]], conversation: Any,
                             preview_count: int = 5) -> str:
        """
        Краткое превью для отправки в Telegram перед файлом.

        Args:
            messages: Список сообщений
            conversation: Объект Conversation
            preview_count: Количество сообщений для превью (default: 5)

        Returns:
            Markdown-форматированное превью
        """
        title = conversation.metadata.title if hasattr(conversation, 'metadata') else "Без названия"
        preview = f"**📜 История чата:** {self.escape_markdown(title)}\n\n"

        # Показываем первые N сообщений
        for msg in messages[:preview_count]:
            timestamp = self.format_timestamp(msg.timestamp, "short") if hasattr(msg, 'timestamp') else ""

            if hasattr(msg, 'type'):
                role = "👤 Вы" if msg.type == "user_question" else "🤖 Бот"
            else:
                role = "👤"

            text = msg.text if hasattr(msg, 'text') else ""
            text_preview = self.truncate_text(text, 80)

            preview += f"**{role}** • {timestamp}\n{text_preview}\n\n"

        # Если есть еще сообщения
        if len(messages) > preview_count:
            remaining = len(messages) - preview_count
            preview += f"_... и еще {remaining} сообщений_\n\n"

        preview += "💾 **Полная история отправлена файлом**"
        return preview
