import re
import logging
from pyrogram import Client

def check_authorized(chat_id: int, authorized_users: set):
    if chat_id not in authorized_users:
        raise ValueError("Ошибка: пользователь не авторизован")
    
def validate_building_type(building_type: str) -> str:
    building_type = building_type.lower()
    if 'отел' in building_type:
        return 'Отель'
    elif 'ресторан' in building_type:
        return 'Ресторан'
    elif 'центр здоров' in building_type or 'центре здоров' in building_type:
        return "Центр Здоровья"
    logging.warning(f"Не удалось спарсить тип заведения")
    return 
    
def validate_date_format(date_str: str) -> bool:
    """
    Проверяет, соответствует ли строка формату YYYY-MM-DD.
    """
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    return bool(re.match(pattern, date_str))

def check_state(state: dict, chat_id: int, app: Client) -> bool:
    if not state:
        # Нет состояния — значит пользователь что-то пишет без контекста
        app.send_message(chat_id, "Я вас слушаю. Откройте меню, если нужно запустить отчёт.")
        return False
    return True

def check_file_detection(filename: str, chat_id: int, app: Client) -> bool:
    if not filename:
        app.send_message(chat_id, "Файл не найден.")
        return False
    return True

def check_valid_data(validate_datas: list[str], chat_id: int, app: Client, msg: str):
    for data in validate_datas:
        if not data:
            app.send_message(chat_id, msg)
            return
        
def check_audio_file_size(file_size: int, max_size: int, chat_id: int, app: Client):
    if file_size > max_size:
        msg = f"Файл слишком большой ({file_size / 1024 / 1024:.1f} MB). Макс 2GB."
        app.send_message(chat_id, msg)
        raise ValueError(msg)