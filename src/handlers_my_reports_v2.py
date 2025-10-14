"""
Новые async handlers для функции "Мои отчеты" v2.

⚠️ КРИТИЧНО: 100% async реализация для FSM workflow операций View/Rename/Delete.

Создано: 2025-10-10
Агент: python-pro
Task ID: 00001_20251010_144500

Интеграция: backend-developer (2025-10-10)
- MessageTracker integration ✅
- BytesIO file sending ✅
- Input validation ✅
- Edge cases handling ✅
- Logging ✅
- Async compatibility ✅

Обновление: fullstack-developer (2025-10-14)
- Автоматическая очистка TXT из чата ✅
- Сохранение message_id в user_states ✅
- Graceful degradation ✅
"""

import logging
import asyncio
from io import BytesIO
from typing import Optional
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from config import user_states, get_user_lock
from md_storage import md_storage_manager
from message_tracker import track_and_send  # ✅ НОВАЯ СИСТЕМА (backend-developer)
from markups import chats_menu_markup_dynamic

logger = logging.getLogger(__name__)

# 🆕 ФАЗА 1.5: Константы
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB лимит для TXT файла
SNAPSHOT_TIMEOUT_MINUTES = 5  # Timeout для snapshot


# ============================================================================
#                    Helper Functions
# ============================================================================

def _read_file_sync(path: str) -> bytes:
    """
    Синхронное чтение файла для использования с asyncio.to_thread().

    Args:
        path: Путь к файлу

    Returns:
        bytes: Содержимое файла
    """
    with open(path, 'rb') as f:
        return f.read()


def validate_report_index(user_input: str, total_reports: int) -> Optional[int]:
    """
    Валидация номера отчета.

    Args:
        user_input: Строка от пользователя
        total_reports: Общее количество отчетов

    Returns:
        Валидный индекс (1-based) или None
    """
    try:
        # Парсим число
        index = int(user_input.strip())

        # Проверяем диапазон
        if 1 <= index <= total_reports:
            return index

        return None
    except (ValueError, AttributeError):
        # Не число или пустая строка
        return None


def _check_snapshot_timeout(chat_id: int) -> tuple[bool, str]:
    """
    🆕 ФАЗА 1.5: Проверка timeout snapshot (5 минут).

    Если snapshot устарел, автоматически очищает его из user_states.

    Args:
        chat_id: ID чата пользователя

    Returns:
        tuple[bool, str]: (is_valid, error_message)
            - is_valid: True если snapshot валиден, False если устарел
            - error_message: Сообщение об ошибке (пустая строка если валиден)
    """
    timestamp = user_states.get(chat_id, {}).get("reports_timestamp")

    if not timestamp:
        return False, "❌ Snapshot не найден"

    # Проверка timeout (5 минут)
    if (datetime.now() - timestamp) > timedelta(minutes=SNAPSHOT_TIMEOUT_MINUTES):
        # Очистка устаревшего snapshot
        user_states[chat_id].pop("reports_snapshot", None)
        user_states[chat_id].pop("reports_timestamp", None)
        user_states[chat_id].pop("step", None)

        logger.warning(f"[SnapshotTimeout] User {chat_id} snapshot expired (>{SNAPSHOT_TIMEOUT_MINUTES} min)")

        return False, (
            f"❌ **Список отчетов устарел** (прошло >{SNAPSHOT_TIMEOUT_MINUTES} минут).\n\n"
            "Запросите заново через кнопку '📄 Мои отчеты'."
        )

    return True, ""


# ============================================================================
#                    ПОДЗАДАЧА 2: Главный handler handle_my_reports_v2()
# ============================================================================

