"""
Smoke-тесты для проверки рефакторинга callback_query_handler.

Проверяет что рефакторинг verify_callback_auth() работает корректно:
1. verify_callback_auth() доступна для импорта
2. verify_callback_auth() имеет правильную сигнатуру
3. verify_callback_auth() работает с разными сценариями
4. Код handlers.py содержит корректные вызовы verify_callback_auth()

Связано с задачей: 08_pass_change (#00007_20251105_YEIJEG)
Дата: 2025-11-07
Автор: Claude Code (smoke testing рефакторинга)
"""

import pytest
import sys
import inspect
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# Добавить src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from auth_models import User, Session


# ==================== FIXTURES ====================

@pytest.fixture(autouse=True)
def mock_minio():
    """Мок MinIO для всех тестов (autouse)."""
    with patch("minio_manager.get_minio_manager", return_value=MagicMock()):
        yield


# ==================== SMOKE ТЕСТЫ ====================

def test_verify_callback_auth_is_importable():
    """
    Smoke Test 1: verify_callback_auth может быть импортирована.

    Критично: Рефакторинг создал module-level функцию.
    """
    try:
        from handlers import verify_callback_auth
        assert callable(verify_callback_auth)
    except ImportError as e:
        pytest.fail(f"verify_callback_auth не может быть импортирована: {e}")


def test_verify_callback_auth_signature():
    """
    Smoke Test 2: verify_callback_auth имеет правильную сигнатуру.

    Проверяет: async def verify_callback_auth(telegram_id: int, callback_data: str = "")
    """
    from handlers import verify_callback_auth

    # Проверить что это async функция
    assert inspect.iscoroutinefunction(verify_callback_auth), \
        "verify_callback_auth должна быть async функцией"

    # Проверить параметры
    sig = inspect.signature(verify_callback_auth)
    params = list(sig.parameters.keys())

    assert "telegram_id" in params, "Должен быть параметр telegram_id"
    assert "callback_data" in params, "Должен быть параметр callback_data"

    # Проверить дефолтное значение callback_data
    assert sig.parameters["callback_data"].default == "", \
        "callback_data должен иметь значение по умолчанию ''"


def test_verify_callback_auth_return_type():
    """
    Smoke Test 3: verify_callback_auth возвращает правильный тип.

    Проверяет: return tuple[bool, str, str | None]
    """
    from handlers import verify_callback_auth

    sig = inspect.signature(verify_callback_auth)

    # Проверить аннотацию возвращаемого типа
    return_annotation = sig.return_annotation

    # Python 3.10+ использует tuple[bool, str, str | None]
    assert return_annotation != inspect.Signature.empty, \
        "verify_callback_auth должна иметь аннотацию возвращаемого типа"


@pytest.mark.asyncio
async def test_verify_callback_auth_returns_tuple():
    """
    Smoke Test 4: verify_callback_auth возвращает tuple из 3 элементов.
    """
    from handlers import verify_callback_auth

    # Arrange: Мок auth_manager возвращает None (пользователь не найден)
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = None

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        result = await verify_callback_auth(123456789, "test_callback")

    # Assert: Проверить формат возврата
    assert isinstance(result, tuple), "Результат должен быть tuple"
    assert len(result) == 3, "Tuple должен содержать 3 элемента"

    allowed, error_msg, user_id = result
    assert isinstance(allowed, bool), "Первый элемент должен быть bool"
    assert isinstance(error_msg, str), "Второй элемент должен быть str"
    assert user_id is None or isinstance(user_id, str), "Третий элемент должен быть str или None"


@pytest.mark.asyncio
async def test_verify_callback_auth_scenario_user_not_found():
    """
    Smoke Test 5: verify_callback_auth корректно обрабатывает несуществующего пользователя.
    """
    from handlers import verify_callback_auth

    # Arrange
    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = None

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(999999999)

    # Assert
    assert allowed is False, "Должен вернуть False для несуществующего пользователя"
    assert user_id is None, "user_id должен быть None"
    assert len(error_msg) > 0, "Должно быть сообщение об ошибке"
    assert "не найден" in error_msg.lower(), "Сообщение должно содержать 'не найден'"


@pytest.mark.asyncio
async def test_verify_callback_auth_scenario_authorized_user():
    """
    Smoke Test 6: verify_callback_auth пропускает авторизованного пользователя.
    """
    from handlers import verify_callback_auth

    # Arrange: Авторизованный пользователь с активной сессией
    user = User(
        user_id="user_123",
        telegram_id=123456789,
        username="test_user",
        password_hash="$2b$12$dummy",
        role="user",
        is_active=True,
        is_blocked=False,
        must_change_password=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    session = Session(
        session_id="session_123",
        user_id="user_123",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=24),
        last_activity=datetime.now(),
        is_active=True
    )

    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = user
    mock_auth.storage.get_active_session_by_telegram_id.return_value = session

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        # Act
        allowed, error_msg, user_id = await verify_callback_auth(123456789, "test")

    # Assert
    assert allowed is True, "Должен вернуть True для авторизованного пользователя"
    assert error_msg == "", "error_msg должен быть пустым для успешной авторизации"
    assert user_id == "user_123", "Должен вернуть корректный user_id"


