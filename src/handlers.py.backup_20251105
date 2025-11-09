from typing import Any, cast
from datetime import datetime, date, timedelta
import os
import re
import threading
import logging
import asyncio
import json
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, Document, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from minio.error import S3Error

from minio_manager import get_minio_manager, MinIOError, MinIOConnectionError, MinIOUploadError

from config import (
    processed_texts,
    user_states,
    STORAGE_DIRS,
    get_auth_manager
)
from utils import run_loading_animation, openai_audio_filter, get_username_from_chat
from constants import COMMAND_HISTORY, COMMAND_STATS, COMMAND_REPORTS
from conversation_manager import conversation_manager
from md_storage import md_storage_manager
from validators import validate_date_format, check_audio_file_size, check_state, check_file_detection, check_valid_data, validate_building_type
from parser import parse_message_text, parse_building_type, parse_zone, parse_file_number, parse_place_name, parse_city, parse_name

from storage import delete_tmp_params, safe_filename, find_real_filename
from datamodels import mapping_building_names, REPORT_MAPPING, mapping_scenario_names

from markups import (
    help_menu_markup,
    storage_menu_markup,
    system_menu_markup,
    chats_menu_markup,
    chats_menu_markup_dynamic,
    interview_or_design_menu,
    interview_menu_markup,
    design_menu_markup,
    building_type_menu_markup,
    make_dialog_markup,
    edit_menu_markup
)

from menus import (
    send_main_menu,
    files_menu_markup,
    show_confirmation_menu,
    show_edit_menu
)
from menu_manager import send_menu
from message_tracker import track_and_send
from storage import process_stored_file

from analysis import (
    assign_roles
)

# Logger для handlers
logger = logging.getLogger(__name__)

from run_analysis import run_analysis_with_spinner, run_dialog_mode

from audio_utils import extract_audio_filename, define_audio_file_params, transcribe_audio_and_save

from openai import PermissionDeniedError as OpenAIPermissionError

# === МУЛЬТИЧАТЫ: Импорты ===
from conversation_manager import conversation_manager
from conversation_handlers import (
    ensure_active_conversation,
    handle_new_chat,
    handle_chat_actions,
    handle_switch_chat_request,
    handle_switch_chat_confirm,
    handle_rename_chat_request,
    handle_rename_chat_input,
    handle_delete_chat_request,
    handle_delete_chat_confirm
)
# === КОНЕЦ МУЛЬТИЧАТЫ ===

# === АВТООТПРАВКА ФАЙЛОВ ===
from file_sender import auto_send_history_file, auto_send_reports_file, send_history_on_demand
# === КОНЕЦ АВТООТПРАВКА ФАЙЛОВ ===

# === МОИ ОТЧЕТЫ V2 ===
from handlers_my_reports_v2 import (
    handle_my_reports_v2,
    handle_report_view_request,
    handle_report_view_input,
    handle_report_rename_request,
    handle_report_rename_number_input,
    handle_report_rename_name_input,
    handle_report_delete_request,
    handle_report_delete_input,
    handle_report_delete_confirm
)
# === КОНЕЦ МОИ ОТЧЕТЫ V2 ===

# === AUTH: Импорты для управления доступом ===
from auth_filters import auth_filter
from access_handlers import (
    handle_access_menu,
    handle_users_menu,
    handle_list_users,
    handle_user_details,
    handle_edit_user,
    handle_change_role,
    handle_confirm_role_change,
    handle_reset_password,
    handle_confirm_reset_password,
    handle_toggle_block_user,
    handle_confirm_block,
    handle_delete_user,
    handle_confirm_delete,
    handle_filter_users_by_role,
    handle_search_user,
    handle_search_user_input,
    handle_invitations_menu,
    handle_create_invitation,
    handle_confirm_create_invite,
    handle_list_invitations,
    handle_invitation_details,
    handle_revoke_invitation,
    handle_confirm_revoke,
    handle_security_menu,
    handle_audit_log,
    handle_change_password_start,
    handle_password_change_current_input,
    handle_password_change_new_input,
    handle_password_change_confirm_input,
    handle_users_pagination,
    handle_invitations_pagination,
    handle_filter_apply,
    handle_filter_reset
)
# === КОНЕЦ AUTH ===

# Initialize MinIO manager
minio_manager = get_minio_manager()

filter_wav_document = filters.create(openai_audio_filter)

audio_file_name_to_save = ""
transcription_text = ""

rags = {}
rags_lock = asyncio.Lock()


async def set_rags(new_rags: dict[str, Any]) -> None:
    """Allow external modules to update loaded RAGs."""
    global rags
    async with rags_lock:
        rags = new_rags

async def ask_client(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    data["client"] = parse_name(text)
    # Переходим к шагу подтверждения
    state["step"] = "confirm_data"
    await show_confirmation_menu(chat_id, state, app)

def ask_employee(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    data["employee"] = parse_name(text)
    state["step"] = "ask_place_name"
    app.send_message(chat_id, "Введите название заведения:")

def ask_building_type(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    data["building_type"] = parse_building_type(text)
    state["step"] = "ask_zone"
    app.send_message(chat_id, "Введите зону (если она есть) или поставьте -:")

def ask_zone(data: dict[str, Any], text: str, mode: str, state: dict[str, Any], chat_id: int, app: Client):
    data['zone_name'] = parse_zone(text)
    if mode == "interview":
        # Для интервью сейчас не запрашиваем город — сразу завершаем сбор
        state["step"] = "ask_client"
        app.send_message(chat_id, "Введите ФИО клиента:")
    else:
        # Если это дизайн — надо спросить город
        state["step"] = "ask_city"
        app.send_message(chat_id, "Введите город:")

def ask_place_name(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    data["place_name"] = parse_place_name(text)
    state["step"] = "ask_building_type"
    app.send_message(chat_id, "Введите тип заведения:")

def ask_date(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    if not validate_date_format(text):
        app.send_message(chat_id, "❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД (например, 2025-01-01).")
        return
    data["date"] = text
    state["step"] = "ask_employee"
    app.send_message(chat_id, "Введите ФИО сотрудника:")

async def ask_city(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    data["city"] = parse_city(text)
    # Переходим к шагу подтверждения
    state["step"] = "confirm_data"
    await show_confirmation_menu(chat_id, state, app)

def ask_audio_number(data: dict[str, Any], text: str, state: dict[str, Any], chat_id: int, app: Client):
    """
    Спрашиваем пользователя номер аудио файла.
    """
    try:
        audio_number = parse_file_number(text)
        data["audio_number"] = audio_number
        state["step"] = "ask_date"
        app.send_message(chat_id, "Введите дату в формате ГГГГ-ММ-ДД (например, 2025-01-01):")
    except ValueError:
        app.send_message(chat_id, "❌ Неверный формат номера файла. Пожалуйста, введите целое число.")

# --------------------------------------------------------------------------------------
#                                Редактирование полей
# --------------------------------------------------------------------------------------

async def handle_edit_field(chat_id: int, field: str, app: Client):
    """
    Ставит шаг (step) на редактирование нужного поля, затем просит ввести новое значение.

    ✅ ОБНОВЛЕНО: Использует track_and_send для автоматической очистки артефактов.
    """
    st = user_states.get(chat_id, {})
    if not st:
        logging.error("Состояние пользователя не найдено.")
        return
    st["previous_step"] = st.get("step")
    st["step"] = f"edit_{field}"
    mode = st.get("mode")
    edit_fields = {
        "audio_number": "Введите новый номер файла:",
        "date": "Введите новую дату в формате ГГГГ-ММ-ДД (например, 2025-01-01):",
        "employee": "Введите новое ФИО Сотрудника:",
        "place_name": "Введите новое название заведения:",
        "building_type": "Введите новый тип заведения",
        "zone_name": "Введите новую зону (если есть)"
    }

    if mode == "design":
        edit_fields["city"] = "Введите новый город:"
    else:
        edit_fields["client"] = "Введите новое ФИО Клиента"

    prompt_text = edit_fields.get(field, "Введите новое значение:")

    # Создаем кнопку "Назад" для отмены редактирования
    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="back_to_confirm")]
    ])

    # Используем track_and_send для автоматической очистки
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=prompt_text,
        reply_markup=cancel_markup,
        message_type="input_request"
    )


async def handle_history_command(message: Message, app: Client) -> None:
    """Обработчик команды /history."""
    chat_id = message.chat.id
    username = await get_username_from_chat(chat_id, app)

    try:
        # Парсим дату из команды (опционально)
        text = message.text.strip()
        parts = text.split()
        target_date = None

        if len(parts) > 1:
            date_str = parts[1]
            # Пытаемся распарсить дату в разных форматах
            date_formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]

            for fmt in date_formats:
                try:
                    target_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue

            if target_date is None:
                app.send_message(
                    chat_id,
                    "❌ Неверный формат даты. Используйте: YYYY-MM-DD, DD.MM.YYYY или DD/MM/YYYY\n"
                    "Пример: `/history 2025-01-15`"
                )
                return

        # Получаем активный чат и показываем его историю
        active_conversation_id = conversation_manager.get_active_conversation_id(chat_id)
        if not active_conversation_id:
            app.send_message(chat_id, "📭 У вас еще нет активных чатов.")
            return

        # Получаем последние 20 сообщений
        messages = conversation_manager.get_messages(chat_id, active_conversation_id, limit=20)
        if not messages:
            app.send_message(chat_id, "📭 В этом чате еще нет сообщений.")
            return

        # Форматируем историю для отображения
        conversation = conversation_manager.load_conversation(chat_id, active_conversation_id)
        result = f"📜 История чата \"{conversation.metadata.title}\"\n\n"

        for msg in messages:
            timestamp = msg.timestamp[:16].replace('T', ' ')  # 2025-10-05 12:30
            role = "👤 Вы" if msg.type == "user_question" else "🤖 Ассистент"
            preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
            file_marker = " 📎" if msg.sent_as == "file" else ""
            result += f"**{role}** ({timestamp}){file_marker}\n{preview}\n\n"

        result += f"📊 Всего сообщений: {conversation.metadata.message_count}\n"
        result += f"📝 Токенов: {conversation.metadata.total_tokens:,}"

        app.send_message(chat_id, result, )

    except Exception as e:
        logging.error(f"Error handling history command: {e}")
        app.send_message(chat_id, "❌ Произошла ошибка при получении истории.")


