from datetime import datetime
from datetime import datetime
import os
import threading
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, Document
from minio.error import S3Error

from src.minio_manager import get_minio_manager, MinIOError, MinIOConnectionError, MinIOUploadError

from config import (
    processed_texts,
    user_states,
    authorized_users,
    STORAGE_DIRS
)
from utils import run_loading_animation, openai_audio_filter
from validators import validate_date_format, check_audio_file_size, check_state, check_file_detection, check_valid_data, check_authorized, validate_building_type
from parser import parse_message_text, parse_building_type, parse_zone, parse_file_number, parse_place_name, parse_city, parse_name

from storage import delete_tmp_params, safe_filename, find_real_filename
from datamodels import mapping_building_names, REPORT_MAPPING, mapping_scenario_names

from markups import (
    help_menu_markup, 
    storage_menu_markup,
    interview_or_design_menu,
    interview_menu_markup,
    design_menu_markup,
    building_type_menu_markup,
    make_dialog_markup
)

from menus import (
    send_main_menu, 
    files_menu_markup,
    register_menu_message,
    clear_active_menus,
    show_confirmation_menu,
    show_edit_menu
)
from storage import process_stored_file

from analysis import (
    assign_roles
)

from run_analysis import run_analysis_with_spinner, run_dialog_mode

from audio_utils import extract_audio_filename, define_audio_file_params, transcribe_audio_and_save
from auth_utils import handle_unauthorized_user

from openai import PermissionDeniedError as OpenAIPermissionError

# Initialize MinIO manager
minio_manager = get_minio_manager()

filter_wav_document = filters.create(openai_audio_filter)

audio_file_name_to_save = ""
transcription_text = ""

rags = {}
rags_lock = asyncio.Lock()


async def set_rags(new_rags: dict) -> None:
    """Allow external modules to update loaded RAGs."""
    global rags
    async with rags_lock:
        rags = new_rags

def ask_client(data: dict, text: str, state: dict, chat_id: int, app: Client):
    data["client"] = parse_name(text)
    # Переходим к шагу подтверждения
    state["step"] = "confirm_data"
    show_confirmation_menu(chat_id, state, app)

def ask_employee(data: dict, text: str, state: dict, chat_id: int, app: Client):
    data["employee"] = parse_name(text)
    state["step"] = "ask_place_name"
    app.send_message(chat_id, "Введите название заведения:")

def ask_building_type(data: dict, text: str, state: dict, chat_id: int, app: Client):
    data["building_type"] = parse_building_type(text)
    state["step"] = "ask_zone"
    app.send_message(chat_id, "Введите зону (если она есть) или поставьте -:")

def ask_zone(data: dict, text: str, mode: str, state: dict, chat_id: int, app: Client):
    data['zone_name'] = parse_zone(text)
    if mode == "interview":
        # Для интервью сейчас не запрашиваем город — сразу завершаем сбор
        state["step"] = "ask_client"
        app.send_message(chat_id, "Введите ФИО клиента:")
    else:
        # Если это дизайн — надо спросить город
        state["step"] = "ask_city"
        app.send_message(chat_id, "Введите город:")

def ask_place_name(data: dict, text: str, state: dict, chat_id: int, app: Client):
    data["place_name"] = parse_place_name(text)
    state["step"] = "ask_building_type"
    app.send_message(chat_id, "Введите тип заведения:")

def ask_date(data: dict, text: str, state: dict, chat_id: int, app: Client):
    if not validate_date_format(text):
        app.send_message(chat_id, "❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД (например, 2025-01-01).")
        return
    data["date"] = text
    state["step"] = "ask_employee"
    app.send_message(chat_id, "Введите ФИО сотрудника:")

def ask_city(data: dict, text: str, state: dict, chat_id: int, app: Client):
    data["city"] = parse_city(text)
    # Переходим к шагу подтверждения
    state["step"] = "confirm_data"
    show_confirmation_menu(chat_id, state, app)

def ask_audio_number(data: dict, text: str, state: dict, chat_id: int, app: Client):
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

