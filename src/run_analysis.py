import logging
import threading
from openai import PermissionDeniedError as OpenAIPermissionError
from pyrogram import Client
from pyrogram.enums import ParseMode
import re
import asyncio
import aiohttp
from pathlib import Path
from docx import Document
import os

from config import ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2, ANTHROPIC_API_KEY_3, ANTHROPIC_API_KEY_4, ANTHROPIC_API_KEY_5, ANTHROPIC_API_KEY_6, ANTHROPIC_API_KEY_7, user_states
from utils import run_loading_animation, smart_send_text_unified, grouped_reports_to_string, get_username_from_chat
from db_handler.db import fetch_prompts_for_scenario_reporttype_building, fetch_prompt_by_name
from datamodels import mapping_report_type_names, mapping_building_names, REPORT_MAPPING, CLASSIFY_DESIGN, CLASSIFY_INTERVIEW
from menus import send_main_menu
from markups import interview_menu_markup, design_menu_markup, main_menu_markup, make_dialog_markup
from menu_manager import send_menu
from message_tracker import track_and_send
from analysis import analyze_methodology, classify_query, extract_from_chunk_parallel, aggregate_citations, classify_report_type, generate_db_answer, extract_from_chunk_parallel_async
from storage import save_user_input_to_db, build_reports_grouped, create_db_in_memory
from query_expander import expand_query
# Router Agent модули для интеллектуального выбора индекса
from relevance_evaluator import evaluate_report_relevance
from index_selector import select_most_relevant_index, INDEX_MAPPING, INDEX_DISPLAY_NAMES
from question_enhancer import enhance_question_for_index


