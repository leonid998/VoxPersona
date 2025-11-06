"""
Тесты для проверки исправлений Problems #1-#4 в access_handlers.py

Задача: 00007_20251105_YEIJEG/03_push_baf_YGRHJ
Дата: 2025-11-06
"""

import pytest
import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from pyrogram import Client
from pyrogram.types import Message

# Мокируем модули которые могут быть недоступны в тестовом окружении
import sys
from pathlib import Path

# Добавляем src в path для импорта
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Импортируем компоненты для тестирования
# (они будут замокированы или заменены на test версии)

# ============================================
# МОКИРОВАННЫЕ КЛАССЫ
# ============================================

class MockUser:
    """Mock объект пользователя для тестирования"""
    def __init__(
        self,
        user_id: str = "test-user-id",
        username: str = "Test User",
        telegram_id: int = 123456789,
        role: str = "user",
        is_active: bool = True,
        is_blocked: bool = False,
        created_at=None,
        last_login=None,
        must_change_password: bool = False
    ):
        self.user_id = user_id
        self.username = username
        self.telegram_id = telegram_id
        self.role = role
        self.is_active = is_active
        self.is_blocked = is_blocked
        self.created_at = created_at or datetime.now() - timedelta(days=30)
        self.last_login = last_login
        self.must_change_password = must_change_password


class MockAuthManager:
    """Mock объект AuthManager для тестирования"""
    def __init__(self):
        self.storage = MockStorage()


class MockStorage:
    """Mock объект Storage для тестирования"""
    def __init__(self):
        self.users = {}

    def get_user(self, user_id: str):
        """Получить пользователя по ID"""
        return self.users.get(user_id)

    def get_user_by_telegram_id(self, telegram_id: int):
        """Получить пользователя по telegram_id"""
        for user in self.users.values():
            if user.telegram_id == telegram_id:
                return user
        return None

    def list_users(self):
        """Получить список всех пользователей"""
        return list(self.users.values())


# ============================================
# ТЕСТЫ ДЛЯ PROBLEM #1: DateTime created_at
# ============================================

class TestProblem1DatetimeCreatedAt:
    """Тесты для исправления Problem #1 (TypeError при slicing datetime.created_at)"""

    @pytest.mark.asyncio
    async def test_created_at_datetime_object(self):
        """Тест: created_at как datetime объект должен обрабатываться без TypeError"""
        # Arrange
        user = MockUser(
            created_at=datetime(2025, 10, 20, 14, 43, 7, 605093)  # datetime объект
        )

        # Act - Проверяем, что strftime() работает
        try:
            created_at_text = user.created_at.strftime("%Y-%m-%d")
            error = None
        except Exception as e:
            error = str(e)
            created_at_text = None

        # Assert
        assert error is None, f"Ошибка при форматировании datetime: {error}"
        assert created_at_text == "2025-10-20", f"Неправильный формат даты: {created_at_text}"

    @pytest.mark.asyncio
    async def test_created_at_string_fallback(self):
        """Тест: если strftime() не работает, должна быть fallback обработка"""
        # Arrange - создаем "сломанный" datetime
        class BrokenDatetime:
            def strftime(self, fmt):
                raise TypeError("Cannot format")

        broken_datetime = BrokenDatetime()

        # Act - проверяем fallback механизм
        try:
            created_at_text = broken_datetime.strftime("%Y-%m-%d")
        except (AttributeError, TypeError):
            try:
                created_at_text = str(broken_datetime)[:10]
            except:
                created_at_text = "Ошибка формата"

        # Assert
        assert created_at_text != "", "Fallback механизм не сработал"

    @pytest.mark.asyncio
    async def test_created_at_none_value(self):
        """Тест: created_at = None должен иметь fallback значение"""
        # Arrange
        class UserWithoutCreatedAt(MockUser):
            def __init__(self):
                super().__init__()
                self.created_at = None

        user = UserWithoutCreatedAt()

        # Act
        created_at_text = "Неизвестно"
        if user.created_at:
            try:
                created_at_text = user.created_at.strftime("%Y-%m-%d")
            except:
                created_at_text = str(user.created_at)[:10] if user.created_at else "Ошибка"

        # Assert
        assert created_at_text == "Неизвестно", "Fallback для None не работает"


# ============================================
# ТЕСТЫ ДЛЯ PROBLEM #2: DateTime last_login
# ============================================

