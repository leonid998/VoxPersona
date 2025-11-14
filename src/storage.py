import os
import re
import logging
import shutil
from pyrogram import Client
import psycopg2
import psycopg2.extras
import collections
import json
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

from config import STORAGE_DIRS, DB_CONFIG
from analysis import transcribe_audio, assign_roles
from datamodels import translit_map
from utils import clean_text, get_embedding_model, split_markdown_text, CustomSentenceTransformerEmbeddings

from db_handler.db import (
    get_scenario,
    get_or_create_employee,
    get_or_create_client,
    get_or_create_place_with_zone,
    get_or_create_city,
    save_audit,
    get_or_save_transcription,
    get_report_type,
    get_building,
    save_user_road
)

_SQL = """
WITH base AS (
    SELECT
        a.transcription_id,
        a.audit_date,
        t.audio_file_name,
        t.number_audio,
        a.audit_id,
        a.audit AS audit_text,
        e.employee_name,
        c.client_name,
        p.place_name,
        p.building_type,
        (
            SELECT json_agg(z.zone_name)
            FROM   place_zone pz
            JOIN   zone z ON z.zone_id = pz.zone_id
            WHERE  pz.place_id = p.place_id
        ) AS zone_names,
        ci.city_name,
        s.scenario_name,
        rt.report_type_desc
    FROM audit a
    JOIN transcription t ON t.transcription_id = a.transcription_id
    JOIN user_road ur ON ur.audit_id = a.audit_id
    JOIN scenario s ON s.scenario_id = ur.scenario_id
    JOIN report_type rt ON rt.report_type_id = ur.report_type_id
    LEFT JOIN employee e ON e.employee_id = a.employee_id
    LEFT JOIN client c ON c.client_id = a.client_id
    LEFT JOIN place p ON p.place_id = a.place_id
    LEFT JOIN city ci ON ci.city_id = a.city_id
    WHERE
      s.scenario_name = %(scenario_name)s
      AND (%(report_type)s IS NULL OR rt.report_type_desc = %(report_type)s)
)
SELECT *
FROM base
ORDER BY transcription_id, report_type_desc, audit_id;
"""


def create_db_in_memory(markdown_text: str):
    """Создает векторную базу данных в памяти без сохранения на диск"""
    logging.info("Создаем векторную базу данных в памяти...")

    logging.info("Разбиваем текст на чанки...")
    chunks = split_markdown_text(markdown_text)

    if isinstance(chunks[0], Document):
        chunks_documents = chunks
    else:
        chunks_documents = [Document(page_content=chunk) for chunk in chunks]

    logging.info(f"Создаем индексную базу в памяти ({len(chunks_documents)} чанков)...")

    logging.info("Информация о токенах в чанках:")
    total_tokens = 0
    for i, doc in enumerate(chunks_documents):
        tokens = len(doc.page_content.split()) * 1.5
        total_tokens += tokens

    logging.info(f"Всего токенов во всех чанках: {int(total_tokens)}")

    model = get_embedding_model()

    embedding = CustomSentenceTransformerEmbeddings(model)

    # Логируем начало создания FAISS индекса
    logging.info(f"Начинаем создание FAISS индекса для {len(chunks_documents)} документов...")
    logging.info("Этот процесс может занять 10-20 минут в зависимости от количества документов. Пожалуйста, ожидайте...")

    # Создаем FAISS из документов
    db_index = FAISS.from_documents(
        documents=chunks_documents,
        embedding=embedding  # Теперь здесь правильный Embeddings-объект
    )

    logging.info(f"✅ FAISS индекс успешно создан! Обработано {len(chunks_documents)} документов.")

    return db_index