def load_market_research_files(rag_name: str) -> str:
    """
    Загружает документы маркетингового исследования из файловой структуры (60 папок отелей)
    для создания RAG индекса.

    Функция сканирует директорию с 60 отелями РФ, извлекает TXT и DOCX файлы согласно конфигурации индекса,
    парсит их содержимое и форматирует с метаданными для последующего индексирования.

    Args:
        rag_name (str): Название индекса для загрузки. Допустимые значения:
            - "Отчеты по дизайну" - TXT отчеты из папки "Дизайн отчеты"
            - "Отчеты по обследованию" - TXT отчеты из папки "Обследование отчеты"
            - "Итоговые отчеты" - TXT отчеты из папки "Итоговые отчеты"
            - "Исходники дизайн" - DOCX файлы с "аудит" в названии (подпапка "Исходники")
            - "Исходники обследование" - DOCX файлы с "обследование" в названии (подпапка "Исходники")

    Returns:
        str: Объединенный текст всех найденных документов с метаданными в формате:
            # Отель: <hotel_name>
            # Файл: <filename>

            <file_text>

            ================================================================================

    Raises:
        FileNotFoundError: Если базовая директория MarketResearch/RF не существует
        ValueError: Если передано неизвестное значение rag_name

    Examples:
        Локальный путь: C:/Users/l0934/Projects/VoxPersona/rag_indices/MarketResearch/RF/
        Серверный путь: /app/rag_indices/MarketResearch/RF/

        >>> content = load_market_research_files("Отчеты по дизайну")
        >>> print(f"Загружено {len(content)} символов из отчетов по дизайну")

    Notes:
        - Обрабатывает .txt файлы (отчеты) и .docx файлы (исходники)
        - Использует кроссплатформенный pathlib.Path
        - Автоматически определяет локальный/серверный режим
        - Пропускает файлы с ошибками чтения (логирует, не прерывает процесс)
        - Проверяет существование папок и наличие документов
    """

    # Автоопределение базового пути (локально vs сервер)
    # Проверка: если существует директория /app/rag_indices И это не Windows
    if os.path.exists("/app/rag_indices/MarketResearch") and os.name != 'nt':
        base_path = Path("/app/rag_indices/MarketResearch/RF")
        logging.info("🌐 Режим: СЕРВЕР - используется путь /app/rag_indices")
    else:
        base_path = Path("C:/Users/l0934/Projects/VoxPersona/rag_indices/MarketResearch/RF")
        logging.info("💻 Режим: ЛОКАЛЬНО - используется путь C:/Users/l0934/Projects/VoxPersona")

    # Проверка существования базовой директории
    if not base_path.exists():
        error_msg = f"❌ Базовая директория не найдена: {base_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)

    logging.info(f"📂 Базовая директория найдена: {base_path}")

    # Маппинг индексов на критерии поиска
    rag_configs = {
        "Отчеты по дизайну": {
            "folder_pattern": "Дизайн отчеты",
            "file_pattern": None,
            "search_type": "folder"
        },
        "Отчеты по обследованию": {
            "folder_pattern": "Обследование отчеты",
            "file_pattern": None,
            "search_type": "folder"
        },
        "Итоговые отчеты": {
            "folder_pattern": "Итоговые отчеты",
            "file_pattern": None,
            "search_type": "folder"
        },
        "Исходники дизайн": {
            "folder_pattern": None,
            "file_pattern": "аудит",  # Регистронезависимо
            "search_type": "file"
        },
        "Исходники обследование": {
            "folder_pattern": None,
            "file_pattern": "обследование",  # Регистронезависимо
            "search_type": "file"
        },
    }

    # Получение конфигурации для указанного индекса
    if rag_name not in rag_configs:
        available_rags = ', '.join(rag_configs.keys())
        error_msg = f"❌ Неизвестный RAG индекс: '{rag_name}'. Доступные: {available_rags}"
        logging.error(error_msg)
        raise ValueError(error_msg)

    config = rag_configs[rag_name]
    logging.info(f"🔍 Конфигурация для '{rag_name}': {config}")

    # Получение списка папок отелей (60 папок)
    hotel_folders = [folder for folder in base_path.iterdir() if folder.is_dir()]
    logging.info(f"🏨 Найдено папок отелей: {len(hotel_folders)}")

    if not hotel_folders:
        logging.warning(f"⚠️ Не найдено ни одной папки отеля в {base_path}")
        return ""

    # Коллекция для всех текстов
    all_texts = []
    files_processed = 0
    files_skipped = 0

    # Итерация по всем папкам отелей
    for hotel_folder in hotel_folders:
        hotel_name = hotel_folder.name
        logging.debug(f"📁 Обработка отеля: {hotel_name}")

        # Определение списка файлов для обработки в зависимости от типа поиска
        files_to_process = []

        if config["search_type"] == "folder":
            # Поиск по папке (Отчеты по дизайну, Обследованию, Итоговые)
            target_folder = hotel_folder / config["folder_pattern"]

            if not target_folder.exists():
                logging.debug(f"⏭️  Пропуск {hotel_name}: папка '{config['folder_pattern']}' не найдена")
                files_skipped += 1
                continue

            # Собираем все TXT файлы из целевой папки (отчеты хранятся в TXT формате)
            files_to_process = list(target_folder.glob("*.txt"))

        elif config["search_type"] == "file":
            # Поиск по паттерну в названии файла (Исходники дизайн/обследование)
            pattern = config["file_pattern"].lower()

            # Поиск в подпапке "Исходники/" (не в корне отеля!)
            sources_folder = hotel_folder / "Исходники"

            if not sources_folder.exists():
                logging.debug(f"⏭️  Пропуск {hotel_name}: папка 'Исходники' не найдена")
                files_skipped += 1
                continue

            # Поиск DOCX файлов с паттерном в названии в подпапке Исходники
            files_to_process = [
                file_path for file_path in sources_folder.glob("*.docx")
                if pattern in file_path.name.lower()
            ]

        # Обработка найденных файлов (TXT или DOCX)
        if not files_to_process:
            logging.debug(f"⏭️  Пропуск {hotel_name}: файлы не найдены")
            files_skipped += 1
            continue

        for file_path in files_to_process:
            try:
                # Парсинг файла в зависимости от расширения
                if file_path.suffix == '.docx':
                    # DOCX файлы (исходники) - парсинг через python-docx
                    doc = Document(file_path)
                    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
                    file_text = "\n".join(paragraphs)
                elif file_path.suffix == '.txt':
                    # TXT файлы (отчеты) - чтение как обычный текстовый файл
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_text = f.read()
                else:
                    # Пропуск файлов с неизвестным расширением
                    logging.debug(f"⏭️  Пропуск файла с неизвестным расширением: {file_path.name}")
                    continue

                # Проверка на пустоту
                if not file_text.strip():
                    logging.debug(f"⚠️ Файл пуст: {file_path.name} ({hotel_name})")
                    continue

                # Форматирование с метаданными
                formatted_text = (
                    f"# Отель: {hotel_name}\n"
                    f"# Файл: {file_path.name}\n\n"
                    f"{file_text}\n\n"
                    f"{'='*80}\n\n"
                )

                all_texts.append(formatted_text)
                files_processed += 1
                logging.debug(f"✅ Обработан файл: {file_path.name} ({hotel_name}), символов: {len(file_text)}")

            except Exception as e:
                # Логирование ошибки без прерывания процесса
                logging.error(f"❌ Ошибка при чтении файла {file_path.name} ({hotel_name}): {e}")
                continue

    # Объединение всех текстов
    combined_content = "".join(all_texts)

    # Итоговый отчет
    logging.info(
        f"✅ Завершена загрузка для '{rag_name}': "
        f"обработано файлов: {files_processed}, "
        f"пропущено отелей: {files_skipped}, "
        f"итоговый объем: {len(combined_content)} символов"
    )

    if not combined_content:
        logging.warning(f"⚠️ Для индекса '{rag_name}' не найдено ни одного документа!")

    return combined_content


