from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datamodels import mapping_scenario_names
from constants import BUTTON_BACK, BUTTON_BACK_WITH_ARROW
from conversation_manager import conversation_manager
from conversations import ConversationMetadata

def main_menu_markup():
    """Главное меню с расширенными кнопками."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("        📱 Чаты/Диалоги        ", callback_data="menu_chats")
        ],
        [
            InlineKeyboardButton("    ⚙️ Системная    ", callback_data="menu_system"),
            InlineKeyboardButton("    ❓ Помощь    ", callback_data="menu_help")
        ]
    ])

def storage_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        📁 Аудио файлы        ", callback_data="view||audio")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_system")]
    ])

def system_menu_markup():
    """Меню системных настроек"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        📁 Хранилище        ", callback_data="menu_storage")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_main")]
    ])

def create_chat_button_row(conv: ConversationMetadata, is_active: bool, chat_number: int = None) -> list:
    """
    Создает ОДНУ кнопку с названием чата на всю ширину.

    При клике открывается меню действий с чатом (переключение, переименование, удаление).

    Args:
        conv: Метаданные чата
        is_active: True если это активный чат
        chat_number: Номер чата по порядку создания (опционально)

    Returns:
        List из одной InlineKeyboardButton
    """
    emoji = "📝" if is_active else "💬"

    # Увеличиваем максимальную длину названия до ~40 символов
    # так как теперь кнопка одна и занимает всю ширину
    if chat_number and chat_number > 0:
        # "📝 1. " занимает ~6 символов, остается ~34 для названия
        prefix_length = len(f"{emoji} {chat_number}. ")
        name_max_length = 40 - prefix_length
    else:
        # "📝 " занимает ~2 символа, остается ~38 для названия
        prefix_length = len(f"{emoji} ")
        name_max_length = 40 - prefix_length

    name = conv.title
    if len(name) > name_max_length:
        name = name[:name_max_length - 3] + "..."

    display_name = f"{chat_number}. {name}" if (chat_number and chat_number > 0) else name

    # Возвращаем ОДНУ кнопку с callback на меню действий
    return [
        InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f"chat_actions||{conv.conversation_id}")
    ]

def chats_menu_markup_dynamic(user_id: int) -> InlineKeyboardMarkup:
    """
    Генерирует динамическое меню Чаты с списком чатов пользователя.

    Структура:
    - Строка 1: [🆕 Новый чат] [« Назад]
    - Строка 2: [📊 Статистика] [📄 Мои отчеты]
    - Строка 3: Активный чат (📝 эмодзи) с номером - ОДНА кнопка
    - Строка 4+: Остальные чаты (💬 эмодзи) с номерами по updated_at DESC - каждый ОДНА кнопка

    Формат кнопки чата: на всю ширину с названием
    Нумерация: по порядку создания (created_at ASC)
    """
    # Статичные строки с расширенными кнопками
    buttons = [
        [
            InlineKeyboardButton("    🆕 Новый чат    ", callback_data="new_chat"),
            InlineKeyboardButton(f"    {BUTTON_BACK}    ", callback_data="menu_main")
        ],
        [
            InlineKeyboardButton("    📊 Статистика    ", callback_data="show_stats"),
            InlineKeyboardButton("    📄 Мои отчеты    ", callback_data="show_my_reports")
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

    # Добавляем активный чат (если есть) с номером - ОДНА кнопка на строку
    if active_chat:
        chat_num = chat_numbers[active_chat.conversation_id]
        buttons.append(create_chat_button_row(active_chat, True, chat_num))

    # Добавляем остальные чаты с номерами - ОДНА кнопка на строку
    for conv in other_chats:
        chat_num = chat_numbers[conv.conversation_id]
        buttons.append(create_chat_button_row(conv, False, chat_num))

    return InlineKeyboardMarkup(buttons)

def chat_actions_menu_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """
    Меню действий с чатом.

    Показывается после клика на название чата.

    Структура:
    - Строка 1: [В Чат] [✏️] [🗑️] [Назад]

    Args:
        conversation_id: ID чата
        chat_name: Название чата для отображения

    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("  В Чат  ", callback_data=f"confirm_switch||{conversation_id}"),
            InlineKeyboardButton("  ✏️  ", callback_data=f"rename_chat||{conversation_id}"),
            InlineKeyboardButton("  🗑️  ", callback_data=f"delete_chat||{conversation_id}"),
            InlineKeyboardButton("  Назад  ", callback_data="menu_chats")
        ]
    ])

def switch_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """Меню подтверждения переключения чата."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("    ✅ Да, перейти    ", callback_data=f"confirm_switch||{conversation_id}"),
            InlineKeyboardButton("    ❌ Отмена    ", callback_data="menu_chats")
        ]
    ])

