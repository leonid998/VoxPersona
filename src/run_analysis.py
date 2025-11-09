import logging
import threading
from openai import PermissionDeniedError as OpenAIPermissionError
from pyrogram import Client
from pyrogram.enums import ParseMode
import re
import asyncio
import aiohttp

from config import ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2, ANTHROPIC_API_KEY_3, ANTHROPIC_API_KEY_4, ANTHROPIC_API_KEY_5, ANTHROPIC_API_KEY_6, ANTHROPIC_API_KEY_7
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


def init_rags(existing_rags: dict | None = None) -> dict:
    rags = existing_rags.copy() if existing_rags else {}

    # Логируем какие индексы уже загружены
    if rags:
        logging.info(f"📦 Получены pre-loaded RAG индексы: {list(rags.keys())}")
    else:
        logging.info("📦 Pre-loaded RAG индексов нет, создаем все с нуля")

    rag_configs = [
        ("Интервью", None, None),
        ("Дизайн", None, None),
        ("Интервью", "Оценка методологии интервью", None),
        ("Интервью", "Отчет о связках", None),
        ("Интервью", "Общие факторы", None),
        ("Интервью", "Факторы в этом заведении", None),
        ("Дизайн", "Оценка методологии аудита", None),
        ("Дизайн", "Соответствие программе аудита", None),
        ("Дизайн", "Структурированный отчет аудита", None),
    ]

    for config in rag_configs:
        scenario_name, report_type, _ = config
        try:
            rag_name = report_type if report_type else scenario_name
            if rag_name in rags:
                logging.info(f"⏭️  Пропуск {rag_name}: уже загружен с диска")
                continue
            logging.info(f"🏗️  Создание индекса {rag_name}...")
            content = build_reports_grouped(scenario_name=scenario_name, report_type=report_type)
            content_str = grouped_reports_to_string(content)

            if rag_name == "Интервью" or rag_name == "Дизайн":
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
    refine_count: int = 0  # ✅ ШАГ 2: Добавлен параметр refine_count
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
    text = (
        f"📝 **Ваш вопрос:**\n"
        f"_{original}_\n\n"
        f"🔍 **Улучшенный вопрос:**\n"
        f"*{expanded_display}*\n\n"
        f"Отправить улучшенный вопрос в {'глубокое исследование' if deep_search else 'быстрый поиск'}?"
    )

    # Полноценная клавиатура с hash и user_states
    from markups import make_query_expansion_markup
    markup = make_query_expansion_markup(
        original_question=original,
        expanded_question=expanded,  # Передаем ПОЛНЫЙ вопрос в callback_data
        conversation_id=conversation_id or "",
        deep_search=deep_search,
        refine_count=refine_count  # ✅ ШАГ 2: Передаем счетчик в markup
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

    try:
        # Классифицируем УЛУЧШЕННЫЙ вопрос (вместо исходного)
        category = classify_query(text_to_search)
        logging.info(f"Сценарий: {category}")

        if category.lower() == "дизайн":
            prompt_name="prompt_classify_design"
            scenario_name="Дизайн"
        elif category.lower() == "интервью":
            prompt_name="prompt_classify_interview"
            scenario_name="Интервью"
        else:
            raise ValueError(f"Не удалось определить сценарий для анализа отчетов")

        content = build_reports_grouped(scenario_name=scenario_name, report_type=None)
        content = grouped_reports_to_string(content)
        rag = rags[scenario_name]

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
