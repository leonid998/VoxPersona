"""
Менеджер меню для Telegram бота VoxPersona.
Решает проблему дублирования меню через правильное управление жизненным циклом.

КЛЮЧЕВОЙ ПРИНЦИП:
- Старое меню ПОЛНОСТЬЮ удаляется (текст + кнопки)
- Новое меню ВСЕГДА появляется внизу чата
- Пользователь НИКОГДА не остается без активного меню
- Чат НЕ захламляется текстовыми артефактами меню
"""

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message
from pyrogram.errors import MessageIdInvalid
import logging
from typing import Optional
from visual_context_manager import VisualContextManager

logger = logging.getLogger(__name__)


class MenuManager:
    """
    Менеджер для правильного управления меню в Telegram боте.

    Основная задача: гарантировать что пользователь всегда видит
    только ОДНО активное меню, и оно всегда находится внизу чата.
    """

    # Словарь для хранения ID последнего меню каждого пользователя
    # Формат: {chat_id: message_id}
    _last_menu_ids = {}

    @classmethod
    async def send_menu_with_cleanup(
        cls,
        chat_id: int,
        app: Client,
        text: str,
        reply_markup: InlineKeyboardMarkup,
        context: Optional[str] = None
    ) -> Message:
        """
        Основной метод для отправки меню.

        Алгоритм:
        1. ПОЛНОСТЬЮ удаляет предыдущее меню (текст + кнопки)
        2. Отправляет новое меню внизу чата
        3. Запоминает ID нового меню
        4. Трекает сообщение для визуальной минимизации (если передан context)

        Это предотвращает захламление чата текстовыми артефактами.

        Args:
            chat_id: ID чата
            app: Pyrogram Client
            text: Текст сообщения
            reply_markup: Клавиатура меню
            context: Контекст для трекинга (conversation_id или "system")

        Returns:
            Message: Отправленное сообщение с меню
        """
        # 1. Полностью удаляем старое меню (текст + кнопки)
        await cls._remove_old_menu_buttons(chat_id, app)

        # 2. Отправляем новое меню ВНИЗУ чата
        new_message = await app.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup
        )

        # 3. Запоминаем ID нового меню
        cls._last_menu_ids[chat_id] = new_message.id

        # 4. Трекаем для визуальной минимизации (если передан context)
        if context:
            VisualContextManager.track_message(chat_id, context, new_message.id)

        logger.info(
            f"Меню отправлено для chat_id={chat_id}, "
            f"message_id={new_message.id}"
        )

        return new_message

    @classmethod
    async def _remove_old_menu_buttons(cls, chat_id: int, app: Client) -> None:
        """
        Полностью удаляет предыдущее меню (сообщение + кнопки).

        Это предотвращает захламление чата текстовыми артефактами меню.

        Args:
            chat_id: ID чата
            app: Pyrogram Client
        """
        last_menu_id = cls._last_menu_ids.get(chat_id)

        if not last_menu_id:
            logger.debug(f"Нет старого меню для chat_id={chat_id}")
            return

        try:
            # Полностью удаляем старое сообщение (текст + кнопки)
            await app.delete_messages(
                chat_id=chat_id,
                message_ids=last_menu_id
            )

            logger.debug(
                f"Удалено меню (message_id={last_menu_id}) "
                f"из чата {chat_id}"
            )

        except MessageIdInvalid:
            # Сообщение не найдено - возможно уже удалено
            logger.debug(
                f"Сообщение {last_menu_id} не найдено в чате {chat_id} "
                f"(возможно уже удалено)"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при удалении меню {last_menu_id} из чата {chat_id}: {e}"
            )

    @classmethod
    def clear_menu_history(cls, chat_id: int) -> None:
        """
        Очищает историю меню для пользователя.

        Используется при:
        - Создании нового чата
        - Завершении ConversationHandler
        - Сбросе состояния пользователя

        Args:
            chat_id: ID чата
        """
        cls._last_menu_ids.pop(chat_id, None)
        logger.info(f"История меню очищена для chat_id={chat_id}")


# ========================================
# Вспомогательные функции
# ========================================

async def send_menu_and_remove_old(
    chat_id: int,
    app: Client,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    context: Optional[str] = None
) -> Message:
    """
    Shortcut для MenuManager.send_menu_with_cleanup().

    Использование:
    ```python
    await send_menu_and_remove_old(
        chat_id=message.chat.id,
        app=app,
        text="Выберите действие:",
        reply_markup=get_main_menu(),
        context=conversation_id  # Опционально для трекинга
    )
    ```
    """
    return await MenuManager.send_menu_with_cleanup(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=reply_markup,
        context=context
    )


def clear_menus(chat_id: int) -> None:
    """
    Shortcut для MenuManager.clear_menu_history().

    Использование:
    ```python
    # При создании нового чата
    clear_menus(chat_id)
    ```
    """
    MenuManager.clear_menu_history(chat_id)
