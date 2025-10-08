"""
Автоотправка истории чата и списка отчетов в виде .txt файлов.

Модуль реализует автоматическую отправку файлов пользователю при входе в бот
через команду /start с соблюдением throttling политики (24 часа между отправками).

Использует:
- BytesIO вместо tempfile для оптимальной производительности
- Реверс через [::-1] для максимальной скорости
- Graceful error handling для надежности
- JSON throttling для контроля частоты отправок

Принципы:
- Single Responsibility: каждая функция делает одно дело
- Open/Closed: легко расширяется новыми типами экспорта
- Liskov Substitution: все функции соответствуют контрактам
- Interface Segregation: минимальные зависимости
- Dependency Inversion: зависимость от абстракций (менеджеров)
"""

import logging
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import List, Optional

from conversation_manager import conversation_manager
from md_storage import md_storage_manager, ReportMetadata
from conversations import ConversationMessage
from config import THROTTLE_DATA_DIR
from pyrogram import Client
from markups import make_dialog_markup

logger = logging.getLogger(__name__)

# ============================================================================
#                           КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ============================================================================

THROTTLE_HOURS = 24  # Интервал между автоотправками (настраиваемый параметр)
THROTTLE_FILE = Path(THROTTLE_DATA_DIR) / "throttle_history.json"

# Создаём директорию при импорте модуля (graceful degradation)
try:
    THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Throttle directory verified: {THROTTLE_FILE.parent}")
except (PermissionError, OSError) as e:
    logger.warning(
        f"Failed to create throttle directory {THROTTLE_FILE.parent}: {e}. "
        "Throttling functionality may not work correctly."
    )
MAX_MESSAGES = 200  # Максимальное количество сообщений для экспорта
MAX_REPORTS = 200   # Максимальное количество отчетов для экспорта


# ============================================================================
#                           ФОРМАТИРОВАНИЕ ДАННЫХ
# ============================================================================

def format_history_for_file(
    messages: List[ConversationMessage],
    chat_title: str
) -> str:
    """
    Форматирует историю чата в читаемый текстовый формат.

    Преобразует список сообщений в структурированный текст с заголовком,
    метаданными и отформатированными сообщениями. Сообщения нумеруются
    и маркируются эмодзи в зависимости от типа.

    Args:
        messages: Список объектов ConversationMessage (уже реверснутый!).
                 Последнее сообщение должно быть первым в списке.
        chat_title: Название чата для заголовка файла.

    Returns:
        str: Отформатированный текст, готовый для записи в .txt файл.
             Включает:
             - Заголовок с названием чата
             - Timestamp экспорта
             - Количество сообщений
             - Список сообщений с нумерацией

    Example:
        >>> messages = [msg3, msg2, msg1]  # Реверснутый список
        >>> text = format_history_for_file(messages, "Мой чат")
        >>> print(text)
        ============================================================
        ИСТОРИЯ ЧАТА: Мой чат
        Экспортировано: 07.10.2025 14:30:00
        Количество сообщений: 3
        ============================================================

        [1] 🤖 Бот (07.10.2025 14:25:00)
        Последнее сообщение...

        [2] 🧑 Вы (07.10.2025 14:20:00)
        Предпоследнее сообщение...
    """
    # Генерация заголовка
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    separator = "=" * 60

    header = f"""{separator}
ИСТОРИЯ ЧАТА: {chat_title}
Экспортировано: {current_time}
Количество сообщений: {len(messages)}
{separator}

"""

    # Форматирование сообщений
    lines = [header]

    for i, msg in enumerate(messages, 1):
        # Парсинг timestamp (ISO формат -> человекочитаемый)
        try:
            timestamp = datetime.fromisoformat(msg.timestamp).strftime("%d.%m.%Y %H:%M:%S")
        except (ValueError, AttributeError):
            timestamp = msg.timestamp[:16].replace('T', ' ')

        # Определение роли с эмодзи
        if msg.type == "user_question":
            role = "🧑 Вы"
        elif msg.type == "bot_answer":
            role = "🤖 Бот"
        else:
            role = "❓ Неизвестно"

        # Маркер файла (если сообщение было отправлено как файл)
        file_marker = " 📎" if msg.sent_as == "file" else ""

        # Форматирование одного сообщения
        formatted = f"[{i}] {role} ({timestamp}){file_marker}\n{msg.text}\n\n"
        lines.append(formatted)

    return "".join(lines)


