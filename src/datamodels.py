mapping_scenario_names = {
    "design": "Дизайн",
    "interview": "Интервью"
}

mapping_report_type_names = {
    "Assessment-of-the-audit-methodology": "Оценка методологии аудита",
    "Information-on-compliance-with-the-audit-program": "Соответствие программе аудита",
    "Structured-information-on-the-audit-program": "Структурированный отчет аудита",
    "Assessment-of-the-interview-methodology": "Оценка методологии интервью",
    "Information-about-common-decision-making-factors": "Общие факторы",
    "Report-on-links": "Отчет о связках",
    "Information-about-the-decision-making-factors-in-this-institution": "Факторы в этом заведении",
}

OPENAI_AUDIO_EXTS = (".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm")

mapping_building_names = {
    "hotel": "Отель",
    "spa": "Центр Здоровья",
    "restaurant": "Ресторан",
    "": "non-building",
    "non-building": "non-building"
}

mapping_part_names = {
    "part1": 1,
    "part2": 2,
    "part3": 3,
    "default": 1
}

REPORT_MAPPING = {
    "report_int_methodology": "Оценка методологии интервью",
    "report_int_links": "Отчет о связках",
    "report_int_general": "Общие факторы",
    "report_int_specific": "Факторы в этом заведении",
    "report_design_audit_methodology": "Оценка методологии аудита",
    "report_design_compliance": "Соответствие программе аудита",
    "report_design_structured": "Структурированный отчет аудита",
}

CLASSIFY_DESIGN = {
    0: "Оценка методологии аудита",
    1: "Соответствие программе аудита",
    2: "Структурированный отчет аудита"
}

CLASSIFY_INTERVIEW = {
    0: "Оценка методологии интервью",
    1: "Отчет о связках",
    2: "Общие факторы",
    3: "Факторы в этом заведении"
}

# Набор символов для "спиннера"
spinner_chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']

# Транслитерация для safe_filename
translit_map = {
    'А': 'A','а': 'a','Б': 'B','б': 'b','В': 'V','в': 'v',
    'Г': 'G','г': 'g','Д': 'D','д': 'd','Е': 'E','е': 'e',
    'Ё': 'Yo','ё': 'yo','Ж': 'Zh','ж': 'zh','З': 'Z','з': 'z',
    'И': 'I','и': 'i','Й': 'Y','й': 'y','К': 'K','к': 'k',
    'Л': 'L','л': 'l','М': 'M','м': 'm','Н': 'N','н': 'n',
    'О': 'O','о': 'o','П': 'P','п': 'p','Р': 'R','р': 'r',
    'С': 'S','с': 's','Т': 'T','т': 't','У': 'U','у': 'u',
    'Ф': 'F','ф': 'f','Х': 'Kh','х': 'kh','Ц': 'Ts','ц': 'ts',
    'Ч': 'Ch','ч': 'ch','Ш': 'Sh','ш': 'sh','Щ': 'Sch','щ': 'sch',
    'Ъ': '','ъ': '','Ы': 'Y','ы': 'y','Ь': '','ь': '',
    'Э': 'E','э': 'e','Ю': 'Yu','ю': 'yu','Я': 'Ya','я': 'ya'
}