async def handle_stats_command(message: Message, app: Client) -> None:
    """Обработчик команды /stats."""
    chat_id = message.chat.id

    try:
        stats_text = conversation_manager.format_user_stats_for_display(chat_id)
        await app.send_message(chat_id, stats_text, )

    except Exception as e:
        logging.error(f"Error handling stats command: {e}")
        await app.send_message(chat_id, "❌ Произошла ошибка при получении статистики.")


async def handle_reports_command(message: Message, app: Client) -> None:
    """Обработчик команды /reports."""
    chat_id = message.chat.id

    try:
        reports = md_storage_manager.get_user_reports(chat_id, limit=10)

        if not reports:
            app.send_message(
                chat_id,
                "📁 **Ваши отчеты:**\n\nУ вас пока нет сохраненных отчетов.",

            )
            return

        # Создаем inline клавиатуру с отчетами
        keyboard = []

        for i, report in enumerate(reports[:5], 1):  # Показываем только 5 последних
            timestamp = datetime.fromisoformat(report.timestamp).strftime("%d.%m %H:%M")
            question_preview = report.question[:40] + "..." if len(report.question) > 40 else report.question
            search_icon = "⚡" if report.search_type == "fast" else "🔍"

            button_text = f"{search_icon} {timestamp}: {question_preview}"
            callback_data = f"send_report||{report.file_path}"

            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        keyboard.append([InlineKeyboardButton("📊 Показать все отчеты", callback_data="show_all_reports")])

        reports_text = md_storage_manager.format_user_reports_for_display(chat_id)

        await send_menu(
            chat_id=chat_id,
            app=app,
            text=reports_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logging.error(f"Error handling reports command: {e}")
        app.send_message(chat_id, "❌ Произошла ошибка при получении отчетов.")


async def handle_report_callback(callback_query: CallbackQuery, app: Client) -> None:
    """
    🆕 ASYNC: Обработчик callback для отправки отчетов.

    Теперь полностью async для совместимости с handlers_my_reports_v2.
    """
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    try:
        if data.startswith("send_report||"):
            relative_path = data.split("send_report||", 1)[1]

            # Получаем путь к файлу
            file_path = md_storage_manager.get_report_file_path(relative_path)

            if file_path and file_path.exists():
                await app.send_document(
                    chat_id,
                    str(file_path),
                    caption="📄 Ваш отчет"
                )
                await app.answer_callback_query(callback_query.id, "✅ Отчет отправлен")
            else:
                await app.answer_callback_query(
                    callback_query.id,
                    "❌ Файл не найден",
                    show_alert=True
                )

        elif data == "show_all_reports":
            # Показываем полный список отчетов
            reports_text = md_storage_manager.format_user_reports_for_display(chat_id)

            # Добавляем кнопку "Назад"
            back_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад к отчетам", callback_data="show_my_reports")]
            ])

            await app.edit_message_text(
                chat_id,
                callback_query.message.id,
                reports_text,
                reply_markup=back_keyboard
            )
            await app.answer_callback_query(callback_query.id)

    except Exception as e:
        logging.error(f"Error handling report callback: {e}")
        await app.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка",
            show_alert=True
        )