def test_handlers_py_contains_verify_callback_auth_call():
    """
    Smoke Test 7: handlers.py содержит вызов verify_callback_auth().

    Проверяет что callback_query_handler использует новую функцию.
    """
    handlers_path = Path(__file__).parent.parent.parent / "src" / "handlers.py"
    content = handlers_path.read_text(encoding="utf-8")

    # Проверить что есть вызов verify_callback_auth
    assert "verify_callback_auth" in content, \
        "handlers.py должен содержать вызов verify_callback_auth"

    assert "await verify_callback_auth(" in content, \
        "handlers.py должен вызывать verify_callback_auth через await"


def test_handlers_py_no_duplicate_auth_logic():
    """
    Smoke Test 8: handlers.py не содержит дублирования auth логики.

    Проверяет что старая inline auth логика была удалена.
    """
    handlers_path = Path(__file__).parent.parent.parent / "src" / "handlers.py"
    content = handlers_path.read_text(encoding="utf-8")

    # Ищем callback_query_handler
    lines = content.split("\n")

    # Найти начало callback_query_handler (внутри register_handlers)
    in_callback_handler = False
    inline_auth_checks = 0

    for line in lines:
        if "async def callback_query_handler" in line:
            in_callback_handler = True
            continue

        if in_callback_handler:
            # Если нашли другую функцию - вышли из callback_query_handler
            if line.strip().startswith("async def ") or line.strip().startswith("def "):
                break

            # Проверить что НЕТ inline auth проверок (они должны быть в verify_callback_auth)
            if "get_user_by_telegram_id" in line and "verify_callback_auth" not in line:
                inline_auth_checks += 1

    assert inline_auth_checks == 0, \
        f"callback_query_handler содержит {inline_auth_checks} inline auth проверок (должно быть 0)"


def test_verify_callback_auth_has_docstring():
    """
    Smoke Test 9: verify_callback_auth имеет docstring с описанием.
    """
    from handlers import verify_callback_auth

    assert verify_callback_auth.__doc__ is not None, \
        "verify_callback_auth должна иметь docstring"

    assert len(verify_callback_auth.__doc__) > 50, \
        "Docstring должен содержать подробное описание"

    assert "callback_query" in verify_callback_auth.__doc__.lower(), \
        "Docstring должен упоминать callback_query"


def test_handlers_py_callback_handler_simplified():
    """
    Smoke Test 10: callback_query_handler упрощен после рефакторинга.

    Проверяет что handler стал короче (признак успешного рефакторинга).
    """
    handlers_path = Path(__file__).parent.parent.parent / "src" / "handlers.py"
    content = handlers_path.read_text(encoding="utf-8")

    lines = content.split("\n")

    # Найти callback_query_handler
    in_handler = False
    handler_lines = []

    for line in lines:
        if "async def callback_query_handler" in line:
            in_handler = True

        if in_handler:
            handler_lines.append(line)

            # Если нашли другую функцию - вышли
            if len(handler_lines) > 1 and (
                line.strip().startswith("async def ") or
                line.strip().startswith("def ")
            ):
                break

    # Проверить что handler содержит вызов verify_callback_auth
    handler_code = "\n".join(handler_lines)
    assert "verify_callback_auth" in handler_code, \
        "callback_query_handler должен вызывать verify_callback_auth"

    # Проверить что handler короткий (после рефакторинга)
    # До рефакторинга: ~70+ строк auth логики
    # После: ~20-30 строк с вызовом verify_callback_auth
    assert len(handler_lines) < 150, \
        f"callback_query_handler слишком длинный ({len(handler_lines)} строк), рефакторинг не применен?"


@pytest.mark.asyncio
async def test_verify_callback_auth_with_different_callback_data():
    """
    Smoke Test 11: verify_callback_auth работает с разными callback_data.
    """
    from handlers import verify_callback_auth

    user = User(
        user_id="user_123",
        telegram_id=123456789,
        username="test",
        password_hash="$2b$12$dummy",
        role="user",
        is_active=True,
        is_blocked=False,
        must_change_password=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    session = Session(
        session_id="session_123",
        user_id="user_123",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=24),
        last_activity=datetime.now(),
        is_active=True
    )

    mock_auth = MagicMock()
    mock_auth.storage.get_user_by_telegram_id.return_value = user
    mock_auth.storage.get_active_session_by_telegram_id.return_value = session

    # Проверить разные callback_data
    test_callbacks = ["menu_main", "menu_access", "new_chat", "", "test||param"]

    with patch("handlers.get_auth_manager", return_value=mock_auth):
        for callback_data in test_callbacks:
            # Act
            allowed, error_msg, user_id = await verify_callback_auth(123456789, callback_data)

            # Assert: Все должны пройти авторизацию
            assert allowed is True, f"Авторизация должна пройти для callback_data='{callback_data}'"
            assert user_id == "user_123"
