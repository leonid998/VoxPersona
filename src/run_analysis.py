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
from analysis import analyze_methodology, classify_query, extract_from_chunk_parallel, aggregate_citations, classify_report_type, generate_db_answer, extract_from_chunk_parallel_async
from storage import save_user_input_to_db, build_reports_grouped, create_db_in_memory


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

def run_dialog_mode(text: str, chat_id: int, app: Client, rags: dict, deep_search: bool = False, conversation_id: str = None):
    try:
        category = classify_query(text)
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
        username = get_username_from_chat(chat_id, app)

        # Сохраняем вопрос пользователя в историю ПЕРЕД поиском
        from chat_history import chat_history_manager
        chat_history_manager.save_message_to_history(
            user_id=chat_id,
            username=username,
            message_id=0,  # Временный ID для пользовательского сообщения
            message_type="user_question",
            text=text
        )

        # Сохраняем вопрос пользователя в conversations (если передан conversation_id)
        if conversation_id:
            from conversation_manager import conversation_manager
            from conversations import ConversationMessage
            from datetime import datetime

            user_message = ConversationMessage(
                timestamp=datetime.now().isoformat(),
                message_id=0,  # Временный ID для пользовательского сообщения
                type="user_question",
                text=text,
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
            app.send_message(chat_id, "Запущено Глубокое Исследование")
            logging.info("Запущено Глубокое исследование")

            # report_type_code = classify_report_type(text, prompt_name=prompt_name)
            # report_type = CLASSIFY_INTERVIEW[report_type_code] if scenario_name == "Интервью" else CLASSIFY_DESIGN[report_type_code]
            # content = rags[report_type]
            # logging.info(f"Тип отчета: {report_type}")
            answer = run_deep_search(content, text=text, chat_id=chat_id, app=app, category=category)
        else:
            app.send_message(chat_id, "Запущен быстрый поиск")
            logging.info("Запущен быстрый поиск")

            # content = build_reports_grouped(scenario_name=scenario_name, report_type=None)
            # content = grouped_reports_to_string(content)
            # rag = rags[scenario_name]
            answer = run_fast_search(text=text, rag=rag)

        formatted_response = f"*Категория запроса:* {category}\n\n{answer}"

        # Используем умную отправку с автоматическим выбором между сообщением и MD файлом
        smart_send_text_unified(
            text=formatted_response,
            chat_id=chat_id,
            app=app,
            username=username,
            question=text,
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
        app.send_message(chat_id, error_message) #TODO: не забыть удалить в продакшене
    finally:
        # После ответа показываем меню выбора режима
        app.send_message(
            chat_id,
            "Какую информацию вы хотели бы получить?",
            reply_markup=make_dialog_markup()
        )

def run_analysis_pass(
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
    msg_ = app.send_message(chat_id, f"⏳ Анализ: {label}...")
    st_ev = threading.Event()
    sp_th = threading.Thread(target=run_loading_animation, args=(chat_id, msg_.id, st_ev, app))
    sp_th.start()

    try:
        audit_text = analyze_methodology(source_text, prompts)

        if is_show_analysis:
            # Получаем username
            username = get_username_from_chat(chat_id, app)

            # Используем умную отправку с автоматическим выбором между сообщением и MD файлом
            smart_send_text_unified(
                text=audit_text,
                chat_id=chat_id,
                app=app,
                username=username,
                question="",  # Для анализа нет исходного вопроса
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

def run_analysis_with_spinner(chat_id: int, processed_texts: dict[int, str], data: dict, app: Client, callback_data: str, transcription_text: str):
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
            result1 = run_analysis_pass(
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
            result2 = run_analysis_pass(
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
        json_result = run_analysis_pass(
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
        result = run_analysis_pass(
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

        json_result = run_analysis_pass(
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
        app.send_message(chat_id, "Какой отчёт хотите посмотреть дальше?", reply_markup=interview_menu_markup())
    elif scenario_name == "Дизайн":
        app.send_message(chat_id, "Какой отчёт хотите посмотреть дальше?", reply_markup=design_menu_markup())

    send_main_menu(chat_id, app)