async def handle_my_reports_v2(chat_id: int, app: Client) -> None:
    """
    Новая реализация функции 'Мои отчеты' (v2).

    Отправляет TXT файл со списком отчетов + меню с кнопками операций.

    🔴 КРИТИЧНО: Полностью async, все операции с await.

    🆕 ОБНОВЛЕНИЕ (2025-10-14): Автоматическая очистка старых TXT из чата.

    Workflow:
    1. Экспортирует список отчетов в TXT файл
    2. Удаляет предыдущий TXT из чата (по message_id)
    3. Отправляет новый файл пользователю
    4. Сохраняет message_id нового файла в user_states
    5. Показывает меню с операциями: Посмотреть/Переименовать/Удалить

    Args:
        chat_id: ID чата пользователя
        app: Pyrogram клиент

    Returns:
        None
    """
    try:
        # ✅ Async совместимость - оборачиваем в asyncio.to_thread()
        reports = await asyncio.to_thread(
            md_storage_manager.get_user_reports, chat_id, None
        )

        if not reports:
            # Нет отчетов - показываем сообщение с меню чатов
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="📁 **Ваши отчеты:**\n\nУ вас пока нет сохраненных отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.warning(f"[MyReportsV2] No reports found for user {chat_id}")
            return

        # ✅ BytesIO отправка TXT файла (backend-developer)
        # Экспортируем список в TXT файл (async)
        txt_path = await asyncio.to_thread(
            md_storage_manager.export_reports_list_to_txt, chat_id
        )

        if not txt_path:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Не удалось экспортировать список отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.error(f"[MyReportsV2] Failed to export reports list for user {chat_id}")
            return

        # 🆕 УДАЛИТЬ ПРЕДЫДУЩИЙ TXT ИЗ ЧАТА (Phase 1)
        old_message_id = user_states.get(chat_id, {}).get("last_reports_list_message_id")
        if old_message_id:
            try:
                await app.delete_messages(chat_id, old_message_id)
                logger.info(f"[MyReportsV2] Deleted old reports list message: {old_message_id}")
            except Exception as e:
                logger.warning(f"[MyReportsV2] Failed to delete old reports list: {e}")

        file_obj = None
        try:
            # Читаем файл асинхронно
            content = await asyncio.to_thread(_read_file_sync, txt_path)

            # 🆕 ФАЗА 1.5: Проверка размера файла (10MB лимит)
            file_size_bytes = len(content)
            file_size_mb = file_size_bytes / (1024 * 1024)

            if file_size_bytes > MAX_FILE_SIZE:
                logger.warning(
                    f"[MyReportsV2] Reports list too large for user {chat_id}: "
                    f"{file_size_mb:.2f} MB ({len(reports)} reports)"
                )
                await track_and_send(
                    chat_id=chat_id,
                    app=app,
                    text=(
                        f"❌ **Список отчетов слишком большой** ({file_size_mb:.1f} MB).\n\n"
                        "**Рекомендации:**\n"
                        "• Удалите старые отчеты\n"
                        "• Используйте фильтры\n"
                        "• Архивируйте отчеты локально"
                    ),
                    reply_markup=chats_menu_markup_dynamic(chat_id),
                    message_type="status_message"
                )
                return

            # Логирование для мониторинга
            logger.info(
                f"[MyReportsV2] Reports list size for user {chat_id}: "
                f"{file_size_mb:.2f} MB ({len(reports)} reports)"
            )

            # Создаем BytesIO
            file_obj = BytesIO(content)
            file_obj.name = f"reports_{chat_id}.txt"

            # Отправляем файл БЕЗ меню
            new_message = await app.send_document(
                chat_id=chat_id,
                document=file_obj,
                caption="📋 **Список ваших отчетов**"
            )

            # 🆕 СОХРАНИТЬ message_id НОВОГО TXT (Phase 1)
            if chat_id not in user_states:
                user_states[chat_id] = {}
            user_states[chat_id]["last_reports_list_message_id"] = new_message.id
            logger.info(f"[MyReportsV2] Saved new reports list message_id: {new_message.id}")

            logger.info(f"[MyReportsV2] TXT file sent to user {chat_id} ({len(reports)} reports)")

        finally:
            # ✅ ОБЯЗАТЕЛЬНО закрыть BytesIO
            if file_obj:
                file_obj.close()

        # 🆕 ФАЗА 1.5: Сохранение snapshot с timestamp
        user_states[chat_id]["reports_snapshot"] = reports
        user_states[chat_id]["reports_timestamp"] = datetime.now()
        logger.info(f"[MyReportsV2] Snapshot saved for user {chat_id} ({len(reports)} reports)")

        # Меню с кнопками операций
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ Посмотреть", callback_data="report_view")],
            [InlineKeyboardButton("✏️ Переименовать", callback_data="report_rename")],
            [InlineKeyboardButton("🗑️ Удалить", callback_data="report_delete")],
            [InlineKeyboardButton("« Назад", callback_data="menu_chats")]
        ])

        # Отправка меню через track_and_send
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="Выберите действие с отчетами:",
            reply_markup=keyboard,
            message_type="menu"
        )

        logger.info(f"[MyReportsV2] User {chat_id} opened reports menu v2")

    except Exception as e:
        logger.error(f"[MyReportsV2] Error for user {chat_id}: {e}", exc_info=True)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка при загрузке отчетов.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )


