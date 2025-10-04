"""
Обработчики для работы с мультичатами в Telegram боте.

Этот модуль содержит функции для:
- Управления активными чатами
- Создания, переключения, переименования и удаления чатов
- Обработки пользовательского ввода для операций с чатами

Принцип: KISS - простые и понятные решения без излишней сложности.
"""

import logging
from datetime import datetime
from typing import Optional

from pyrogram import Client
from pyrogram.types import CallbackQuery

from conversation_manager import conversation_manager
from conversations import ConversationMessage
from config import user_states
from utils import get_username_from_chat
from markups import (
    make_dialog_markup,
    switch_chat_confirmation_markup,
    delete_chat_confirmation_markup,
    chats_menu_markup_dynamic,
    chat_actions_menu_markup
)
from menu_manager import send_menu, clear_menus

logger = logging.getLogger(__name__)


def ensure_active_conversation(user_id: int, username: str, first_message: str = "") -> str:
    """
    Проверяет наличие активного чата, создает если нужно.
    Вызывается при каждом сообщении пользователя.

    Args:
        user_id: ID пользователя Telegram
        username: Username пользователя
        first_message: Первое сообщение для генерации названия чата

    Returns:
        conversation_id активного чата
    """
    try:
        # Получаем ID активного чата
        active_id = conversation_manager.get_active_conversation_id(user_id)

        # Проверяем существование и валидность активного чата
        if active_id:
            conversation = conversation_manager.load_conversation(user_id, active_id)
            if conversation:
                logger.info(f"Используется активный чат {active_id} для пользователя {user_id}")
                return active_id

        # Активного чата нет - создаем новый
        chat_name = first_message[:50] if first_message else "Новый чат"
        if len(first_message) > 50:
            chat_name += "..."

        new_conversation_id = conversation_manager.create_conversation(
            user_id=user_id,
            username=username,
            first_question=chat_name
        )

        logger.info(f"Создан новый активный чат {new_conversation_id} для пользователя {user_id}")
        return new_conversation_id

    except Exception as e:
        logger.error(f"Ошибка в ensure_active_conversation для пользователя {user_id}: {e}")
        # В случае ошибки создаем новый чат
        return conversation_manager.create_conversation(
            user_id=user_id,
            username=username,
            first_question="Новый чат"
        )


async def handle_new_chat(chat_id: int, app: Client):
    """
    Обработчик создания нового чата.
    Callback: "new_chat"

    Args:
        chat_id: ID чата Telegram
        app: Pyrogram Client
    """
    try:
        # Получаем username пользователя
        username = await get_username_from_chat(chat_id, app)

        # Получаем старый conversation_id ДО создания нового
        old_conversation_id = conversation_manager.get_active_conversation_id(chat_id)

        # Создаем новый чат
        new_conversation_id = conversation_manager.create_conversation(
            user_id=chat_id,
            username=username,
            first_question="Новый чат"
        )

        # Устанавливаем состояние для нового чата
        user_states[chat_id] = {
            "conversation_id": new_conversation_id,
            "step": "dialog_mode",
            "deep_search": False
        }

        # Очищаем историю меню (новый контекст)
        clear_menus(chat_id)

        # Объединяем текст и отправляем меню внизу
        text = (
            "✨ Новый чат создан!\n\n"
            "Какую информацию вы хотели бы получить?\n\n"
            "Выберите действие:"
        )

        await send_menu(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=make_dialog_markup()
        )

        logger.info(f"Создан новый чат {new_conversation_id} для пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при создании нового чата для пользователя {chat_id}: {e}")
        app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при создании нового чата. Попробуйте еще раз."
        )


async def handle_chat_actions(chat_id: int, conversation_id: str, app: Client):
    """
    Показывает меню действий с чатом.
    Callback: "chat_actions||{conversation_id}"

    Отображает:
    - Название чата
    - Кнопки: [Да, перейти] [Нет]
    - Кнопки: [Изменить] [Удалить]

    Args:
        chat_id: ID чата Telegram
        conversation_id: ID чата для действий
        app: Pyrogram Client
    """
    try:
        # Загружаем метаданные чата
        conversation = conversation_manager.load_conversation(chat_id, conversation_id)

        if not conversation:
            await app.send_message(
                chat_id=chat_id,
                text="❌ Чат не найден"
            )
            return

        chat_name = conversation.metadata.title

        # Отправляем меню действий
        await send_menu(
            chat_id=chat_id,
            app=app,
            text=f"🔄 Чат: *{chat_name}*\n\nВыберите действие:",
            reply_markup=chat_actions_menu_markup(conversation_id, chat_name)
        )

        logger.info(f"Показано меню действий для чата {conversation_id} пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при показе меню действий чата {conversation_id} для пользователя {chat_id}: {e}")
        await app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка. Попробуйте еще раз."
        )