async def handle_authorized_text(app: Client, user_states: dict[int, dict[str, Any]], message: Message):
    """
    Этот хендлер обрабатывает все текстовые сообщения от авторизованного пользователя,
    в т.ч. логику по шагам (сбор данных для интервью/дизайна).
    """
    c_id = message.chat.id
    text_ = message.text.strip()

    # Проверяем команды истории, статистики и отчетов
    if text_.startswith(COMMAND_HISTORY):
        await handle_history_command(message, app)
        return
    elif text_.startswith(COMMAND_STATS):
        await handle_stats_command(message, app)
        return
    elif text_.startswith(COMMAND_REPORTS):
        await handle_reports_command(message, app)
        return

    # === МУЛЬТИЧАТЫ: Проверка переименования чата ===
    if c_id in user_states and user_states[c_id].get("step") == "renaming_chat":
        await handle_rename_chat_input(c_id, text_, app)
        return
    # === КОНЕЦ МУЛЬТИЧАТЫ ===

    # === МОИ ОТЧЕТЫ V2: FSM обработка ===
    if c_id in user_states:
        step = user_states[c_id].get("step")

        # View workflow
        if step == "report_view_ask_number":
            await handle_report_view_input(c_id, text_, app)
            return

        # Rename workflow
        elif step == "report_rename_ask_number":
            await handle_report_rename_number_input(c_id, text_, app)
            return
        elif step == "report_rename_ask_new_name":
            await handle_report_rename_name_input(c_id, text_, app)
            return

        # Delete workflow
        elif step == "report_delete_ask_number":
            await handle_report_delete_input(c_id, text_, app)
            return
    # === КОНЕЦ МОИ ОТЧЕТЫ V2 ===

    # === AUTH: FSM обработка смены пароля (ИЗМЕНЕНИЕ 1) ===
    if c_id in user_states:
        step = user_states[c_id].get("step")

        # FSM: Смена пароля
        if step == "password_change_current":
            await handle_password_change_current_input(c_id, text_, app)
            return

        elif step == "password_change_new":
            await handle_password_change_new_input(c_id, text_, app)
            return

        elif step == "password_change_confirm":
            await handle_password_change_confirm_input(c_id, text_, app)
            return

        # FSM: Поиск пользователя
        elif step == "access_search_user_input":
            await handle_search_user_input(c_id, text_, app)
            return
    # === КОНЕЦ AUTH FSM ===


    # Проверяем, есть ли у пользователя активное состояние
    st = user_states.get(c_id)
    logging.info(f"Пользователь {c_id} отправил текст '{text_[:50]}...'. Состояние: {st}")

    # === ПРОВЕРКА РЕЖИМА ДИАЛОГА ===
    # Пользователь должен сначала выбрать чат и режим поиска
    if not st or st.get("step") != "dialog_mode":
        logging.warning(f"Пользователь {c_id} не прошёл проверку режима. st={st}")
        await app.send_message(
            c_id,
            "📌 Для начала работы:\n\n"
            "1️⃣ Выберите чат или создайте новый\n"
            "2️⃣ Выберите режим поиска (быстрый или глубокий)\n"
            "3️⃣ Задайте вопрос\n\n"
            "Откройте главное меню ниже 👇"
        )
        await send_main_menu(c_id, app)
        return
    # === КОНЕЦ ПРОВЕРКИ ===

    # === МУЛЬТИЧАТЫ: Получение conversation_id ===
    conversation_id = st.get("conversation_id")
    if not conversation_id:
        # Fallback: создаем чат если его нет в состоянии
        username = await get_username_from_chat(c_id, app)
        conversation_id = ensure_active_conversation(c_id, username, text_)
        st["conversation_id"] = conversation_id
        user_states[c_id] = st  # ✅ Сохраняем изменения обратно
    # === КОНЕЦ МУЛЬТИЧАТЫ ===


    if st.get("step") == "dialog_mode":
        deep = st.get("deep_search", False)
        # Отправляем системное сообщение-статус через MessageTracker
        msg = await track_and_send(
            chat_id=c_id,
            app=app,
            text="⏳ Думаю...",
            message_type="status_message"
        )
        st_ev = threading.Event()
        sp_th = threading.Thread(target=run_loading_animation, args=(c_id, msg.id, st_ev, app))
        sp_th.start()
        try:
            if not rags:
                await app.send_message(c_id, "🔄 База знаний ещё загружается, попробуйте позже.")
            else:
                await run_dialog_mode(
                    message=message,
                    app=app,
                    deep_search=deep,
                    rags=rags,
                    conversation_id=conversation_id
                )
            return
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            await app.send_message(c_id, "Произошла ошибка")
        finally:
            st_ev.set()
            sp_th.join()

    # Если пользователь находится в режиме редактирования
    if st.get("step", "").startswith("edit_"):
        step = st["step"]
        field = st["step"].split("edit_")[1]
        # Валидация даты
        if field == "date" and not validate_date_format(text_):
            app.send_message(c_id, "Неверный формат даты. Попробуйте снова.")
            return

        # Сохраняем новое значение
        data_ = st.setdefault("data", {})
        data_[field] = text_

        previous_step = st.pop("previous_step", "confirm_data")
        st["step"] = previous_step

        await show_confirmation_menu(c_id, st, app)
        return

    mode = st.get("mode")        # 'interview' или 'design'
    if mode is None:
        # Если mode не установлен, возвращаемся к главному меню
        user_states.pop(c_id, None)
        app.send_message(c_id, "Режим не выбран. Начните заново /start.")
        send_main_menu(c_id, app)
        return
    # Проверяем, что mode является строкой
    if not isinstance(mode, str):
        user_states.pop(c_id, None)
        app.send_message(c_id, "Некорректный режим. Начните заново /start.")
        send_main_menu(c_id, app)
        return

    step = st.get("step")        # например, 'ask_employee'
    data_ = st.setdefault("data", {})

    if st.get("step") == "inputing_fields":
        ask_audio_number(data_, text_, st, c_id, app)
        return

    if step == "ask_employee":
        ask_employee(data_, text_, st, c_id, app)
        return

    elif step == "ask_audio_number":
        ask_audio_number(data_, text_, st, c_id, app)
        return

    elif step == "ask_place_name":
        ask_place_name(data_, text_, st, c_id, app)
        return

    elif step == "ask_date":
        ask_date(data_, text_, st, c_id, app)

    elif step == "ask_city":
        await ask_city(data_, text_, st, c_id, app)
        return

    elif step == "ask_building_type":
        ask_building_type(data_, text_, st, c_id, app)
        return

    elif step == "ask_zone":
        ask_zone(data_, text_, mode, st, c_id, app)

    elif step == "ask_client":
        await ask_client(data_, text_, st, c_id, app)
    else:
        # На всякий случай, если что-то пошло не так
        user_states.pop(c_id, None)
        app.send_message(c_id, "Неизвестное состояние. Начните заново /start.")
        send_main_menu(c_id, app)

# =========================================================================
#  Callback-queries
# =========================================================================

async def handle_help_menu(chat_id: int, app: Client):
    kb, txt = help_menu_markup()
    await send_menu(chat_id, app, txt, kb)

async def handle_menu_storage(chat_id: int, app: Client):
    await send_menu(chat_id, app, "Что анализируем?:", interview_or_design_menu())

async def handle_menu_system(chat_id: int, app: Client):
    # Получить роль пользователя для отображения меню по правам
    from config import get_auth_manager

    auth = get_auth_manager()
    user_role = "user"  # По умолчанию
    if auth:
        user = auth.storage.get_user_by_telegram_id(chat_id)
        if user:
            user_role = user.role

    await send_menu(chat_id, app, "⚙️ Системные настройки:", system_menu_markup(user_role=user_role))

async def handle_menu_chats(chat_id: int, app: Client):
    """Показывает меню чатов с динамическим списком."""
    await send_menu(
        chat_id,
        app,
        "📱 История и статистика чатов:",
        chats_menu_markup_dynamic(chat_id)
    )

async def handle_main_menu(chat_id: int, app: Client):
    await send_main_menu(chat_id, app)

async def handle_show_stats(chat_id: int, app: Client):
    """Показывает статистику чатов"""
    try:
        stats_text = conversation_manager.format_user_stats_for_display(chat_id)

        # Показываем статистику с меню чатов внизу
        await send_menu(
            chat_id=chat_id,
            app=app,
            text=stats_text,
            reply_markup=chats_menu_markup_dynamic(chat_id)
        )
    except Exception as e:
        logging.error(f"Error showing stats: {e}")
        await send_menu(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при получении статистики.",
            reply_markup=chats_menu_markup_dynamic(chat_id)
        )

async def handle_show_my_reports(chat_id: int, app: Client):
    """
    🆕 V2: Показывает список отчетов через TXT файл + меню операций.

    Делегирует всю логику handlers_my_reports_v2.handle_my_reports_v2()
    """
    await handle_my_reports_v2(chat_id, app)

async def handle_view_files(chat_id: int, data, app: Client):
    parts = data.split("||")
    if len(parts) < 2:
        return
    cat = parts[1]
    await send_menu(chat_id, app, f"Файлы в '{cat}':", files_menu_markup(cat))

