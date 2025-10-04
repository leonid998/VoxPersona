"""
Менеджер меню для Telegram бота VoxPersona.

⚠️ УСТАРЕЛ: Теперь используется message_tracker.py с интеллектуальной системой очистки.

НОВАЯ СИСТЕМА (message_tracker.py):
- Автоматически отслеживает ВСЕ интерактивные элементы
- Умная очистка по типу элемента (menu/input_request/confirmation)
- Не нужно ручное управление в каждом обработчике
- Гарантирует чистоту чата

ОБРАТНАЯ СОВМЕСТИМОСТЬ:
Этот модуль оставлен для обратной совместимости.
Все функции теперь используют MessageTracker под капотом.

Используйте напрямую:
```python
from message_tracker import track_and_send, clear_tracked_messages

# Вместо send_menu:
await track_and_send(chat_id, app, text, markup, message_type="menu")

# Вместо clear_menus:
clear_tracked_messages(chat_id)
```
"""

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message
import logging
from typing import Optional

# Импортируем новую систему
from message_tracker import track_and_send as _track_and_send, clear_tracked_messages as _clear_tracked

logger = logging.getLogger(__name__)


class MenuManager:
    """
    ⚠️ УСТАРЕВШИЙ КЛАСС - сохранен для обратной совместимости.

    Теперь используется MessageTracker из message_tracker.py.

    Все методы этого класса теперь используют MessageTracker под капотом.
    """

    @classmethod
    async def send_menu_with_cleanup(
        cls,
        chat_id: int,
        app: Client,
        text: str,
        reply_markup: InlineKeyboardMarkup
    ) -> Message:
        """
        ⚠️ УСТАРЕЛ: Используйте track_and_send() из message_tracker.py

        Этот метод оставлен для обратной совместимости.
        Теперь использует MessageTracker под капотом.
        """
        return await _track_and_send(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=reply_markup,
            message_type="menu"
        )

    @classmethod
    def clear_menu_history(cls, chat_id: int) -> None:
        """
        ⚠️ УСТАРЕЛ: Используйте clear_tracked_messages() из message_tracker.py

        Этот метод оставлен для обратной совместимости.
        Теперь использует MessageTracker под капотом.
        """
        _clear_tracked(chat_id)


# ========================================
# Вспомогательные функции (обратная совместимость)
# ========================================

async def send_menu(
    chat_id: int,
    app: Client,
    text: str,
    reply_markup: InlineKeyboardMarkup
) -> Message:
    """
    ⚠️ УСТАРЕЛ: Используйте track_and_send() из message_tracker.py

    Этот метод оставлен для обратной совместимости.
    Теперь использует MessageTracker под капотом.

    Использование:
    ```python
    # Старый способ (работает):
    await send_menu(chat_id, app, text, markup)

    # Новый способ (рекомендуется):
    from message_tracker import track_and_send
    await track_and_send(chat_id, app, text, markup, message_type="menu")
    ```
    """
    return await _track_and_send(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=reply_markup,
        message_type="menu"
    )


def clear_menus(chat_id: int) -> None:
    """
    ⚠️ УСТАРЕЛ: Используйте clear_tracked_messages() из message_tracker.py

    Этот метод оставлен для обратной совместимости.
    Теперь использует MessageTracker под капотом.

    Использование:
    ```python
    # Старый способ (работает):
    clear_menus(chat_id)

    # Новый способ (рекомендуется):
    from message_tracker import clear_tracked_messages
    clear_tracked_messages(chat_id)
    ```
    """
    _clear_tracked(chat_id)