def save_user_input_to_db(transcript: str, scenario_name: str, data: dict, audit_text: str, label: str = ""):
    """
    Сохраняем введённые пользователем поля в таблицу audit (через save_audit)
    и затем записываем цепочку (scenario, report_type, building) в user_road.

    Параметры:
      - transcript   : транскрибация
      - scenario_name         : 'Интервью' или 'Дизайн'
      - data         : словарь, где хранятся 'employee', 'place_name', 'type_of_location', ...
      - label        : строка, которая указывает, какой именно отчёт выбрал пользователь
                        (например, 'report_int_general'), чтобы получить report_type_desc.
      - audit_text   : Результат аудита (отчёт)
    """
    employee_name = data.get("employee", "")
    client_name =   data.get("client", "")
    place_name    = data.get("place_name", "")
    type_of_location = data.get("type_of_location", "")
    city_name     = data.get("city", "")
    audit_date    = data.get("date", "")
    zone_name     = data.get("zone_name", "")
    number_audio  = data.get("audio_number", "")
    building_type = data.get("building_type", "")
    audio_file_name = data.get("audio_file_name", "")
    # Получаем человекочитаемый тип отчёта из mapping_report_type_names
    # Если в mapping_report_type_names нет такого ключа, используем дефолт.

    # 1) Сценарий (Интервью / Дизайн)
    scenario_id = get_scenario(scenario_name)

    # 2) Сотрудник, заведение, учреждение, клиент
    employee_id = get_or_create_employee(employee_name)
    place_id = get_or_create_place_with_zone(place_name, building_type, zone_name)
    city_id = get_or_create_city(city_name)
    client_id = get_or_create_client(client_name)

    # 3) Сохраняем транскрипт
    transcription_id = get_or_save_transcription(
        transcription_text=transcript,
        audio_file_name=audio_file_name,
        number_audio=number_audio
    )

    # 4) Создаём запись в audit
    #    (как и раньше — используется save_audit).
    #    audit хранит только scenario_id (а не report_type_id и building_id).
    audit_id = save_audit(
        audit_text=audit_text,
        employee_id=employee_id,
        place_id=place_id,
        audit_date=audit_date,
        city_id=city_id,
        transcription_id=transcription_id,
        client_id=client_id
    )

    # 5) report_type и building (новая логика)
    report_type_id = get_report_type(label, scenario_id)
    building_id = get_building(type_of_location)

    # 6) Теперь записываем в user_road цепочку (audit, scenario, report_type, building)
    save_user_road(
        audit_id=audit_id,
        scenario_id=scenario_id,
        report_type_id=report_type_id,
        building_id=building_id
    )

def safe_filename(name: str) -> str:
    """
    Формирует безопасное имя файла, в том числе транслитерируя кириллицу.
    """
    out = []
    for ch in name:
        if ch in translit_map:
            out.append(translit_map[ch])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    res = "".join(out)
    res = re.sub(r"_+", "_", res)
    if len(res) > 30:
        return res[:15] + "_" + res[-15:]
    return res

def find_real_filename(folder: str, filename: str) -> str:
    for file in os.listdir(folder):
        if safe_filename(file) == filename:
            return file

def delete_tmp_dir(tmp_dir: str):
    try:
        shutil.rmtree(tmp_dir)
        logging.info(f"Временная директория {tmp_dir} удалена.")
    except Exception as e:
        logging.error(f"Ошибка удаления временной директории: {e}")

def delete_tmp_file(tmp_file: str):
    try:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
    except Exception as e:
        logging.error(f"Ошибка удаления временного файла: {e}")

def delete_tmp_msg(msg, client_id: int, app: Client):
    try:
        app.delete_messages(client_id, msg.id)
    except:
        pass

def delete_tmp_params(msg, tmp_file: str, tmp_dir: str, client_id: int, app: Client):
    # Удаляем временное сообщение
    delete_tmp_msg(msg, client_id, app)

    # Удаляем временный файл
    delete_tmp_file(tmp_file)

    # Удаляем временную директорию
    delete_tmp_dir(tmp_dir)

