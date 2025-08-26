import os
import psycopg2

from src.config import DB_CONFIG
from src.datamodels import mapping_scenario_names, mapping_report_type_names, mapping_building_names, mapping_part_names

# Корневая папка, где лежат сценарии
BASE_DIR = "/root/Vox/VoxPersona/prompts-by-scenario"

def get_or_create_scenario(cursor, scenario_name: str):
    """
    Возвращает scenario_id для заданного scenario_name.
    Если сценарий не найден — создаёт новую запись.
    """
    cursor.execute('SELECT "scenario_id" FROM "scenario" WHERE "scenario_name" = %s', (scenario_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "scenario" ("scenario_name") VALUES (%s) RETURNING "scenario_id";',
            (scenario_name,)
        )
        scenario_id = cursor.fetchone()[0]
        return scenario_id

def get_or_create_report_type(cursor, report_type_name: str, scenario_id: int):
    """
    Возвращает report_type_id для заданного report_type_name и scenario_id.
    Если report_type не найдён — создаёт новую запись.
    """
    cursor.execute(
        'SELECT "report_type_id" FROM "report_type" '
        'WHERE "report_type_desc" = %s AND "scenario_id" = %s',
        (report_type_name, scenario_id)
    )
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "report_type" ("report_type_desc", "scenario_id") VALUES (%s, %s) '
            'RETURNING "report_type_id";',
            (report_type_name, scenario_id)
        )
        report_type_id = cursor.fetchone()[0]
        return report_type_id