def handle_edit_field(chat_id: int, field: str, app: Client):
    """
    Ставит шаг (step) на редактирование нужного поля, затем просит ввести новое значение.
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

    app.send_message(chat_id, prompt_text)

def handle_authorized_text(app: Client, user_states: dict[int, dict], message: Message):
    """
    Этот хендлер обрабатывает все текстовые сообщения от авторизованного пользователя,
    в т.ч. логику по шагам (сбор данных для интервью/дизайна).
    """
    c_id = message.chat.id
    text_ = message.text.strip()

    # Проверяем, есть ли у пользователя активное состояние
    st = user_states.get(c_id)

    if not check_state(st, c_id, app):
        logging.info("Нет состояния. Пользователь что-то пишет без контекста")
        send_main_menu(c_id, app)
        return
    
    if st.get("step") == "dialog_mode":
        deep = st.get("deep_search", False)
        msg = app.send_message(c_id, "⏳ Думаю...")
        st_ev = threading.Event()
        sp_th = threading.Thread(target=run_loading_animation, args=(c_id, msg.id, st_ev, app))
        sp_th.start()
        try:
            if not rags:
                app.send_message(c_id, "🔄 База знаний ещё загружается, попробуйте позже.")
            else:
                run_dialog_mode(chat_id=c_id, app=app, text=text_, deep_search=deep, rags=rags)
            return
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            app.send_message(c_id, "Произошла ошибка")
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
        
        show_confirmation_menu(c_id, st, app)
        return

    mode = st.get("mode")        # 'interview' или 'design'
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
        ask_city(data_, text_, st, c_id, app)
        return
    
    elif step == "ask_building_type":
        ask_building_type(data_, text_, st, c_id, app)
        return
    
    elif step == "ask_zone":
        ask_zone(data_, text_, mode, st, c_id, app)

    elif step == "ask_client":
        ask_client(data_, text_, st, c_id, app)
    else:
        # На всякий случай, если что-то пошло не так
        user_states.pop(c_id, None)
        app.send_message(c_id, "Неизвестное состояние. Начните заново /start.")
        send_main_menu(c_id, app)

# =========================================================================
#  Callback-queries
# =========================================================================

def handle_help_menu(chat_id: int, app: Client):
    clear_active_menus(chat_id, app)
    kb, txt = help_menu_markup()
    mm = app.send_message(chat_id, txt, reply_markup=kb)
    register_menu_message(chat_id, mm.id)

def handle_menu_storage(chat_id: int, app: Client):
    clear_active_menus(chat_id, app)
    mm = app.send_message(chat_id, "Что анализируем?:", reply_markup=interview_or_design_menu())
    register_menu_message(chat_id, mm.id)

def handle_main_menu(chat_id: int, app: Client):
    send_main_menu(chat_id, app)

def handle_view_files(chat_id: int, data, app: Client):
    parts = data.split("||")
    if len(parts) < 2: 
        return
    cat = parts[1]
    clear_active_menus(chat_id, app)
    mm = app.send_message(chat_id, f"Файлы в '{cat}':", reply_markup=files_menu_markup(cat))
    register_menu_message(chat_id, mm.id)

def process_selected_file(chat_id: int, category: str, filename: str, app: Client):
    msg = app.send_message(chat_id, "⏳ Обрабатываю файл...")
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
        app.delete_messages(chat_id, msg.id)
    
    # app.send_message(chat_id, "Что анализируем дальше?", reply_markup=interview_or_design_menu())
    # send_main_menu(chat_id, app)


def preprocess_parts(data: str, treshold: int=3) -> list[str]:
    parts = data.split("||")
    if len(parts) < treshold:
        logging.error("Неверный формат данных для choose_building")
        return
    return parts

def handle_file_selection(chat_id: int, data: str, app: Client):
    parts = preprocess_parts(data)
    category, file_name = parts[1], parts[2]
    folder = STORAGE_DIRS.get(category, "")
    real_name = find_real_filename(folder, file_name)
    if not check_file_detection(real_name, chat_id, app):
        logging.error(f"Файл {real_name} не найден")
        raise ValueError(f"Файл {real_name} не найден")
    process_selected_file(chat_id, category, real_name, app)

def handle_file_deletion(chat_id: int, data: str, app: Client):
    parts = preprocess_parts(data)
    category, file_name = parts[1], parts[2]
    folder = STORAGE_DIRS.get(category, "")
    real_name = find_real_filename(folder, file_name)
    if not check_file_detection(real_name, chat_id, app):
        logging.error(f"Файл {real_name} не найден")
        raise ValueError(f"Файл {real_name} не найден")

    try:
        os.remove(os.path.join(folder, real_name))
        # app.send_message(chat_id, "Файл удалён.")
        logging.info("Файл удалён.")
    except Exception as e:
        # app.send_message(chat_id, f"Ошибка удаления: {e}")
        logging.error(f"Ошибка удаления: {e}")

    mm = app.send_message(chat_id, f"Список файлов в '{category}':", reply_markup=files_menu_markup(category))
    register_menu_message(chat_id, mm.id)

def file_upload_handler(chat_id: int, data: str, app: Client):
    parts = preprocess_parts(data, 2)
    category = parts[1]
    # user_states[chat_id] = {"upload_category": category}
    user_states.setdefault(chat_id, {})["upload_category"] = category
    app.send_message(chat_id, f"Отправьте документ для сохранения в '{category}'.")

# --------------------------------------------------------------------------------------
#                        Подтверждение и сохранение (Callback)
# --------------------------------------------------------------------------------------

def handle_confirm_data(chat_id: int, app: Client):
    st = user_states.get(chat_id)
    if not st:
        return
    st["data_collected"] = True
    st["step"] = None

    mode = st.get("mode", "—")
    d = st.get("data", {})
    employee = d.get("employee", "—")
    place = d.get("place_name", "—")
    date_ = d.get("date", "—")
    city = d.get("city", "")
    zone_name = d.get("zone_name", "")
    number_audio = d.get("audio_number", "—")
    building_type = d.get("building_type", "—")
    client = d.get("client", "")

    msg = (
        f"**Данные сохранены**:\n\n"
        f"**Сценарий**: {mapping_scenario_names[mode]}\n"
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

    msg += "Теперь выберите отчёт."

    app.send_message(chat_id, msg)
    if mode == "interview":
        app.send_message(chat_id, "Доступные отчёты:", reply_markup=interview_menu_markup())
    elif mode == "design":
        app.send_message(chat_id, "Доступные отчёты:", reply_markup=design_menu_markup())

def handle_back_to_confirm(chat_id: int, app: Client):
    st = user_states.get(chat_id)
    if not st:
        return
    st["step"] = "confirm_data"
    show_confirmation_menu(chat_id, st, app)

def handle_mode_selection(chat_id: int, mode: str, app: Client):
    """
    Выбор сценария «Интервью» или «Дизайн»
    """
        
    clear_active_menus(chat_id, app)
    user_states[chat_id] = {
        "mode": "interview" if mode == "mode_interview" else "design",
        "data": {}
    }
    st = user_states[chat_id]
    mm = app.send_message(chat_id, "📦 Меню хранилища:", reply_markup=storage_menu_markup())
    register_menu_message(chat_id, mm.id)
    
def preprocess_report_without_buildings(chat_id: int, data: str, app: Client, building_name: str = "non-building"):
    validate_datas = []
    st = user_states.get(chat_id, {})
    mode = st.get("mode")
    data_ = st.get("data", {})
    data_["audio_file_name"] = audio_file_name_to_save

    validate_datas.append(mode)
    validate_datas.append(data_)

    check_valid_data(validate_datas, chat_id, app, "Не хватает данных для формирования отчёта. Начните заново.")
    
    data_["type_of_location"] = building_name

    try:
        run_analysis_with_spinner(
            chat_id=chat_id,
            processed_texts=processed_texts,
            app=app,
            callback_data=data,
            data=data_,
            transcription_text=transcription_text
        )
    except Exception as e:
        logging.error(f"Ошибка при обработке отчёта {data}: {e}")
        # app.send_message(chat_id, f"❌ Произошла ошибка при обработке запроса: {str(e)}")

def preprocess_report_with_buildings(chat_id: int, data: str, app: Client):
    st = user_states.setdefault(chat_id, {})
    st["pending_report"] = data
    clear_active_menus(chat_id, app)
    mm = app.send_message(chat_id, "Выберите тип заведения:", reply_markup=building_type_menu_markup())
    register_menu_message(chat_id, mm.id)

def handle_report(chat_id: int, callback_data : str, app: Client):
    if callback_data  in [
        "report_int_methodology",
        "report_int_links",
        "report_design_audit_methodology"
    ]:
        preprocess_report_without_buildings(chat_id, callback_data , app)

    elif callback_data  in [
        "report_int_general", 
        "report_int_specific",
        "report_design_compliance",
        "report_design_structured"
    ]:

        state = user_states.get(chat_id, {})
        data = state.get("data", {})
        building_type = data.get('building_type', "")
        valid_building_type = validate_building_type(building_type)
        if valid_building_type is None:
            preprocess_report_with_buildings(chat_id, callback_data , app)
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

def handle_choose_building(chat_id: int, data: str, app: Client):
    validate_datas = []
    parts = preprocess_parts(data, 2) # 'hotel' / 'restaurant' / 'spa'
    short_name = parts[1]
    st = user_states.get(chat_id, {})
    pending_report = st.get("pending_report", None)
    mode = st.get("mode")
    data_ = st.get("data", {})
    data_["audio_file_name"] = audio_file_name_to_save

    validate_datas.append(mode)
    validate_datas.append(pending_report)
    validate_datas.append(data_)

    check_valid_data(validate_datas, chat_id, app, "Неизвестно, какой отчёт вы хотели. Начните заново.")

    # Преобразуем short_name из callback в нормальное название
    building_name = mapping_building_names.get(short_name, short_name)

    data_["type_of_location"] = building_name


    #Запускаем анализ
    run_analysis_with_spinner(
        chat_id=chat_id,
        processed_texts=processed_texts,
        app=app,
        callback_data=pending_report,
        data=data_,
        transcription_text=transcription_text
    )

    st["pending_report"] = None

def handle_toggle_deep(callback: CallbackQuery, app: Client):
    chat_id = callback.message.chat.id
    st = user_states.get(chat_id, {})
    st["deep_search"] = not st.get("deep_search", False)
    callback.message.edit_reply_markup(make_dialog_markup(st["deep_search"]))

def handle_menu_dialog(chat_id: int, app: Client):
    # Сначала очищаем предыдущие меню
    clear_active_menus(chat_id, app)

    user_states[chat_id] = {"step": "dialog_mode", "deep_search": False}
    app.send_message(
        chat_id,
        "Какую информацию вы хотели бы получить?",
        reply_markup=make_dialog_markup(False)
    )

def register_handlers(app: Client):
    """
    Регистрируем все хендлеры Pyrogram.
    """

    @app.on_message(filters.command("start"))
    def cmd_start(app: Client, message: Message):
        c_id = message.chat.id
        if c_id not in authorized_users:
            app.send_message(c_id, "Вы не авторизованы. Введите пароль:")
        else:
            send_main_menu(c_id, app)

    @app.on_message(filters.text & ~filters.command("start"))
    def handle_auth_text(client: Client, message: Message):
        """
        Обрабатываем ввод пользователя при авторизации.
        Если пользователь ещё не авторизован — ждём пароль.
        Если авторизован, передаём управление другому хендлеру (handle_authorized_text).
        """
        c_id = message.chat.id

        # Пользователь уже авторизован?
        if c_id in authorized_users:
            handle_authorized_text(app, user_states, message)
            return
        
        # Если пользователь ещё не авторизован — проверяем пароль
        handle_unauthorized_user(authorized_users, message, app)  


    @app.on_message(filters.voice | filters.audio | filter_wav_document)
    def handle_audio_msg(app: Client, message: Message, tmpdir: str="/root/Vox/VoxPersona/temp_audio", max_size: int=2 * 1024 * 1024 * 1024):
        """
        Приём голосового или аудио-сообщения, до 2 ГБ.
        Транскрибируем → assign_roles → сохраняем в processed_texts для дальнейшего анализа.
        Аудиофайл сохраняется в MinIO, временная директория удаляется.
        """
        c_id = message.chat.id
        global audio_file_name_to_save
        global transcription_text
        st = user_states.get(c_id, {})
        mode =  st.get("mode")

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
            handle_assign_roles(c_id, app, mode, processed_texts)
            st["step"] = "inputing_fields"
            if message.caption:
                text = message.caption.strip()
                try:
                    parsed_data = parse_message_text(text, mode)
                    st["data"] = parsed_data
                    show_confirmation_menu(c_id, st, app)
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

            delete_tmp_params(msg=msg_, tmp_file=downloaded, tmp_dir=tmpdir, client_id=c_id, app=app)

    @app.on_message(filters.document)
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
            fold = STORAGE_DIRS.get(cat, "")
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
    
    @app.on_callback_query()
    def callback_query_handler(client: Client, callback: CallbackQuery):
        c_id = callback.message.chat.id
        data = callback.data
        try:
            callback.answer()
        except:
            pass

        try:
            # Главное меню
            if data == "menu_main":
                handle_main_menu(c_id, app)
            elif data == "menu_dialog":
                handle_menu_dialog(c_id, app)
            elif data == "menu_help":
                handle_help_menu(c_id, app)
            elif data == "menu_storage":
                handle_menu_storage(c_id, app)
            # Просмотр файлов
            elif data.startswith("view||"):
                handle_view_files(c_id, data, app)

            elif data.startswith("select||"):
                handle_file_selection(c_id, data, app)

            elif data.startswith("delete||"):
                handle_file_deletion(c_id, data, app)

            elif data.startswith("upload||"):
                file_upload_handler(c_id, data, app)

            elif data == "toggle_deep":
                handle_toggle_deep(callback, app)
                return

            # Выбор сценария
            elif data in ["mode_interview", "mode_design"]:
                handle_mode_selection(c_id, data, app)

            # Подтверждение данных
            elif data == "confirm_data":
                handle_confirm_data(c_id, app)
            elif data == "edit_data":
                show_edit_menu(c_id, user_states.get(c_id, {}), app)

            elif data == "back_to_confirm":
                handle_back_to_confirm(c_id, app)

            elif data.startswith("edit_"):
                # Обрабатываем выбор поля для редактирования
                field = data.split("edit_")[1]
                handle_edit_field(c_id, field, app)

            #Отчеты
            elif data in REPORT_MAPPING.keys():
                handle_report(c_id, data, app)

            # # --- Обработка выбора здания:
            elif data.startswith("choose_building||"):
                handle_choose_building(c_id, data, app)
        
        except ValueError as ve:
            logging.exception(ve)
            return

        except Exception as e:
            logging.exception(f"Ошибка в callback_query_handler: {e}")

