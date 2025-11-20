from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datamodels import mapping_scenario_names
from constants import BUTTON_BACK, BUTTON_BACK_WITH_ARROW
from conversation_manager import conversation_manager
from conversations import ConversationMetadata
import time
import hashlib
from typing import List, Tuple, Optional

# Константы для session management
SESSION_TTL_SECONDS = 3600  # 1 час TTL для сессий query expansion

def main_menu_markup():
    """Главное меню с расширенными кнопками."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("        Чаты/Диалоги        ", callback_data="menu_chats")
        ],
        [
            InlineKeyboardButton("    Системная    ", callback_data="menu_system"),
            InlineKeyboardButton("    Помощь    ", callback_data="menu_help")
        ]
    ])

def storage_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("        Аудио файлы        ", callback_data="view||audio")],
        [InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_system")]
    ])

def system_menu_markup(user_role: str = "user"):
    """
    Системное меню (раздел "Системная").

    Args:
        user_role: Роль пользователя для отображения доп. пунктов
    """
    buttons = [
        [InlineKeyboardButton("        Хранилище        ", callback_data="menu_storage")]
    ]

    # ТОЛЬКО ДЛЯ SUPER_ADMIN
    if user_role == "super_admin":
        buttons.append([
            InlineKeyboardButton("        Настройки доступа        ", callback_data="menu_access")
        ])

    # K-04: КНОПКИ ДЛЯ ADMIN (прямой доступ к приглашениям)
    if user_role == "admin":
        buttons.append([
            InlineKeyboardButton("        Управление приглашениями        ", callback_data="access_invitations_menu")
        ])

    buttons.append([
        InlineKeyboardButton(f"        {BUTTON_BACK}        ", callback_data="menu_main")
    ])

    return InlineKeyboardMarkup(buttons)

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
    emoji = "[active]" if is_active else "[chat]"

    # Увеличиваем максимальную длину названия до ~40 символов
    # так как теперь кнопка одна и занимает всю ширину
    if chat_number and chat_number > 0:
        # "[active] 1. " занимает ~12 символов, остается ~28 для названия
        prefix_length = len(f"{emoji} {chat_number}. ")
        name_max_length = 40 - prefix_length
    else:
        # "[active] " занимает ~9 символов, остается ~31 для названия
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
    - Строка 1: [Новый чат] [Назад]
    - Строка 2: [Статистика] [Мои отчеты]
    - Строка 3: Активный чат с номером - ОДНА кнопка
    - Строка 4+: Остальные чаты с номерами по updated_at DESC - каждый ОДНА кнопка

    Формат кнопки чата: на всю ширину с названием
    Нумерация: по порядку создания (created_at ASC)
    """
    # Статичные строки с расширенными кнопками
    buttons = [
        [
            InlineKeyboardButton("    Новый чат    ", callback_data="new_chat"),
            InlineKeyboardButton(f"    {BUTTON_BACK}    ", callback_data="menu_main")
        ],
        [
            InlineKeyboardButton("    Статистика    ", callback_data="show_stats"),
            InlineKeyboardButton("    Мои отчеты    ", callback_data="show_my_reports")
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
    - Строка 1: [В Чат] [Edit] [Delete] [Назад]

    Args:
        conversation_id: ID чата
        chat_name: Название чата для отображения

    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("  В Чат  ", callback_data=f"confirm_switch||{conversation_id}"),
            InlineKeyboardButton("  Edit  ", callback_data=f"rename_chat||{conversation_id}"),
            InlineKeyboardButton("  Delete  ", callback_data=f"delete_chat||{conversation_id}"),
            InlineKeyboardButton("  Назад  ", callback_data="menu_chats")
        ]
    ])

def switch_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """Меню подтверждения переключения чата."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("    Да, перейти    ", callback_data=f"confirm_switch||{conversation_id}"),
            InlineKeyboardButton("    Отмена    ", callback_data="menu_chats")
        ]
    ])

def delete_chat_confirmation_markup(conversation_id: str, chat_name: str) -> InlineKeyboardMarkup:
    """Меню подтверждения удаления чата."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("    Да, удалить    ", callback_data=f"confirm_delete||{conversation_id}"),
            InlineKeyboardButton("    Отмена    ", callback_data="menu_chats")
        ]
    ])

