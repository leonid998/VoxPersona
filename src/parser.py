from __future__ import annotations
from datetime import datetime
import re
from validators import validate_building_type
import pymorphy2

PRETEXT_RE = re.compile(r"^\s*(о|об|обо|про|по)\s+", re.I)

def del_pretext(text: str) -> str:
    return PRETEXT_RE.sub("", text)

def normalize_building_info(building_info: str) -> str:
    """
    1. Убирает предлоги 'о', 'об', 'обо' в начале строки.
    2. Переводит 'отеле' -> 'отель', 'центре здоровья' -> 'центр здоровья', 
       'ресторане' -> 'ресторан' и т.п.
    """
    text = building_info.lower().strip()

    # 1) Удаляем начальные предлоги: о, об, обо (с пробелами или без)
    # Пример: "об отеле", "о центре здоровья"
    text = del_pretext(text)

    # 2) Замены склонённых форм на «базу»
    synonyms = {
        "отеле": "отель",
        "отель": "отель",  
        
        "центре здоровья": "центр здоровья",
        "центр здоровья": "центр здоровья",
        
        "ресторане": "ресторан",
        "ресторан": "ресторан",

    }

    text = synonyms.get(text, text)

    return text.strip()

def parse_file_number(audio_number: str) -> int:
    match = re.search(r"(\d+)", audio_number.strip())
    if match:
        return int(match.group(1))
    return None
    # return int(audio_number.replace("№", "").strip())

def parse_date(date: str) -> str:
    return str(datetime.strptime(date, "%Y.%m.%d").strftime("%Y-%m-%d"))

def _lemmatize(word: str) -> str:
    """Лемма слова (нормальная форма)."""
    morph = pymorphy2.MorphAnalyzer()
    p = morph.parse(word)
    return p[0].normal_form if p else word

def _title(words: list[str]) -> str:
    """Title‑Case для списка слов без изменения их формы."""
    return " ".join(w.title() for w in words)

def _normalize_first_word(words: list[str]) -> str:
    """
    Лемматизирует только первое слово, остальные оставляет как есть,
    потом приводит всё к Title‑Case.
    """
    if not words:
        return ""
    first, *rest = words
    first = _lemmatize(first)
    return _title([first, *rest])

def parse_zone(zone: str) -> str:
    """
    «о центре здоровья при отеле»  →  «Центр Здоровья»
    «Номерной фонд, фасад»         →  «Номерной Фонд, Фасад»
    """
    AFTER_PRI_RE = re.compile(r"\bпри\b.*$", re.I)

    zone = zone.strip()
    if not zone or zone == "-":
        return "-"

    zone = PRETEXT_RE.sub("", zone.lower())
    zone = AFTER_PRI_RE.sub("", zone)

    parts_out = []
    for raw in zone.split(","):
        raw = raw.strip()
        if not raw:
            continue
        parts_out.append(_normalize_first_word(raw.split()))

    return ", ".join(parts_out)

def parse_building_type(building_type: str) -> str:
    building_type = normalize_building_info(building_type)
    valid_building_type = validate_building_type(building_type)
    return valid_building_type if valid_building_type is not None else building_type

def parse_name(name: str) -> str:
    return name.strip().lower().title()

def parse_city(city_name: str) -> str:
    return city_name.strip().lower().title()

def parse_place_name(place_name: str) -> str:
    return place_name.strip().lower().title()

def parse_design(lines: list[str]) -> dict:
    data = {}

    if len(lines) == 7:
        # Зона есть
        audio_number, date, employee, place_name, building_type, zone_name, city = lines
    elif len(lines) == 6:
        # Зоны нет
        audio_number, date, employee, place_name, building_type, city = lines
        zone_name = "-"
    else:
        raise ValueError("Неверное количество полей для сценария 'дизайн'.")

    data["audio_number"] = parse_file_number(audio_number)
    data["date"] = parse_date(date.strip())
    data["employee"] = parse_name(employee)
    data["place_name"] = parse_place_name(place_name)
    data["building_type"] = parse_building_type(building_type)
    data["zone_name"] = parse_zone(zone_name)
    data["city"] = parse_city(city)

    return data

def parse_building_info(building_info: str, data: dict) -> tuple:
    if "при" in building_info:
        zone, building_type = building_info.split("при")
        data["zone_name"] = parse_zone(zone)
        data["building_type"] = parse_building_type(building_type)
        return data
    
    data["zone_name"] = "-"
    data["building_type"] = parse_building_type(building_info)
    return data

def parse_interview(lines: list[str]) -> dict:
    data = {}
    if len(lines) != 6:
        raise ValueError("Неверное количество полей для сценария 'интервью'.")

    audio_number, date, employee, client, building_info, place_name = lines

    data["audio_number"] = parse_file_number(audio_number)
    data["date"] = date if "-" in date else parse_date(date.strip())
    data["employee"] = parse_name(employee)
    data["client"] = parse_name(client)
    data["place_name"] = parse_place_name(place_name)

    data = parse_building_info(building_info, data)
    
    return data


def parse_message_text(text: str, mode: str) -> dict:
    """
    Парсит текст сообщения и извлекает данные для сценариев "дизайн" или "интервью".
    :param text: Текст сообщения.
    :param mode: Сценарий ("design" или "interview").
    :return: Словарь с извлеченными данными.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if mode == "design":
        data = parse_design(lines)

    elif mode == "interview":
        data = parse_interview(lines)

    return data