"""
MessageTracker - Единая интеллектуальная система отслеживания и очистки интерактивных элементов.

ПРОБЛЕМА:
- Старые меню остаются висеть в чате когда диалог ушел дальше
- app.send_message() создает артефакты текста + кнопки
- Ручное управление очисткой требует изменений в каждом обработчике

РЕШЕНИЕ:
MessageTracker автоматически:
1. Отслеживает ВСЕ интерактивные элементы (меню, запросы ввода, подтверждения)
2. Определяет тип элемента (меню, input_request, confirmation)
3. Очищает устаревшие элементы когда контекст меняется
4. Гарантирует что в чате висит только актуальное меню/запрос

ТИПЫ ОТСЛЕЖИВАЕМЫХ ЭЛЕМЕНТОВ:
- menu: Обычное меню с кнопками
- input_request: Запрос ввода текста от пользователя (например, "Введите название чата")
- confirmation: Подтверждающий диалог (например, "Удалить чат?")
- info_message: Информационное сообщение без кнопок (автоматически НЕ очищается)

АВТОМАТИЧЕСКАЯ ОЧИСТКА:
- Новое меню → очищает все предыдущие меню + input_request + confirmation
- Новый input_request → очищает предыдущие input_request
- Новый confirmation → очищает предыдущие confirmation
- Смена контекста (новый чат) → очищает ВСЁ

ИСПОЛЬЗОВАНИЕ:
```python
# Вместо send_menu:
await track_and_send(
    chat_id=chat_id,
    app=app,
    text="Выберите действие:",
    reply_markup=main_menu_markup(),
    message_type="menu"
)

# Вместо app.send_message для запроса ввода:
await track_and_send(
    chat_id=chat_id,
    app=app,
    text="Введите новое название чата:",
    reply_markup=cancel_button_markup(),
    message_type="input_request"
)

# Очистка при смене контекста:
clear_tracked_messages(chat_id)
```
"""

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message
from pyrogram.errors import MessageIdInvalid
import logging
from typing import Optional, List, Literal
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Типы отслеживаемых сообщений
MessageType = Literal["menu", "input_request", "confirmation", "info_message"]


@dataclass
class TrackedMessage:
    """
    Отслеживаемое сообщение с метаданными.

    Attributes:
        message_id: ID сообщения в Telegram
        message_type: Тип сообщения (menu/input_request/confirmation/info)
        timestamp: Время создания
        has_buttons: Есть ли кнопки
    """
    message_id: int
    message_type: MessageType
    timestamp: datetime
    has_buttons: bool