def format_reports_for_file(reports: List[ReportMetadata]) -> str:
    """
    Форматирует список отчетов в читаемый текстовый формат.

    Преобразует список отчетов в структурированный текст с заголовком,
    метаданными и детальной информацией по каждому отчету.

    Args:
        reports: Список объектов ReportMetadata (уже реверснутый!).
                Новые отчеты должны быть первыми в списке.

    Returns:
        str: Отформатированный текст, готовый для записи в .txt файл.
             Включает:
             - Заголовок
             - Timestamp экспорта
             - Количество отчетов
             - Список отчетов с детальной информацией

    Example:
        >>> reports = [report3, report2, report1]  # Реверснутый список
        >>> text = format_reports_for_file(reports)
        >>> print(text)
        ============================================================
        СПИСОК ОТЧЕТОВ
        Экспортировано: 07.10.2025 14:30:00
        Количество отчетов: 3
        ============================================================

        [1] 2025-10-07 14:00:00 - voxpersona_20251007_140000.txt
            Вопрос: Анализ рынка недвижимости...
            Путь: md_reports/user_123/voxpersona_20251007_140000.txt
            Размер: 45.2 KB | Токены: 12,345 | Тип: ⚡ Быстрый
    """
    # Генерация заголовка
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    separator = "=" * 60

    header = f"""{separator}
СПИСОК ОТЧЕТОВ
Экспортировано: {current_time}
Количество отчетов: {len(reports)}
{separator}

"""

    # Форматирование отчетов
    lines = [header]

    for i, report in enumerate(reports, 1):
        # Парсинг timestamp
        try:
            timestamp = datetime.fromisoformat(report.timestamp).strftime("%d.%m.%Y %H:%M:%S")
        except (ValueError, AttributeError):
            timestamp = report.timestamp[:16].replace('T', ' ')

        # Извлечение имени файла из пути
        filename = Path(report.file_path).name

        # Определение типа поиска с эмодзи
        if report.search_type == "fast":
            search_icon = "⚡ Быстрый"
        elif report.search_type == "deep":
            search_icon = "🔍 Глубокий"
        else:
            search_icon = "❓ Неизвестный"

        # Размер в KB
        size_kb = report.size_bytes / 1024

        # Форматирование одного отчета
        formatted = f"""[{i}] {timestamp} - {filename}
    Вопрос: {report.question}
    Путь: {report.file_path}
    Размер: {size_kb:.1f} KB | Токены: {report.tokens:,} | Тип: {search_icon}

"""
        lines.append(formatted)

    return "".join(lines)


# ============================================================================
#                           THROTTLING СИСТЕМА
# ============================================================================

def should_send_file(user_id: int, file_type: str) -> bool:
    """
    Проверяет, можно ли отправить файл пользователю (throttling).

    Читает throttle_history.json и проверяет timestamp последней отправки.
    Если прошло >= THROTTLE_HOURS с момента последней отправки, возвращает True.

    Args:
        user_id: ID пользователя Telegram.
        file_type: Тип файла ("history" или "reports").

    Returns:
        bool: True если файл можно отправить (throttling прошел),
              False если нужно подождать.

    Example:
        >>> should_send_file(123456, "history")
        True  # Прошло >= 24 часа
        >>> should_send_file(123456, "history")
        False  # Только что отправили
    """
    try:
        # Создаем файл если не существует
        if not THROTTLE_FILE.exists():
            logger.debug(f"Throttle file not found, allowing send for user {user_id}")
            return True

        # Читаем JSON
        with open(THROTTLE_FILE, 'r', encoding='utf-8') as f:
            throttle_data = json.load(f)

        # Проверяем наличие записи для пользователя
        user_key = str(user_id)
        if user_key not in throttle_data:
            logger.debug(f"No throttle record for user {user_id}, allowing send")
            return True

        # Проверяем timestamp для конкретного типа файла
        key_name = f"{file_type}_last_sent"
        if key_name not in throttle_data[user_key]:
            logger.debug(f"No {file_type} throttle for user {user_id}, allowing send")
            return True

        # Парсим timestamp последней отправки
        last_sent_str = throttle_data[user_key][key_name]
        last_sent = datetime.fromisoformat(last_sent_str)

        # Проверяем интервал
        now = datetime.now()
        time_diff = now - last_sent
        hours_passed = time_diff.total_seconds() / 3600

        if hours_passed >= THROTTLE_HOURS:
            logger.info(
                f"Throttle passed for user {user_id}, {file_type}: "
                f"{hours_passed:.1f}h since last send"
            )
            return True
        else:
            logger.info(
                f"Throttle active for user {user_id}, {file_type}: "
                f"only {hours_passed:.1f}h passed, need {THROTTLE_HOURS}h"
            )
            return False

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse throttle JSON: {e}")
        # При ошибке парсинга разрешаем отправку (fail-safe)
        return True
    except Exception as e:
        logger.error(f"Error checking throttle for user {user_id}: {e}")
        # При любой ошибке разрешаем отправку (fail-safe)
        return True