def load_all_report_descriptions() -> dict[str, str]:
    """
    Загружает все 22 файла описаний отчетов из Description/Report content/.

    Рекурсивно обходит директорию Description/Report content/, читает все .md файлы
    и создает словарь с короткими именами отчетов в качестве ключей.

    Returns:
        dict[str, str]: Словарь {короткое_имя_отчета: содержимое_файла}
        Пример: {
            "Структурированный_отчет_аудита": "# Описание отчета...",
            "Общие_факторы": "# Общие факторы...",
            ...
        }

    Raises:
        FileNotFoundError: Если директория Description/Report content/ не существует
        RuntimeError: Если загружено не 22 файла (ожидаемое количество)

    Example:
        >>> descriptions = load_all_report_descriptions()
        >>> len(descriptions)
        22
        >>> "Краткое резюме" in descriptions
        True
    """
    # Определение корневой директории проекта (локально vs сервер)
    # Проверяем платформу: на Windows всегда используем локальный путь
    import sys
    is_windows = sys.platform == "win32"
    server_path = Path("/home/voxpersona_user/VoxPersona")

    if not is_windows and server_path.exists():
        base_path = server_path
        logging.info("🌐 Сервер: используем путь /home/voxpersona_user/VoxPersona")
    else:
        base_path = Path(__file__).parent.parent
        logging.info(f"💻 Локально: используем путь {base_path}")

    # Путь к директории с описаниями отчетов
    descriptions_dir = base_path / "Description" / "Report content"

    if not descriptions_dir.exists():
        error_msg = f"Директория с описаниями отчетов не найдена: {descriptions_dir}"
        logging.error(f"❌ {error_msg}")
        raise FileNotFoundError(error_msg)

    logging.info(f"📂 Загрузка описаний отчетов из: {descriptions_dir}")

    # Маппинг длинных названий → короткие имена
    name_mappings = {
        "Краткое резюме комплексного обследования": "Краткое резюме",
        "Ощущения от отеля": "Ощущения",
        "Заполняемость_и_бронирование": "Заполняемость",
        "Итоговый_отчет": "Итоговый",
        "Отдых_и_восстановление": "Отдых",
        "Рекомендации_по_улучшению": "Рекомендации",
        "Сильные стороны дизайна": "Сильные стороны",
        "Недостатки_дизайна": "Недостатки",
        "Ожидания_и_реальность": "Ожидания",
        "Противоречия_концепции_и_дизайна": "Противоречия",
        "Востребованность_гостиничного_хозяйства": "Востребованность",
        "Обустройство_гостиничного_хозяйства": "Обустройство",
        "Качество_инфраструктуры": "Качество инфраструктуры",
    }

    def extract_short_name(filename: str) -> str:
        """
        Извлекает короткое имя отчета из имени файла.

        Args:
            filename: Имя файла (например, "Содержание_отчетов_Итоговый_отчет.md")

        Returns:
            str: Короткое имя (например, "Итоговый")
        """
        # Убираем расширение .md
        name = filename.replace(".md", "")

        # Убираем префиксы (разные варианты написания)
        prefixes = [
            "Содержание_отчетов_",
            "Содержание отчетов_",
            "Содержание отчетов ",
            "Главная_"
        ]
        for prefix in prefixes:
            name = name.replace(prefix, "")

        # Применяем маппинг для длинных названий
        for long_name, short_name in name_mappings.items():
            if long_name in name:
                return short_name

        return name

    # Словарь для хранения описаний
    descriptions = {}

    # Рекурсивный обход всех .md файлов
    md_files = list(descriptions_dir.rglob("*.md"))
    logging.info(f"🔍 Найдено {len(md_files)} .md файлов")

    for file_path in md_files:
        try:
            # Извлекаем короткое имя
            short_name = extract_short_name(file_path.name)

            # Читаем содержимое файла
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Сохраняем в словарь
            descriptions[short_name] = content
            logging.debug(f"  ✅ {file_path.name} → '{short_name}' ({len(content)} символов)")

        except Exception as e:
            logging.error(f"  ❌ Ошибка при чтении {file_path.name}: {e}")
            # Не прерываем процесс, продолжаем загрузку остальных файлов
            continue

    # Валидация: должно быть ровно 22 файла
    expected_count = 22
    actual_count = len(descriptions)

    if actual_count != expected_count:
        error_msg = (
            f"Загружено {actual_count} описаний, ожидалось {expected_count}. "
            f"Загруженные: {sorted(descriptions.keys())}"
        )
        logging.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

    logging.info(f"✅ Успешно загружено {actual_count} описаний отчетов")
    logging.debug(f"📋 Загруженные отчеты: {sorted(descriptions.keys())}")

    return descriptions


def init_rags(existing_rags: dict | None = None) -> dict:
    rags = existing_rags.copy() if existing_rags else {}

    # Логируем какие индексы уже загружены
    if rags:
        logging.info(f"📦 Получены pre-loaded RAG индексы: {list(rags.keys())}")
    else:
        logging.info("📦 Pre-loaded RAG индексов нет, создаем все с нуля")

    # === РАСШИРЕННАЯ КОНФИГУРАЦИЯ: 9 существующих + 5 новых МИ индексов ===
    rag_configs = [
        # Существующие индексы (PostgreSQL)
        ("Интервью", None, None),
        ("Дизайн", None, None),
        ("Интервью", "Оценка методологии интервью", None),
        ("Интервью", "Отчет о связках", None),
        ("Интервью", "Общие факторы", None),
        ("Интервью", "Факторы в этом заведении", None),
        ("Дизайн", "Оценка методологии аудита", None),
        ("Дизайн", "Соответствие программе аудита", None),
        ("Дизайн", "Структурированный отчет аудита", None),

        # === НОВЫЕ ИНДЕКСЫ МИ (Маркетинговое исследование) ===
        (None, "Отчеты по дизайну", "market_research"),
        (None, "Отчеты по обследованию", "market_research"),
        (None, "Итоговые отчеты", "market_research"),
        (None, "Исходники дизайн", "market_research"),
        (None, "Исходники обследование", "market_research"),
    ]

    for config in rag_configs:
        # === ИЗМЕНЕНИЕ: Теперь распаковываем все 3 элемента tuple ===
        scenario_name, report_type, source_type = config

        try:
            rag_name = report_type if report_type else scenario_name
            if rag_name in rags:
                logging.info(f"⏭️  Пропуск {rag_name}: уже загружен с диска")
                continue
            logging.info(f"🏗️  Создание индекса {rag_name}...")

            # === ВЫБОР ИСТОЧНИКА ДАННЫХ ===
            if source_type == "market_research":
                # МИ индексы: загрузка из файловой структуры (60 отелей)
                content_str = load_market_research_files(rag_name)
                if not content_str:
                    logging.warning(f"⚠️ Пропуск {rag_name}: нет данных МИ")
                    continue
            else:
                # Существующие индексы: загрузка из PostgreSQL
                # ✅ ФИЛЬТРАЦИЯ МЕТОДОЛОГИЧЕСКИХ ОТЧЕТОВ:
                # Для индексов "Интервью" и "Дизайн" исключаем методологические отчеты
                # ✅ ПРОБЛЕМА #5: Добавлен type hint list[str] | None
                exclude_types: list[str] | None = None

                if rag_name == "Интервью":
                    exclude_types = ["Оценка методологии интервью"]
                    logging.info(f"📋 Индекс 'Интервью': исключаем типы {exclude_types}")
                elif rag_name == "Дизайн":
                    exclude_types = [
                        "Оценка методологии аудита",
                        "Соответствие программе аудита"
                    ]
                    logging.info(f"📋 Индекс 'Дизайн': исключаем типы {exclude_types}")

                content = build_reports_grouped(
                    scenario_name=scenario_name,
                    report_type=report_type,
                    exclude_report_types=exclude_types  # ✅ Передаем список для исключения
                )
                content_str = grouped_reports_to_string(content)
            # === КОНЕЦ ВЫБОРА ИСТОЧНИКА ===

            # === РАСШИРЕННОЕ УСЛОВИЕ: 7 FAISS индексов (2 старых + 5 новых МИ) ===
            if rag_name in ["Интервью", "Дизайн", "Отчеты по дизайну", "Отчеты по обследованию", "Итоговые отчеты", "Исходники дизайн", "Исходники обследование"]:
                rag_db = create_db_in_memory(content_str)
                rags[rag_name] = rag_db
                logging.info(f"✅ FAISS индекс для {rag_name} сформирован успешно")
            else:
                rags[rag_name] = content_str
                logging.info(f"✅ Текстовый индекс для {rag_name} сформирован успешно")
        except Exception as e:
            logging.error(f"Ошибка при создании рага для {config}: {e}")
            continue  # Продолжить со следующим индексом вместо return

    # Проверка, были ли созданы хотя бы какие-то индексы
    if not rags:
        logging.warning("Не удалось создать ни одного RAG индекса!")

    return rags

