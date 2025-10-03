"""
Менеджер меню для Telegram бота VoxPersona.
Решает проблему дублирования меню через правильное управление жизненным циклом.

КЛЮЧЕВОЙ ПРИНЦИП:
- Старое меню удаляется (кнопки убираются)
- Новое меню ВСЕГДА появляется внизу чата
- Пользователь НИКОГДА не остается без активного меню
"""

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.errors import MessageNotModified, MessageIdInvalid
import logging

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
        reply_markup: InlineKeyboardMarkup
    ) -> Message:
        """
        Основной метод для отправки меню.

        Алгоритм:
        1. Удаляет кнопки у предыдущего меню (если есть)
        2. Отправляет новое меню внизу чата
        3. Запоминает ID нового меню

        Args:
            chat_id: ID чата
            app: Pyrogram Client
            text: Текст сообщения
            reply_markup: Клавиатура меню

        Returns:
            Message: Отправленное сообщение с меню
        """
        # 1. Удаляем кнопки у старого меню
        await cls._remove_old_menu_buttons(chat_id, app)

        # 2. Отправляем новое меню ВНИЗУ чата
        new_message = app.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup
        )

        # 3. Запоминаем ID нового меню
        cls._last_menu_ids[chat_id] = new_message.id

        logger.info(
            f"Меню отправлено для chat_id={chat_id}, "
            f"message_id={new_message.id}"
        )

        return new_message

    @classmethod
    async def _remove_old_menu_buttons(cls, chat_id: int, app: Client) -> None:
        """
        Удаляет кнопки у предыдущего меню.

        Args:
            chat_id: ID чата
            app: Pyrogram Client
        """
        last_menu_id = cls._last_menu_ids.get(chat_id)

        if not last_menu_id:
            logger.debug(f"Нет старого меню для chat_id={chat_id}")
            return

        try:
            # Удаляем кнопки, оставляя текст сообщения
            app.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=last_menu_id,
                reply_markup=None
            )

            logger.debug(
                f"Удалены кнопки у сообщения {last_menu_id} "
                f"в чате {chat_id}"
            )

        except MessageNotModified:
            # Кнопки уже удалены - это нормально
            logger.debug(f"Кнопки уже удалены у сообщения {last_menu_id}")

        except MessageIdInvalid:
            # Сообщение не найдено - возможно удалено
            logger.warning(
                f"Сообщение {last_menu_id} не найдено в чате {chat_id}"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при удалении кнопок у сообщения {last_menu_id}: {e}"
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
    reply_markup: InlineKeyboardMarkup
) -> Message:
    """
    Shortcut для MenuManager.send_menu_with_cleanup().

    Использование:
    ```python
    await send_menu_and_remove_old(
        chat_id=message.chat.id,
        app=app,
        text="Выберите действие:",
        reply_markup=get_main_menu()
    )
    ```
    """
    return await MenuManager.send_menu_with_cleanup(
        chat_id=chat_id,
        app=app,
        text=text,
        reply_markup=reply_markup
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