def delete_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """Меню подтверждения удаления чата."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("    🗑️ Да, удалить    ", callback_data=f"confirm_delete||{conversation_id}"),
            InlineKeyboardButton("    ❌ Отмена    ", callback_data="menu_chats")
        ]
    ])

def chats_menu_markup():
    """Меню истории чатов"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("    🆕 Новый чат    ", callback_data="new_chat"),
            InlineKeyboardButton(f"    {BUTTON_BACK}    ", callback_data="menu_main")
        ],
        [
            InlineKeyboardButton("    📊 Статистика    ", callback_data="show_stats"),
            InlineKeyboardButton("    📄 Мои отчеты    ", callback_data="show_my_reports")
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
            InlineKeyboardButton("    ✅ Подтвердить    ", callback_data="confirm_data"),
            InlineKeyboardButton("    ✏️ Изменить    ", callback_data="edit_data")
        ]
    ])

    return kb, text_summary

def edit_menu_markup(mode: str):
    "Меню редактирования данных"

    markups = [
        [InlineKeyboardButton("        Номер файла        ", callback_data="edit_audio_number")],
        [InlineKeyboardButton("        Дата        ", callback_data="edit_date")],
        [InlineKeyboardButton("        ФИО Сотрудника        ", callback_data="edit_employee")],
        [InlineKeyboardButton("        Заведение        ", callback_data="edit_place_name")],
        [InlineKeyboardButton("        Тип заведения        ", callback_data="edit_building_type")],
        [InlineKeyboardButton("        Зона        ", callback_data="edit_zone_name")],
    ]

    if mode == "design":
        markups.append([InlineKeyboardButton("        Город        ", callback_data="edit_city")])
    else:
        markups.append([InlineKeyboardButton("        ФИО Клиента        ", callback_data="edit_client")],)

    markups.append([InlineKeyboardButton(f"        {BUTTON_BACK_WITH_ARROW}        ", callback_data="back_to_confirm")])

    kb = InlineKeyboardMarkup(markups)
    return kb

def make_dialog_markup() -> InlineKeyboardMarkup:
    """
    Меню выбора режима поиска.

    Структура:
    - Строка 1: [⚡ Быстрый поиск] [🔬 Глубокое исследование]
    - Строка 2: [📜 Получить историю] [📱 Чаты/Диалоги]
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Быстрый поиск", callback_data="mode_fast"),
            InlineKeyboardButton("🔬 Глубокое исследование", callback_data="mode_deep")
        ],
        [
            InlineKeyboardButton("📜 Получить историю", callback_data="send_history_manual"),
            InlineKeyboardButton("📱 Чаты/Диалоги", callback_data="menu_chats")
        ]
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
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_main")]])
    return kb, text_

def interview_or_design_menu():
    """Меню выбора: ИНТЕРВЬЮ / ДИЗАЙН."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("  ИНТЕРВЬЮ  ", callback_data="mode_interview"),
            InlineKeyboardButton("  ДИЗАЙН  ", callback_data="mode_design"),
            InlineKeyboardButton(f"  {BUTTON_BACK}  ", callback_data="menu_main")
        ]
    ])

def building_type_menu_markup():
    """Выбор типа здания"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("  Отель  ", callback_data="choose_building||hotel"),
            InlineKeyboardButton("  Ресторан  ", callback_data="choose_building||restaurant"),
            InlineKeyboardButton("  Центр здоровья  ", callback_data="choose_building||spa"),
        ]
    ])

def interview_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("    1) Оценка методологии интервью    ", callback_data="report_int_methodology")],
        [InlineKeyboardButton("    2) Отчет о связках    ", callback_data="report_int_links")],
        [InlineKeyboardButton("    3) Общие факторы    ", callback_data="report_int_general")],
        [InlineKeyboardButton("    4) Факторы в этом заведении    ", callback_data="report_int_specific")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_main")]
    ])

def design_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("    1) Оценка методологии аудита    ", callback_data="report_design_audit_methodology")],
        [InlineKeyboardButton("    2) Соответствие программе аудита    ", callback_data="report_design_compliance")],
        [InlineKeyboardButton("    3) Структурированный отчет аудита    ", callback_data="report_design_structured")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_main")]
    ])