def run_fast_search(text: str, rag) -> str:
    logging.info("Формирование ответа")
    answer = generate_db_answer(text, rag)
    return answer

def run_deep_search(content: str, text: str, chat_id: int, app: Client, category: str) -> str:
    api_keys = [ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2, ANTHROPIC_API_KEY_3, ANTHROPIC_API_KEY_4, ANTHROPIC_API_KEY_5, ANTHROPIC_API_KEY_6, ANTHROPIC_API_KEY_7]

    chunks = re.split(r'^# Чанк transcription_id \d+', content, flags=re.MULTILINE)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

    logging.info(f"Получено {len(chunks)} чанков для сценария {category}")

    if not chunks:
        app.send_message(chat_id, f"Ошибка: не найдены отчеты для категории '{category}'")
        return

    extract_prompt = fetch_prompt_by_name(prompt_name="prompt_extract")
    aggregation_prompt = fetch_prompt_by_name(prompt_name="prompt_agg")

    # === Асинхронный вызов extract_from_chunk_parallel_async ===
    async def main():
        async with aiohttp.ClientSession() as session:
            return await extract_from_chunk_parallel_async(
                text=text,
                chunks=chunks,
                extract_prompt=extract_prompt,
                api_keys=api_keys,
                session=session
            )

    try:
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(main())
    except RuntimeError as e:
        results = asyncio.run(main())

    citations = [r for r in results if r != "##not_found##" and not r.startswith("[ERROR]")]

    if citations:
        aggregated_answer = aggregate_citations(
            text=text,
            citations=citations,
            aggregation_prompt=aggregation_prompt
        )
    else:
        aggregated_answer = "Извините, по вашему запросу ничего не найдено в доступных отчетах."

    return aggregated_answer