class MessageTracker:
    """
    Единый интеллектуальный трекер всех интерактивных элементов в чате.

    Отслеживает:
    - Меню (menu)
    - Запросы ввода (input_request)
    - Подтверждения (confirmation)
    - Информационные сообщения (info_message)

    Автоматически очищает устаревшие элементы при появлении новых.
    """

    # Структура: {chat_id: [TrackedMessage, ...]}
    _tracked_messages: dict[int, List[TrackedMessage]] = {}

    @classmethod
    async def track_and_send(
        cls,
        chat_id: int,
        app: Client,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        message_type: MessageType = "menu"
    ) -> Message:
        """
        Основной метод: отправляет сообщение и отслеживает его.

        Алгоритм:
        1. Определяет что нужно очистить (по типу нового сообщения)
        2. Очищает устаревшие элементы
        3. Отправляет новое сообщение
        4. Добавляет в трекинг

        Args:
            chat_id: ID чата
            app: Pyrogram Client
            text: Текст сообщения
            reply_markup: Клавиатура (опционально)
            message_type: Тип сообщения (menu/input_request/confirmation/info_message)

        Returns:
            Message: Отправленное сообщение
        """
        # ШАГ 1: Очищаем устаревшие элементы
        await cls._cleanup_by_type(chat_id, app, message_type)

        # ШАГ 2: Отправляем новое сообщение
        new_message = await app.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup
        )

        # ШАГ 3: Добавляем в трекинг
        tracked = TrackedMessage(
            message_id=new_message.id,
            message_type=message_type,
            timestamp=datetime.now(),
            has_buttons=reply_markup is not None
        )

        if chat_id not in cls._tracked_messages:
            cls._tracked_messages[chat_id] = []

        cls._tracked_messages[chat_id].append(tracked)

        logger.info(
            f"[MessageTracker] Отправлено {message_type} для chat_id={chat_id}, "
            f"message_id={new_message.id}, tracked_count={len(cls._tracked_messages[chat_id])}"
        )

        return new_message

    @classmethod
    async def _cleanup_by_type(
        cls,
        chat_id: int,
        app: Client,
        new_message_type: MessageType
    ) -> None:
        """
        Очищает устаревшие элементы в зависимости от типа нового сообщения.

        Правила очистки:
        - menu → очистить ВСЁ (menu + input_request + confirmation)
        - input_request → очистить предыдущие input_request + confirmation
        - confirmation → очистить предыдущие confirmation
        - info_message → НЕ очищать ничего (информационное сообщение)

        Args:
            chat_id: ID чата
            app: Pyrogram Client
            new_message_type: Тип нового сообщения
        """
        if chat_id not in cls._tracked_messages:
            return

        messages = cls._tracked_messages[chat_id]

        # Определяем какие типы нужно удалить
        types_to_delete = []

        if new_message_type == "menu":
            # Новое меню → удалить ВСЁ кроме info_message
            types_to_delete = ["menu", "input_request", "confirmation"]

        elif new_message_type == "input_request":
            # Новый запрос ввода → удалить старые запросы и подтверждения
            types_to_delete = ["input_request", "confirmation"]

        elif new_message_type == "confirmation":
            # Новое подтверждение → удалить старые подтверждения
            types_to_delete = ["confirmation"]

        elif new_message_type == "info_message":
            # Информационное сообщение → НЕ удалять ничего
            return

        # Удаляем сообщения указанных типов
        messages_to_delete = [
            msg for msg in messages
            if msg.message_type in types_to_delete
        ]

        for msg in messages_to_delete:
            await cls._delete_single_message(chat_id, app, msg.message_id)

        # Удаляем из трекинга
        cls._tracked_messages[chat_id] = [
            msg for msg in messages
            if msg.message_type not in types_to_delete
        ]

        if messages_to_delete:
            logger.info(
                f"[MessageTracker] Очищено {len(messages_to_delete)} сообщений "
                f"типов {types_to_delete} для chat_id={chat_id}"
            )

    @classmethod
    async def _delete_single_message(
        cls,
        chat_id: int,
        app: Client,
        message_id: int
    ) -> None:
        """
        Удаляет одно сообщение с обработкой ошибок.

        Args:
            chat_id: ID чата
            app: Pyrogram Client
            message_id: ID сообщения для удаления
        """
        try:
            await app.delete_messages(
                chat_id=chat_id,
                message_ids=message_id
            )
            logger.debug(
                f"[MessageTracker] Удалено сообщение message_id={message_id} "
                f"из chat_id={chat_id}"
            )

        except MessageIdInvalid:
            logger.debug(
                f"[MessageTracker] Сообщение {message_id} не найдено "
                f"в chat_id={chat_id} (уже удалено)"
            )

        except Exception as e:
            logger.error(
                f"[MessageTracker] Ошибка при удалении message_id={message_id} "
                f"из chat_id={chat_id}: {e}"
            )

    @classmethod
    def clear_all_tracked(cls, chat_id: int) -> None:
        """
        Очищает ВСЮ историю отслеживаемых сообщений для пользователя.

        Используется при:
        - Создании нового чата (смена контекста)
        - Удалении последнего чата (смена контекста)
        - Выходе из режима диалога

        Args:
            chat_id: ID чата
        """
        if chat_id in cls._tracked_messages:
            count = len(cls._tracked_messages[chat_id])
            cls._tracked_messages.pop(chat_id, None)
            logger.info(
                f"[MessageTracker] Очищена ВСЯ история ({count} сообщений) "
                f"для chat_id={chat_id}"
            )

    @classmethod
    async def cleanup_all_messages(cls, chat_id: int, app: Client) -> None:
        """
        Физически удаляет ВСЕ отслеживаемые сообщения из чата.

        Используется при:
        - Критическом сбросе состояния
        - Очистке чата по запросу пользователя

        Args:
            chat_id: ID чата
            app: Pyrogram Client
        """
        if chat_id not in cls._tracked_messages:
            return

        messages = cls._tracked_messages[chat_id]

        for msg in messages:
            await cls._delete_single_message(chat_id, app, msg.message_id)

        cls._tracked_messages.pop(chat_id, None)

        logger.info(
            f"[MessageTracker] Физически удалены ВСЕ сообщения ({len(messages)}) "
            f"для chat_id={chat_id}"
        )

    @classmethod
    def get_tracked_count(cls, chat_id: int) -> int:
        """
        Возвращает количество отслеживаемых сообщений для чата.

        Args:
            chat_id: ID чата

        Returns:
            int: Количество отслеживаемых сообщений
        """
        return len(cls._tracked_messages.get(chat_id, []))

    @classmethod
    def get_tracked_messages(cls, chat_id: int) -> List[TrackedMessage]:
        """
        Возвращает список всех отслеживаемых сообщений для чата.

        Args:
            chat_id: ID чата

        Returns:
            List[TrackedMessage]: Список отслеживаемых сообщений
        """
        return cls._tracked_messages.get(chat_id, []).copy()


# ========================================
# Вспомогательные функции (shortcuts)
# ========================================

async def track_and_send(
    chat_id: int,
    app: Client,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    message_type: MessageType = "menu"
) -> Message:
    """
    Shortcut для MessageTracker.track_and_send().

    Использование:
    ```python
    # Меню
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text="Выберите действие:",
        reply_markup=main_menu_markup(),
        message_type="menu"
    )

    # Запрос ввода
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text="Введите новое название:",
        reply_markup=cancel_markup(),
        message_type="input_request"
    )

    # Подтверждение
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text="Удалить чат?",
        reply_markup=yes_no_markup(),
        message_type="confirmation"
    )
    ```
    """
    return await MessageTracker.track_and_send(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=reply_markup,
        message_type=message_type
    )


def clear_tracked_messages(chat_id: int) -> None:
    """
    Shortcut для MessageTracker.clear_all_tracked().

    Использование:
    ```python
    # При создании нового чата
    clear_tracked_messages(chat_id)

    # При удалении последнего чата
    clear_tracked_messages(chat_id)
    ```
    """
    MessageTracker.clear_all_tracked(chat_id)


async def cleanup_all_tracked(chat_id: int, app: Client) -> None:
    """
    Shortcut для MessageTracker.cleanup_all_messages().

    Физически удаляет ВСЕ отслеживаемые сообщения из чата.

    Использование:
    ```python
    # Критический сброс
    await cleanup_all_tracked(chat_id, app)
    ```
    """
    await MessageTracker.cleanup_all_messages(chat_id, app)
