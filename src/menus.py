from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client
import os
from typing import Any
from storage import safe_filename

from config import STORAGE_DIRS, active_menus
from markups import main_menu_markup, confirm_menu_markup, edit_menu_markup
from constants import BUTTON_BACK

def files_menu_markup(category: str):
    """
    Клавиатура списка файлов в указанной категории.
    Позволяет выбрать файл (для обработки) или удалить.
    """

    fold = STORAGE_DIRS.get(category, "")
    rows = []
    try:
        fs = os.listdir(fold)
    except OSError:
        fs = []

    for f in fs:
        sf = safe_filename(f)
        b_open = InlineKeyboardButton(f, callback_data=f"select||{category}||{sf}")
        b_del  = InlineKeyboardButton("❌", callback_data=f"delete||{category}||{sf}")
        rows.append([b_open, b_del])

    # Кнопка для загрузки нового файла
    rows.append([InlineKeyboardButton("Загрузить файл", callback_data=f"upload||{category}")])
    rows.append([InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)

async def send_main_menu(chat_id: int, app: Client):
    from menu_manager import send_menu
    await send_menu(chat_id, app, "🏠 Главное меню:", main_menu_markup())

async def show_confirmation_menu(chat_id: int, state: dict[str, Any], app: Client):
    """
    Показываем пользователю сводку всех полей и просим подтвердить или редактировать.
    """
    from menu_manager import send_menu
    data_ = state.get("data", {})
    mode = state.get("mode", "—")
    client = data_.get("client", "")
    employee = data_.get("employee", "—")
    place = data_.get("place_name", "—")
    date_ = data_.get("date", "—")
    zone_name = data_.get("zone_name", "—")
    file_number = data_.get("audio_number", "—")
    building_type = data_.get("building_type", "—")
    city = data_.get("city", "")

    kb, text_summary = confirm_menu_markup(
        mode=mode,
        employee=employee,
        place=place,
        date=date_,
        city=city,
        zone_name=zone_name,
        file_number=file_number,
        building_type=building_type,
        client=client
        )

    await send_menu(chat_id, app, text_summary, kb)

async def show_edit_menu(chat_id: int, state: dict[str, Any], app: Client):
    """
    Клавиатура с вариантами, какое поле редактировать.
    """
    from menu_manager import send_menu
    mode = state.get("mode", "")

    kb = edit_menu_markup(mode)
    await send_menu(chat_id, app, "Какое поле хотите изменить?", kb)