async def show_expanded_query_menu(
    chat_id: int,
    app: Client,
    original: str,
    expanded: str,
    conversation_id: str,
    deep_search: bool,
    refine_count: int = 0,  # ✅ ШАГ 2: Добавлен параметр refine_count
    selected_index: str | None = None  # ✅ ФАЗА 3: Добавлен параметр selected_index (Router Agent)
):
    """
    Показывает оригинальный и улучшенный вопрос пользователю.

    ФАЗА 4: Обновлено - использует make_query_expansion_markup()

    Args:
        chat_id: ID чата Telegram
        app: Pyrogram клиент
        original: Исходный вопрос пользователя
        expanded: Улучшенный вопрос
        conversation_id: ID мультичата (может быть None)
        deep_search: True = глубокое исследование, False = быстрый поиск
        refine_count: Текущее количество попыток уточнения (защита от зацикливания)
        selected_index: Вручную выбранный индекс (None = автовыбор Router Agent)
    """
    # FIX (2025-11-09): Защита от MESSAGE_TOO_LONG
    # ЗАЧЕМ: Telegram лимит 4096 символов на текстовое сообщение
    # ПОЧЕМУ 3900: Безопасный лимит с запасом для markdown форматирования и кнопок (4096 - 196 overhead)
    # TODO (P2): В будущем добавить кнопку "Показать полностью" → отправка файлом при обрезке
    # Связь: TASKS/2025-11-09_query_expansion_errors/inspection.md (РЕШЕНИЕ 3 - гибридный подход)

    MAX_TELEGRAM_TEXT = 3900  # Telegram limit 4096 - overhead для форматирования
    expanded_display = expanded

    # Проверяем длину улучшенного вопроса
    if len(expanded) > MAX_TELEGRAM_TEXT:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"[Query Expansion] Expanded question too long: {len(expanded)} chars, "
            f"truncating to {MAX_TELEGRAM_TEXT} chars. Chat ID: {chat_id}"
        )
        # Обрезаем с предупреждением для пользователя
        expanded_display = (
            expanded[:MAX_TELEGRAM_TEXT] +
            "\n\n⚠️ _(Вопрос обрезан из-за ограничения длины Telegram)_"
        )

    # Формируем текст сообщения с обработанным expanded_question
    # === ROUTER AGENT: Отображение выбранного индекса ===
    # Если пользователь вручную выбрал индекс - показываем его
    index_info = ""
    if selected_index:
        index_display_name = INDEX_DISPLAY_NAMES.get(selected_index, selected_index)
        index_info = f"🎯 **Поиск будет в индексе:** {index_display_name}\n\n"

    text = (
        f"📝 **Ваш вопрос:**\n"
        f"_{original}_\n\n"
        f"🔍 **Улучшенный вопрос:**\n"
        f"*{expanded_display}*\n\n"
        f"{index_info}Отправить улучшенный вопрос в {'глубокое исследование' if deep_search else 'быстрый поиск'}?"
    )


    # Полноценная клавиатура с hash и user_states
    from markups import make_query_expansion_markup
    markup = make_query_expansion_markup(
        original_question=original,
        expanded_question=expanded,  # Передаем ПОЛНЫЙ вопрос в callback_data
        conversation_id=conversation_id or "",
        deep_search=deep_search,
        refine_count=refine_count,  # ✅ ШАГ 2: Передаем счетчик в markup
        selected_index=selected_index  # ✅ ФАЗА 3: Передача выбранного индекса
    )

    # Отправляем меню с защитой от MESSAGE_TOO_LONG
    try:
        await send_menu(chat_id, app, text, markup)
    except Exception as e:
        # Если всё равно превышен лимит (например, из-за original вопроса) - используем fallback
        if "MESSAGE_TOO_LONG" in str(e):
            logger = logging.getLogger(__name__)
            logger.error(
                f"[Query Expansion] MESSAGE_TOO_LONG even after truncation! "
                f"Text length: {len(text)} chars. Chat ID: {chat_id}. "
                f"Sending minimal fallback message."
            )
            # Минимальное сообщение-fallback
            fallback_text = (
                f"✅ Вопрос улучшен.\n\n"
                f"Отправить в {'глубокое исследование' if deep_search else 'быстрый поиск'}?"
            )
            await send_menu(chat_id, app, fallback_text, markup)
        else:
            # Прокидываем другие исключения наверх
            raise