def get_or_create_building(cursor, building_name: str):
    """
    Возвращает building_id для заданного building_type.
    Если здание не найдено — создаёт новую запись.
    """
    cursor.execute('SELECT "building_id" FROM "buildings" WHERE "building_type" = %s', (building_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "buildings" ("building_type") VALUES (%s) RETURNING "building_id";',
            (building_name,)
        )
        building_id = cursor.fetchone()[0]
        return building_id

def create_buildings_report_type(cursor, building_id: int, report_type_id: int):
    """
    Создаёт связь между building и report_type в таблице buildings_report_type,
    если такая связь ещё не существует.
    """
    # Проверим, нет ли уже такой связи
    cursor.execute(
        'SELECT 1 FROM "buildings_report_type" WHERE "building_id" = %s AND "report_type_id" = %s',
        (building_id, report_type_id)
    )
    result = cursor.fetchone()
    if not result:
        cursor.execute(
            'INSERT INTO "buildings_report_type" ("building_id", "report_type_id") VALUES (%s, %s)',
            (building_id, report_type_id)
        )

def get_or_create_prompt(cursor, prompt_text: str, run_part: str, prompt_name: str, is_json_prompt: bool):
    """
    Возвращает prompt_id для заданного текста промпта.
    Если промпт не найден — создаёт новую запись.
    """
    cursor.execute('SELECT "prompt_id" FROM "prompts" WHERE "prompt" = %s', (prompt_text,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute(
            'INSERT INTO "prompts" ("prompt", "run_part", "prompt_name","is_json_prompt") VALUES (%s, %s, %s, %s) RETURNING "prompt_id";',
            (prompt_text, run_part, prompt_name, is_json_prompt)
        )
        prompt_id = cursor.fetchone()[0]
        return prompt_id

def create_prompts_buildings(cursor, prompt_id: int, building_id: int, report_type_id: int):
    """
    Создаёт связь между prompt и (building, report_type)
    в таблице prompts_buildings, если такой связи ещё нет.
    """
    cursor.execute(
        '''SELECT 1
           FROM "prompts_buildings"
           WHERE "prompt_id" = %s 
             AND "building_id" = %s
             AND "report_type_id" = %s''',
        (prompt_id, building_id, report_type_id)
    )
    result = cursor.fetchone()
    if not result:
        cursor.execute(
            '''INSERT INTO "prompts_buildings" ("prompt_id", "building_id", "report_type_id")
               VALUES (%s, %s, %s)''',
            (prompt_id, building_id, report_type_id)
        )


def process_folder(cursor, path, report_type_id=None, building_id=None, run_part: int=1, is_json_prompt: bool=False):
    for entry in os.scandir(path):
        if entry.is_dir():
            folder_name = entry.name
            lower_name = folder_name.lower()

            if lower_name in ['hotel', 'restaurant', 'spa', 'non-building']:
                building_name = mapping_building_names[folder_name]
                current_building_id = get_or_create_building(cursor, building_name)
                if report_type_id:
                    create_buildings_report_type(cursor, current_building_id, report_type_id)
                process_folder(cursor, entry.path, report_type_id, current_building_id, run_part, is_json_prompt)

            elif lower_name in ["part1", "part2", "part3"]:
                new_run_part = mapping_part_names[lower_name]
                process_folder(cursor, entry.path, report_type_id, building_id, new_run_part, is_json_prompt)

            elif lower_name == "json-prompt":
                process_folder(cursor, entry.path, report_type_id, building_id, run_part, True)

            else:
                process_folder(cursor, entry.path, report_type_id, building_id, run_part, is_json_prompt)

        else:
            with open(entry.path, 'r', encoding='utf-8') as f:
                filename = entry.path.split("/")[-1].strip(".txt")
                prompt_text = f.read().strip()
                if prompt_text:
                    prompt_id = get_or_create_prompt(cursor, prompt_text, run_part, prompt_name=filename, is_json_prompt=is_json_prompt)

                    if building_id is None and report_type_id is not None:
                        non_building_id = get_or_create_building(cursor, mapping_building_names['non-building'])
                        create_buildings_report_type(cursor, non_building_id, report_type_id)
                        create_prompts_buildings(cursor, prompt_id, non_building_id, report_type_id)

                    elif building_id is not None:
                        create_prompts_buildings(cursor, prompt_id, building_id, report_type_id)


def main():
    connection = psycopg2.connect(**DB_CONFIG)
    cursor = connection.cursor()

    # Обходим корневую папку "prompts-by-scenario"
    for scenario_entry in os.scandir(BASE_DIR):
        if scenario_entry.is_dir():
            scenario_name = scenario_entry.name  # например, 'design' или 'interview'
            if scenario_name == "assign_roles":
                for roles in os.scandir(scenario_entry):
                    role_name =  roles.name
                    with open(os.path.join(scenario_entry, role_name), 'r', encoding='utf-8') as f:
                        prompt_text = f.read().strip()
                        if prompt_text:
                            prompt_id = get_or_create_prompt(cursor, prompt_text, 1, prompt_name=role_name.strip(".txt"), is_json_prompt=False)
                continue

            elif scenario_name == "sql_prompts":
                for part_entry in os.scandir(scenario_entry):
                    if part_entry.is_dir() and part_entry.name.startswith("part"):
                        # Извлекаем номер части из имени папки (например, "part1" -> 1)
                        try:
                            part_number = int(part_entry.name.replace("part", ""))
                        except ValueError:
                            print(f"Некорректное имя папки: {part_entry.name}")
                            continue

                        # Обходим файлы внутри подпапки
                        for file_entry in os.scandir(part_entry):
                            if file_entry.is_file() and file_entry.name.endswith(".txt"):
                                with open(file_entry.path, 'r', encoding='utf-8') as f:
                                    prompt_text = f.read().strip()
                                    if prompt_text:
                                        # Сохраняем промпт с указанием номера части
                                        prompt_id = get_or_create_prompt(
                                            cursor,
                                            prompt_text,
                                            part_number,
                                            prompt_name=file_entry.name.strip(".txt"),
                                            is_json_prompt=False
                                        )
                continue
                    
            scenario_name = mapping_scenario_names[scenario_name]
            scenario_id = get_or_create_scenario(cursor, scenario_name)

            # Внутри папки сценария обходим папки report_type
            for report_type_entry in os.scandir(scenario_entry.path):
                if report_type_entry.is_dir():
                    report_type_name = report_type_entry.name
                    report_type_name = mapping_report_type_names[report_type_name]
                    report_type_id = get_or_create_report_type(cursor, report_type_name, scenario_id)

                    # Обрабатываем содержимое папки report_type
                    process_folder(cursor, report_type_entry.path, report_type_id, None)
                else:
                    # Если в папке сценария лежат файлы (редкий случай),
                    # то можно, например, пропустить или обработать иначе:
                    pass

    connection.commit()
    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