async def handle_switch_chat_request(
    chat_id: int,
    conversation_id: str,
    app: Client,
    callback_query: CallbackQuery
):
    """
    Запрашивает подтверждение переключения чата.
    Callback: "switch_chat||{conversation_id}"

    УСТАРЕЛ: Теперь используется chat_actions||
    Оставлен для обратной совместимости.

    Args:
        chat_id: ID чата Telegram
        conversation_id: ID чата для переключения
        app: Pyrogram Client
        callback_query: Callback query объект
    """
    try:
        # Загружаем метаданные чата
        conversation = conversation_manager.load_conversation(chat_id, conversation_id)

        if not conversation:
            await callback_query.answer("❌ Чат не найден", show_alert=True)
            return

        chat_name = conversation.metadata.title

        # Отправляем запрос на подтверждение
        await callback_query.edit_message_text(
            text=f"🔄 Перейти в чат '{chat_name}'?",
            reply_markup=switch_chat_confirmation_markup(conversation_id, chat_name)
        )

        logger.info(f"Запрошено подтверждение переключения на чат {conversation_id} для пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при запросе переключения чата {conversation_id} для пользователя {chat_id}: {e}")
        await callback_query.answer("❌ Ошибка при переключении чата", show_alert=True)


async def handle_switch_chat_confirm(
    chat_id: int,
    conversation_id: str,
    app: Client
):
    """
    Переключает на выбранный чат.
    Callback: "confirm_switch||{conversation_id}"

    Args:
        chat_id: ID чата Telegram
        conversation_id: ID чата для переключения
        app: Pyrogram Client
    """
    try:
        # Получаем старый conversation_id ДО переключения для минимизации его сообщений
        old_conversation_id = conversation_manager.get_active_conversation_id(chat_id)

        # Устанавливаем чат как активный
        conversation_manager.set_active_conversation(chat_id, conversation_id)

        # Устанавливаем состояние для переключенного чата
        user_states[chat_id] = {
            "conversation_id": conversation_id,
            "step": "dialog_mode",
            "deep_search": False
        }

        # Загружаем чат и последние 5 сообщений
        conversation = conversation_manager.load_conversation(chat_id, conversation_id)

        if not conversation:
            app.send_message(
                chat_id=chat_id,
                text="❌ Не удалось загрузить чат"
            )
            return

        messages = conversation_manager.get_messages(chat_id, conversation_id, limit=5)

        # Формируем единое сообщение
        text = f"✅ Переключено на чат: {conversation.metadata.title}\n\n"

        if messages:
            text += "📜 Последние 5 сообщений:\n\n"
            for msg in messages:
                role_emoji = "👤" if msg.type == "user_question" else "🤖"
                # Обрезаем длинные сообщения
                msg_preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
                text += f"{role_emoji} {msg_preview}\n\n"
        else:
            text += "💬 История пуста.\n\n"

        text += "Выберите действие:"

        # Отправляем объединенное сообщение с меню внизу
        await send_menu(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=make_dialog_markup()
        )

        logger.info(f"Пользователь {chat_id} переключился на чат {conversation_id}")

    except Exception as e:
        logger.error(f"Ошибка при переключении на чат {conversation_id} для пользователя {chat_id}: {e}")
        app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при переключении чата"
        )


async def handle_rename_chat_request(
    chat_id: int,
    conversation_id: str,
    app: Client
):
    """
    Запрашивает новое название чата.
    Callback: "rename_chat||{conversation_id}"

    Args:
        chat_id: ID чата Telegram
        conversation_id: ID чата для переименования
        app: Pyrogram Client
    """
    try:
        # Загружаем метаданные чата
        conversation = conversation_manager.load_conversation(chat_id, conversation_id)

        if not conversation:
            await app.send_message(
                chat_id=chat_id,
                text="❌ Чат не найден"
            )
            return

        old_name = conversation.metadata.title

        # Устанавливаем состояние переименования
        user_states[chat_id] = {
            "step": "renaming_chat",
            "conversation_id": conversation_id
        }

        # Запрашиваем новое название
        await app.send_message(
            chat_id=chat_id,
            text=f"✏️ Введите новое название для чата '{old_name}':"
        )

        logger.info(f"Запрошено переименование чата {conversation_id} для пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при запросе переименования чата {conversation_id} для пользователя {chat_id}: {e}")
        await app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка. Попробуйте еще раз."
        )