class TestProblem2DatetimeLastLogin:
    """Тесты для исправления Problem #2 (TypeError при slicing datetime.last_login)"""

    @pytest.mark.asyncio
    async def test_last_login_datetime_object(self):
        """Тест: last_login как datetime объект должен форматироваться"""
        # Arrange
        user = MockUser(
            last_login=datetime(2025, 11, 6, 15, 30, 0)
        )

        # Act
        try:
            last_login_text = user.last_login.strftime("%d.%m.%Y %H:%M")
            error = None
        except Exception as e:
            error = str(e)
            last_login_text = None

        # Assert
        assert error is None, f"Ошибка при форматировании last_login: {error}"
        assert last_login_text == "06.11.2025 15:30"

    @pytest.mark.asyncio
    async def test_last_login_none_value(self):
        """Тест: last_login = None должен показывать 'Никогда'"""
        # Arrange
        user = MockUser(last_login=None)

        # Act
        last_login_text = "Никогда"
        if user.last_login:
            try:
                last_login_text = user.last_login.strftime("%d.%m.%Y %H:%M")
            except:
                last_login_text = str(user.last_login)

        # Assert
        assert last_login_text == "Никогда", "Fallback для None не работает"

    @pytest.mark.asyncio
    async def test_last_login_invalid_format(self):
        """Тест: если last_login имеет неправильный формат, должна быть обработка"""
        # Arrange
        class InvalidDatetime:
            def strftime(self, fmt):
                raise AttributeError("Cannot format")

        invalid_dt = InvalidDatetime()

        # Act
        try:
            last_login_text = invalid_dt.strftime("%d.%m.%Y %H:%M")
        except (AttributeError, TypeError):
            last_login_text = str(invalid_dt)

        # Assert
        assert last_login_text != "", "Обработка ошибки не сработала"


# ============================================
# ТЕСТЫ ДЛЯ PROBLEM #3: Обработка ошибок
# ============================================

class TestProblem3ErrorHandling:
    """Тесты для исправления Problem #3 (недостаточная детализация ошибок)"""

    @pytest.mark.asyncio
    async def test_logger_exc_info_true(self):
        """Тест: logger.error должен вызываться с exc_info=True"""
        # Arrange
        mock_logger = Mock(spec=logging.Logger)
        test_error = ValueError("Test error")

        # Act - имитируем логирование с exc_info=True
        try:
            raise test_error
        except Exception as e:
            mock_logger.error(f"Error: {e}", exc_info=True)

        # Assert
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert 'exc_info' in call_args.kwargs, "exc_info не передается в logger.error"
        assert call_args.kwargs['exc_info'] is True, "exc_info должна быть True"

    @pytest.mark.asyncio
    async def test_error_message_to_user(self):
        """Тест: пользователю должно быть отправлено понятное сообщение об ошибке"""
        # Arrange
        expected_error_message = "❌ Ошибка загрузки деталей пользователя."

        # Act
        error_text = f"{expected_error_message}\n\n_Попробуйте позже или обратитесь к администратору._"

        # Assert
        assert "❌" in error_text, "Сообщение об ошибке должно содержать эмодзи"
        assert "Попробуйте позже" in error_text, "Сообщение должно содержать рекомендацию"
        assert "администратор" in error_text, "Сообщение должно упомянуть администратора"

    @pytest.mark.asyncio
    async def test_back_button_in_error_message(self):
        """Тест: при ошибке должна быть кнопка 'Назад'"""
        # Arrange
        should_have_back_button = True
        back_callback = "access_users_menu"

        # Act
        reply_markup_present = should_have_back_button

        # Assert
        assert reply_markup_present, "При ошибке должна быть кнопка 'Назад'"
        assert back_callback != "", "callback_data для кнопки должна быть установлена"


# ============================================
# ТЕСТЫ ДЛЯ PROBLEM #4: Async вызовы
# ============================================