async def process_selected_file(chat_id: int, category: str, filename: str, app: Client):
    # Отправляем системное сообщение-статус через MessageTracker
    msg = await track_and_send(
        chat_id=chat_id,
        app=app,
        text="⏳ Обрабатываю файл...",
        message_type="status_message"
    )
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=run_loading_animation, args=(chat_id, msg.id, stop_event, app))
    spinner_thread.start()

    try:
        result = process_stored_file(category, filename, chat_id, app)
        if result is not None:
            processed_texts[chat_id] = result
            # app.edit_message_text(chat_id, msg.id, "✅ Файл обработан.")
            logging.info("✅ Файл обработан.")
    finally:
        stop_event.set()
        spinner_thread.join()
        await app.delete_messages(chat_id, msg.id)

    # app.send_message(chat_id, "Что анализируем дальше?", reply_markup=interview_or_design_menu())
    # send_main_menu(chat_id, app)


def preprocess_parts(data: str, treshold: int=3) -> list[str] | None:
    parts = data.split("||")
    if len(parts) < treshold:
        logging.error("Неверный формат данных для choose_building")
        return None
    return parts

async def handle_file_selection(chat_id: int, data: str, app: Client):
    parts = preprocess_parts(data)
    if parts is None:
        await app.send_message(chat_id, "Ошибка обработки данных")
        return
    category, file_name = parts[1], parts[2]
    folder = STORAGE_DIRS.get(category, "")
    real_name = find_real_filename(folder, file_name)
    if not check_file_detection(real_name, chat_id, app):
        logging.error(f"Файл {real_name} не найден")
        raise ValueError(f"Файл {real_name} не найден")
    await process_selected_file(chat_id, category, real_name, app)

async def handle_file_deletion(chat_id: int, data: str, app: Client):
    parts = preprocess_parts(data)
    if parts is None:
        app.send_message(chat_id, "Ошибка обработки данных")
        return
    category, file_name = parts[1], parts[2]
    folder = STORAGE_DIRS.get(category, "")
    real_name = find_real_filename(folder, file_name)
    if not check_file_detection(real_name, chat_id, app):
        logging.error(f"Файл {real_name} не найден")
        raise ValueError(f"Файл {real_name} не найден")

    try:
        os.remove(os.path.join(folder, real_name))
        logging.info("Файл удалён.")
    except Exception as e:
        logging.error(f"Ошибка удаления: {e}")

    await send_menu(
        chat_id=chat_id,
        app=app,
        text=f"Список файлов в '{category}':",
        reply_markup=files_menu_markup(category)
    )

async def file_upload_handler(chat_id: int, data: str, app: Client):
    parts = preprocess_parts(data, 2)
    if parts is None:
        await app.send_message(chat_id, "Ошибка обработки данных")
        return
    category = parts[1]
    # user_states[chat_id] = {"upload_category": category}
    user_states.setdefault(chat_id, {})["upload_category"] = category
    await app.send_message(chat_id, f"Отправьте документ для сохранения в '{category}'.")

# --------------------------------------------------------------------------------------
#                        Подтверждение и сохранение (Callback)
# --------------------------------------------------------------------------------------

async def handle_confirm_data(chat_id: int, app: Client):
    st = user_states.get(chat_id)
    if not st:
        return
    st["data_collected"] = True
    st["step"] = None

    mode = st.get("mode", "—")
    d = cast(dict[str, Any], st.get("data", {}))
    employee = d.get("employee", "—")
    place = d.get("place_name", "—")
    date_ = d.get("date", "—")
    city = d.get("city", "")
    zone_name = d.get("zone_name", "")
    number_audio = d.get("audio_number", "—")
    building_type = d.get("building_type", "—")
    client = d.get("client", "")

    # Проверяем, что mode является строкой для безопасного доступа к словарю
    scenario_name = mapping_scenario_names.get(mode, "—") if isinstance(mode, str) else "—"

    msg = (
        f"**Данные сохранены**:\n\n"
        f"**Сценарий**: {scenario_name}\n"
        f"**Номер файла**: {number_audio}\n"
        f"**Дата**: {date_}\n"
        f"**ФИО Сотрудника**: {employee}\n"
        f"**Заведение**: {place}\n"
        f"**Тип заведения**: {building_type}\n"
        f"**Зона**: {zone_name}\n"
    )

    if city:
        msg += f"**Город**: {city}\n\n"
    if client:
        msg += f"**ФИО Клиента**: {client}\n\n"

    msg += "**Доступные отчёты:**"

    # Отправляем объединенное сообщение с меню
    markup = None
    if mode == "interview":
        markup = interview_menu_markup()
    elif mode == "design":
        markup = design_menu_markup()

    if markup:
        await send_menu(
            chat_id=chat_id,
            app=app,
            text=msg,
            reply_markup=markup
        )

async def handle_back_to_confirm(chat_id: int, app: Client):
    st = user_states.get(chat_id)
    if not st:
        return
    st["step"] = "confirm_data"
    await show_confirmation_menu(chat_id, st, app)

async def handle_mode_selection(chat_id: int, mode: str, app: Client):
    """
    Выбор сценария «Интервью» или «Дизайн»
    """

    user_states[chat_id] = {
        "mode": "interview" if mode == "mode_interview" else "design",
        "data": {}
    }
    st = user_states[chat_id]
    await send_menu(chat_id, app, "📦 Меню хранилища:", storage_menu_markup())

async def preprocess_report_without_buildings(chat_id: int, data: str, app: Client, building_name: str = "non-building"):
    validate_datas = []
    st = user_states.get(chat_id, {})
    mode = st.get("mode")
    data_ = cast(dict[str, Any], st.get("data", {}))

    data_["audio_file_name"] = audio_file_name_to_save

    validate_datas.append(mode)
    validate_datas.append(data_)

    check_valid_data(validate_datas, chat_id, app, "Не хватает данных для формирования отчёта. Начните заново.")

    data_["type_of_location"] = building_name

    try:
        await run_analysis_with_spinner(
            chat_id=chat_id,
            processed_texts=processed_texts,
            app=app,
            callback_data=data,
            data=data_,
            transcription_text=transcription_text
        )
    except Exception as e:
        logging.error(f"Ошибка при обработке отчёта {data}: {e}")
        # app.send_message(chat_id, f"❌ Произошла ошибка при обработке запроса: {str(e)}"))

async def preprocess_report_with_buildings(chat_id: int, data: str, app: Client):
    st = user_states.setdefault(chat_id, {})
    st["pending_report"] = data
    await send_menu(chat_id, app, "Выберите тип заведения:", building_type_menu_markup())

async def handle_report(chat_id: int, callback_data : str, app: Client):
    if callback_data  in [
        "report_int_methodology",
        "report_int_links",
        "report_design_audit_methodology"
    ]:
        await preprocess_report_without_buildings(chat_id, callback_data , app)

    elif callback_data  in [
        "report_int_general",
        "report_int_specific",
        "report_design_compliance",
        "report_design_structured"
    ]:

        state = user_states.get(chat_id, {})
        data = cast(dict[str, Any], state.get("data", {}))
        building_type = data.get('building_type', "")
        valid_building_type = validate_building_type(building_type)
        if valid_building_type is None:
            await preprocess_report_with_buildings(chat_id, callback_data , app)
        else:
            building_type = valid_building_type
            data['building_type'] = building_type
            preprocess_report_without_buildings(chat_id, callback_data , app, building_name=building_type)

def handle_assign_roles(chat_id: int, app: Client, mode: str, processed_texts: dict[int, str]):
    # Если пользователь выбрал «Интервью» — расставляем роли
    if mode == "interview":
        transcript = processed_texts.get(chat_id)
        if transcript:
            msg_ = app.send_message(chat_id, "🔄 Расставляю роли в диалоге...")
            st_ev = threading.Event()
            sp_th = threading.Thread(target=run_loading_animation, args=(chat_id, msg_.id, st_ev, app))
            sp_th.start()
            try:
                # Расставляем роли
                roles_ = assign_roles(transcript)
                processed_texts[chat_id] = roles_

                # Обновляем сообщение об успешной обработке
                app.edit_message_text(chat_id, msg_.id, "✅ Роли в диалоге расставлены.")
                logging.info("✅ Роли в диалоге расставлены.")

            except Exception as e:
                logging.exception(f"❌ Ошибка при расстановке ролей: {str(e)}")
                # app.edit_message_text(chat_id, msg_.id, f"❌ Ошибка при расстановке ролей: {str(e)}")

            finally:
                # Останавливаем спиннер
                st_ev.set()
                sp_th.join()