async def handle_rename_chat_input(
    chat_id: int,
    new_name: str,
    app: Client
):
    """
    Применяет новое название к чату.
    Вызывается из text message handler.

    Args:
        chat_id: ID чата Telegram
        new_name: Новое название чата
        app: Pyrogram Client
    """
    try:
        # Получаем conversation_id из состояния
        state = user_states.get(chat_id, {})
        conversation_id = state.get("conversation_id")

        if not conversation_id:
            app.send_message(
                chat_id=chat_id,
                text="❌ Ошибка: не найден ID чата для переименования"
            )
            return

        # Загружаем чат
        conversation = conversation_manager.load_conversation(chat_id, conversation_id)

        if not conversation:
            app.send_message(
                chat_id=chat_id,
                text="❌ Чат не найден"
            )
            return

        # Обновляем название
        conversation.metadata.title = new_name.strip()
        conversation.metadata.updated_at = datetime.now().isoformat()

        # Сохраняем изменения
        conversation_manager.save_conversation(conversation)

        # Очищаем состояние
        user_states[chat_id] = {}

        # Объединяем результат + меню
        text = f"✅ Чат переименован в '{new_name}'\n\nВаши чаты:"

        await send_menu(
            chat_id=chat_id,
            app=app,
            text=text,
            reply_markup=chats_menu_markup_dynamic(chat_id)
        )

        logger.info(f"Чат {conversation_id} переименован в '{new_name}' для пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при переименовании чата для пользователя {chat_id}: {e}")
        app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при переименовании чата"
        )


async def handle_delete_chat_request(
    chat_id: int,
    conversation_id: str,
    app: Client
):
    """
    Запрашивает подтверждение удаления чата.
    Callback: "delete_chat||{conversation_id}"

    Args:
        chat_id: ID чата Telegram
        conversation_id: ID чата для удаления
        app: Pyrogram Client
    """
    try:
        # Загружаем метаданные чата
        conversation = conversation_manager.load_conversation(chat_id, conversation_id)

        if not conversation:
            await app.send_message(
                chat_id=chat_id,
                text="❌ Чат не найден"
            )
            return

        chat_name = conversation.metadata.title

        # Отправляем запрос на подтверждение
        await app.send_message(
            chat_id=chat_id,
            text=f"⚠️ Удалить чат '{chat_name}'?\n\nЭто действие необратимо.",
            reply_markup=delete_chat_confirmation_markup(conversation_id, chat_name)
        )

        logger.info(f"Запрошено удаление чата {conversation_id} для пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при запросе удаления чата {conversation_id} для пользователя {chat_id}: {e}")
        await app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка. Попробуйте еще раз."
        )


async def handle_delete_chat_confirm(
    chat_id: int,
    conversation_id: str,
    username: str,
    app: Client
):
    """
    Удаляет чат.
    Callback: "confirm_delete||{conversation_id}"

    Args:
        chat_id: ID чата Telegram
        conversation_id: ID чата для удаления
        username: Username пользователя
        app: Pyrogram Client
    """
    try:
        # Удаляем чат
        conversation_manager.delete_conversation(chat_id, conversation_id)

        # Проверяем, остались ли чаты
        all_conversations = conversation_manager.list_conversations(chat_id)

        if not all_conversations:
            # Нет чатов - создаем новый
            new_conversation_id = conversation_manager.create_conversation(
                user_id=chat_id,
                username=username,
                first_question="Новый чат"
            )

            # Очищаем историю меню (новый контекст)
            clear_menus(chat_id)

            text = (
                "✅ Чат удален\n\n"
                "Это был ваш последний чат. Создан новый чат.\n\n"
                "Ваши чаты:"
            )

            await send_menu(
                chat_id=chat_id,
                app=app,
                text=text,
                reply_markup=chats_menu_markup_dynamic(chat_id)
            )

            logger.info(f"Удален последний чат {conversation_id}, создан новый {new_conversation_id} для пользователя {chat_id}")
        else:
            # Остались чаты - возвращаемся в меню
            text = "✅ Чат удален\n\nВаши чаты:"

            await send_menu(
                chat_id=chat_id,
                app=app,
                text=text,
                reply_markup=chats_menu_markup_dynamic(chat_id)
            )

            logger.info(f"Удален чат {conversation_id} для пользователя {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка при удалении чата {conversation_id} для пользователя {chat_id}: {e}")
        app.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при удалении чата"
        )
