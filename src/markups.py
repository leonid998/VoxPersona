from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datamodels import mapping_scenario_names
from constants import BUTTON_BACK, BUTTON_BACK_WITH_ARROW
from conversation_manager import conversation_manager
from conversations import ConversationMetadata

def main_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Чаты/Диалоги", callback_data="menu_chats")
        ],
        [
            InlineKeyboardButton("⚙️ Системная", callback_data="menu_system"),
            InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
        ]
    ])

def storage_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Аудио файлы", callback_data="view||audio")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_system")]
    ])

def system_menu_markup():
    """Меню системных настроек"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Хранилище", callback_data="menu_storage")],
        [InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")]
    ])

def create_chat_button_row(conv: ConversationMetadata, is_active: bool, chat_number: int = None) -> list:
    """
    Создает кнопку чата с ТОЧНЫМИ пропорциями 50%/25%/25% через расчет длины текстов.

    Пропорции достигаются за счет:
    - Название чата: ~24 символа (включая эмодзи и номер) = 50%
    - Переименовать: ~12 символов = 25%
    - Удалить: ~12 символов = 25%

    Args:
        conv: Метаданные чата
        is_active: True если это активный чат
        chat_number: Номер чата по порядку создания (опционально)

    Returns:
        List из 3 InlineKeyboardButton
    """
    emoji = "📝" if is_active else "💬"

    # ТОЧНЫЙ РАСЧЕТ для пропорций 50%/25%/25%:
    # Целевая длина кнопки названия: 24 символа (включая эмодзи, номер, пробелы)
    # Формат: "📝 1. Название..." = 2 (эмодзи+пробел) + 2-3 (номер) + 2 (". ") + текст

    if chat_number:
        # "📝 1. " занимает ~6 символов, остается 18 для названия
        prefix_length = len(f"{emoji} {chat_number}. ")
        name_max_length = 24 - prefix_length
    else:
        # "📝 " занимает ~2 символа, остается 22 для названия
        prefix_length = len(f"{emoji} ")
        name_max_length = 24 - prefix_length

    name = conv.title
    if len(name) > name_max_length:
        name = name[:name_max_length - 3] + "..."

    display_name = f"{chat_number}. {name}" if chat_number else name

    # Кнопки фиксированной длины для точных пропорций 25%/25%
    # Каждая кнопка ~12 символов
    return [
        InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f"switch_chat||{conv.conversation_id}"),
        InlineKeyboardButton("✏️ Изменить", callback_data=f"rename_chat||{conv.conversation_id}"),  # 10 символов
        InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_chat||{conv.conversation_id}")    # 9 символов
    ]

def chats_menu_markup_dynamic(user_id: int) -> InlineKeyboardMarkup:
    """
    Генерирует динамическое меню Чаты с списком чатов пользователя.

    Структура:
    - Строка 1: [🆕 Новый чат] [« Назад]
    - Строка 2: [📊 Статистика] [📄 Мои отчеты]
    - Строка 3: Активный чат (📝 эмодзи) с номером
    - Строка 4+: Остальные чаты (💬 эмодзи) с номерами по updated_at DESC

    Формат кнопки чата: [60% номер+название] [20% ✏️] [20% 🗑️]
    Нумерация: по порядку создания (created_at ASC)
    """
    # Статичные строки
    buttons = [
        [
            InlineKeyboardButton("🆕 Новый чат", callback_data="new_chat"),
            InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="show_stats"),
            InlineKeyboardButton("📄 Мои отчеты", callback_data="show_my_reports")
        ]
    ]

    # Загружаем список чатов
    conversations = conversation_manager.list_conversations(user_id)

    if not conversations:
        return InlineKeyboardMarkup(buttons)

    # Используем сохраненные номера чатов из metadata (или 0 для старых чатов)
    # Старые чаты без chat_number получат номер 0, новые - постоянный номер
    chat_numbers = {
        conv.conversation_id: conv.chat_number
        for conv in conversations
    }

    # Разделяем на активный и остальные
    active_chat = None
    other_chats = []

    for conv in conversations:
        if conv.is_active:
            active_chat = conv
        else:
            other_chats.append(conv)

    # Сортируем остальные чаты по updated_at DESC
    other_chats.sort(key=lambda x: x.updated_at, reverse=True)

    # Добавляем активный чат (если есть) с номером
    if active_chat:
        chat_num = chat_numbers[active_chat.conversation_id]
        buttons.append(create_chat_button_row(active_chat, True, chat_num))

    # Добавляем остальные чаты с номерами
    for conv in other_chats:
        chat_num = chat_numbers[conv.conversation_id]
        buttons.append(create_chat_button_row(conv, False, chat_num))

    return InlineKeyboardMarkup(buttons)

def switch_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """Меню подтверждения переключения чата."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, перейти", callback_data=f"confirm_switch||{conversation_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="menu_chats")
        ]
    ])

def delete_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """Меню подтверждения удаления чата."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"confirm_delete||{conversation_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="menu_chats")
        ]
    ])

def chats_menu_markup():
    """Меню истории чатов"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🆕 Новый чат", callback_data="new_chat"),
            InlineKeyboardButton(BUTTON_BACK, callback_data="menu_main")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="show_stats"),
            InlineKeyboardButton("📄 Мои отчеты", callback_data="show_my_reports")
        ]
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

def make_dialog_markup() -> InlineKeyboardMarkup:
    """
    Меню выбора режима поиска.

    Структура:
    - Строка 1: [Быстрый поиск] [Глубокое исследование]
    - Строка 2: [Главное меню]
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Быстрый поиск", callback_data="mode_fast"),
            InlineKeyboardButton("🔬 Глубокое исследование", callback_data="mode_deep")
        ],
        [InlineKeyboardButton("📱 Чаты/Диалоги", callback_data="menu_chats")]
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