def update_last_sent(user_id: int, file_type: str) -> None:
    """
    Обновляет timestamp последней отправки файла в throttle_history.json.

    Создает директорию data/ и файл throttle_history.json если не существуют.
    Обновляет или создает запись для пользователя с текущим timestamp.

    Args:
        user_id: ID пользователя Telegram.
        file_type: Тип файла ("history" или "reports").

    Example:
        >>> update_last_sent(123456, "history")
        # throttle_history.json обновлен:
        # {
        #   "123456": {
        #     "history_last_sent": "2025-10-07T14:30:00"
        #   }
        # }
    """
    try:
        # Создаем директорию data/ если не существует
        THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Читаем существующие данные или создаем новые
        if THROTTLE_FILE.exists():
            with open(THROTTLE_FILE, 'r', encoding='utf-8') as f:
                throttle_data = json.load(f)
        else:
            throttle_data = {}

        # Обновляем timestamp
        user_key = str(user_id)
        if user_key not in throttle_data:
            throttle_data[user_key] = {}

        key_name = f"{file_type}_last_sent"
        throttle_data[user_key][key_name] = datetime.now().isoformat()

        # Сохраняем обратно в файл
        with open(THROTTLE_FILE, 'w', encoding='utf-8') as f:
            json.dump(throttle_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Updated throttle for user {user_id}, {file_type}")

    except Exception as e:
        logger.error(f"Failed to update throttle for user {user_id}: {e}")


# ============================================================================
#                           АВТООТПРАВКА ФАЙЛОВ
# ============================================================================

async def auto_send_history_file(user_id: int, app: Client) -> bool:
    """
    Автоматически отправляет историю чата пользователю в виде .txt файла.

    Функция:
    1. Проверяет throttling (24 часа с последней отправки)
    2. Получает активный чат пользователя
    3. Загружает последние 200 сообщений
    4. Форматирует в текст
    5. Отправляет через BytesIO
    6. Обновляет throttling timestamp

    Args:
        user_id: ID пользователя Telegram.
        app: Pyrogram клиент для отправки сообщений.

    Returns:
        bool: True если файл успешно отправлен, False в противном случае.
              False может означать:
              - Throttling активен (не прошло 24 часа)
              - Нет активного чата
              - Пустая история
              - Ошибка при отправке

    Example:
        >>> await auto_send_history_file(123456, app)
        True  # Файл успешно отправлен

    Note:
        Использует BytesIO вместо tempfile для оптимальной производительности.
        Реверс через [::-1] для максимальной скорости.
    """
    file_obj = None

    try:
        # 1. Проверка throttling
        if not should_send_file(user_id, "history"):
            logger.info(f"Skipping history file for user {user_id} due to throttling")
            return False

        # 2. Получение активного чата (двухшаговый API)
        conversation_id = conversation_manager.get_active_conversation_id(user_id)
        if not conversation_id:
            logger.info(f"No active conversation for user {user_id}")
            return False

        # 3. Загрузка чата
        conversation = conversation_manager.load_conversation(user_id, conversation_id)
        if not conversation or not conversation.messages:
            logger.info(f"Empty conversation for user {user_id}")
            return False

        # 4. Ограничение сообщений (последние 200)
        messages = conversation.messages[-MAX_MESSAGES:]

        # 5. Реверс (последнее сообщение первым) - быстрый метод [::-1]
        reversed_messages = messages[::-1]

        # 6. Форматирование
        content = format_history_for_file(reversed_messages, conversation.metadata.title)

        # 7. Создание BytesIO объекта
        content_bytes = content.encode('utf-8')
        file_obj = BytesIO(content_bytes)
        file_obj.name = f"history_{user_id}.txt"

        # 8. Формирование caption
        caption = (
            f"📜 История чата '{conversation.metadata.title}'\n"
            f"📊 Сообщений: {len(messages)} (последние первыми)\n"
            f"📅 Экспортировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # 9. Отправка файла
        await app.send_document(
            chat_id=user_id,
            document=file_obj,
            caption=caption,
            reply_markup=make_dialog_markup()
        )

        # 10. Обновление throttling
        update_last_sent(user_id, "history")

        logger.info(
            f"History file sent to user {user_id}: "
            f"{len(messages)} messages, {len(content_bytes)} bytes"
        )

        return True

    except Exception as e:
        logger.error(f"Error sending history file to user {user_id}: {e}", exc_info=True)
        return False

    finally:
        # Закрываем BytesIO объект
        if file_obj:
            file_obj.close()


async def auto_send_reports_file(user_id: int, app: Client) -> bool:
    """
    Автоматически отправляет список отчетов пользователю в виде .txt файла.

    Функция:
    1. Проверяет throttling (24 часа с последней отправки)
    2. Получает список отчетов пользователя (до 200 штук)
    3. Форматирует в текст
    4. Отправляет через BytesIO
    5. Обновляет throttling timestamp

    Args:
        user_id: ID пользователя Telegram.
        app: Pyrogram клиент для отправки сообщений.

    Returns:
        bool: True если файл успешно отправлен, False в противном случае.
              False может означать:
              - Throttling активен (не прошло 24 часа)
              - Нет отчетов
              - Ошибка при отправке

    Example:
        >>> await auto_send_reports_file(123456, app)
        True  # Файл успешно отправлен

    Note:
        Использует BytesIO вместо tempfile для оптимальной производительности.
        Отчеты уже реверснуты (новые первыми) в get_user_reports().
    """
    file_obj = None

    try:
        # 1. Проверка throttling
        if not should_send_file(user_id, "reports"):
            logger.info(f"Skipping reports file for user {user_id} due to throttling")
            return False

        # 2. Получение отчетов (уже отсортированы: новые первыми)
        reports = md_storage_manager.get_user_reports(user_id, limit=MAX_REPORTS)

        if not reports:
            logger.info(f"No reports found for user {user_id}")
            return False

        # 3. Форматирование (отчеты уже реверснуты в get_user_reports)
        content = format_reports_for_file(reports)

        # 4. Создание BytesIO объекта
        content_bytes = content.encode('utf-8')
        file_obj = BytesIO(content_bytes)
        file_obj.name = f"reports_{user_id}.txt"

        # 5. Формирование caption
        caption = (
            f"📋 Список ваших отчетов\n"
            f"📊 Отчетов: {len(reports)} (последние первыми)\n"
            f"📅 Экспортировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # 6. Отправка файла
        await app.send_document(
            chat_id=user_id,
            document=file_obj,
            caption=caption
        )

        # 7. Обновление throttling
        update_last_sent(user_id, "reports")

        logger.info(
            f"Reports file sent to user {user_id}: "
            f"{len(reports)} reports, {len(content_bytes)} bytes"
        )

        return True

    except Exception as e:
        logger.error(f"Error sending reports file to user {user_id}: {e}", exc_info=True)
        return False

    finally:
        # Закрываем BytesIO объект
        if file_obj:
            file_obj.close()


# ============================================================================
#                           ПУБЛИЧНЫЙ API МОДУЛЯ
# ============================================================================

__all__ = [
    'auto_send_history_file',
    'auto_send_reports_file',
    'format_history_for_file',
    'format_reports_for_file',
    'should_send_file',
    'update_last_sent',
]