def process_stored_file(category: str, filename: str, chat_id: int, app: Client) -> str | None:
    """
    Обработка файла из хранилища:
      - audio: транскрибация + assign_roles
      - text_without_roles: assign_roles
      - text_with_roles: просто читаем
    """
    fold = STORAGE_DIRS.get(category, "")
    path_ = os.path.join(fold, filename)

    if not os.path.exists(path_):
        app.send_message(chat_id, f"Файл '{filename}' не найден.")
        return None

    try:
        if category == "audio":
            raw_ = transcribe_audio(path_)
            try:
                roles_ = assign_roles(raw_)
                # app.edit_message_text(chat_id, msg_.id, "✅ Роли в диалоге расставлены.")
                logging.info("✅ Роли в диалоге расставлены.")

            except Exception as e:
                logging.exception(f"❌ Ошибка при расстановке ролей: {str(e)}")
                # app.edit_message_text(chat_id, msg_.id, f"❌ Ошибка при расстановке ролей: {str(e)}")

            logging.info(f"[process_stored_file|audio] Сохранён текст длиной {len(roles_)} символов.")
            return roles_

        else:
            app.send_message(chat_id, "Неверная категория файла.")
            return None

    except Exception as e:
        logging.error(f"Ошибка process_stored_file: {e}")
        app.send_message(chat_id, f"Ошибка обработки файла: {e}")
        return None


def build_reports_grouped(
    scenario_name: str,
    report_type: str | None = None,
    exclude_report_types: list[str] | None = None
) -> dict[int, list[str]]:
    """
    Строит словарь отчетов по сценарию, группируя их по transcription_id.

    Args:
        scenario_name: Название сценария ('Интервью' или 'Дизайн')
        report_type: Тип отчета для фильтрации (None = все типы)
        exclude_report_types: Список типов отчетов для исключения из результата
            Пример: ["Оценка методологии интервью", "Оценка методологии аудита"]

    Returns:
        dict[int, list[str]]: Словарь {transcription_id: [список_отчетов_в_формате_json+текст]}

    Notes:
        - Фильтрация exclude_report_types применяется ПОСЛЕ построения словаря
        - Исключение происходит на уровне отдельных отчетов внутри transcription
        - Если после исключения transcription остается пустым, он не включается в результат

    Examples:
        >>> # Получить все отчеты по интервью, кроме методологии
        >>> reports = build_reports_grouped(
        ...     scenario_name="Интервью",
        ...     exclude_report_types=["Оценка методологии интервью"]
        ... )
    """
    if not scenario_name:
        raise ValueError("scenario_name must be provided")

    params = {
        "scenario_name": scenario_name,
        "report_type": report_type
    }

    with psycopg2.connect(**DB_CONFIG) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(_SQL, params)
        rows = cur.fetchall()

    grouped: dict[int, list[str]] = collections.defaultdict(list)

    # Счетчики для логирования
    total_reports = 0
    excluded_count = 0

    for r in rows:
        transcription_id = r["transcription_id"]
        report_type_desc = r["report_type_desc"]

        total_reports += 1

        # ✅ ФИЛЬТРАЦИЯ: Пропускаем отчеты из exclude_report_types
        if exclude_report_types and report_type_desc in exclude_report_types:
            excluded_count += 1
            logging.debug(
                f"  ⏭️  Исключен отчет: transcription_id={transcription_id}, "
                f"type='{report_type_desc}'"
            )
            continue  # Не добавляем этот отчет в результат

        header = {
            "transcription_id": transcription_id,
            "audit_date": str(r["audit_date"]),
            "audio_file_name": r["audio_file_name"],
            "number_audio": r["number_audio"],
            "audit_id": r["audit_id"],
            "employee_name": r["employee_name"],
            "client_name": r["client_name"],
            "place_name": r["place_name"],
            "building_type": r["building_type"],
            "zone_names": r["zone_names"],
            "city_name": r["city_name"],
            "scenario_name": r["scenario_name"],
            "report_type_desc": report_type_desc,
        }

        parts = [
            json.dumps(header, ensure_ascii=False, default=str)
        ]
        if r["audit_text"]:
            parts.append(clean_text(r["audit_text"]))

        grouped[transcription_id].append("\n\n".join(parts))


    # ✅ ЛОГИРОВАНИЕ: Итоговая статистика по исключениям
    if exclude_report_types:
        logging.info(
            f"  📊 Статистика фильтрации: "
            f"всего отчетов={total_reports}, "
            f"исключено={excluded_count}, "
            f"осталось={total_reports - excluded_count}, "
            f"transcription_ids={len(grouped)}"
        )
        logging.info(f"  🚫 Исключенные типы: {exclude_report_types}")

    return grouped