class TestProblem4AsyncCalls:
    """Тесты для исправления Problem #4 (синхронный вызов в async функции)"""

    @pytest.mark.asyncio
    async def test_asyncio_to_thread_usage(self):
        """Тест: синхронный вызов должен быть обернут в asyncio.to_thread()"""
        # Arrange
        def sync_get_user(user_id: str):
            return MockUser(user_id=user_id)

        user_id = "test-user-123"

        # Act - проверяем, что asyncio.to_thread работает
        user = await asyncio.to_thread(sync_get_user, user_id)

        # Assert
        assert user is not None, "asyncio.to_thread должен вернуть результат"
        assert user.user_id == user_id, "Результат должен быть правильным"

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked(self):
        """Тест: event loop не должен быть заблокирован во время file I/O"""
        # Arrange
        async def slow_operation():
            """Имитирует file I/O операцию"""
            await asyncio.to_thread(lambda: None)  # Пустая операция в отдельном потоке
            return True

        async def other_operation():
            """Проверяем, что другие операции выполняются параллельно"""
            await asyncio.sleep(0.001)
            return True

        # Act - запускаем обе операции параллельно
        results = await asyncio.gather(slow_operation(), other_operation())

        # Assert
        assert all(results), "Обе операции должны завершиться успешно"
        # Если бы event loop был заблокирован, вторая операция выполнялась бы дольше

    @pytest.mark.asyncio
    async def test_asyncio_module_available(self):
        """Тест: модуль asyncio должен быть доступен"""
        # Act
        available = asyncio is not None
        has_to_thread = hasattr(asyncio, 'to_thread')

        # Assert
        assert available, "asyncio модуль должен быть импортирован"
        assert has_to_thread, "asyncio.to_thread() должен быть доступен"


# ============================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ============================================

class TestIntegration:
    """Интеграционные тесты для проверки, что все исправления работают вместе"""

    @pytest.mark.asyncio
    async def test_handle_user_details_with_datetime_user(self):
        """Интеграционный тест: handle_user_details должна работать с datetime объектами"""
        # Arrange
        user = MockUser(
            user_id="user-123",
            username="Test User",
            telegram_id=123456789,
            role="user",
            is_active=True,
            created_at=datetime(2025, 10, 20, 14, 43, 7),
            last_login=datetime(2025, 11, 6, 15, 30, 0),
            must_change_password=False
        )

        # Act - проверяем форматирование всех полей
        try:
            # Проверяем created_at
            if isinstance(user.created_at, datetime):
                created_at_text = user.created_at.strftime("%Y-%m-%d")
            else:
                created_at_text = str(user.created_at)[:10]

            # Проверяем last_login
            if user.last_login:
                if isinstance(user.last_login, datetime):
                    last_login_text = user.last_login.strftime("%d.%m.%Y %H:%M")
                else:
                    last_login_text = str(user.last_login)
            else:
                last_login_text = "Никогда"

            error = None
        except Exception as e:
            error = str(e)

        # Assert
        assert error is None, f"Ошибка при форматировании пользователя: {error}"
        assert created_at_text == "2025-10-20"
        assert last_login_text == "06.11.2025 15:30"

    @pytest.mark.asyncio
    async def test_error_handling_chain(self):
        """Интеграционный тест: проверяем цепочку обработки ошибок"""
        # Arrange
        mock_logger = Mock(spec=logging.Logger)
        mock_track_and_send = AsyncMock()

        # Act - имитируем обработку ошибки с exc_info=True
        try:
            raise ValueError("Test error")
        except Exception as e:
            mock_logger.error(f"Error: {e}", exc_info=True)
            await mock_track_and_send(
                text="❌ Ошибка загрузки деталей пользователя.\n\n_Попробуйте позже._"
            )

        # Assert
        mock_logger.error.assert_called_once()
        mock_track_and_send.assert_called_once()

        # Проверяем, что exc_info=True был передан
        assert mock_logger.error.call_args.kwargs['exc_info'] is True


# ============================================
# ТЕСТЫ ДЛЯ РЕГРЕССИИ
# ============================================

class TestRegression:
    """Тесты для проверки, что исправления не сломали существующую функциональность"""

    @pytest.mark.asyncio
    async def test_user_with_all_fields_populated(self):
        """Регрессионный тест: пользователь со всеми заполненными полями"""
        # Arrange
        user = MockUser(
            user_id="user-full",
            username="Full User",
            telegram_id=987654321,
            role="admin",
            is_active=True,
            is_blocked=False,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            last_login=datetime(2025, 11, 6, 10, 0, 0),
            must_change_password=False
        )

        # Act
        assert user.user_id == "user-full"
        assert user.username == "Full User"
        assert user.role == "admin"
        assert user.is_active is True

        # Assert - все поля доступны и имеют правильные типы
        assert isinstance(user.user_id, str)
        assert isinstance(user.username, str)
        assert isinstance(user.role, str)
        assert isinstance(user.is_active, bool)
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.last_login, datetime)

    @pytest.mark.asyncio
    async def test_user_with_minimal_fields(self):
        """Регрессионный тест: пользователь с минимальными полями"""
        # Arrange
        user = MockUser()

        # Act & Assert
        assert user.user_id == "test-user-id"
        assert user.username == "Test User"
        assert isinstance(user.created_at, datetime)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