def chats_menu_markup():
    """Меню истории чатов"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("    Новый чат    ", callback_data="new_chat"),
            InlineKeyboardButton(f"    {BUTTON_BACK}    ", callback_data="menu_main")
        ],
        [
            InlineKeyboardButton("    Статистика    ", callback_data="show_stats"),
            InlineKeyboardButton("    Мои отчеты    ", callback_data="show_my_reports")
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
            InlineKeyboardButton("    Подтвердить    ", callback_data="confirm_data"),
            InlineKeyboardButton("    Изменить    ", callback_data="edit_data")
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
    - Строка 1: [Быстрый поиск] [Глубокое исследование]
    - Строка 2: [Получить историю] [Чаты/Диалоги]
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Быстрый поиск", callback_data="mode_fast"),
            InlineKeyboardButton("Глубокое исследование", callback_data="mode_deep")
        ],
        [
            InlineKeyboardButton("Получить историю", callback_data="send_history_manual"),
            InlineKeyboardButton("Чаты/Диалоги", callback_data="menu_chats")
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

def make_index_selection_markup() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для ручного выбора RAG индекса.

    ФАЗА 3: Router Agent - UI для выбора индекса

    Структура:
    - 7 кнопок для индексов (каждая на отдельной строке)
    - Кнопка "Назад" для возврата в меню запроса

    Returns:
        InlineKeyboardMarkup с кнопками выбора индекса
    """
    return InlineKeyboardMarkup([
        # Индекс 1: Дизайн (структурированные данные)
        [InlineKeyboardButton("Дизайн (Структурированные аудиты)", callback_data="idx_Dizayn")],
        # Индекс 2: Интервью (транскрипции)
        [InlineKeyboardButton("Интервью (Транскрипции)", callback_data="idx_Intervyu")],
        # Индекс 3: Отчеты по дизайну (60 отелей)
        [InlineKeyboardButton("Отчеты по дизайну (60 отелей)", callback_data="idx_Otchety_po_dizaynu")],
        # Индекс 4: Отчеты по обследованию
        [InlineKeyboardButton("Отчеты по обследованию", callback_data="idx_Otchety_po_obsledovaniyu")],
        # Индекс 5: Итоговые отчеты
        [InlineKeyboardButton("Итоговые отчеты", callback_data="idx_Itogovye_otchety")],
        # Индекс 6: Исходники (Дизайн)
        [InlineKeyboardButton("Исходники (Дизайн)", callback_data="idx_Iskhodniki_dizayn")],
        # Индекс 7: Исходники (Обследование)
        [InlineKeyboardButton("Исходники (Обследование)", callback_data="idx_Iskhodniki_obsledovanie")],
        # Кнопка "Назад" (возврат к меню запроса)
        [InlineKeyboardButton(f"{BUTTON_BACK} Назад", callback_data="back_to_query_menu")]
    ])


def make_index_mode_selection_markup() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора режима определения индекса.

    ФАЗА 3: Router Agent - выбор режима перед поиском без улучшения вопроса

    Используется когда пользователь выбирает "Отправить как есть"
    и должен определить какой индекс использовать для поиска.

    Returns:
        InlineKeyboardMarkup с 2 режимами + кнопка назад
    """
    return InlineKeyboardMarkup([
        # Режим 1: Автоматический выбор Router Agent
        [InlineKeyboardButton("Автовыбор индекса", callback_data="search_auto_index")],
        # Режим 2: Ручной выбор пользователем
        [InlineKeyboardButton("Выбрать индекс вручную", callback_data="search_manual_index")],
        # Кнопка назад
        [InlineKeyboardButton(f"{BUTTON_BACK} Назад", callback_data="back_to_query_choice")]
    ])


def make_query_expansion_markup(
    original_question: str,
    expanded_question: str,
    conversation_id: str,
    deep_search: bool,
    refine_count: int = 0,
    selected_index: Optional[str] = None,
    top_indices: Optional[List[Tuple[str, float]]] = None
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора: отправить улучшенный вопрос или уточнить.

    ФАЗА 4: Query Expansion UI Components
    ФАЗА 3: Добавлена кнопка ручного выбора индекса
    ЗАДАЧА 2.3: Добавлена поддержка top_indices для передачи в enhance_question_for_index

    Callback data format: "команда||hash"
    - expand_send||{hash}: Отправить улучшенный вопрос в поиск
    - expand_refine||{hash}: Уточнить вопрос еще раз
    - select_index_manual: Выбрать индекс вручную (новая кнопка)

    Args:
        original_question: Исходный вопрос пользователя
        expanded_question: Улучшенный вопрос после query expansion
        conversation_id: ID мультичата для сохранения истории
        deep_search: True = глубокое исследование, False = быстрый поиск
        refine_count: Текущее количество попыток уточнения (защита от зацикливания)
        selected_index: Выбранный вручную индекс (опционально)
        top_indices: Топ-K релевантных индексов от Router Agent для передачи в enhance_question_for_index
                    Формат: [(index_name, score), ...]

    Returns:
        InlineKeyboardMarkup с 4 кнопками (Отправить, Уточнить, Выбрать индекс, Назад)
    """
    # ВАЖНО: callback_data в Telegram ограничен 64 байтами!
    # Не передаем полный вопрос, используем временное хранилище

    # Генерируем короткий ID для хранения в user_states
    query_hash = hashlib.md5(expanded_question.encode()).hexdigest()[:8]

    # Сохраняем в глобальное хранилище (user_states)
    from config import user_states

    # Создаем ключ для временного хранения
    # TODO: Добавить периодическую очистку user_states по TTL
    # Рекомендация: использовать cachetools.TTLCache или фоновую задачу asyncio
    # для автоматического удаления устаревших сессий (created_at + ttl < now)
    temp_key = f"expansion_{query_hash}"
    user_states[temp_key] = {
        "original": original_question,
        "expanded": expanded_question,
        "conversation_id": conversation_id,
        "deep_search": deep_search,
        "refine_count": refine_count,
        "selected_index": selected_index,
        "top_indices": top_indices,
        "created_at": time.time(),
        "ttl": SESSION_TTL_SECONDS
    }

    # callback_data: команда||hash
    send_data = f"expand_send||{query_hash}"
    refine_data = f"expand_refine||{query_hash}"

    return InlineKeyboardMarkup([
        # Кнопка 1: Отправить улучшенный запрос в поиск
        [InlineKeyboardButton("Отправить в поиск", callback_data=send_data)],
        # Кнопка 2: Уточнить запрос еще раз
        [InlineKeyboardButton("Уточнить еще раз", callback_data=refine_data)],
        # Кнопка 3: Выбрать индекс вручную (НОВАЯ)
        [InlineKeyboardButton("Выбрать индекс вручную", callback_data="select_index_manual")],
        # Кнопка 4: Назад
        [InlineKeyboardButton("Назад", callback_data="menu_dialog")]
    ])