async def run_dialog_mode(message, app: Client, rags: dict, deep_search: bool = False, conversation_id: str = None, skip_expansion: bool = False):
    # Извлекаем данные из message
    text = message.text
    chat_id = message.chat.id

    # ============ НАЧАЛО НОВОГО КОДА: QUERY EXPANSION ============
    # FIX (2025-11-09 Session 6): Добавлена поддержка пропуска expand_query
    # ЗАЧЕМ: При нажатии "Отправить в поиск" вопрос УЖЕ улучшен, повторный expand не нужен
    # БЫЛО: Двойное улучшение → бесконечный цикл меню
    # СТАЛО: skip_expansion=True → прямой переход к RAG поиску
    # Связь: TASKS/2025-11-09_query_expansion_errors/inspection.md (Session 6 - КОРЕНЬ ПРОБЛЕМЫ)

    if not skip_expansion:
        # Улучшение вопроса через Query Expansion
        expansion_result = expand_query(text)

        # Проверка: использован ли descry.md и улучшен ли вопрос
        if expansion_result["used_descry"] and expansion_result["expanded"] != text:
            # Показать пользователю улучшенный вопрос с опциями
            await show_expanded_query_menu(
                chat_id=chat_id,
                app=app,
                original=expansion_result["original"],
                expanded=expansion_result["expanded"],
                conversation_id=conversation_id,
                deep_search=deep_search,
                refine_count=0  # ✅ ШАГ 3: Первая попытка - счетчик = 0
            )
            return  # Ожидаем callback от пользователя

        # Если улучшение не применено - используем исходный вопрос
        text_to_search = expansion_result.get("expanded", text)
    else:
        # Пропуск Query Expansion - используем вопрос как есть
        # Этот путь используется при skip_expansion=True (например, из handle_expand_send)
        text_to_search = text

    # ============ КОНЕЦ НОВОГО КОДА: QUERY EXPANSION ============

    # ============================================================
    # Проверка ручного выбора индекса пользователем
    # ============================================================
    # Если пользователь вручную выбрал индекс через UI - используем его вместо Router Agent
    user_selected_index = user_states.get(chat_id, {}).get("selected_index")

    if user_selected_index:
        # Пользователь вручную выбрал индекс - пропускаем автоматический Router Agent
        logging.info(f"[Manual Index] Обнаружен ручной выбор индекса: {user_selected_index}")
        logging.info(f"[Manual Index] Пропускаем автоматический Router Agent")

        try:
            # Загружаем описания отчетов для улучшения вопроса
            report_descriptions = load_all_report_descriptions()
            logging.info(f"[Manual Index] Загружено {len(report_descriptions)} описаний отчетов")

            # Улучшаем вопрос для ВЫБРАННОГО индекса
            enhanced_question = enhance_question_for_index(
                text_to_search,
                user_selected_index,
                report_descriptions
            )
            logging.info(f"[Manual Index] Вопрос улучшен для индекса '{user_selected_index}'")
            logging.debug(f"[Manual Index] Улучшенный вопрос: {enhanced_question[:150]}...")

            # Обновляем запрос на улучшенный
            text_to_search = enhanced_question

            # Маппинг на RAG индекс (Router Agent использует транслитерацию, rags - русские имена)
            ROUTER_TO_RAG_MAPPING = {
                "Dizayn": "Дизайн",
                "Intervyu": "Интервью",
                "Iskhodniki_dizayn": "Исходники дизайн",
                "Iskhodniki_obsledovanie": "Исходники обследование",
                "Itogovye_otchety": "Итоговые отчеты",
                "Otchety_po_dizaynu": "Отчеты по дизайну",
                "Otchety_po_obsledovaniyu": "Отчеты по обследованию"
            }

            scenario_name = ROUTER_TO_RAG_MAPPING.get(user_selected_index, user_selected_index)
            logging.info(f"[Manual Index] Маппинг индекса: '{user_selected_index}' → '{scenario_name}'")

            # Проверка что выбранный индекс существует в rags
            if scenario_name not in rags:
                raise ValueError(f"Индекс '{scenario_name}' не найден в доступных rags: {list(rags.keys())}")

            # Очищаем ручной выбор из user_states (использовали один раз)
            user_states[chat_id].pop("selected_index", None)
            logging.info(f"[Manual Index] ✅ Ручной выбор использован и очищен")

            # Пропускаем блок Router Agent ниже (переменная scenario_name уже установлена)
            skip_router_agent = True

        except Exception as e:
            logging.error(f"[Manual Index] ❌ Ошибка при обработке ручного выбора: {e}")
            logging.warning(f"[Manual Index] Откат к автоматическому Router Agent")
            skip_router_agent = False
            # При ошибке - удаляем невалидный ручной выбор
            user_states.get(chat_id, {}).pop("selected_index", None)
    else:
        # Ручной выбор не обнаружен - используем автоматический Router Agent
        skip_router_agent = False

    # ============================================================
    # Router Agent: выбор индекса на основе релевантности отчетов
    # ============================================================
    if not skip_router_agent:
        try:
            logging.info("[Router] Запуск Router Agent для выбора оптимального индекса...")

            # Этап 1: Загрузка описаний всех отчетов (внутри try для обработки ошибок)
            logging.info("[Router] Загрузка описаний 22 отчетов...")
            report_descriptions = load_all_report_descriptions()
            logging.debug(f"[Router] Загружено {len(report_descriptions)} описаний отчетов")

            # Этап 2: Оценка релевантности всех отчетов к запросу пользователя
            logging.info(f"[Router] Оценка релевантности отчетов для запроса: {text_to_search[:100]}...")
            report_relevance = await evaluate_report_relevance(text_to_search, report_descriptions)
            logging.debug(f"[Router] Результаты оценки релевантности: {report_relevance}")

            # Этап 3: Выбор наиболее релевантного индекса
            logging.info("[Router] Выбор наиболее релевантного индекса на основе оценок...")
            selected_index = select_most_relevant_index(report_relevance, INDEX_MAPPING)
            logging.info(f"[Router] ✅ Выбран индекс: {selected_index}")

            # Этап 4: Улучшение вопроса для выбранного индекса
            logging.info(f"[Router] Улучшение вопроса для индекса '{selected_index}'...")
            enhanced_question = enhance_question_for_index(text_to_search, selected_index, report_descriptions)  # ИСПРАВЛЕНО: убран await (sync функция)
            logging.info(f"[Router] Улучшенный вопрос: {enhanced_question[:150]}...")

            # Обновление запроса и выбор RAG индекса
            text_to_search = enhanced_question

            # ИСПРАВЛЕНИЕ #1: Маппинг имен индексов Router Agent → rags
            # Router Agent использует транслитерированные имена (Dizayn, Intervyu),
            # а rags использует русские имена (Дизайн, Интервью)
            ROUTER_TO_RAG_MAPPING = {
                "Dizayn": "Дизайн",
                "Intervyu": "Интервью",
                "Iskhodniki_dizayn": "Исходники дизайн",
                "Iskhodniki_obsledovanie": "Исходники обследование",
                "Itogovye_otchety": "Итоговые отчеты",
                "Otchety_po_dizaynu": "Отчеты по дизайну",
                "Otchety_po_obsledovaniyu": "Отчеты по обследованию"
            }

            scenario_name = ROUTER_TO_RAG_MAPPING.get(selected_index, selected_index)
            logging.info(f"[Router] Маппинг индекса: '{selected_index}' → '{scenario_name}'")

            # Проверка что выбранный индекс существует в rags
            if scenario_name not in rags:
                raise ValueError(f"Индекс '{scenario_name}' не найден в доступных rags: {list(rags.keys())}")

            rag = rags[scenario_name]

            # ИСПРАВЛЕНИЕ #3: Определение category для совместимости с остальным кодом
            category = scenario_name  # Используем русское название индекса как категорию
            logging.info(f"[Router] Используется RAG индекс: {scenario_name}, категория: {category}")

        except Exception as e:
            # Fallback: откат к старой системе классификации при любой ошибке
            logging.warning(f"[Router] ⚠️ Ошибка Router Agent: {e}")
            logging.warning("[Router] Откат к fallback-системе классификации (classify_query)...")

            try:
                # Старая система классификации
                category = classify_query(text_to_search)
                logging.info(f"[Fallback] Определен сценарий: {category}")

                if category.lower() == "дизайн":
                    scenario_name = "Дизайн"
                elif category.lower() == "интервью":
                    scenario_name = "Интервью"
                else:
                    raise ValueError(f"Fallback classify_query не смог определить сценарий: {category}")

                rag = rags[scenario_name]
                # ИСПРАВЛЕНИЕ: category уже определен выше (classify_query вернул значение)
                logging.info(f"[Fallback] ✅ Используется RAG индекс: {scenario_name}, категория: {category}")

            except Exception as fallback_error:
                logging.error(f"[Fallback] ❌ Критическая ошибка в fallback-системе: {fallback_error}")
                raise ValueError(f"Не удалось определить сценарий ни через Router Agent, ни через fallback: {fallback_error}")

    # Формирование контента отчетов для выбранного сценария
    try:
        content = build_reports_grouped(scenario_name=scenario_name, report_type=None)
        content = grouped_reports_to_string(content)
    except Exception as content_error:
        logging.error(f"❌ Ошибка при формировании контента отчетов: {content_error}")
        content = ""  # Fallback на пустой контент

        # Получаем username
        username = await get_username_from_chat(chat_id, app)

        # Сохраняем вопрос пользователя в conversations (если передан conversation_id)
        # ВАЖНО: Сохраняем ИСХОДНЫЙ вопрос пользователя, а не улучшенный
        if conversation_id:
            from conversation_manager import conversation_manager
            from conversations import ConversationMessage
            from datetime import datetime

            user_message = ConversationMessage(
                timestamp=datetime.now().isoformat(),
                message_id=message.id,  # Используем реальный Telegram message ID
                type="user_question",
                text=text,  # Сохраняем ИСХОДНЫЙ текст пользователя
                tokens=0,  # Токены вопроса не считаем
                sent_as=None,
                file_path=None,
                search_type="deep" if deep_search else "fast"
            )

            conversation_manager.add_message(
                user_id=chat_id,
                conversation_id=conversation_id,
                message=user_message
            )

        if deep_search:
            # Отправляем системное сообщение-статус через MessageTracker
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="Запущено Глубокое Исследование",
                message_type="status_message"
            )
            logging.info("Запущено Глубокое исследование")

            # report_type_code = classify_report_type(text_to_search, prompt_name=prompt_name)
            # report_type = CLASSIFY_INTERVIEW[report_type_code] if scenario_name == "Интервью" else CLASSIFY_DESIGN[report_type_code]
            # content = rags[report_type]
            # logging.info(f"Тип отчета: {report_type}")

            # Используем УЛУЧШЕННЫЙ вопрос для глубокого поиска
            answer = run_deep_search(content, text=text_to_search, chat_id=chat_id, app=app, category=category)
        else:
            # Отправляем системное сообщение-статус через MessageTracker
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="Запущен быстрый поиск",
                message_type="status_message"
            )
            logging.info("Запущен быстрый поиск")

            # content = build_reports_grouped(scenario_name=scenario_name, report_type=None)
            # content = grouped_reports_to_string(content)
            # rag = rags[scenario_name]

            # Используем УЛУЧШЕННЫЙ вопрос для быстрого поиска
            answer = run_fast_search(text=text_to_search, rag=rag)

        formatted_response = f"*Категория запроса:* {category}\n\n{answer}"

        # Используем умную отправку с автоматическим выбором между сообщением и MD файлом
        # В вопросе отображаем ИСХОДНЫЙ текст пользователя
        await smart_send_text_unified(
            text=formatted_response,
            chat_id=chat_id,
            app=app,
            username=username,
            question=text,  # Отображаем ИСХОДНЫЙ вопрос пользователя
            search_type="deep" if deep_search else "fast",
            parse_mode=ParseMode.MARKDOWN,
            conversation_id=conversation_id
        )

        max_log_length = 3000
        answer_to_log = answer if len(answer) <= max_log_length else answer[:max_log_length] + "... [обрезано]"
        logging.info(f"Ответ отправлен | Ответ: {answer_to_log}")

    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        logging.error(f"Произошла ошибка: {e}", exc_info=True)
        await app.send_message(chat_id, error_message) #TODO: не забыть удалить в продакшене
    finally:
        # После ответа показываем меню выбора режима
        await send_menu(
            chat_id=chat_id,
            app=app,
            text="Какую информацию вы хотели бы получить?",
            reply_markup=make_dialog_markup()
        )