# ============================================================================
#             ПОДЗАДАЧА 3: FSM логика "Посмотреть" (View workflow)
# ============================================================================

async def handle_report_view_request(chat_id: int, app: Client) -> None:
    """
    Запрашивает номер отчета для просмотра.

    🔴 КРИТИЧНО: Async handler, все Pyrogram методы с await.

    Workflow:
    1. Получает общее количество отчетов
    2. Устанавливает FSM состояние "report_view_ask_number"
    3. Запрашивает номер отчета у пользователя

    Args:
        chat_id: ID чата пользователя
        app: Pyrogram клиент

    Returns:
        None
    """
    try:
        # ✅ Async совместимость
        reports = await asyncio.to_thread(
            md_storage_manager.get_user_reports, chat_id, None
        )
        total_reports = len(reports)

        if total_reports == 0:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="📭 У вас нет отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.warning(f"[ReportView] User {chat_id} has no reports")
            return

        # Устанавливаем FSM состояние
        if chat_id not in user_states:
            user_states[chat_id] = {}
        user_states[chat_id].update({
            "step": "report_view_ask_number",
            "total_reports": total_reports
        })

        # Кнопка отмены
        cancel_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ])

        # ✅ MessageTracker интеграция (backend-developer)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=f"👁️ **Посмотреть отчет**\n\nВведите номер отчета (1-{total_reports}):",
            reply_markup=cancel_markup,
            message_type="input_request"  # ✅ Правильный тип для запроса ввода
        )

        logger.info(f"[ReportView] User {chat_id} requested view, total reports: {total_reports}")

    except Exception as e:
        logger.error(f"[ReportView] Error for user {chat_id}: {e}", exc_info=True)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )


async def handle_report_view_input(chat_id: int, user_input: str, app: Client) -> None:
    """
    Обрабатывает ввод номера отчета для просмотра.

    🔴 КРИТИЧНО: Async функция, все операции с await.

    Workflow:
    1. Валидирует введенный номер
    2. Получает отчет по индексу
    3. Отправляет файл отчета
    4. Очищает FSM состояние
    5. Показывает меню чатов

    Args:
        chat_id: ID чата пользователя
        user_input: Введенный пользователем текст
        app: Pyrogram клиент

    Returns:
        None
    """
    # 🆕 ФАЗА 1.5: Concurrent control - получаем Lock
    async with get_user_lock(chat_id):
        # 🆕 ФАЗА 1.5: Проверка timeout snapshot
        is_valid, error_msg = _check_snapshot_timeout(chat_id)
        if not is_valid:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=error_msg,
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="status_message"
            )
            return

        state = user_states.get(chat_id, {})
        total_reports = state.get("total_reports", 0)

        # ✅ Использование validate_report_index() (backend-developer)
        index = validate_report_index(user_input, total_reports)
        if index is None:
            # Некорректный ввод - показываем ошибку
            retry_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data="report_view")],
                [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
            ])

            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=f"❌ **Некорректный номер**\n\nВведите число от 1 до {total_reports}.",
                reply_markup=retry_markup,
                message_type="input_request"
            )
            logger.warning(f"[ReportView] User {chat_id} entered invalid number: {user_input}")
            return

        # ✅ Async совместимость + edge cases
        report = await asyncio.to_thread(
            md_storage_manager.get_report_by_index, chat_id, index
        )

        if not report:
            # ✅ Edge case: Отчет удален между запросом и действием
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ **Отчет не найден.**\n\nВозможно он был удален.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.warning(f"[ReportView] Report index {index} not found for user {chat_id}")
            user_states[chat_id] = {}  # Очистить FSM
            return

        # Получаем путь к файлу
        file_path = md_storage_manager.get_report_file_path(report.file_path)
        if not file_path or not file_path.exists():
            # ✅ Edge case: Файл отчета не найден
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ **Файл отчета не найден.**\n\nВозможно он был удален.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.error(f"[ReportView] Report file not found: {report.file_path}")
            user_states[chat_id] = {}
            return

        # ✅ BytesIO отправка MD файла (backend-developer)
        file_obj = None
        try:
            # Читаем файл асинхронно
            content = await asyncio.to_thread(_read_file_sync, str(file_path))

            # Создаем BytesIO
            file_obj = BytesIO(content)
            file_obj.name = f"report_{index}.txt"

            # Отправляем файл
            await app.send_document(
                chat_id=chat_id,
                document=file_obj,
                caption=f"📄 Отчет #{index}: {report.question[:50]}..."
            )

            logger.info(f"[ReportView] User {chat_id} viewed report #{index}")

        except Exception as e:
            logger.error(f"[ReportView] Error sending report #{index} to {chat_id}: {e}", exc_info=True)
            await app.send_message(chat_id, "❌ Ошибка при отправке файла.")

        finally:
            # ✅ ОБЯЗАТЕЛЬНО закрыть BytesIO
            if file_obj:
                file_obj.close()

        # Очищаем только FSM состояние операции
        user_states[chat_id].pop("step", None)
        user_states[chat_id].pop("total_reports", None)

        # Показываем статус
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="✅ Отчет отправлен!",
            message_type="status_message"
        )

        # Возвращаем в меню "Мои отчеты"
        await handle_my_reports_v2(chat_id, app)


# ============================================================================
#        ПОДЗАДАЧА 4: FSM логика "Переименовать" (Rename workflow)
# ============================================================================

async def handle_report_rename_request(chat_id: int, app: Client) -> None:
    """
    Запрашивает номер отчета для переименования.

    🔴 КРИТИЧНО: Async handler, все Pyrogram методы с await.

    Workflow:
    1. Получает общее количество отчетов
    2. Устанавливает FSM состояние "report_rename_ask_number"
    3. Запрашивает номер отчета

    Args:
        chat_id: ID чата пользователя
        app: Pyrogram клиент

    Returns:
        None
    """
    try:
        # ✅ Async совместимость
        reports = await asyncio.to_thread(
            md_storage_manager.get_user_reports, chat_id, None
        )
        total_reports = len(reports)

        if total_reports == 0:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="📭 У вас нет отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.warning(f"[ReportRename] User {chat_id} has no reports")
            return

        # Устанавливаем FSM состояние
        if chat_id not in user_states:
            user_states[chat_id] = {}
        user_states[chat_id].update({
            "step": "report_rename_ask_number",
            "total_reports": total_reports
        })

        # Кнопка отмены
        cancel_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ])

        # ✅ MessageTracker интеграция (backend-developer)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=f"✏️ **Переименовать отчет**\n\nВведите номер отчета (1-{total_reports}):",
            reply_markup=cancel_markup,
            message_type="input_request"  # ✅ Правильный тип для запроса ввода
        )

        logger.info(f"[ReportRename] User {chat_id} requested rename, total reports: {total_reports}")

    except Exception as e:
        logger.error(f"[ReportRename] Error for user {chat_id}: {e}", exc_info=True)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )


