from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datamodels import mapping_scenario_names
from constants import BUTTON_BACK, BUTTON_BACK_WITH_ARROW

def main_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📁 Хранилище", callback_data="menu_storage"),
            InlineKeyboardButton("Режим диалога", callback_data="menu_dialog"),
            InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
        ]
    ])

def storage_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Аудио файлы", callback_data="view||audio")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])

def confirm_menu_markup(mode: str, file_number: int,  employee: str, building_type: str, place: str, date: str, city: str, zone_name: str, client: str):
    "Меню проверки данных"
    text_summary = (
            f"**Проверка введённых данных**\n\n"
            f"**Сценарий**: {mapping_scenario_names[mode]}\n"
            f"**Номер файла**: {file_number}\n"
            f"**Дата**: {date}\n"
            f"**ФИО Сотрудника**: {employee}\n"
            f"**Заведение**: {place}\n"
            f"**Тип заведения**: {building_type}\n"
            f"**Зона**: {zone_name}\n"
        )
    
    if city:
        text_summary += f"**Город**: {city}\n\n"
    if client:
        text_summary += f"**ФИО Клиента**: {client}\n\n"
    
    text_summary += "Подтвердить или изменить?"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_data"),
            InlineKeyboardButton("✏️ Изменить", callback_data="edit_data")
        ]
    ])

    return kb, text_summary

def edit_menu_markup(mode: str):
    "Меню редактирования данных"

    markups = [
        [InlineKeyboardButton("Номер файла", callback_data="edit_audio_number")],
        [InlineKeyboardButton("Дата", callback_data="edit_date")],
        [InlineKeyboardButton("ФИО Сотрудника", callback_data="edit_employee")],
        [InlineKeyboardButton("Заведение", callback_data="edit_place_name")],
        [InlineKeyboardButton("Тип заведения", callback_data="edit_building_type")],
        [InlineKeyboardButton("Зона", callback_data="edit_zone_name")],
    ]

    if mode == "design":
        markups.append([InlineKeyboardButton("Город", callback_data="edit_city")])
    else:
        markups.append([InlineKeyboardButton("ФИО Клиента", callback_data="edit_client")],)
    
    markups.append([InlineKeyboardButton(BUTTON_BACK_WITH_ARROW, callback_data="back_to_confirm")])

    kb = InlineKeyboardMarkup(markups)
    return kb

def make_dialog_markup(enabled: bool) -> InlineKeyboardMarkup:
    label = "✅ Глубокое исследование" if enabled else "🔍 Глубокое исследование"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="toggle_deep")],
        [InlineKeyboardButton("Главное меню", callback_data="menu_main")]
    ])

def help_menu_markup():
    text_ = (
        "Бот имеет два режима: 'Хранилище' и 'Режим диалога'\n\n"
        "В режиме 'Хранилище' Вы можете загружать аудио, они будут автоматически обрабатываться и сохраняться в базу данных и получать отчеты\n\n"
        "В режиме диалога Вы можете задавать боту различные вопросы для получения какой-либо информации\n\n"
        "Структура отчётов:\n\n"
        "ИНТЕРВЬЮ:\n"
        "1) Оценка методологии интервью\n"
        "2) Отчёт о связках (качество-принятие)\n"
        "3) Информация об общих факторах\n"
        "4) Информация о факторах в этом заведении\n"
        "5) Анализ работы сотрудника\n\n"
        "ДИЗАЙН:\n"
        "1) Оценка методологии аудита\n"
        "2) Информация о соответствии (авто)\n"
        "3) Структурированный отчёт (авто)\n\n"
        "Макс 2 ГБ, без ffmpeg."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]])
    return kb, text_

def interview_or_design_menu():
    """Меню выбора: ИНТЕРВЬЮ / ДИЗАЙН."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ИНТЕРВЬЮ", callback_data="mode_interview"),
            InlineKeyboardButton("ДИЗАЙН", callback_data="mode_design"),
            InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")
        ]
    ])

def building_type_menu_markup():
    """Выбор типа здания"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Отель", callback_data="choose_building||hotel"),
            InlineKeyboardButton("Ресторан", callback_data="choose_building||restaurant"),
            InlineKeyboardButton("Центр здоровья", callback_data="choose_building||spa"),
        ]
    ]) 

def interview_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1) Оценка методологии интервью", callback_data="report_int_methodology")],
        [InlineKeyboardButton("2) Отчет о связках", callback_data="report_int_links")],
        [InlineKeyboardButton("3) Общие факторы", callback_data="report_int_general")],
        [InlineKeyboardButton("4) Факторы в этом заведении", callback_data="report_int_specific")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])

def design_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1) Оценка методологии аудита", callback_data="report_design_audit_methodology")],
        [InlineKeyboardButton("2) Соответствие программе аудита", callback_data="report_design_compliance")],
        [InlineKeyboardButton("3) Структурированный отчет аудита", callback_data="report_design_structured")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])