async def run_analysis_pass(
    chat_id: int,
    source_text: str,
    label: str,
    scenario_name: str,
    data: dict,
    prompts: list[tuple[str, int]],
    app: Client,
    transcription_text: str,
    is_show_analysis: bool=True,
    conversation_id: str = None
) -> str:
    """
    Один «проход» анализа: крутит спиннер, вызывает analyze_methodology,
    возвращает (и сразу отправляет) результат пользователю.
    """
    # Отправляем системное сообщение-статус через MessageTracker
    msg_ = await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"⏳ Анализ: {label}...",
        message_type="status_message"
    )
    st_ev = threading.Event()
    sp_th = threading.Thread(target=run_loading_animation, args=(chat_id, msg_.id, st_ev, app))
    sp_th.start()

    try:
        audit_text = analyze_methodology(source_text, prompts)

        if is_show_analysis:
            # Получаем username
            username = await get_username_from_chat(chat_id, app)

            # Используем умную отправку с автоматическим выбором между сообщением и MD файлом
            await smart_send_text_unified(
                text=audit_text,
                chat_id=chat_id,
                app=app,
                username=username,
                question=f"Анализ методологии: {label}",
                search_type="analysis",
                parse_mode=None,
                conversation_id=conversation_id
            )

            app.edit_message_text(chat_id, msg_.id, f"✅ Завершено: {label}")

        # Сохраняем в БД (теперь всё — сотрудник, place_name, city(если дизайн), building).
        save_user_input_to_db(transcript=transcription_text, scenario_name=scenario_name, data=data, label=label, audit_text=audit_text)
        logging.info("Отчёт успешно сохранен в БД")
    except OpenAIPermissionError:
        logging.exception("Неверный API_KEY?")
        app.edit_message_text(chat_id, msg_.id, "🚫 Ошибка: LLM недоступна (ключ/регион).")
    except Exception as e:
        logging.exception("Ошибка анализа")
        app.edit_message_text(chat_id, msg_.id, f"❌ Ошибка: {e}")
        audit_text = ""
    finally:
        st_ev.set()
        sp_th.join()
        try:
            app.delete_messages(chat_id, msg_.id)
        except:
            pass

    return audit_text