async def handle_report_rename_number_input(chat_id: int, user_input: str, app: Client) -> None:
    """
    Обрабатывает ввод номера отчета для переименования (шаг 1).

    🔴 КРИТИЧНО: Async функция, все операции с await.

    Workflow:
    1. Валидирует номер
    2. Получает отчет по индексу
    3. Сохраняет в FSM: report_index, old_name
    4. Переходит к шагу "report_rename_ask_new_name"
    5. Запрашивает новое имя

    Args:
        chat_id: ID чата пользователя
        user_input: Введенный пользователем текст
        app: Pyrogram клиент

    Returns:
        None
    """
    state = user_states.get(chat_id, {})
    total_reports = state.get("total_reports", 0)

    # ✅ Использование validate_report_index()
    index = validate_report_index(user_input, total_reports)
    if index is None:
        # Некорректный ввод
        retry_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="report_rename")],
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ])

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=f"❌ **Некорректный номер**\n\nВведите число от 1 до {total_reports}.",
            reply_markup=retry_markup,
            message_type="input_request"
        )
        logger.warning(f"[ReportRename] User {chat_id} entered invalid number: {user_input}")
        return

    # ✅ Async совместимость + edge cases
    report = await asyncio.to_thread(
        md_storage_manager.get_report_by_index, chat_id, index
    )

    if not report:
        # ✅ Edge case: Отчет не найден
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ **Отчет не найден.**\n\nВозможно он был удален.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )
        logger.warning(f"[ReportRename] Report index {index} not found for user {chat_id}")
        user_states[chat_id] = {}
        return

    # Сохраняем в FSM состояние
    if chat_id not in user_states:
        user_states[chat_id] = {}
    user_states[chat_id].update({
        "step": "report_rename_ask_new_name",
        "report_index": index,
        "old_name": report.question
    })

    # Кнопка отмены
    cancel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
    ])

    # ✅ MessageTracker интеграция (backend-developer)
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"✏️ **Переименовать отчет #{index}**\n\n"
             f"Текущее название:\n`{report.question}`\n\n"
             f"Введите новое название:",
        reply_markup=cancel_markup,
        message_type="input_request"  # ✅ Правильный тип для запроса ввода
    )

    logger.info(f"[ReportRename] User {chat_id} selected report #{index} for rename")


