"""
Тесты для ФАЗА 2: Issues 1.3 + 1.4 - Унификация валидации паролей

Проверяет:
- Централизованная валидация через auth.security.validate_password()
- Политика паролей: 5-8 символов, буквы + цифры обязательны
- UI сообщения обновлены с "минимум 8" на "5-8 символов"

Author: agent-organizer
Date: 2025-11-05
Task: #00007_20251105_YEIJEG/01_bag_8563784537 (Issues 1.3 + 1.4)
"""

import pytest
import sys
from pathlib import Path

# Настройка sys.path для импорта модулей из src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth_security import AuthSecurityManager


class TestPhase2PasswordValidation:
    """Тесты для унифицированной валидации паролей (Issues 1.3 + 1.4)."""

    def test_password_too_short(self):
        """Тест: пароль меньше 5 символов отклоняется."""
        security = AuthSecurityManager()

        # 4 символа - слишком короткий
        is_valid, error_msg = security.validate_password("abc1")

        assert is_valid == False
        assert "5-8 символов" in error_msg
        assert "4" in error_msg  # Указывает текущую длину

    def test_password_too_long(self):
        """Тест: пароль больше 8 символов отклоняется."""
        security = AuthSecurityManager()

        # 11 символов - слишком длинный
        is_valid, error_msg = security.validate_password("abcdefgh123")

        assert is_valid == False
        assert "5-8 символов" in error_msg
        assert "11" in error_msg  # Указывает текущую длину

    def test_password_no_letters(self):
        """Тест: пароль без букв отклоняется."""
        security = AuthSecurityManager()

        # Только цифры
        is_valid, error_msg = security.validate_password("12345")

        assert is_valid == False
        assert "буквы" in error_msg.lower()

    def test_password_no_digits(self):
        """Тест: пароль без цифр отклоняется."""
        security = AuthSecurityManager()

        # Только буквы
        is_valid, error_msg = security.validate_password("abcde")

        assert is_valid == False
        assert "цифры" in error_msg.lower()

    def test_password_valid_5_chars(self):
        """Тест: минимальный валидный пароль (5 символов) принимается."""
        security = AuthSecurityManager()

        # 5 символов: буквы + цифры
        is_valid, error_msg = security.validate_password("abc12")

        assert is_valid == True
        assert error_msg == ""

    def test_password_valid_8_chars(self):
        """Тест: максимальный валидный пароль (8 символов) принимается."""
        security = AuthSecurityManager()

        # 8 символов: буквы + цифры
        is_valid, error_msg = security.validate_password("abcd1234")

        assert is_valid == True
        assert error_msg == ""

    def test_password_valid_mixed_case(self):
        """Тест: пароль с заглавными буквами принимается."""
        security = AuthSecurityManager()

        # Смешанный регистр
        is_valid, error_msg = security.validate_password("Test123")

        assert is_valid == True
        assert error_msg == ""

    def test_password_boundary_exactly_5(self):
        """Тест: граничное значение - ровно 5 символов."""
        security = AuthSecurityManager()

        is_valid, error_msg = security.validate_password("a1b2c")

        assert is_valid == True
        assert error_msg == ""

    def test_password_boundary_exactly_8(self):
        """Тест: граничное значение - ровно 8 символов."""
        security = AuthSecurityManager()

        is_valid, error_msg = security.validate_password("a1b2c3d4")

        assert is_valid == True
        assert error_msg == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