async def run_analysis_with_spinner(chat_id: int, processed_texts: dict[int, str], data: dict, app: Client, callback_data: str, transcription_text: str):
    """
    Показывает «спиннер» и запускает функцию анализа.
    Подгружает промпты из БД (scenario, report_type, building).
    """
    label = REPORT_MAPPING[callback_data]
    building_name = data.get("type_of_location", "")
    txt = processed_texts.get(chat_id, "")

    if not txt:
        app.send_message(chat_id, "Нет текста для анализа. Сначала загрузите/обработайте аудио/текст.")
        return

    # Определяем scenario_name для примера
    if "int_" in callback_data:
        scenario_name = "Интервью"
    elif "design" in callback_data:
        scenario_name = "Дизайн"
    else:
        scenario_name = ""

    report_type_desc = mapping_report_type_names.get(callback_data, label)

    prompts_list = []
    if not building_name:
        building_name = mapping_building_names[building_name]

    if scenario_name and building_name and report_type_desc:
        try:
            prompts_list = fetch_prompts_for_scenario_reporttype_building(
                scenario_name=scenario_name,
                report_type_desc=report_type_desc,
                building_type=building_name
            )
        except Exception as e:
            logging.exception("Ошибка при выборке промптов")

    json_prompts = [(p, rp) for (p, rp, is_json_prompt) in prompts_list if is_json_prompt]
    ordinary_prompts = [(p, rp) for (p, rp, is_json_prompt) in prompts_list if not is_json_prompt]

    if scenario_name == "Интервью" and report_type_desc == "Общие факторы":
        logging.info("Готовлю два отчёта")
        # prompts_list -> [(prompt_text, run_part, is_json_prompts), ...]

        # Сгруппируем. Например, part1 = все промпты, где run_part=1
        #               part2 = все промпты, где run_part=2
        part1 = [(p, rp) for (p, rp) in ordinary_prompts if rp == 1]
        part2 = [(p, rp) for (p, rp) in ordinary_prompts if rp == 2]

        # Если run_part не заполнен — part1 или part2 будут пусты,
        # можно подстраховаться проверкой. В простом случае:
        if part1:
            # Первый проход
            result1 = await run_analysis_pass(
                chat_id=chat_id,
                source_text=txt,
                label=label,
                scenario_name=scenario_name,
                data=data,
                app=app,
                prompts=part1,
                is_show_analysis=False,
                transcription_text=transcription_text
            )

            logging.info("Отчет с общими факторами сформирован")
            # Вывести результат пользователю (уже внутри run_analysis_pass)
        if part2:
            # Второй проход
            result2 = await run_analysis_pass(
                chat_id=chat_id,
                source_text=txt,
                label=label,
                scenario_name=scenario_name,
                data=data,
                app=app,
                prompts=part2,
                is_show_analysis=False,
                transcription_text=transcription_text
            )

            logging.info("Отчет с неизученными факторами сформирован")
            # Вывести результат пользователю (уже внутри run_analysis_pass)
        json_result = await run_analysis_pass(
            chat_id=chat_id,
            source_text=result1 + "\n" + result2,
            label=label,
            scenario_name=scenario_name,
            data=data,
            app=app,
            prompts=json_prompts,
            is_show_analysis=True,
            transcription_text=transcription_text
        )

        logging.info("Проведён количественный анализ")
    else:
        # Любой другой отчёт — один проход, игнорируем run_part
        # Считаем, что prompts_list содержит один набор (или много промптов),
        # но все они обрабатываются в один вызов analyze_methodology.
        result = await run_analysis_pass(
            chat_id=chat_id,
            source_text=txt,
            label=label,
            scenario_name=scenario_name,
            data=data,
            app=app,
            prompts=ordinary_prompts,
            is_show_analysis=False,
            transcription_text=transcription_text
        )

        logging.info("Отчёт сформирован")

        json_result = await run_analysis_pass(
            chat_id=chat_id,
            source_text=result,
            label=label,
            scenario_name=scenario_name,
            data=data,
            app=app,
            prompts=json_prompts,
            is_show_analysis=True,
            transcription_text=transcription_text
        )

        logging.info("Проведён количественный анализ")

    if scenario_name == "Интервью":
        await send_menu(chat_id, app, "Какой отчёт хотите посмотреть дальше?", interview_menu_markup())
    elif scenario_name == "Дизайн":
        await send_menu(chat_id, app, "Какой отчёт хотите посмотреть дальше?", design_menu_markup())

    send_main_menu(chat_id, app)
