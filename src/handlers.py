from typing import Any, cast
from datetime import datetime, date
import os
import re
import threading
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, Document, InlineKeyboardMarkup, InlineKeyboardButton
from minio.error import S3Error

from src.minio_manager import get_minio_manager, MinIOError, MinIOConnectionError, MinIOUploadError

from config import (
    processed_texts,
    user_states,
    authorized_users,
    STORAGE_DIRS
)
from utils import run_loading_animation, openai_audio_filter, get_username_from_chat
from constants import COMMAND_HISTORY, COMMAND_STATS, COMMAND_REPORTS
from conversation_manager import conversation_manager
from md_storage import md_storage_manager
from validators import validate_date_format, check_audio_file_size, check_state, check_file_detection, check_valid_data, check_authorized, validate_building_type
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

from run_analysis import run_analysis_with_spinner, run_dialog_mode

from audio_utils import extract_audio_filename, define_audio_file_params, transcribe_audio_and_save
from auth_utils import handle_unauthorized_user

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
from file_sender import auto_send_history_file, auto_send_reports_file
# === КОНЕЦ АВТООТПРАВКА ФАЙЛОВ ===

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


def handle_report_callback(callback_query: CallbackQuery, app: Client) -> None:
    """Обработчик callback для отправки отчетов."""
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    try:
        if data.startswith("send_report||"):
            relative_path = data.split("send_report||", 1)[1]

            # Получаем путь к файлу
            file_path = md_storage_manager.get_report_file_path(relative_path)

            if file_path and file_path.exists():
                app.send_document(
                    chat_id,
                    str(file_path),
                    caption="📄 Ваш отчет"
                )
                app.answer_callback_query(callback_query.id, "✅ Отчет отправлен")
            else:
                app.answer_callback_query(
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

            app.edit_message_text(
                chat_id,
                callback_query.message.id,
                reports_text,
                reply_markup=back_keyboard
            )
            app.answer_callback_query(callback_query.id)

    except Exception as e:
        logging.error(f"Error handling report callback: {e}")
        app.answer_callback_query(
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
    await send_menu(chat_id, app, "⚙️ Системные настройки:", system_menu_markup())

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
    """Показывает список отчетов пользователя"""
    try:
        reports = md_storage_manager.get_user_reports(chat_id, limit=10)

        if not reports:
            # Показываем сообщение об отсутствии отчетов с меню чатов внизу
            await send_menu(
                chat_id=chat_id,
                app=app,
                text="📁 **Ваши отчеты:**\n\nУ вас пока нет сохраненных отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id)
            )
            return

        keyboard = []
        for i, report in enumerate(reports[:5], 1):
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
        logging.error(f"Error showing reports: {e}")
        await send_menu(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при получении отчетов.",
            reply_markup=chats_menu_markup_dynamic(chat_id)
        )

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

    @app.on_message(filters.command("start"))  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def cmd_start(app: Client, message: Message):
        c_id = message.chat.id
        if c_id not in authorized_users:
            await app.send_message(c_id, "Вы не авторизованы. Введите пароль:")
        else:
            # Автоотправка истории и отчетов
            await auto_send_history_file(c_id, app)
            await auto_send_reports_file(c_id, app)

            await send_main_menu(c_id, app)

    @app.on_message(filters.text & ~filters.command("start"))  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def handle_auth_text(client: Client, message: Message):
        """
        Обрабатываем ввод пользователя при авторизации.
        Если пользователь ещё не авторизован — ждём пароль.
        Если авторизован, передаём управление другому хендлеру (handle_authorized_text).
        """
        c_id = message.chat.id

        # Пользователь уже авторизован?
        if c_id in authorized_users:
            await handle_authorized_text(app, user_states, message)
            return

        # Если пользователь ещё не авторизован — проверяем пароль
        await handle_unauthorized_user(authorized_users, message, app)


    @app.on_message(filters.voice | filters.audio | filter_wav_document)  # type: ignore[misc,reportUntypedFunctionDecorator]
    async def handle_audio_msg(app: Client, message: Message, tmpdir: str="/root/Vox/VoxPersona/temp_audio", max_size: int=2 * 1024 * 1024 * 1024):
        """
        Приём голосового или аудио-сообщения, до 2 ГБ.
        Транскрибируем → assign_roles → сохраняем в processed_texts для дальнейшего анализа.
        Аудиофайл сохраняется в MinIO, временная директория удаляется.
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

        try:
            check_authorized(c_id, authorized_users)
        except ValueError as e:
            logging.exception(e)
            app.send_message(c_id, "Вы не авторизованы.")
            return

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

    @app.on_message(filters.document)  # type: ignore[misc,reportUntypedFunctionDecorator]
    def handle_document_msg(app: Client, message: Message):
        """
        Приём документа. Сохранение в хранилище, если пользователь выбрал "upload||category".
        """
        c_id = message.chat.id
        if c_id not in authorized_users:
            return

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

            # Обработка отчетов
            elif data.startswith("send_report||") or data == "show_all_reports":
                handle_report_callback(callback, app)

        except ValueError as ve:
            logging.exception(ve)
            return

        except Exception as e:
            logging.exception(f"Ошибка в callback_query_handler: {e}")