async def handle_choose_building(chat_id: int, data: str, app: Client):
    validate_datas = []
    parts = preprocess_parts(data, 2) # 'hotel' / 'restaurant' / 'spa'
    if parts is None:
        app.send_message(chat_id, "Ошибка обработки данных")
        return
    short_name = parts[1]
    st = user_states.get(chat_id, {})
    pending_report = st.get("pending_report", None)
    mode = st.get("mode")
    data_ = cast(dict[str, Any], st.get("data", {}))

    if not isinstance(pending_report, str):
        logging.error("pending_report не является строкой")
        return
    if not isinstance(mode, str):
        logging.error("mode не является строкой")
        return

    data_["audio_file_name"] = audio_file_name_to_save

    # Преобразуем short_name из callback в нормальное название
    building_name = mapping_building_names.get(short_name, short_name)

    data_["type_of_location"] = building_name

    validate_datas.append(mode)
    validate_datas.append(pending_report)
    validate_datas.append(data_)

    check_valid_data(validate_datas, chat_id, app, "Неизвестно, какой отчёт вы хотели. Начните заново.")

    #Запускаем анализ
    await run_analysis_with_spinner(
        chat_id=chat_id,
        processed_texts=processed_texts,
        app=app,
        callback_data=pending_report,
        data=data_,
        transcription_text=transcription_text
    )

    st["pending_report"] = None

async def handle_mode_fast(callback: CallbackQuery, app: Client):
    """Обработчик выбора быстрого поиска."""
    chat_id = callback.message.chat.id

    # Сохраняем существующее состояние
    st = user_states.get(chat_id, {})

    # Проверяем наличие необходимых полей
    if "step" not in st or "conversation_id" not in st:
        # Если состояние было сброшено - переинициализируем
        username = await get_username_from_chat(chat_id, app)
        conversation_id = ensure_active_conversation(chat_id, username)
        st = {
            "conversation_id": conversation_id,
            "step": "dialog_mode",
            "deep_search": False
        }
    else:
        # Если состояние корректное - просто обновляем deep_search
        st["deep_search"] = False

    # Сохраняем обновлённое состояние
    user_states[chat_id] = st

    await callback.answer("⚡ Выбран быстрый поиск")
    logging.info(f"Пользователь {chat_id} выбрал быстрый поиск. Состояние: {st}")

    # Удаляем старое меню и показываем инструкцию
    await send_menu(
        chat_id,
        app,
        "✅ Режим установлен: **Быстрый поиск**\n\n"
        "Теперь задайте ваш вопрос 👇",
        make_dialog_markup()
    )


async def handle_mode_deep(callback: CallbackQuery, app: Client):
    """Обработчик выбора глубокого исследования."""
    chat_id = callback.message.chat.id

    # Сохраняем существующее состояние
    st = user_states.get(chat_id, {})

    # Проверяем наличие необходимых полей
    if "step" not in st or "conversation_id" not in st:
        # Если состояние было сброшено - переинициализируем
        username = await get_username_from_chat(chat_id, app)
        conversation_id = ensure_active_conversation(chat_id, username)
        st = {
            "conversation_id": conversation_id,
            "step": "dialog_mode",
            "deep_search": True
        }
    else:
        # Если состояние корректное - просто обновляем deep_search
        st["deep_search"] = True

    # Сохраняем обновлённое состояние
    user_states[chat_id] = st

    await callback.answer("🔬 Выбрано глубокое исследование")
    logging.info(f"Пользователь {chat_id} выбрал глубокое исследование. Состояние: {st}")

    # Удаляем старое меню и показываем инструкцию
    await send_menu(
        chat_id,
        app,
        "✅ Режим установлен: **Глубокое исследование**\n\n"
        "Теперь задайте ваш вопрос 👇",
        make_dialog_markup()
    )

async def handle_menu_dialog(chat_id: int, app: Client):
    # Получаем текущее состояние или создаем новое
    st = user_states.get(chat_id, {})

    # Сохраняем conversation_id если он есть, иначе создаем новый чат
    conversation_id = st.get("conversation_id")
    if not conversation_id:
        username = await get_username_from_chat(chat_id, app)
        conversation_id = ensure_active_conversation(chat_id, username)

    # Устанавливаем состояние диалога
    user_states[chat_id] = {
        "conversation_id": conversation_id,
        "step": "dialog_mode",
        "deep_search": st.get("deep_search", False)  # Сохраняем предыдущий режим
    }

    await send_menu(
        chat_id,
        app,
        "Какую информацию вы хотели бы получить?",
        make_dialog_markup()
    )

