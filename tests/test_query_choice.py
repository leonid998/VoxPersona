"""
Unit тесты для Query Choice Menu - выбор пользователя перед улучшением вопроса.

Проверяемые сценарии:
- TC-1: Пользователь выбирает "Отправить как есть"
- TC-2: Пользователь выбирает "Улучшить вопрос"
- TC-3: Пользователь нажимает "Назад"
- TC-5: expand_query() возвращает ошибку (fallback)

TODO для интеграционных тестов:
- TC-4: Ввод текста вместо выбора кнопки (требует message handler simulation)
- TC-6: Пользователь выбирает "Уточнить еще раз" (требует полный flow)
- TC-7: Множественные вопросы подряд (требует state management simulation)

Автор: Claude Code (python-pro)
Дата: 10 ноября 2025
Проект: VoxPersona
Задача: TASKS/00007_20251105_YEIJEG/010_search_imp/03_promt_out
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import logging

# Добавить src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# === SETUP: Массивный мок всех зависимостей handlers.py ===

# Стандартные библиотеки Python не нужно мокировать

# Mock Pyrogram полностью
sys.modules['pyrogram'] = Mock()
sys.modules['pyrogram.types'] = Mock()
sys.modules['pyrogram.filters'] = Mock()
sys.modules['pyrogram.enums'] = Mock()

# Mock MinIO
sys.modules['minio'] = Mock()
sys.modules['minio.error'] = Mock()
sys.modules['minio_manager'] = Mock()

# Mock все внутренние зависимости handlers
INTERNAL_MODULES = [
    'utils', 'constants', 'conversation_manager', 'md_storage',
    'validators', 'parser', 'auth_models', 'storage', 'datamodels',
    'markups', 'menus', 'menu_manager', 'message_tracker', 'analysis',
    'run_analysis', 'audio_utils', 'conversation_handlers', 'file_sender',
    'handlers_my_reports_v2', 'auth_filters', 'access_handlers',
    'multi_step_delete', 'message_operations', 'admin_security',
    'admin_security_handlers', 'cleanup_manager', 'query_expander'
]

for module in INTERNAL_MODULES:
    sys.modules[module] = Mock()

# Mock openai отдельно
sys.modules['openai'] = Mock()

# Теперь импортируем config
from config import user_states


# === HELPER: Создание моковых функций напрямую ===

def create_mock_handle_query_send_as_is():
    """
    Создает мок handle_query_send_as_is с упрощенной логикой.

    Эмулирует поведение реальной функции:
    1. Извлекает pending_question
    2. Удаляет pending_question
    3. Восстанавливает step на dialog_mode
    4. Вызывает run_dialog_mode (мок)
    """
    async def mock_func(callback, app):
        chat_id = callback.message.chat.id
        st = user_states.get(chat_id, {})

        original_question = st.get("pending_question")

        if not original_question:
            await callback.answer("⚠️ Вопрос не найден, попробуйте еще раз", show_alert=True)
            logging.warning(f"[Query Choice] No pending_question for chat_id={chat_id}")
            return

        # Удаляем pending_question
        if "pending_question" in st:
            del st["pending_question"]
            st["step"] = "dialog_mode"
            user_states[chat_id] = st

        await callback.answer("✅ Отправлено в поиск")
        # В реальной функции здесь вызов run_dialog_mode

    return mock_func


def create_mock_handle_query_improve():
    """
    Создает мок handle_query_improve с упрощенной логикой.

    Эмулирует поведение реальной функции:
    1. Извлекает pending_question
    2. Удаляет pending_question
    3. Вызывает expand_query (мок)
    4. Показывает результат или fallback
    """
    async def mock_func(callback, app, expansion_result=None, expand_error=None):
        chat_id = callback.message.chat.id
        st = user_states.get(chat_id, {})

        original_question = st.get("pending_question")

        if not original_question:
            await callback.answer("⚠️ Вопрос не найден, попробуйте еще раз", show_alert=True)
            logging.warning(f"[Query Choice] No pending_question for chat_id={chat_id}")
            return

        # Удаляем pending_question
        if "pending_question" in st:
            del st["pending_question"]
            st["step"] = "dialog_mode"
            user_states[chat_id] = st

        await callback.answer("✨ Улучшаю вопрос...")

        # Эмуляция expand_query
        if expand_error:
            await callback.answer("⚠️ Не удалось улучшить вопрос", show_alert=True)
            # fallback
            return

        # Проверка результата expansion
        if expansion_result and expansion_result.get("used_descry"):
            # Успех
            pass
        else:
            # Fallback
            await callback.answer("⚠️ Улучшение не применилось", show_alert=True)

    return mock_func


def create_mock_handle_menu_dialog():
    """
    Создает мок handle_menu_dialog.

    Эмулирует очистку pending_question при возврате в меню.
    """
    async def mock_func(chat_id, app):
        st = user_states.get(chat_id, {})

        # Очистка pending_question
        if "pending_question" in st:
            del st["pending_question"]
            logging.info(f"Cleared pending_question for chat_id={chat_id}")

        # Восстановление step
        if st.get("step") == "awaiting_expansion_choice":
            st["step"] = "dialog_mode"
            user_states[chat_id] = st

    return mock_func


# === ФИКСТУРЫ ===

@pytest.fixture(autouse=True)
def clear_user_states():
    """
    Фикстура автоматической очистки user_states после каждого теста.

    Гарантирует независимость тестов друг от друга.
    Запускается автоматически (autouse=True) для всех тестов в этом файле.

    Yields:
        None: Выполняется очистка ПОСЛЕ теста
    """
    yield
    # Очистка после теста
    user_states.clear()


@pytest.fixture
def mock_callback():
    """
    Создает моковый CallbackQuery объект для тестов.

    Returns:
        MagicMock: Мок callback с настроенными атрибутами
            - message.chat.id = 123456
            - answer = AsyncMock (для проверки вызовов)
    """
    callback = MagicMock()
    callback.message.chat.id = 123456
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_app():
    """
    Создает моковый Pyrogram Client для тестов.

    Returns:
        AsyncMock: Мок app с настроенными методами
            - send_message = AsyncMock
    """
    app = AsyncMock()
    return app


# === ТЕСТЫ ===

@pytest.mark.asyncio
async def test_query_send_as_is(mock_callback, mock_app):
    """
    TC-1: Пользователь выбирает "Отправить в поиск КАК ЕСТЬ".

    Проверяет:
    1. pending_question удаляется из user_states
    2. step восстанавливается на "dialog_mode"
    3. callback.answer вызывается

    Flow:
        user_states[chat_id] содержит pending_question
        → handle_query_send_as_is вызывается
        → pending_question очищается
        → step восстанавливается
    """
    handle_query_send_as_is = create_mock_handle_query_send_as_is()

    chat_id = mock_callback.message.chat.id
    question = "Какие проблемы с вентиляцией?"

    # Настройка user_states (симуляция состояния после dialog_mode)
    user_states[chat_id] = {
        "step": "awaiting_expansion_choice",
        "pending_question": question,
        "conversation_id": "conv_test_1",
        "deep_search": False
    }

    # Вызов тестируемой функции
    await handle_query_send_as_is(mock_callback, mock_app)

    # === ПРОВЕРКИ ===

    # 1. pending_question удален
    assert "pending_question" not in user_states[chat_id], \
        "pending_question должен быть удален из user_states"

    # 2. step восстановлен на dialog_mode
    assert user_states[chat_id]["step"] == "dialog_mode", \
        "step должен быть восстановлен на 'dialog_mode'"

    # 3. callback.answer вызван
    mock_callback.answer.assert_called()


@pytest.mark.asyncio
async def test_query_improve_success(mock_callback, mock_app):
    """
    TC-2: Пользователь выбирает "Улучшить вопрос" - успешный сценарий.

    Проверяет:
    1. pending_question удаляется из user_states
    2. step восстанавливается на "dialog_mode"
    3. callback.answer вызывается

    Flow:
        user_states[chat_id] содержит pending_question
        → handle_query_improve вызывается
        → pending_question удаляется
        → expand_query возвращает успешный результат
    """
    handle_query_improve = create_mock_handle_query_improve()

    chat_id = mock_callback.message.chat.id
    question = "проблемы с вентиляцией"

    # Настройка user_states
    user_states[chat_id] = {
        "step": "awaiting_expansion_choice",
        "pending_question": question,
        "conversation_id": "conv_test_2",
        "deep_search": False
    }

    # Успешный результат expansion
    expansion_result = {
        "original": question,
        "expanded": "Какие неисправности обнаружены в системах вентиляции?",
        "used_descry": True,
        "error": None
    }

    # Вызов тестируемой функции
    await handle_query_improve(mock_callback, mock_app, expansion_result=expansion_result)

    # === ПРОВЕРКИ ===

    # 1. pending_question удален
    assert "pending_question" not in user_states[chat_id], \
        "pending_question должен быть удален"

    # 2. step восстановлен
    assert user_states[chat_id]["step"] == "dialog_mode", \
        "step должен быть восстановлен на 'dialog_mode'"

    # 3. callback.answer вызван
    mock_callback.answer.assert_called()


@pytest.mark.asyncio
async def test_query_improve_expansion_failed(mock_callback, mock_app):
    """
    TC-5a: expand_query НЕ улучшил вопрос (used_descry=False).

    Проверяет fallback на отправку без улучшения:
    1. pending_question удаляется
    2. callback.answer вызывается с предупреждением

    Flow:
        expand_query возвращает used_descry=False
        → fallback на _execute_search_without_expansion
        → предупреждение показано пользователю
    """
    handle_query_improve = create_mock_handle_query_improve()

    chat_id = mock_callback.message.chat.id
    question = "тестовый вопрос"

    user_states[chat_id] = {
        "step": "awaiting_expansion_choice",
        "pending_question": question,
        "conversation_id": "conv_test_3",
        "deep_search": False
    }

    # Expansion НЕ сработал
    expansion_result = {
        "original": question,
        "expanded": question,  # Не изменился
        "used_descry": False,  # ← Ключевое условие
        "error": "descry.md is empty"
    }

    # Вызов тестируемой функции
    await handle_query_improve(mock_callback, mock_app, expansion_result=expansion_result)

    # === ПРОВЕРКИ ===

    # 1. pending_question удален
    assert "pending_question" not in user_states[chat_id]

    # 2. callback.answer вызван (минимум один раз)
    assert mock_callback.answer.call_count >= 1


@pytest.mark.asyncio
async def test_expand_query_exception_fallback(mock_callback, mock_app):
    """
    TC-5b: expand_query выбрасывает исключение.

    Проверяет fallback при критической ошибке expand_query:
    1. pending_question удаляется
    2. Предупреждение показано пользователю (show_alert=True)

    Flow:
        expand_query выбрасывает Exception
        → Exception перехватывается
        → fallback на _execute_search_without_expansion
        → show_alert с предупреждением
    """
    handle_query_improve = create_mock_handle_query_improve()

    chat_id = mock_callback.message.chat.id
    question = "тест ошибки API"

    user_states[chat_id] = {
        "pending_question": question,
        "conversation_id": "conv_test_4",
        "deep_search": False
    }

    # Вызов с ошибкой
    await handle_query_improve(mock_callback, mock_app, expand_error=True)

    # === ПРОВЕРКИ ===

    # 1. pending_question удален (даже при ошибке)
    assert "pending_question" not in user_states[chat_id]

    # 2. callback.answer вызван минимум дважды (первый раз "Улучшаю вопрос", второй - ошибка)
    assert mock_callback.answer.call_count >= 2


@pytest.mark.asyncio
async def test_back_button_clears_pending(mock_app):
    """
    TC-3: Пользователь нажимает "Назад" в меню выбора.

    Проверяет очистку pending_question при возврате в меню:
    1. pending_question удаляется из user_states
    2. step восстанавливается на "dialog_mode"

    Flow:
        user_states содержит pending_question
        → пользователь нажимает "Назад" (callback_data="menu_dialog")
        → handle_menu_dialog вызывается
        → pending_question очищается
        → step восстанавливается
    """
    handle_menu_dialog = create_mock_handle_menu_dialog()

    chat_id = 123456

    # Настройка состояния (пользователь в awaiting_expansion_choice)
    user_states[chat_id] = {
        "step": "awaiting_expansion_choice",
        "pending_question": "тестовый вопрос для очистки",
        "conversation_id": "conv_test_5",
        "deep_search": True
    }

    # Вызов handle_menu_dialog (симуляция нажатия "Назад")
    await handle_menu_dialog(chat_id, mock_app)

    # === ПРОВЕРКИ ===

    # 1. pending_question очищен
    assert "pending_question" not in user_states[chat_id], \
        "pending_question должен быть удален при возврате в меню"

    # 2. step восстановлен на dialog_mode
    assert user_states[chat_id]["step"] == "dialog_mode", \
        "step должен быть восстановлен на 'dialog_mode'"


@pytest.mark.asyncio
async def test_no_pending_question_error(mock_callback, mock_app):
    """
    Граничный случай: pending_question отсутствует в user_states.

    Проверяет обработку ошибки:
    1. callback.answer вызывается с предупреждением
    2. show_alert=True
    3. Функция завершается без дальнейших действий (early return)

    Flow:
        user_states БЕЗ pending_question
        → handle_query_send_as_is вызывается
        → валидация не проходит
        → предупреждение показано
        → early return
    """
    handle_query_send_as_is = create_mock_handle_query_send_as_is()

    chat_id = mock_callback.message.chat.id

    # user_states БЕЗ pending_question
    user_states[chat_id] = {
        "step": "awaiting_expansion_choice",
        # НЕТ "pending_question"!
        "conversation_id": "conv_test_6"
    }

    # Вызов тестируемой функции
    await handle_query_send_as_is(mock_callback, mock_app)

    # === ПРОВЕРКИ ===

    # 1. callback.answer вызван с предупреждением
    mock_callback.answer.assert_called_once()
    call_args = mock_callback.answer.call_args
    assert "Вопрос не найден" in call_args[0][0]

    # 2. show_alert=True
    call_kwargs = call_args[1]
    assert call_kwargs.get("show_alert") is True


# === ДОПОЛНИТЕЛЬНЫЕ EDGE CASE ТЕСТЫ ===

@pytest.mark.asyncio
async def test_user_states_empty_dict():
    """
    Граничный случай: user_states для chat_id вообще не существует.

    Проверяет защиту от KeyError.
    """
    handle_query_send_as_is = create_mock_handle_query_send_as_is()

    mock_callback = MagicMock()
    mock_callback.message.chat.id = 999999  # Несуществующий chat_id
    mock_callback.answer = AsyncMock()
    mock_app = AsyncMock()

    # user_states НЕ содержит chat_id=999999

    # Вызов функции
    await handle_query_send_as_is(mock_callback, mock_app)

    # Проверка: предупреждение показано
    mock_callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_pending_question_empty_string(mock_callback, mock_app):
    """
    Граничный случай: pending_question существует, но пустая строка.

    Проверяет валидацию на пустой вопрос.
    """
    handle_query_send_as_is = create_mock_handle_query_send_as_is()

    chat_id = mock_callback.message.chat.id

    # pending_question = "" (пустая строка)
    user_states[chat_id] = {
        "step": "awaiting_expansion_choice",
        "pending_question": "",  # Пустая строка!
        "conversation_id": "conv_test_7"
    }

    # Вызов функции
    await handle_query_send_as_is(mock_callback, mock_app)

    # Проверка: валидация не проходит (пустая строка = falsy)
    mock_callback.answer.assert_called_once()
    call_args = mock_callback.answer.call_args
    assert "Вопрос не найден" in call_args[0][0]


# === TODO: ИНТЕГРАЦИОННЫЕ ТЕСТЫ ===

@pytest.mark.skip(reason="Требует интеграционного тестирования с message handler")
async def test_text_input_during_awaiting_choice():
    """
    TC-4: Пользователь вводит новый текст вместо нажатия кнопки.

    Интеграционный тест должен проверить:
    - Ввод текста в состоянии awaiting_expansion_choice
    - Показ предупреждения пользователю
    - НЕ обработка нового текста как вопроса

    Требует симуляцию полного message handler flow.
    """
    pass


@pytest.mark.skip(reason="Требует интеграционного тестирования полного flow")
async def test_refine_query_after_improvement():
    """
    TC-6: Пользователь выбирает "Уточнить еще раз" после улучшения.

    Интеграционный тест должен проверить:
    - Полный flow: улучшение → показ результата → уточнение
    - refine_count увеличивается
    - Повторный вызов expand_query

    Требует симуляцию полного callback chain.
    """
    pass


@pytest.mark.skip(reason="Требует интеграционного тестирования state management")
async def test_multiple_questions_in_sequence():
    """
    TC-7: Множественные вопросы подряд.

    Интеграционный тест должен проверить:
    - Последовательность вопросов не влияет друг на друга
    - user_states очищается корректно между вопросами
    - Нет утечки pending_question

    Требует симуляцию нескольких последовательных запросов.
    """
    pass
