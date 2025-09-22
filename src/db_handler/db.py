import logging
import psycopg2  # pyright: ignore[reportMissingModuleSource]
from datetime import datetime
from functools import wraps
from typing import Any, Callable, TypeVar, Optional

from config import DB_CONFIG

# Type variable for generic function decoration
F = TypeVar('F', bound=Callable[..., Any])

def db_transaction(commit: bool = True):
    """
    Декоратор для выполнения функции внутри контекста подключения к базе данных.
    
    :param commit: Флаг, указывающий, нужно ли выполнять conn.commit().
                   По умолчанию True (фиксирует изменения).
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    result = func(cursor, *args, **kwargs)
                if commit:
                    conn.commit()  # Фиксируем изменения, если commit=True
            return result
        return wrapper
    return decorator

def get_db_connection():
    # Filter out None values and map to correct psycopg2 parameter names
    config = {}
    if DB_CONFIG.get("dbname"):
        config["dbname"] = DB_CONFIG["dbname"]
    if DB_CONFIG.get("user"):
        config["user"] = DB_CONFIG["user"]
    if DB_CONFIG.get("password"):
        config["password"] = DB_CONFIG["password"]
    if DB_CONFIG.get("host"):
        config["host"] = DB_CONFIG["host"]
    if DB_CONFIG.get("port"):
        config["port"] = DB_CONFIG["port"]
    
    return psycopg2.connect(**config)

@db_transaction(commit=True)
def get_or_create_client(cursor, client_name: str) -> int:
    cursor.execute('SELECT "client_id" FROM "client" WHERE "client_name" = %s', (client_name,))
    result = cursor.fetchone()
    if result:
        logging.info(f"Найдены данные по client_name = {client_name} из таблицы client")
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "client" ("client_name") VALUES (%s) RETURNING "client_id";',
            (client_name,)
        )
        logging.info(f"Данные в таблицу employee успешно сохранены: client_name = {client_name}")
        return cursor.fetchone()[0]

@db_transaction(commit=True)
def get_or_create_employee(cursor, employee_name: str) -> int:
    cursor.execute('SELECT "employee_id" FROM "employee" WHERE "employee_name" = %s', (employee_name,))
    result = cursor.fetchone()
    if result:
        logging.info(f"Найдены данные по employee_name = {employee_name} из таблицы employee")
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "employee" ("employee_name") VALUES (%s) RETURNING "employee_id";',
            (employee_name,)
        )
        logging.info(f"Данные в таблицу employee успешно сохранены: employee_name = {employee_name}")
        return cursor.fetchone()[0]
    
def get_or_create_zone(cursor, zone_name: str) -> int:
    """
    Ищет зону по названию (zone_name) в таблице zone.
    Если зоны нет — создаёт новую запись.
    Возвращает zone_id.
    """
    cursor.execute(
        '''SELECT "zone_id"
           FROM "zone"
           WHERE "zone_name" = %s
        ''',
        (zone_name,)
    )
    row = cursor.fetchone()
    if row:
        logging.info(f"Найдены данные по zone_name = {zone_name} из таблицы zone")
        return row[0]
    else:
        cursor.execute(
            '''INSERT INTO "zone" ("zone_name")
               VALUES (%s)
               RETURNING "zone_id";
            ''',
            (zone_name,)
        )
        logging.info(f"Зона {zone_name} успешно сохранена в таблицу zone")
        return cursor.fetchone()[0]

def add_zone_to_place(cursor, place_id: int, zone_id: int):
    """
    Добавляет связь между place и zone в таблицу place_zone.
    Гарантирует, что запись в place_zone будет уникальной.
    """
    cursor.execute(
        '''SELECT 1 FROM "place_zone"
           WHERE "place_id" = %s AND "zone_id" = %s
        ''',
        (place_id, zone_id)
    )
    if not cursor.fetchone():
        cursor.execute(
            '''INSERT INTO "place_zone" ("place_id", "zone_id")
               VALUES (%s, %s);
            ''',
            (place_id, zone_id)
        )
        logging.info(f"Связь между place_id = {place_id} и zone_id = {zone_id} успешно добавлена в place_zone.")
    else:
        logging.info(f"Связь между place_id = {place_id} и zone_id = {zone_id} уже существует.")

@db_transaction(commit=True)
def get_or_create_place_with_zone(cursor, place_name: str, building_type: str, zone_name: str) -> int:
    """
    Ищет место по названию (place_name) в таблице place.
    Если места нет — создаёт новую запись с указанием building_type.
    Затем создает или получает зону (zone) и связывает их в таблице place_zone.
    Возвращает place_id.
    """
    cursor.execute('SELECT "place_id" FROM "place" WHERE "place_name" = %s AND "building_type" = %s', (place_name, building_type))
    result = cursor.fetchone()

    if result:
        logging.info(f"Найдены данные по place_name = {place_name} и building_type = {building_type} из таблицы place")
        place_id = result[0]
    else:
        cursor.execute(
            'INSERT INTO "place" ("place_name", "building_type") VALUES (%s, %s) RETURNING "place_id";',
            (place_name, building_type)
        )
        place_id = cursor.fetchone()[0]
        logging.info(f"Данные в таблицу place успешно сохранены: place_name = {place_name}, building_type = {building_type}")
    
    zone_id = get_or_create_zone(cursor, zone_name)

    add_zone_to_place(cursor, place_id, zone_id)

    return place_id

@db_transaction(commit=True)
def get_or_create_city(cursor, city_name: str) -> int:
    """
    Если для каждого заведения хотите создавать entry в city:
    В вашем примере это может быть "Gourmet Inc" для ресторана, "Spa World" и т.д.
    Или можно оставить один city, если не используете в логике.
    """
    cursor.execute('SELECT "city_id" FROM "city" WHERE "city_name" = %s', (city_name,))
    result = cursor.fetchone()
    if result:
        logging.info(f"Найдены данные по city_name = {city_name} из таблицы city")
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "city" ("city_name") VALUES (%s) RETURNING "city_id";',
            (city_name,)
        )
        logging.info(f"Данные в таблицу city успешно сохранены: city_name = {city_name}")
        return cursor.fetchone()[0]
    
@db_transaction(commit=True)
def get_building(cursor, building_type: str) -> int:
    """
    Ищет здание по названию (building_type) в таблице buildings.
    Если такого нет — создаёт новую запись.
    Возвращает building_id.
    """
    cursor.execute(
        '''SELECT "building_id"
           FROM "buildings"
           WHERE "building_type" = %s
        ''',
        (building_type,)
    )
    result = cursor.fetchone()[0]
    params = f"building_type = {building_type}"
    if result is None:
        msg = f"Не удалось получить название здания для {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info(f"Найдены данные {params} из таблицы buildings")
    return result

    
def validate_ids(cursor, building_id: int, report_type_id: int):
    """
    Validates that the given building_id and report_type_id exist in their respective tables.
    Raises an exception if either ID is invalid.
    """
    # Validate building_id
    cursor.execute('SELECT 1 FROM buildings WHERE building_id = %s', (building_id,))
    if not cursor.fetchone():
        logging.error(f"Invalid building_id: {building_id}")
        raise ValueError(f"Invalid building_id: {building_id}")

    # Validate report_type_id
    cursor.execute('SELECT 1 FROM report_type WHERE report_type_id = %s', (report_type_id,))
    if not cursor.fetchone():
        logging.error(f"Invalid report_type_id: {report_type_id}")
        raise ValueError(f"Invalid report_type_id: {report_type_id}")


def ensure_buildings_report_type_exists(cursor, building_id: int, report_type_id: int):
    """
    Ensures that the combination of building_id and report_type_id exists in the buildings_report_type table.
    If it does not exist, inserts the combination.
    """
    cursor.execute(
        '''
        SELECT 1
        FROM buildings_report_type
        WHERE building_id = %s AND report_type_id = %s
        ''',
        (building_id, report_type_id)
    )
    params = f"building_id = {building_id} и report_type_id = {report_type_id}"
    if not cursor.fetchone():
        msg = f"Не удалось получить {params} из таблицы buildings_report_type"
        logging.error(msg)
        raise ValueError(msg)

@db_transaction(commit=True)
def save_user_road(cursor,
                   audit_id: int,
                   scenario_id: int,
                   report_type_id: int,
                   building_id: int):
    """
    Записываем «прохождение» пользователя в таблицу user_road,
    чтобы зафиксировать связку (audit, scenario, report_type, building).
    """
    # Step 1: Validate input IDs
    validate_ids(cursor, building_id, report_type_id)

    # Step 2: Ensure the combination of building_id and report_type_id exists
    ensure_buildings_report_type_exists(cursor, building_id, report_type_id)

    # Step 3: Insert into the user_road table
    cursor.execute(
        '''
        INSERT INTO "user_road"
        ("audit_id", "scenario_id", "report_type_id", "building_id")
        VALUES (%s, %s, %s, %s)
        RETURNING "user_road_id";
        ''',
        (audit_id, scenario_id, report_type_id, building_id)
    )
    logging.info(f"Данные в таблицу user_road успешно сохранены: audit_id = {audit_id}, scenario_id = {scenario_id}, report_type_id = {report_type_id}, building_id = {building_id}")
    return cursor.fetchone()[0]

@db_transaction(commit=True)
def get_scenario(cursor, scenario_name: str) -> int:
    cursor.execute('SELECT "scenario_id" FROM "scenario" WHERE "scenario_name" = %s', (scenario_name,))
    result = cursor.fetchone()[0]
    params = f"scenario_name = {scenario_name}"
    if result is None:
        msg = f"Не удалось получить сценарий для {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info(f"Найдены данные по {params} из таблицы scenario")
    return result

@db_transaction(commit=True)
def get_report_type(cursor, report_type_name: str, scenario_id: int) -> int:
    cursor.execute(
        '''SELECT "report_type_id"
           FROM "report_type"
           WHERE "report_type_desc" = %s AND "scenario_id" = %s''',
        (report_type_name, scenario_id)
    )
    result = cursor.fetchone()
    params = f"report_type_desc = {report_type_name} и scenario_id = {scenario_id}"
    if result is None:
        msg = f"Не удалось получить report type для {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info(f"Найдены данные по {params}")
    return result[0]

@db_transaction(commit=True)
def save_audit(cursor, transcription_id: int, audit_text: str, employee_id: int, place_id: int, audit_date: str, city_id: Optional[int] = None, client_id: Optional[int] = None) -> int:
    """
    Создаём новую запись аудита.
    """
    cursor.execute(
        '''INSERT INTO "audit" ("audit", "employee_id", "client_id", "place_id", "audit_date", "city_id", "transcription_id")
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           RETURNING "audit_id";''',
        (audit_text, employee_id, client_id, place_id, audit_date, city_id, transcription_id)
    )
    result = cursor.fetchone()
    params = f"employee_id = {employee_id}, client_id = {client_id}, place_id = {place_id}, audit_date = {audit_date}, city_id = {city_id}, transcription_id = {transcription_id}."
    if result is None:
        msg = f"Failed to insert audit record. No audit_id returned with parameters: {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info(f"Данные успешно сохранены в таблицу audit: {params}")
    return result[0]

@db_transaction(commit=True)
def get_or_save_transcription(cursor, transcription_text: str, audio_file_name: str, number_audio: int) -> int:
    """
    Сохраняем транскрибацию аудио в таблицу transcription.
    """
    cursor.execute('SELECT "transcription_id" FROM "transcription" WHERE "transcription_text" = %s AND "audio_file_name" = %s', (transcription_text, audio_file_name))
    result = cursor.fetchone()
    if result is not None:
        logging.info(f"Транскрибация для файла {audio_file_name} уже загружена в базу данных")
        return result[0]
    
    transcription_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        '''INSERT INTO "transcription" ("transcription_text", "audio_file_name", "transcription_date", "number_audio")
           VALUES (%s, %s, %s, %s)
           RETURNING "transcription_id";''',
        (transcription_text, audio_file_name, transcription_date, number_audio)
    )
    result = cursor.fetchone()[0]
    params = f"audio_file_name = {audio_file_name}, number_audio = {number_audio}, transcription_date = {transcription_date}"
    if result is None:
        msg = f"Failed to insert transcription record. No audit_id returned with parameters: {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info(f"Данные успешно сохранены в таблицу transcription: {params}")
    return result


@db_transaction(commit=False)
def fetch_prompt_by_name(cursor, prompt_name: str):
    query = """
    SELECT p.prompt
    FROM "prompts" p
    WHERE p.prompt_name = %s
    """
    cursor.execute(query, (prompt_name,))
    result = cursor.fetchone()[0]
    params = f"prompt_name = {prompt_name}"
    if result is None:
        msg = f"Данные из таблицы prompt не найдены: Отсутствует {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info(f"Найдены данные по {params} из таблицы prompts")
    return result

# Функция для выборки промптов по цепочке scenario->report_type->building->prompts
@db_transaction(commit=False)
def fetch_prompts_for_scenario_reporttype_building(cursor, scenario_name: str, report_type_desc: str, building_type: str):
    """
    Возвращает список текстов промптов (p.prompt, p.run_part),
    соответствующих указанному сценарию, типу отчёта и зданию.
    """
    query = """
        SELECT DISTINCT p."prompt", p."run_part", p."is_json_prompt"
        FROM "scenario" s
        -- Связываем scenario с report_type
        JOIN "report_type" rt 
            ON s."scenario_id" = rt."scenario_id"
        -- Связываем report_type с buildings_report_type
        JOIN "buildings_report_type" brt 
            ON rt."report_type_id" = brt."report_type_id"
        -- Связываем buildings_report_type с buildings
        JOIN "buildings" b 
            ON brt."building_id" = b."building_id"
        -- Связываем prompts_buildings с buildings_report_type
        JOIN "prompts_buildings" pb 
            ON pb."building_id" = brt."building_id"
            AND pb."report_type_id" = brt."report_type_id"
        -- Связываем prompts_buildings с prompts
        JOIN "prompts" p 
            ON p."prompt_id" = pb."prompt_id"
        -- Фильтруем по заданным параметрам
        WHERE s."scenario_name" = %s
        AND rt."report_type_desc" = %s
        AND b."building_type" = %s
        ORDER BY p."run_part";
    """
    cursor.execute(query, (scenario_name, report_type_desc, building_type))
    rows = cursor.fetchall()
    params = f"scenario_name = {scenario_name}, report_type_desc = {report_type_desc}, building_type = {building_type}"
    if rows is None:
        msg = f"Не найден ни один промпт по параметрам: {params}"
        logging.error(msg)
        raise ValueError(msg)
    result = [(row[0], row[1], row[2]) for row in rows]
    logging.info(f"Успешно найдено {len(result)} промптов по параметрам: {params}")
    return result

@db_transaction(commit=True)
def send_generated_query(cursor, query: str):
    """
    Принимает на вход произвольный запрос к базе данных, сгенерированный моделью
    """
    cursor.execute(query)
    result = cursor.fetchall()
    params = f"{query}"
    if result is None:
        msg = f"Не найдены данные, проверьте SQL запрос: {params}"
        logging.error(msg)
        raise ValueError(msg)
    logging.info("Успешны получены данные из бд")
    return result