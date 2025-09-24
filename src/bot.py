import os
import re
import time
import logging
import threading
import warnings
import io
from typing import Callable

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
    Document
)
from dotenv import load_dotenv
# Import Claude API function for analysis
from analysis import send_msg_to_model
from openai import PermissionDeniedError as OpenAIPermissionError
from constants import BUTTON_BACK, CLAUDE_ERROR_MESSAGE

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# ================== Загрузка .env (ключи) ==================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")    # Whisper
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not all([OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("Не все ключи (OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, API_ID, API_HASH) заданы!")

# ================== Глобальные ==================
processed_texts: dict[int, str] = {}
user_states: dict[int, dict[str, str]] = {}
authorized_users = set()  
active_menus: dict[int, list[int]] = {}

STORAGE_DIRS = {
    "audio": "audio_files",
    "text_without_roles": "text_without_roles",
    "text_with_roles": "text_with_roles"
}
for fold in STORAGE_DIRS.values():
    os.makedirs(fold, exist_ok=True)

PROMPTS_DIR = "prompts"

translit_map = {
    'А': 'A','а': 'a','Б': 'B','б': 'b','В': 'V','в': 'v',
    'Г': 'G','г': 'g','Д': 'D','д': 'd','Е': 'E','е': 'e',
    'Ё': 'Yo','ё': 'yo','Ж': 'Zh','ж': 'zh','З': 'Z','з': 'z',
    'И': 'I','и': 'i','Й': 'Y','й': 'y','К': 'K','к': 'k',
    'Л': 'L','л': 'l','М': 'M','м': 'm','Н': 'N','н': 'n',
    'О': 'O','о': 'o','П': 'P','п': 'p','Р': 'R','р': 'r',
    'С': 'S','с': 's','Т': 'T','т': 't','У': 'U','у': 'u',
    'Ф': 'F','ф': 'f','Х': 'Kh','х': 'kh','Ц': 'Ts','ц': 'ts',
    'Ч': 'Ch','ч': 'ch','Ш': 'Sh','ш': 'sh','Щ': 'Sch','щ': 'sch',
    'Ъ': '','ъ': '','Ы': 'Y','ы': 'y','Ь': '','ь': '',
    'Э': 'E','э': 'e','Ю': 'Yu','ю': 'yu','Я': 'Ya','я': 'ya'
}
def safe_filename(name: str) -> str:
    out=[]
    for ch in name:
        if ch in translit_map:
            out.append(translit_map[ch])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    res="".join(out)
    res=re.sub(r"_+", "_", res)
    if len(res)>30:
        return res[:15] + "_" + res[-15:]
    return res

# ========== Pyrogram-клиент =========
app = Client(
    "voxpersona_bot",
    api_id=int(API_ID) if API_ID else 0,
    api_hash=API_HASH or "",
    bot_token=TELEGRAM_BOT_TOKEN
)

# ========== Спиннер-анимация =========
spinner_chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
def run_loading_animation(chat_id: int, msg_id: int, stop_event: threading.Event):
    idx=0
    while not stop_event.is_set():
        sp=spinner_chars[idx % len(spinner_chars)]
        try:
            app.edit_message_text(chat_id, msg_id, f"⏳ Обработка... {sp}")
        except Exception:
            pass
        idx+=1
        time.sleep(0.5)

def clear_active_menus(chat_id: int):
    if chat_id in active_menus:
        for mid in active_menus[chat_id]:
            try:
                app.delete_messages(chat_id, mid)
            except Exception:
                pass
        active_menus[chat_id]=[]

def register_menu_message(chat_id: int, msg_id: int):
    if chat_id not in active_menus:
        active_menus[chat_id]=[]
    active_menus[chat_id].append(msg_id)

# ========== Загрузка промпта из файла =========
def load_prompt(file_name: str)->str:
    p_=os.path.join(PROMPTS_DIR, file_name)
    if not os.path.exists(p_):
        logging.warning(f"Файл промпта {file_name} не найден.")
        return ""
    try:
        with open(p_,"r",encoding="utf-8") as f:
            return f.read()
    except Exception:
        logging.exception(f"Ошибка чтения промпта {file_name}")
        return ""

# ========== Меню (главное, интервью, дизайн) =========
def main_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📁 Хранилище", callback_data="menu_storage"),
            InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
        ]
    ])