def register_handlers(app: Client):
    """
    Регистрируем все хендлеры Pyrogram.
    """

    @app.on_message(filters.command("start") & auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def cmd_start(app: Client, message: Message):
        """Команда /start - доступна только авторизованным пользователям."""
        c_id = message.chat.id
        await send_main_menu(c_id, app)

    # === AUTH: Login flow для пользователей без активной сессии ===
    @app.on_message(filters.command("start") & ~auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def cmd_start_login(client: Client, message: Message):
        """
        Обработчик /start для НЕавторизованных пользователей.
        Проверяет существование user и запрашивает пароль.
        """
        c_id = message.chat.id
        telegram_id = message.from_user.id

        auth = get_auth_manager()
        if not auth:
            await message.reply_text("⚠️ Система авторизации недоступна. Попробуйте позже.")
            return

        # Проверить существование пользователя
        user = auth.storage.get_user_by_telegram_id(telegram_id)

        if user:
            # User существует, но нет активной сессии → запросить пароль
            user_states[c_id] = {
                "step": "awaiting_password",
                "user_id": user.user_id,
                "telegram_id": telegram_id,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(minutes=5)  # W-03: timeout 5 минут
            }
            await message.reply_text(
                "🔐 **Вход в систему**\n\n"
                f"Здравствуйте, {user.username}!\n"
                "Введите пароль для авторизации:",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"Login prompt sent: telegram_id={telegram_id}, user_id={user.user_id}")
        else:
            # User НЕ существует → доступ запрещен (требуется приглашение)
            await message.reply_text(
                "❌ **Доступ запрещен**\n\n"
                "Для использования бота требуется приглашение от администратора.\n"
                "Обратитесь к администратору для получения доступа."
            )
            logger.warning(f"Access denied - user not found: telegram_id={telegram_id}")

    @app.on_message(filters.text & ~filters.command("start") & ~auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def handle_password_input(client: Client, message: Message):
        """
        Обработчик ввода пароля для НЕавторизованных пользователей.
        """
        c_id = message.chat.id
        telegram_id = message.from_user.id

        # Проверить FSM state
        if c_id not in user_states or user_states[c_id].get("step") != "awaiting_password":
            # Неавторизованный пользователь отправил текст, но НЕ в состоянии ожидания пароля
            await message.reply_text(
                "❌ Вы не авторизованы. Отправьте /start для входа."
            )
            return

        # W-03: Проверка истечения timeout (5 минут)
        state = user_states[c_id]
        if state.get("expires_at") and datetime.now() > state["expires_at"]:
            del user_states[c_id]
            await message.reply_text(
                "⏱️ **Время ввода пароля истекло**\n\n"
                "Отправьте /start заново для повторной попытки."
            )
            logger.info(f"Login timeout expired: telegram_id={telegram_id}")
            return

        auth = get_auth_manager()
        if not auth:
            await message.reply_text("⚠️ Система авторизации недоступна.")
            return

        password = message.text.strip()
        user_id = user_states[c_id].get("user_id")

        # КРИТИЧНО: Удалить сообщение с паролем из истории чата (W-02)
        try:
            await message.delete()
            logger.debug(f"Password message deleted: telegram_id={telegram_id}")
        except Exception as e:
            logger.warning(f"Failed to delete password message: {e}")

        # Попытка аутентификации (C-01: добавлен await!)
        session = await auth.authenticate(telegram_id, password)

        if session:
            # ✅ Успешная аутентификация
            del user_states[c_id]  # Очистить FSM state

            await message.reply_text(
                "✅ **Вход выполнен успешно!**\n\n"
                "Добро пожаловать в VoxPersona."
            )

            # Отправить главное меню
            await send_main_menu(c_id, client)

            logger.info(f"Login successful: telegram_id={telegram_id}, session_id={session.session_id}")
        else:
            # ❌ Неверный пароль
            attempts = user_states[c_id].get("attempts", 0) + 1
            user_states[c_id]["attempts"] = attempts

            if attempts >= 3:
                # Блокировка после 3 неудачных попыток
                del user_states[c_id]
                await message.reply_text(
                    "❌ **Превышено количество попыток**\n\n"
                    "Слишком много неудачных попыток входа.\n"
                    "Попробуйте снова через некоторое время."
                )
                logger.warning(f"Login failed - max attempts reached: telegram_id={telegram_id}")
            else:
                # Повторный запрос пароля
                await message.reply_text(
                    f"❌ **Неверный пароль**\n\n"
                    f"Попытка {attempts} из 3. Попробуйте еще раз:"
                )
                logger.warning(f"Login failed - wrong password: telegram_id={telegram_id}, attempt={attempts}")
    # === КОНЕЦ AUTH LOGIN FLOW ===

    # === AUTH: Регистрация команды /change_password (ИЗМЕНЕНИЕ 4) ===
    @app.on_message(filters.command("change_password") & auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def cmd_change_password(client: Client, message: Message):
        """Команда смены пароля (доступна всем авторизованным)."""
        c_id = message.chat.id
        await handle_change_password_start(c_id, client)
    # === КОНЕЦ AUTH ===

    # === AUTH: Применение auth_filter к текстовым сообщениям (ИЗМЕНЕНИЕ 3) ===
    @app.on_message(filters.text & ~filters.command("start") & auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def handle_auth_text(client: Client, message: Message):
        """
        Обрабатываем ввод пользователя при авторизации.
        Если пользователь ещё не авторизован — ждём пароль.
        Если авторизован, передаём управление другому хендлеру (handle_authorized_text).

        ✅ ОБНОВЛЕНО: Используется auth_filter для автоматической проверки авторизации
        """
        c_id = message.chat.id

        # Auth filter уже проверил авторизацию - просто обрабатываем текст
        await handle_authorized_text(app, user_states, message)

    # === AUTH: Применение auth_filter к аудио сообщениям (ИЗМЕНЕНИЕ 3) ===
    @app.on_message((filters.voice | filters.audio | filter_wav_document) & auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def handle_audio_msg(app: Client, message: Message, tmpdir: str="/root/Vox/VoxPersona/temp_audio", max_size: int=2 * 1024 * 1024 * 1024):
        """
        Приём голосового или аудио-сообщения, до 2 ГБ.
        Транскрибируем → assign_roles → сохраняем в processed_texts для дальнейшего анализа.
        Аудиофайл сохраняется в MinIO, временная директория удаляется.

        ✅ ОБНОВЛЕНО: Используется auth_filter для автоматической проверки авторизации
        """
        c_id = message.chat.id
        global audio_file_name_to_save
        global transcription_text
        st = user_states.get(c_id, {})
        mode = st.get("mode")

        # Проверяем тип mode
        if mode is not None and not isinstance(mode, str):
            logging.error("mode не является строкой")
            mode = None

        # ✅ Проверка авторизации уже выполнена через auth_filter

        file_size = define_audio_file_params(message)

        try:
            check_audio_file_size(file_size, max_size, c_id, app)
        except ValueError as e:
            logging.exception(e)
            return

        os.makedirs(tmpdir, exist_ok=True)

        file_name = extract_audio_filename(message)
        path = os.path.join(tmpdir, file_name)

        msg_ = app.send_message(c_id, "🎙️ Обрабатываю аудио, подождите...")
        st_ev = threading.Event()
        sp_th = threading.Thread(target=run_loading_animation, args=(c_id, msg_.id, st_ev, app))
        sp_th.start()

        try:
            # Скачиваем аудиофайл во временную директорию
            downloaded = app.download_media(message, file_name=path)
            if downloaded is None:
                raise ValueError("Не удалось скачать файл")
            audio_file_name_to_save = os.path.basename(downloaded)

            # Используем новый MinIOManager для загрузки
            metadata = {
                'user_id': str(c_id),
                'upload_timestamp': datetime.now().isoformat(),
                'file_type': 'audio',
                'processing_status': 'uploaded'
            }

            success = minio_manager.upload_audio_file(
                file_path=downloaded,
                object_name=file_name,
                metadata=metadata
            )

            if success:
                logging.info(f"Аудиофайл {file_name} успешно загружен в MinIO.")
            else:
                raise MinIOUploadError(f"Не удалось загрузить {file_name}")

            transcription_text = transcribe_audio_and_save(downloaded, c_id, processed_texts)

            app.edit_message_text(c_id, msg_.id, "✅ Аудио обработано!")
            # Если пользователь выбрал «Интервью» — расставляем роли
            if isinstance(mode, str):
                handle_assign_roles(c_id, app, mode, processed_texts)
            st["step"] = "inputing_fields"
            if message.caption:
                text = message.caption.strip()
                try:
                    if isinstance(mode, str):
                        parsed_data = parse_message_text(text, mode)
                        st["data"] = parsed_data
                        await show_confirmation_menu(c_id, st, app)
                    else:
                        app.send_message(c_id, "Не удалось автоматически спарсить данные, необходимо заполнить вручную поля.\n Пожалуйста, введите номер файла:")
                except Exception as e:
                    app.send_message(c_id, "Не удалось автоматически спарсить данные, необходимо заполнить вручную поля.\n Пожалуйста, введите номер файла:")
                    logging.error(f"Ошибка парсинга данных: {e}")
                return
            else:
                app.send_message(c_id, "Не удалось автоматически спарсить данные, необходимо заполнить вручную поля.\n Пожалуйста, введите номер файла:")

        except (MinIOError, MinIOConnectionError, MinIOUploadError) as e:
            logging.error(f"❌ Ошибка MinIO: {e}")
            app.edit_message_text(c_id, msg_.id, "❌ Ошибка загрузки в хранилище")
            send_main_menu(c_id, app)
            return

        except S3Error as e:
            logging.error(f"❌ Ошибка: Не удалось загрузить файл в MinIO.: {e}")
            app.edit_message_text(c_id, msg_.id, "❌ Ошибка обработки аудио")
            send_main_menu(c_id, app)
            return

        except OpenAIPermissionError:
            logging.exception("🚫 Ошибка: Whisper недоступен (ключ/регион).")
            # app.edit_message_text(c_id, msg_.id, "🚫 Ошибка: Whisper недоступен (ключ/регион).")
            app.edit_message_text(c_id, msg_.id, "❌ Ошибка обработки аудио")
            send_main_menu(c_id, app)
        except Exception as e:
            logging.exception(f"❌Ошибка обработки аудио: {e}")
            # app.edit_message_text(c_id, msg_.id, f"❌ Ошибка: {e}")
            app.edit_message_text(c_id, msg_.id, "❌ Ошибка обработки аудио")
            send_main_menu(c_id, app)
        finally:
            # Останавливаем спиннер
            st_ev.set()
            sp_th.join()

            # Проверяем, что downloaded был создан в try блоке
            downloaded_file = locals().get('downloaded')
            if downloaded_file:
                delete_tmp_params(msg=msg_, tmp_file=downloaded_file, tmp_dir=tmpdir, client_id=c_id, app=app)

    # === AUTH: Применение auth_filter к документам (ИЗМЕНЕНИЕ 3) ===
    @app.on_message(filters.document & auth_filter)  # type: ignore[misc,reportUntypedFunctionDecorator]
    def handle_document_msg(app: Client, message: Message):
        """
        Приём документа. Сохранение в хранилище, если пользователь выбрал "upload||category".

        ✅ ОБНОВЛЕНО: Используется auth_filter для автоматической проверки авторизации
        """
        c_id = message.chat.id

        # ✅ Проверка авторизации уже выполнена через auth_filter

        doc: Document = message.document
        st = user_states.get(c_id, {})
        if "upload_category" in st:
            cat = st["upload_category"]
            if isinstance(cat, str):
                fold = STORAGE_DIRS.get(cat, "")
            else:
                logging.error("upload_category не является строкой")
                return
            if not fold:
                # app.send_message(c_id, "Ошибка: неизвестная категория.")
                logging.error("Ошибка: неизвестная категория.")
                return

            current_time = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
            orig_name = doc.file_name or f"file_{current_time}"
            sf = safe_filename(orig_name)
            path_ = os.path.join(fold, sf)

            try:
                app.download_media(message, file_name=path_)
                # app.send_message(c_id, f"✅ Файл '{orig_name}' сохранён в '{cat}'.")
                logging.info(f"✅ Файл '{orig_name}' сохранён в '{cat}'.")
            except Exception as e:
                logging.exception(f"❌ Ошибка сохранения документа: {e}")
                # app.send_message(c_id, f"❌ Ошибка сохранения: {e}")

            user_states.pop(c_id, None)
        else:
            app.send_message(c_id, "Сначала выберите действие «Загрузить файл» в меню.")

        send_main_menu(c_id, app)

    @app.on_callback_query()  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def callback_query_handler(client: Client, callback: CallbackQuery):
        c_id = callback.message.chat.id
        data = callback.data
        try:
            await callback.answer()
        except:
            pass

        # ============ MENU CRAWLER PROTECTION ============
        # Защита от опасных действий для тестового пользователя
        TEST_USER_ID = int(os.getenv('TEST_USER_ID', 0))

        if TEST_USER_ID and callback.from_user.id == TEST_USER_ID:
            # Загрузка конфигурации crawler
            config_path = Path(__file__).parent.parent / "menu_crawler" / "config" / "crawler_config.json"

            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    crawler_config = json.load(f)
                    safe_navigation = crawler_config.get('safe_navigation', [])
                    forbidden_actions = crawler_config.get('forbidden_actions', [])
            except FileNotFoundError:
                # Fallback конфигурация если файл не найден
                safe_navigation = ['menu_main', 'menu_chats', 'menu_system', 'menu_help', 'menu_access', 'access_list']
                forbidden_actions = ['delete_', 'confirm_delete', 'upload_', 'new_chat', 'report_', 'edit_', 'access_create', 'access_revoke']

            callback_data = callback.data

            # Приоритет 1: Проверка whitelist (разрешенные безопасные действия)
            is_safe = False
            for safe_pattern in safe_navigation:
                if callback_data.startswith(safe_pattern) or callback_data == safe_pattern:
                    is_safe = True
                    break

            # Приоритет 2: Проверка blacklist (запрещенные опасные действия)
            is_forbidden = False
            for forbidden_pattern in forbidden_actions:
                if forbidden_pattern in callback_data:
                    is_forbidden = True
                    break

            # Блокировка запрещенных действий
            if is_forbidden and not is_safe:
                await callback.answer(
                    "🚫 Действие заблокировано для тестового пользователя",
                    show_alert=True
                )
                logger.warning(f"Blocked TEST_USER action: {callback_data}")

                # Отправить JSON ответ для crawler (для детектирования блокировки)
                await callback.message.answer(
                    f"🤖 CRAWLER_BLOCKED: {callback_data}",
                    parse_mode=None
                )
                return  # Прерываем выполнение
        # ============ END MENU CRAWLER PROTECTION ============

        try:
            # === МУЛЬТИЧАТЫ: Обработчики callback ===
            if data == "new_chat":
                await handle_new_chat(c_id, app)
                return

            elif data.startswith("chat_actions||"):
                conversation_id = data.split("||")[1]
                await handle_chat_actions(c_id, conversation_id, app)
                return

            elif data.startswith("switch_chat||"):
                conversation_id = data.split("||")[1]
                await handle_switch_chat_request(c_id, conversation_id, app, callback)
                return

            elif data.startswith("confirm_switch||"):
                conversation_id = data.split("||")[1]
                await handle_switch_chat_confirm(c_id, conversation_id, app)
                return

            elif data.startswith("rename_chat||"):
                conversation_id = data.split("||")[1]
                await handle_rename_chat_request(c_id, conversation_id, app)
                return

            elif data.startswith("delete_chat||"):
                conversation_id = data.split("||")[1]
                await handle_delete_chat_request(c_id, conversation_id, app)
                return

            elif data.startswith("confirm_delete||"):
                conversation_id = data.split("||")[1]
                username = await get_username_from_chat(c_id, app)
                await handle_delete_chat_confirm(c_id, conversation_id, username, app)
                return
            # === КОНЕЦ МУЛЬТИЧАТЫ ===


            # Главное меню
            if data == "menu_main":
                await handle_main_menu(c_id, app)
            elif data == "menu_dialog":
                await handle_menu_dialog(c_id, app)
            elif data == "menu_help":
                await handle_help_menu(c_id, app)
            elif data == "menu_system":
                await handle_menu_system(c_id, app)
            elif data == "menu_chats":
                await handle_menu_chats(c_id, app)
            elif data == "menu_storage":
                await handle_menu_storage(c_id, app)

            # === AUTH: Callback роутинг для меню управления доступом (ИЗМЕНЕНИЕ 2) ===
            elif data == "menu_access":
                await handle_access_menu(c_id, app)

            # Управление пользователями
            elif data == "access_users_menu":
                await handle_users_menu(c_id, app)

            elif data == "access_list_users":
                await handle_list_users(c_id, 1, app)

            elif data.startswith("access_list_users||page||"):
                page = int(data.split("||")[2])
                await handle_users_pagination(c_id, page, app)

            elif data.startswith("access_user_details||"):
                user_id = data.split("||")[1]
                await handle_user_details(c_id, user_id, app)

            elif data.startswith("access_edit_user||"):
                user_id = data.split("||")[1]
                await handle_edit_user(c_id, user_id, app)

            elif data.startswith("access_change_role||"):
                user_id = data.split("||")[1]
                await handle_change_role(c_id, user_id, app)

            elif data.startswith("access_set_role||"):
                parts = data.split("||")
                await handle_confirm_role_change(c_id, parts[1], parts[2], app)

            elif data.startswith("access_reset_password||"):
                user_id = data.split("||")[1]
                await handle_reset_password(c_id, user_id, app)

            elif data.startswith("access_confirm_reset||"):
                user_id = data.split("||")[1]
                await handle_confirm_reset_password(c_id, user_id, app)

            elif data.startswith("access_toggle_block||"):
                user_id = data.split("||")[1]
                await handle_toggle_block_user(c_id, user_id, app)

            elif data.startswith("access_confirm_block||"):
                parts = data.split("||")
                await handle_confirm_block(c_id, parts[1], app)

            elif data.startswith("access_delete_user||"):
                user_id = data.split("||")[1]
                await handle_delete_user(c_id, user_id, app)

            elif data.startswith("access_confirm_delete||"):
                user_id = data.split("||")[1]
                await handle_confirm_delete(c_id, user_id, app)

            elif data.startswith("access_filter||"):
                role = data.split("||")[1]
                await handle_filter_apply(c_id, role, app)

            elif data == "access_filter_reset":
                await handle_filter_reset(c_id, app)

            elif data == "access_search_user":
                await handle_search_user(c_id, app)

            elif data == "access_filter_roles":
                await handle_filter_users_by_role(c_id, app)

            # Приглашения
            elif data == "access_invitations_menu":
                await handle_invitations_menu(c_id, app)

            elif data.startswith("access_create_invite||"):
                role = data.split("||")[1]  # admin или user
                await handle_create_invitation(c_id, role, app)

            elif data.startswith("access_confirm_invite||"):
                role = data.split("||")[1]
                await handle_confirm_create_invite(c_id, role, app)

            elif data == "access_list_invites":
                await handle_list_invitations(c_id, 1, app)

            elif data.startswith("access_list_invites||page||"):
                page = int(data.split("||")[2])
                await handle_invitations_pagination(c_id, page, app)

            elif data.startswith("access_invite_details||"):
                invite_code = data.split("||")[1]
                await handle_invitation_details(c_id, invite_code, app)

            elif data.startswith("access_revoke_invite||"):
                invite_code = data.split("||")[1]
                await handle_revoke_invitation(c_id, invite_code, app)

            elif data.startswith("access_confirm_revoke||"):
                invite_code = data.split("||")[1]
                await handle_confirm_revoke(c_id, invite_code, app)

            # Безопасность
            elif data == "access_security_menu":
                await handle_security_menu(c_id, app)

            elif data == "access_audit_log":
                await handle_audit_log(c_id, 1, app)

            elif data.startswith("access_audit_log||page||"):
                page = int(data.split("||")[2])
                await handle_audit_log(c_id, page, app)
            # === КОНЕЦ AUTH РОУТИНГА ===

            # Меню чатов
            elif data == "show_stats":
                await handle_show_stats(c_id, app)
            elif data == "show_my_reports":
                await handle_show_my_reports(c_id, app)
            # Просмотр файлов
            elif data.startswith("view||"):
                await handle_view_files(c_id, data, app)

            elif data.startswith("select||"):
                await handle_file_selection(c_id, data, app)

            elif data.startswith("delete||"):
                await handle_file_deletion(c_id, data, app)

            elif data.startswith("upload||"):
                await file_upload_handler(c_id, data, app)

            elif data == "mode_fast":
                await handle_mode_fast(callback, app)
                return

            elif data == "mode_deep":
                await handle_mode_deep(callback, app)
                return

            # Выбор сценария
            elif data in ["mode_interview", "mode_design"]:
                await handle_mode_selection(c_id, data, app)

            # Подтверждение данных
            elif data == "confirm_data":
                handle_confirm_data(c_id, app)
            elif data == "edit_data":
                current_state = user_states.get(c_id, {})
                await show_edit_menu(c_id, current_state, app)

            elif data == "back_to_confirm":
                await handle_back_to_confirm(c_id, app)

            elif data.startswith("edit_"):
                # Обрабатываем выбор поля для редактирования
                field = data.split("edit_")[1]
                await handle_edit_field(c_id, field, app)

            #Отчеты
            elif data in REPORT_MAPPING.keys():
                await handle_report(c_id, data, app)

            # # --- Обработка выбора здания:
            elif data.startswith("choose_building||"):
                await handle_choose_building(c_id, data, app)

            # === МОИ ОТЧЕТЫ V2: Callback обработка ===
            # View workflow
            elif data == "report_view":
                await handle_report_view_request(c_id, app)
                return

            # Rename workflow
            elif data == "report_rename":
                await handle_report_rename_request(c_id, app)
                return

            # Delete workflow
            elif data == "report_delete":
                await handle_report_delete_request(c_id, app)
                return

            elif data.startswith("report_delete_confirm||"):
                # Извлекаем index из callback (report_delete_confirm||5)
                # Но нужно просто вызвать handler - index уже сохранен в FSM
                await handle_report_delete_confirm(c_id, app)
                return
            # === КОНЕЦ МОИ ОТЧЕТЫ V2 ===

            # Обработка отчетов (старая система)
            elif data.startswith("send_report||") or data == "show_all_reports":
                await handle_report_callback(callback, app)

            # Ручная отправка истории
            elif data == "send_history_manual":
                # Получаем conversation_id из состояния пользователя
                st = user_states.get(c_id, {})
                conversation_id = st.get("conversation_id")

                if not conversation_id:
                    # Fallback: берем активный чат
                    conversation_id = conversation_manager.get_active_conversation_id(c_id)

                if conversation_id:
                    # Отправляем системное сообщение
                    await track_and_send(
                        chat_id=c_id,
                        app=app,
                        text="⏳ Экспортирую историю...",
                        message_type="status_message"
                    )

                    # Отправляем историю БЕЗ throttling
                    await send_history_on_demand(c_id, conversation_id, app)
                else:
                    await app.send_message(c_id, "❌ Нет активного чата.")

                return


        except ValueError as ve:
            logging.exception(ve)
            return

        except Exception as e:
            logging.exception(f"Ошибка в callback_query_handler: {e}")

    # ============ TEST CALLBACK HANDLER FOR MENU CRAWLER ============
    @app.on_message(filters.command("test_callback"))  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def test_callback_handler(client: Client, message: Message):
        """
        Специальный обработчик для Menu Crawler.
        Эмулирует нажатие callback кнопки без реального CallbackQuery.

        БЕЗОПАСНОСТЬ: Доступен ТОЛЬКО для TEST_USER_ID.

        Использование:
            /test_callback menu_system
            /test_callback show_stats
        """
        TEST_USER_ID = int(os.getenv('TEST_USER_ID', 0))

        # Защита: только для TEST_USER_ID
        if not TEST_USER_ID or message.from_user.id != TEST_USER_ID:
            await message.reply("🚫 Эта команда доступна только для тестирования")
            return

        # Извлечь callback_data из команды
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("⚠️ Использование: /test_callback <callback_data>")
            return

        callback_data = parts[1].strip()

        # Создать mock CallbackQuery
        from types import SimpleNamespace

        # Получить последнее сообщение от бота с клавиатурой
        bot_message = None
        async for msg in client.get_chat_history(message.chat.id, limit=5):
            if msg.reply_markup and msg.from_user and msg.from_user.is_bot:
                bot_message = msg
                break

        if not bot_message:
            await message.reply("⚠️ Не найдено сообщение от бота с клавиатурой")
            return

        # Mock CallbackQuery
        mock_callback = SimpleNamespace(
            id=f"test_{callback_data}_{message.id}",
            from_user=message.from_user,
            message=bot_message,
            chat_instance="test_crawler",
            data=callback_data,
            answer=lambda text="", show_alert=False: asyncio.create_task(
                message.reply(f"🤖 {text}" if text else "🤖 OK")
            )
        )

        try:
            # Вызвать основной обработчик
            await callback_query_handler(client, mock_callback)
            await message.reply(f"✅ Test callback: {callback_data}")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            logging.exception(f"test_callback error: {e}")
    # ============ END TEST CALLBACK HANDLER ============
