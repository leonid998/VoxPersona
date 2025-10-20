"""
Базовые валидаторы для VoxPersona.

Примечание: Проверки авторизации, ролей и прав перенесены в auth_filters.py (Custom Filters).
Этот модуль содержит только базовые валидаторы форматов данных и бизнес-логики.

Разделение ответственности:
- auth_filters.py: Авторизация, роли, права (async filters для Pyrogram handlers)
- validators.py: Валидация данных, форматов, бизнес-правил (sync функции)

Автор: backend-developer
Дата: 17 октября 2025
Задача: T17 (#00005_20251014_HRYHG) - Гибридный подход
"""

from typing import Any
import re
import logging
from pyrogram import Client


def validate_building_type(building_type: str) -> str:
    """
    Валидация и нормализация типа заведения.

    Поддерживаемые типы:
    - Отель
    - Ресторан
    - Центр Здоровья

    Args:
        building_type: Тип заведения (любой регистр)

    Returns:
        str: Нормализованное название типа или пустая строка если не распознано
    """
    building_type = building_type.lower()
    if 'отел' in building_type:
        return 'Отель'
    elif 'ресторан' in building_type:
        return 'Ресторан'
    elif 'центр здоров' in building_type or 'центре здоров' in building_type:
        return "Центр Здоровья"
    logging.warning("Не удалось спарсить тип заведения")
    return ""  # Возвращаем пустую строку по умолчанию


def validate_date_format(date_str: str) -> bool:
    """
    Проверяет, соответствует ли строка формату YYYY-MM-DD.

    Args:
        date_str: Строка с датой

    Returns:
        bool: True если формат корректен
    """
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    return bool(re.match(pattern, date_str))


def check_state(state: dict[str, Any] | None, chat_id: int, app: Client) -> bool:
    """
    Проверяет наличие FSM состояния пользователя.

    Args:
        state: Текущее состояние FSM (может быть None)
        chat_id: ID чата пользователя
        app: Pyrogram Client для отправки сообщений

    Returns:
        bool: True если состояние существует, False если нет
    """
    if not state:
        # Нет состояния — значит пользователь что-то пишет без контекста
        app.send_message(chat_id, "Я вас слушаю. Откройте меню, если нужно запустить отчёт.")
        return False
    return True


def check_file_detection(filename: str, chat_id: int, app: Client) -> bool:
    """
    Проверяет, был ли обнаружен файл.

    Args:
        filename: Имя файла (может быть пустым)
        chat_id: ID чата пользователя
        app: Pyrogram Client для отправки сообщений

    Returns:
        bool: True если файл обнаружен, False если нет
    """
    if not filename:
        app.send_message(chat_id, "Файл не найден.")
        return False
    return True


def check_valid_data(validate_datas: list[str], chat_id: int, app: Client, msg: str) -> None:
    """
    Проверяет корректность данных в списке.

    Отправляет сообщение пользователю если любое из значений пустое.

    Args:
        validate_datas: Список строк для проверки
        chat_id: ID чата пользователя
        app: Pyrogram Client для отправки сообщений
        msg: Сообщение для отправки при ошибке валидации
    """
    for data in validate_datas:
        if not data:
            app.send_message(chat_id, msg)
            return


def check_audio_file_size(file_size: int, max_size: int, chat_id: int, app: Client):
    """
    Проверяет размер аудиофайла.

    Args:
        file_size: Размер файла в байтах
        max_size: Максимальный допустимый размер в байтах
        chat_id: ID чата пользователя
        app: Pyrogram Client для отправки сообщений

    Raises:
        ValueError: Если размер файла превышает максимально допустимый
    """
    if file_size > max_size:
        msg = f"Файл слишком большой ({file_size / 1024 / 1024:.1f} MB). Макс 2GB."
        app.send_message(chat_id, msg)
        raise ValueError(msg)
