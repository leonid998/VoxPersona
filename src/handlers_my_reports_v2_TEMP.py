async def handle_report_view_input(chat_id: int, user_input: str, app: Client) -> None:
    """
    Обрабатывает ввод номера отчета для просмотра.

    🔴 КРИТИЧНО: Async функция, все операции с await.
    🆕 ФАЗА 1.5: Добавлен timeout check + Lock для concurrent control.

    Workflow:
    1. Проверяет timeout snapshot (5 минут)
    2. Валидирует введенный номер
    3. Получает отчет по индексу
    4. Отправляет файл отчета
    5. Очищает FSM состояние
    6. Показывает меню чатов

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

        # Очищаем FSM состояние
        user_states[chat_id] = {}

        # Показываем меню чатов
        await track_and_send(
            chat_id=chat_id,
            app=app,
            text="✅ Отчет отправлен!",
            reply_markup=chats_menu_markup_dynamic(chat_id),
            message_type="menu"
        )