def send_main_menu(chat_id: int):
    clear_active_menus(chat_id)
    mm=app.send_message(chat_id,"🏠 Главное меню:", reply_markup=main_menu_markup())
    if mm:
        register_menu_message(chat_id, mm.id)

def storage_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Аудио файлы", callback_data="view||audio")],
        [InlineKeyboardButton("Текст без ролей", callback_data="view||text_without_roles")],
        [InlineKeyboardButton("Текст с ролями", callback_data="view||text_with_roles")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])

def help_menu_markup():
    text_ = (
        "Структура отчётов:\n\n"
        "ИНТЕРВЬЮ:\n"
        "1) Оценка методологии интервью\n"
        "2) Отчёт о связках (качество-принятие)\n"
        "3) Информация об общих факторах\n"
        "4) Информация о факторах в этом заведении\n"
        "ДИЗАЙН:\n"
        "1) Оценка методологии аудита\n"
        "2) Информация о соответствии программе аудита\n"
        "3) Структурированный отчёт аудита\n\n"
        "Макс 2 ГБ, без ffmpeg."
    )
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]])
    return kb, text_

def interview_or_design_menu():
    """Мини-меню (ИНТЕРВЬЮ / ДИЗАЙН), вызываем после транскрибации."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ИНТЕРВЬЮ", callback_data="mode_interview"),
            InlineKeyboardButton("ДИЗАЙН", callback_data="mode_design")
        ]
    ])

def interview_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1) Оценка методологии интервью", callback_data="report_int_methodology")],
        [InlineKeyboardButton("2) Отчет о связках", callback_data="report_int_links")],
        [InlineKeyboardButton("3) Общие факторы", callback_data="report_int_general")],
        [InlineKeyboardButton("4) Факторы в этом заведении", callback_data="report_int_specific")],
        [InlineKeyboardButton("5) Анализ работы сотрудника", callback_data="report_int_employee")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])

def design_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1) Оценка методологии аудита", callback_data="report_design_audit_methodology")],
        [InlineKeyboardButton("2) Соответствие программе аудита", callback_data="report_design_compliance")],
        [InlineKeyboardButton("3) Структурированный отчет аудита", callback_data="report_design_structured")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])

def files_menu_markup(category: str):
    fold=STORAGE_DIRS.get(category,"")
    rows=[]
    try:
        fs=os.listdir(fold)
    except OSError:
        fs=[]
    for f in fs:
        sf=safe_filename(f)
        b_open=InlineKeyboardButton(f, callback_data=f"select||{category}||{sf}")
        b_del=InlineKeyboardButton("❌", callback_data=f"delete||{category}||{sf}")
        rows.append([b_open,b_del])
    rows.append([InlineKeyboardButton("Загрузить файл", callback_data=f"upload||{category}")])
    rows.append([InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)

# ========== Транскрибация (байты) ==========
def transcribe_audio_raw(file_path: str)->str:
    import openai
    old_base=openai.api_base
    old_key=openai.api_key
    openai.api_base="https://api.openai.com/v1"
    openai.api_key=OPENAI_API_KEY
    
    CHUNK_SIZE=24*1024*1024  # 24 MB, чтобы избежать 413

    try:
        size_=os.path.getsize(file_path)
        with open(file_path,"rb") as f:
            data=f.read()
        if size_<=CHUNK_SIZE:
            bio=io.BytesIO(data)
            bio.name="audio_chunk.wav"
            resp=openai.Audio.transcribe("whisper-1", bio, response_format="json")
            return resp["text"]
        else:
            out=[]
            start=0
            while start<len(data):
                chunk=data[start : start+CHUNK_SIZE]
                start+=CHUNK_SIZE
                part=io.BytesIO(chunk)
                part.name="audio_part.wav"
                try:
                    r_=openai.Audio.transcribe("whisper-1", part, response_format="json")
                    out.append(r_["text"])
                except Exception as e:
                    logging.error(f"Ошибка транскрибирования чанка: {e}")
            return " ".join(out).strip()
    finally:
        openai.api_base=old_base
        openai.api_key=old_key

def transcribe_audio(path_: str)->str:
    return transcribe_audio_raw(path_)

# ========== Claude wrapper (migrated from VSEGPT) ==========
def claude_complete(prompt: str, err: str = CLAUDE_ERROR_MESSAGE) -> str:
    """
    Wrapper function to maintain compatibility with existing code while using Claude API.
    """
    messages = [{"role": "user", "content": prompt}]
    return send_msg_to_model(messages=messages, err=err)

# ========== Для ДИЗАЙНА (auto) ==========
def auto_detect_category(text:str)->str:
    lw=text.lower()
    if "ресторан" in lw or "restaurant" in lw:
        return "restaurant"
    elif "центр здоровья" in lw or "health" in lw:
        return "health_center"
    elif "отель" in lw or "hotel" in lw:
        return "hotel"
    return "hotel"

# ========== Расстановка ролей (assign_roles) ==========
def assign_roles(text: str)->str:
    base_=load_prompt("assign_roles.txt")
    if not base_:
        base_="Определи, где [Сотрудник:], где [Клиент:]."
    prompt_=f"{base_}\n\nТекст:\n{text}"
    logging.info(f"[assign_roles] Длина сырого текста: {len(text)} символов.")
    result=claude_complete(prompt_,"Ошибка assign_roles")
    logging.info(f"[assign_roles] Длина результата: {len(result)} символов.")
    return result

# ========== Интервью ==========
def analyze_interview_methodology(text: str)->str:
    base_=load_prompt("interview_methodology.txt")
    if not base_:
        base_="Проанализируй методологию интервью."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,"Ошибка методологии интервью")

def analyze_quality_decision_links(text: str)->str:
    base_=load_prompt("quality_decision_links.txt")
    if not base_:
        base_="Проанализируй связки (качество-принятие)."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,"Ошибка связок")

def analyze_interview_general(text: str)->str:
    base_=load_prompt("interview_general_factors.txt")
    if not base_:
        base_="Общие факторы (интервью)."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,"Ошибка общих факторов (интервью)")

def analyze_interview_specific(text: str)->str:
    base_=load_prompt("interview_specific_factors.txt")
    if not base_:
        base_="Специфические факторы (интервью)."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,"Ошибка специф.факторов (интервью)")

def analyze_employee_performance(text: str)->str:
    base_=load_prompt("interview_employee_performance.txt")
    if not base_:
        base_="Проанализируй работу сотрудника."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,"Ошибка анализа сотрудника")

# ========== ДИЗАЙН ==========
def analyze_design_audit(text: str)->str:
    base_=load_prompt("design_audit_methodology.txt")
    if not base_:
        base_="Оценка методологии аудита дизайна."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,"Ошибка методологии аудита")

def analyze_audit_compliance(text: str)->str:
    cat=auto_detect_category(text)
    if cat=="hotel":
        fn="hotel_audit_compliance.txt"
    elif cat=="restaurant":
        fn="restaurant_audit_compliance.txt"
    else:
        fn="health_center_audit_compliance.txt"
    base_=load_prompt(fn)
    if not base_:
        base_=f"Соответствие аудита ({cat})."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,f"Ошибка соответствия аудита ({cat})")

def analyze_structured_audit(text: str)->str:
    cat=auto_detect_category(text)
    if cat=="hotel":
        fn="structured_hotel_audit.txt"
    elif cat=="restaurant":
        fn="structured_restaurant_audit.txt"
    else:
        fn="structured_health_center_audit.txt"
    base_=load_prompt(fn)
    if not base_:
        base_=f"Структурированный отчет ({cat})."
    p=f"{base_}\n\nТекст:\n{text}"
    return claude_complete(p,f"Ошибка структур.аудита ({cat})")

# ========== process_stored_file (хранилище) ==========
def process_stored_file(category: str, filename: str, chat_id: int)->str|None:
    fold=STORAGE_DIRS.get(category,"")
    path_=os.path.join(fold,filename)
    if not os.path.exists(path_):
        app.send_message(chat_id,f"Файл '{filename}' не найден.")
        return None
    try:
        if category=="audio":
            raw_=transcribe_audio(path_)
            roles_=assign_roles(raw_)
            logging.info(f"[process_stored_file|audio] Сохранён текст длиной {len(roles_)} символов.")
            return roles_
        elif category=="text_without_roles":
            with open(path_,"r",encoding="utf-8") as f:
                text_=f.read()
            logging.info(f"[process_stored_file|text_without_roles] Прочитали текст длиной {len(text_)} символов.")
            assigned_=assign_roles(text_)
            logging.info(f"[process_stored_file|text_without_roles] После assign_roles длина {len(assigned_)} символов.")
            return assigned_
        elif category=="text_with_roles":
            with open(path_,"r",encoding="utf-8") as f:
                final_=f.read()
            logging.info(f"[process_stored_file|text_with_roles] Файл длиной {len(final_)} символов.")
            return final_
        else:
            app.send_message(chat_id,"Неверная категория файла.")
            return None
    except Exception as e:
        logging.error(f"Ошибка process_stored_file: {e}")
        app.send_message(chat_id,f"Ошибка обработки файла: {e}")
        return None

# ========== /start и авторизация ==========
def cmd_start(_: Client, message: Message) -> None:
    """Обработчик команды /start с явной типизацией"""
    c_id=message.chat.id
    if c_id not in authorized_users:
        app.send_message(c_id,"Вы не авторизованы. Введите пароль:")
    else:
        send_main_menu(c_id)

# Регистрируем декорированный обработчик
@app.on_message(filters.command("start"))  # type: ignore[misc]
def _cmd_start_handler(client: Client, message: Message) -> None:  # pyright: ignore[reportUnusedFunction]
    """Декорированная реализация для cmd_start"""
    return cmd_start(client, message)

def handle_auth_text(_: Client, message: Message) -> None:
    """Обработчик авторизации по тексту с явной типизацией"""
    c_id=message.chat.id
    if c_id in authorized_users:
        return
    if message.text.strip()=="1243":
        authorized_users.add(c_id)
        app.send_message(c_id,"✅ Авторизация успешна!")
        send_main_menu(c_id)
    else:
        app.send_message(c_id,"❌ Неверный пароль. Попробуйте снова:")

# Регистрируем декорированный обработчик
@app.on_message(filters.text & ~filters.command("start"))  # type: ignore[misc]
def _handle_auth_text_handler(client: Client, message: Message) -> None:  # pyright: ignore[reportUnusedFunction]
    """Декорированная реализация для handle_auth_text"""
    return handle_auth_text(client, message)

# ========== Приём аудио ==========
def handle_audio_msg(_: Client, message: Message) -> None:
    """Обработчик аудио сообщений с явной типизацией"""
    c_id=message.chat.id
    if c_id not in authorized_users:
        return

    MAX_SIZE=2*1024*1024*1024
    if message.voice:
        f_size=message.voice.file_size
        ext=".ogg"
    else:
        f_size=message.audio.file_size
        ext=".mp3"

    if f_size>MAX_SIZE:
        app.send_message(c_id,f"Файл слишком большой ({f_size/1024/1024:.1f} MB). Макс 2GB.")
        return

    tmpdir="temp_audio"
    os.makedirs(tmpdir,exist_ok=True)
    fn=f"audio_{int(time.time())}{ext}"
    path_=os.path.join(tmpdir,fn)

    msg_=app.send_message(c_id,"🎙️ Обрабатываю аудио, подождите...")
    st_ev=threading.Event()
    sp_th=threading.Thread(target=run_loading_animation, args=(c_id,msg_.id,st_ev))
    sp_th.start()

    downloaded = None
    try:
        downloaded=app.download_media(message, file_name=path_)
        raw_=transcribe_audio(downloaded)
        roles_=assign_roles(raw_)
        processed_texts[c_id]=roles_
        app.edit_message_text(c_id,msg_.id,"✅ Аудио обработано! Выберите режим анализа:")
    except OpenAIPermissionError:
        logging.exception("Неверный OPENAI_API_KEY?")
        app.edit_message_text(c_id,msg_.id,"🚫 Ошибка: Whisper недоступен (ключ/регион).")
        downloaded = None
    except Exception as e:
        logging.exception("Ошибка обработки аудио")
        app.edit_message_text(c_id,msg_.id,f"❌ Ошибка: {e}")
        downloaded = None
    finally:
        st_ev.set()
        sp_th.join()
        try:
            app.delete_messages(c_id,msg_.id)
        except Exception:
            pass
        try:
            if downloaded:
                os.remove(downloaded)
        except OSError:
            pass

    # Подменю: ИНТЕРВЬЮ / ДИЗАЙН
    app.send_message(c_id,"Что анализируем дальше?", reply_markup=interview_or_design_menu())
    send_main_menu(c_id)

# Регистрируем декорированный обработчик
@app.on_message(filters.voice | filters.audio)  # type: ignore[misc]
def _handle_audio_msg_handler(client: Client, message: Message) -> None:  # pyright: ignore[reportUnusedFunction]
    """Декорированная реализация для handle_audio_msg"""
    return handle_audio_msg(client, message)

# ========== Приём документов (для хранилища) ==========
def handle_document_msg(_: Client, message: Message) -> None:
    """Обработчик документов с явной типизацией"""
    c_id=message.chat.id
    if c_id not in authorized_users:
        return
    doc: Document=message.document
    st=user_states.get(c_id,{})
    if "upload_category" in st:
        cat=st["upload_category"]
        fold=STORAGE_DIRS.get(cat,"")
        if not fold:
            app.send_message(c_id,"Ошибка: неизвестная категория.")
            return
        orig_name=doc.file_name or f"file_{int(time.time())}"
        sf=safe_filename(orig_name)
        path_=os.path.join(fold,sf)
        try:
            app.download_media(message, file_name=path_)
            app.send_message(c_id,f"✅ Файл '{orig_name}' сохранён в '{cat}'.")
        except Exception as e:
            logging.exception("Ошибка сохранения документа")
            app.send_message(c_id,f"❌ Ошибка сохранения: {e}")
        user_states.pop(c_id,None)  # pyright: ignore[reportUnusedCallResult]
    else:
        app.send_message(c_id,"Сначала выберите действие (Загрузить файл) в меню.")

    send_main_menu(c_id)

# Регистрируем декорированный обработчик
@app.on_message(filters.document)  # type: ignore[misc]
def _handle_document_msg_handler(client: Client, message: Message) -> None:  # pyright: ignore[reportUnusedFunction]
    """Декорированная реализация для handle_document_msg"""
    return handle_document_msg(client, message)

# ========== CALLBACK QUERY (меню) ==========

def handle_menu_navigation(c_id: int, data: str) -> bool:
    """Обработка навигации по меню"""
    if data == "menu_main":
        send_main_menu(c_id)
        return True
    
    if data == "menu_help":
        clear_active_menus(c_id)
        mk, txt = help_menu_markup()
        mm = app.send_message(c_id, txt, reply_markup=mk)
        register_menu_message(c_id, mm.id)
        return True
    
    if data == "menu_storage":
        clear_active_menus(c_id)
        mm = app.send_message(c_id, "📦 Меню хранилища:", reply_markup=storage_menu_markup())
        register_menu_message(c_id, mm.id)
        return True
    
    return False

def handle_file_operations(c_id: int, data: str) -> bool:
    """Обработка операций с файлами"""
    if data.startswith("view||"):
        parts = data.split("||")
        if len(parts) < 2:
            return True
        cat = parts[1]
        clear_active_menus(c_id)
        mm = app.send_message(c_id, f"Файлы в '{cat}':", reply_markup=files_menu_markup(cat))
        register_menu_message(c_id, mm.id)
        return True
    
    if data.startswith("select||"):
        _handle_file_selection(c_id, data)
        return True
    
    if data.startswith("delete||"):
        _handle_file_deletion(c_id, data)
        return True
    
    if data.startswith("upload||"):
        parts = data.split("||")
        if len(parts) < 2:
            return True
        cat = parts[1]
        user_states[c_id] = {"upload_category": cat}
        app.send_message(c_id, f"Отправьте документ, который хотите сохранить в '{cat}'.")
        return True
    
    return False

def _handle_file_selection(c_id: int, data: str) -> None:
    """Обработка выбора файла"""
    parts = data.split("||")
    if len(parts) < 3:
        return
    
    cat, sfn = parts[1], parts[2]
    fold = STORAGE_DIRS.get(cat, "")
    real_name = _find_real_filename(fold, sfn)
    
    if not real_name:
        app.send_message(c_id, "Файл не найден.")
        return
    
    msg_ = app.send_message(c_id, "⏳ Обрабатываю файл...")
    st_ev = threading.Event()
    sp_th = threading.Thread(target=run_loading_animation, args=(c_id, msg_.id, st_ev))
    sp_th.start()
    
    try:
        res = process_stored_file(cat, real_name, c_id)
        if res is not None:
            processed_texts[c_id] = res
            app.edit_message_text(c_id, msg_.id, "✅ Файл обработан.")
    finally:
        st_ev.set()
        sp_th.join()
        app.delete_messages(c_id, msg_.id)
    
    app.send_message(c_id, "Что анализируем дальше?", reply_markup=interview_or_design_menu())
    send_main_menu(c_id)

def _handle_file_deletion(c_id: int, data: str) -> None:
    """Обработка удаления файла"""
    parts = data.split("||")
    if len(parts) < 3:
        return
    
    cat, sfn = parts[1], parts[2]
    fold = STORAGE_DIRS.get(cat, "")
    real_name = _find_real_filename(fold, sfn)
    
    if not real_name:
        app.send_message(c_id, "Файл не найден.")
        return
    
    try:
        os.remove(os.path.join(fold, real_name))
        app.send_message(c_id, "Файл удалён.")
    except Exception as e:
        app.send_message(c_id, f"Ошибка удаления: {e}")
    
    mm = app.send_message(c_id, f"Список файлов в '{cat}':", reply_markup=files_menu_markup(cat))
    register_menu_message(c_id, mm.id)

def _find_real_filename(fold: str, sfn: str) -> str | None:
    """Поиск реального имени файла по безопасному имени"""
    try:
        for f in os.listdir(fold):
            if safe_filename(f) == sfn:
                return f
    except OSError:
        pass
    return None

def handle_mode_selection(c_id: int, data: str) -> bool:
    """Обработка выбора режима анализа"""
    if data == "mode_interview":
        clear_active_menus(c_id)
        mm = app.send_message(c_id, "ИНТЕРВЬЮ:", reply_markup=interview_menu_markup())
        register_menu_message(c_id, mm.id)
        return True
    
    if data == "mode_design":
        clear_active_menus(c_id)
        mm = app.send_message(c_id, "ДИЗАЙН:", reply_markup=design_menu_markup())
        register_menu_message(c_id, mm.id)
        return True
    
    return False

def handle_interview_reports(c_id: int, data: str) -> bool:
    """Обработка отчетов интервью"""
    interview_reports = {
        "report_int_methodology": (analyze_interview_methodology, "Оценка методологии интервью"),
        "report_int_links": (analyze_quality_decision_links, "Отчет о связках (качество-принятие)"),
        "report_int_general": (analyze_interview_general, "Общие факторы (Интервью)"),
        "report_int_specific": (analyze_interview_specific, "Факторы в этом заведении (Интервью)"),
        "report_int_employee": (analyze_employee_performance, "Анализ работы сотрудника")
    }
    
    if data in interview_reports:
        func, label = interview_reports[data]
        run_analysis_with_spinner(c_id, func, label)
        return True
    
    return False

def handle_design_reports(c_id: int, data: str) -> bool:
    """Обработка отчетов дизайна"""
    design_reports = {
        "report_design_audit_methodology": (analyze_design_audit, "Оценка методологии аудита"),
        "report_design_compliance": (analyze_audit_compliance, "Информация о соответствии программе аудита"),
        "report_design_structured": (analyze_structured_audit, "Структурированный отчет аудита")
    }
    
    if data in design_reports:
        func, label = design_reports[data]
        run_analysis_with_spinner(c_id, func, label)
        return True
    
    return False

def callback_query_handler(_: Client, callback: CallbackQuery) -> None:
    """Обработчик callback запросов с явной типизацией"""
    c_id = callback.message.chat.id
    data = callback.data
    
    try:
        callback.answer()
    except Exception:
        pass
    
    try:
        # Делегируем обработку специализированным функциям
        handlers = [
            handle_menu_navigation,
            handle_file_operations,
            handle_mode_selection,
            handle_interview_reports,
            handle_design_reports
        ]
        
        for handler in handlers:
            if handler(c_id, data):
                return
                
    except Exception:
        logging.exception("Ошибка обработки callback_data")

# Регистрируем декорированный обработчик
@app.on_callback_query()  # type: ignore[misc]
def _callback_query_handler_impl(client: Client, callback: CallbackQuery) -> None:  # pyright: ignore[reportUnusedFunction]
    """Декорированная реализация для callback_query_handler"""
    return callback_query_handler(client, callback)

def run_analysis_with_spinner(chat_id: int, func: Callable[[str], str], label: str):
    txt_=processed_texts.get(chat_id,"")
    if not txt_:
        app.send_message(chat_id,"Нет текста для анализа. Сначала загрузите/обработайте аудио/текст.")
        return
    msg_=app.send_message(chat_id,f"⏳ {label}...")
    st_ev=threading.Event()
    sp_th=threading.Thread(target=run_loading_animation, args=(chat_id,msg_.id,st_ev))
    sp_th.start()

    try:
        result=func(txt_)
        # Результат разбиваем по 4096
        block=4096
        for i in range(0,len(result),block):
            app.send_message(chat_id, result[i:i+block])
        app.edit_message_text(chat_id, msg_.id, f"✅ Завершено: {label}")
    except OpenAIPermissionError:
        logging.exception("Неверный Claude API Key?")
        app.edit_message_text(chat_id, msg_.id, "🚫 Ошибка: Claude API недоступен (ключ/регион).")
    except Exception as e:
        logging.exception("Ошибка анализа")
        app.edit_message_text(chat_id, msg_.id, f"❌ Ошибка: {e}")
    finally:
        st_ev.set()
        sp_th.join()
        try:
            app.delete_messages(chat_id, msg_.id)
        except Exception:
            pass

    send_main_menu(chat_id)

# ========== Запуск ==========
if __name__=="__main__":
    logging.info("Бот запущен. Ожидаю сообщений...")
    app.run()