async def handle_report_rename_name_input(chat_id: int, user_input: str, app: Client) -> None:
    """
    Обрабатывает ввод нового имени отчета (шаг 2).

    🔴 КРИТИЧНО: Async функция, все операции с await.

    Workflow:
    1. Получает report_index из FSM
    2. Вызывает md_storage_manager.rename_report()
    3. Показывает результат (успех/ошибка)
    4. Очищает FSM состояние
    5. Показывает меню чатов

    Args:
        chat_id: ID чата пользователя
        user_input: Введенное новое имя
        app: Pyrogram клиент

    Returns:
        None
    """
    # 🆕 ФАЗА 1.5: Concurrent control - получаем Lock
    async with get_user_lock(chat_id):
        # 🆕 ФАЗА 1.5: Проверка timeout snapshot
        is_valid, error_msg = _check_snapshot_timeout(chat_id)
        if not is_valid:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=error_msg,
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="status_message"
            )
            return

        state = user_states.get(chat_id, {})
        index = state.get("report_index")
        old_name = state.get("old_name", "")

        if not index:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Ошибка: состояние не найдено.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.error(f"[ReportRename] Missing report_index in state for user {chat_id}")
            return

        new_name = user_input.strip()

        # ✅ Async совместимость + edge cases
        success = await asyncio.to_thread(
            md_storage_manager.rename_report, chat_id, index, new_name
        )

        if success:
            result_text = (
                f"✅ **Отчет #{index} переименован!**\n\n"
                f"Старое название:\n`{old_name}`\n\n"
                f"Новое название:\n`{new_name}`"
            )
            logger.info(f"[ReportRename] User {chat_id} renamed report #{index}: '{old_name}' -> '{new_name}'")
        else:
            # ✅ Edge case: Ошибка при переименовании
            result_text = "❌ **Не удалось переименовать отчет.**\n\nПопробуйте позже."
            logger.error(f"[ReportRename] Failed to rename report #{index} for user {chat_id}")

        # Очищаем только FSM состояние операции
        user_states[chat_id].pop("step", None)
        user_states[chat_id].pop("report_index", None)
        user_states[chat_id].pop("old_name", None)

        # Показываем результат
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=result_text,
            message_type="status_message"
        )

        # Возвращаем в меню "Мои отчеты" с обновленным списком
        await handle_my_reports_v2(chat_id, app)


# ============================================================================
#           ПОДЗАДАЧА 5: FSM логика "Удалить" (Delete workflow)
# ============================================================================

async def handle_report_delete_request(chat_id: int, app: Client) -> None:
    """
    Запрашивает номер отчета для удаления.

    🔴 КРИТИЧНО: Async handler, все Pyrogram методы с await.

    Workflow:
    1. Получает общее количество отчетов
    2. Устанавливает FSM состояние "report_delete_ask_number"
    3. Запрашивает номер отчета

    Args:
        chat_id: ID чата пользователя
        app: Pyrogram клиент

    Returns:
        None
    """
    try:
        # ✅ Async совместимость
        reports = await asyncio.to_thread(
            md_storage_manager.get_user_reports, chat_id, None
        )
        total_reports = len(reports)

        if total_reports == 0:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="📭 У вас нет отчетов.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.warning(f"[ReportDelete] User {chat_id} has no reports")
            return

        # Устанавливаем FSM состояние
        if chat_id not in user_states:
            user_states[chat_id] = {}
        user_states[chat_id].update({
            "step": "report_delete_ask_number",
            "total_reports": total_reports
        })

        # Кнопка отмены
        cancel_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ])

        # ✅ MessageTracker интеграция (backend-developer)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=f"🗑️ **Удалить отчет**\n\nВведите номер отчета (1-{total_reports}):",
            reply_markup=cancel_markup,
            message_type="input_request"  # ✅ Правильный тип для запроса ввода
        )

        logger.info(f"[ReportDelete] User {chat_id} requested delete, total reports: {total_reports}")

    except Exception as e:
        logger.error(f"[ReportDelete] Error for user {chat_id}: {e}", exc_info=True)
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ Произошла ошибка.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )


async def handle_report_delete_input(chat_id: int, user_input: str, app: Client) -> None:
    """
    Обрабатывает ввод номера отчета для удаления.

    🔴 КРИТИЧНО: Async функция, все операции с await.

    Workflow:
    1. Валидирует номер
    2. Получает отчет по индексу
    3. Сохраняет в FSM: report_index, report_name
    4. Показывает подтверждение с кнопками "Да, удалить" / "Отмена"

    Args:
        chat_id: ID чата пользователя
        user_input: Введенный пользователем текст
        app: Pyrogram клиент

    Returns:
        None
    """
    state = user_states.get(chat_id, {})
    total_reports = state.get("total_reports", 0)

    # ✅ Использование validate_report_index()
    index = validate_report_index(user_input, total_reports)
    if index is None:
        # Некорректный ввод
        retry_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="report_delete")],
            [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
        ])

        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=f"❌ **Некорректный номер**\n\nВведите число от 1 до {total_reports}.",
            reply_markup=retry_markup,
            message_type="input_request"
        )
        logger.warning(f"[ReportDelete] User {chat_id} entered invalid number: {user_input}")
        return

    # ✅ Async совместимость + edge cases
    report = await asyncio.to_thread(
        md_storage_manager.get_report_by_index, chat_id, index
    )

    if not report:
        # ✅ Edge case: Отчет не найден
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="❌ **Отчет не найден.**\n\nВозможно он был удален.",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )
        logger.warning(f"[ReportDelete] Report index {index} not found for user {chat_id}")
        user_states[chat_id] = {}
        return

    # Сохраняем в FSM состояние
    if chat_id not in user_states:
        user_states[chat_id] = {}
    user_states[chat_id].update({
        "step": "report_delete_confirm",
        "report_index": index,
        "report_name": report.question
    })

    # Показываем подтверждение
    confirm_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"report_delete_confirm||{index}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="show_my_reports")]
    ])

    # ✅ MessageTracker интеграция (backend-developer)
    await track_and_send(
        chat_id=chat_id,
        app=app,
        text=f"🗑️ **Удалить отчет #{index}?**\n\n"
             f"`{report.question}`\n\n"
             f"⚠️ Это действие нельзя отменить!",
        reply_markup=confirm_markup,
        message_type="confirmation"  # ✅ Правильный тип для подтверждения
    )

    logger.info(f"[ReportDelete] User {chat_id} selected report #{index} for deletion")


async def handle_report_delete_confirm(chat_id: int, app: Client) -> None:
    """
    Применяет удаление отчета после подтверждения.

    🔴 КРИТИЧНО: Async handler, все Pyrogram методы с await.

    Workflow:
    1. Получает report_index из FSM
    2. Вызывает md_storage_manager.delete_report()
    3. Показывает результат (успех/ошибка)
    4. Очищает FSM состояние
    5. Показывает меню чатов

    Args:
        chat_id: ID чата пользователя
        app: Pyrogram клиент

    Returns:
        None
    """
    # 🆕 ФАЗА 1.5: Concurrent control - получаем Lock
    async with get_user_lock(chat_id):
        # 🆕 ФАЗА 1.5: Проверка timeout snapshot
        is_valid, error_msg = _check_snapshot_timeout(chat_id)
        if not is_valid:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text=error_msg,
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="status_message"
            )
            return

        state = user_states.get(chat_id, {})
        index = state.get("report_index")
        report_name = state.get("report_name", "")

        if not index:
            await track_and_send(
                chat_id=chat_id,
                app=app,
                text="❌ Ошибка: состояние не найдено.",
                reply_markup=chats_menu_markup_dynamic(chat_id),
                message_type="menu"
            )
            logger.error(f"[ReportDelete] Missing report_index in state for user {chat_id}")
            return

        # ✅ Async совместимость + edge cases
        success = await asyncio.to_thread(
            md_storage_manager.delete_report, chat_id, index
        )

        if success:
            result_text = f"✅ **Отчет #{index} удален!**\n\n`{report_name}`"
            logger.info(f"[ReportDelete] User {chat_id} deleted report #{index}: '{report_name}'")
        else:
            # ✅ Edge case: Ошибка при удалении
            result_text = "❌ **Не удалось удалить отчет.**\n\nПопробуйте позже."
            logger.error(f"[ReportDelete] Failed to delete report #{index} for user {chat_id}")

        # Очищаем только FSM состояние операции
        user_states[chat_id].pop("step", None)
        user_states[chat_id].pop("report_index", None)
        user_states[chat_id].pop("report_name", None)

        # Показываем результат
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text=result_text,
            message_type="status_message"
        )

        # Возвращаем в меню "Мои отчеты" с обновленным списком
        await handle_my_reports_v2(chat_id, app)
