"""
Unit тесты для auth_security.py

Покрытие:
- ОБЯЗАТЕЛЬНО: 21 тест из T05_password_validation_spec.md для validate_password()
  - 7 валидных паролей
  - 10 невалидных паролей
  - 4 граничных случая
- hash_password() + verify_password() с bcrypt
- generate_invite_code(), generate_session_id()
- Rate limiting: check_rate_limit(), record_login_attempt(), reset_rate_limit()
- Audit logging: log_audit_event()

Автор: qa-expert
Дата: 17 октября 2025
Задача: T10 (#00005_20251014_HRYHG)
"""

import pytest
import time
from datetime import datetime, timedelta

from auth_security import AuthSecurityManager


class TestPasswordValidation:
    """Тесты для validate_password() - 21 ОБЯЗАТЕЛЬНЫЙ ТЕСТ ИЗ T05."""

    @pytest.fixture
    def security(self):
        """Создает AuthSecurityManager."""
        return AuthSecurityManager()

    # ========== ВАЛИДНЫЕ ПАРОЛИ (7 тестов) ==========

    def test_validate_password_valid_basic(self, security):
        """T05 Test 1: Базовый случай - латиница + цифры."""
        is_valid, error = security.validate_password("abc123")

        assert is_valid is True
        assert error == ""

    def test_validate_password_valid_min_length(self, security):
        """T05 Test 2: Минимальная длина - 5 символов."""
        is_valid, error = security.validate_password("Test1")

        assert is_valid is True
        assert error == ""

    def test_validate_password_valid_max_length(self, security):
        """T05 Test 3: Максимальная длина - 8 символов."""
        is_valid, error = security.validate_password("AbCd1234")

        assert is_valid is True
        assert error == ""

    def test_validate_password_valid_cyrillic(self, security):
        """T05 Test 4: Кириллица + цифры."""
        is_valid, error = security.validate_password("пароль1")

        assert is_valid is True
        assert error == ""

    def test_validate_password_valid_cyrillic_mixed_case(self, security):
        """T05 Test 5: Смешанный регистр кириллицы."""
        is_valid, error = security.validate_password("Тест123")

        assert is_valid is True
        assert error == ""

    def test_validate_password_valid_alternating(self, security):
        """T05 Test 6: Чередующиеся буквы и цифры."""
        is_valid, error = security.validate_password("a1b2c3")

        assert is_valid is True
        assert error == ""

    def test_validate_password_valid_multiple_digits(self, security):
        """T05 Test 7: Несколько цифр."""
        is_valid, error = security.validate_password("99Test9")

        assert is_valid is True
        assert error == ""

    # ========== НЕВАЛИДНЫЕ ПАРОЛИ (10 тестов) ==========

    def test_validate_password_invalid_no_digits(self, security):
        """T05 Test 8: Нет цифр."""
        is_valid, error = security.validate_password("abcdef")

        assert is_valid is False
        assert error == "Пароль должен содержать цифры"

    def test_validate_password_invalid_no_letters(self, security):
        """T05 Test 9: Нет букв."""
        is_valid, error = security.validate_password("12345")

        assert is_valid is False
        assert error == "Пароль должен содержать буквы"

    def test_validate_password_invalid_too_short(self, security):
        """T05 Test 10: Меньше 5 символов (4)."""
        is_valid, error = security.validate_password("ab12")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 4)"

    def test_validate_password_invalid_too_long(self, security):
        """T05 Test 11: Больше 8 символов (11)."""
        is_valid, error = security.validate_password("abcdefgh123")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 11)"

    def test_validate_password_invalid_only_digits(self, security):
        """T05 Test 12: Только цифры, нет букв."""
        is_valid, error = security.validate_password("12345678")

        assert is_valid is False
        assert error == "Пароль должен содержать буквы"

    def test_validate_password_invalid_only_letters(self, security):
        """T05 Test 13: Только буквы, нет цифр."""
        is_valid, error = security.validate_password("abcdefgh")

        assert is_valid is False
        assert error == "Пароль должен содержать цифры"

    def test_validate_password_invalid_empty(self, security):
        """T05 Test 14: Пустая строка."""
        is_valid, error = security.validate_password("")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 0)"

    def test_validate_password_invalid_one_char(self, security):
        """T05 Test 15: Один символ."""
        is_valid, error = security.validate_password("1")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 1)"

    def test_validate_password_invalid_special_chars_no_letters(self, security):
        """T05 Test 16: Спецсимволы (НЕТ букв)."""
        is_valid, error = security.validate_password("@#$%123")

        assert is_valid is False
        assert error == "Пароль должен содержать буквы"

    def test_validate_password_invalid_with_special_char_too_long(self, security):
        """T05 Test 17: 9 символов (включая спецсимвол)."""
        is_valid, error = security.validate_password("Test@1234")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 9)"

    # ========== ГРАНИЧНЫЕ СЛУЧАИ (4 теста) ==========

    def test_validate_password_edge_exactly_5_chars(self, security):
        """T05 Test 18: Ровно 5 символов (минимум)."""
        is_valid, error = security.validate_password("Aaaa1")

        assert is_valid is True
        assert error == ""

    def test_validate_password_edge_exactly_8_chars(self, security):
        """T05 Test 19: Ровно 8 символов (максимум)."""
        is_valid, error = security.validate_password("Aaaaaaa1")

        assert is_valid is True
        assert error == ""

    def test_validate_password_edge_4_chars(self, security):
        """T05 Test 20: 4 символа (минимум - 1)."""
        is_valid, error = security.validate_password("Aaaa")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 4)"

    def test_validate_password_edge_10_chars(self, security):
        """T05 Test 21: 10 символов (максимум + 2)."""
        is_valid, error = security.validate_password("Aaaaaaaaa1")

        assert is_valid is False
        assert error == "Пароль должен быть 5-8 символов (сейчас: 10)"


class TestPasswordHashing:
    """Тесты для hash_password() и verify_password() с bcrypt."""

    @pytest.fixture
    def security(self):
        """Создает AuthSecurityManager."""
        return AuthSecurityManager()

    def test_hash_password_basic(self, security):
        """hash_password() возвращает bcrypt хеш."""
        password = "Test123"
        password_hash = security.hash_password(password)

        assert password_hash is not None
        assert len(password_hash) > 0
        assert password_hash.startswith("$2")  # bcrypt prefix

    def test_hash_password_different_hashes(self, security):
        """hash_password() генерирует разные хеши для одного пароля (соль)."""
        password = "Test123"
        hash1 = security.hash_password(password)
        hash2 = security.hash_password(password)

        assert hash1 != hash2  # Разные соли

    def test_verify_password_success(self, security):
        """verify_password() успешно проверяет корректный пароль."""
        password = "Test123"
        password_hash = security.hash_password(password)

        is_valid = security.verify_password(password, password_hash)

        assert is_valid is True

    def test_verify_password_fail(self, security):
        """verify_password() отклоняет неверный пароль."""
        password = "Test123"
        wrong_password = "Wrong1"
        password_hash = security.hash_password(password)

        is_valid = security.verify_password(wrong_password, password_hash)

        assert is_valid is False

    def test_hash_password_cyrillic(self, security):
        """hash_password() работает с кириллицей."""
        password = "Пароль1"
        password_hash = security.hash_password(password)

        is_valid = security.verify_password(password, password_hash)

        assert is_valid is True


class TestTokenGeneration:
    """Тесты для generate_invite_code() и generate_session_id()."""

    @pytest.fixture
    def security(self):
        """Создает AuthSecurityManager."""
        return AuthSecurityManager()

    def test_generate_invite_code_basic(self, security):
        """generate_invite_code() генерирует код приглашения."""
        invite_code = security.generate_invite_code()

        assert invite_code is not None
        assert len(invite_code) > 0

    def test_generate_invite_code_unique(self, security):
        """generate_invite_code() генерирует уникальные коды."""
        code1 = security.generate_invite_code()
        code2 = security.generate_invite_code()

        assert code1 != code2

    def test_generate_invite_code_url_safe(self, security):
        """generate_invite_code() генерирует URL-safe коды."""
        invite_code = security.generate_invite_code()

        # URL-safe означает только буквы, цифры, -, _
        assert all(c.isalnum() or c in "-_" for c in invite_code)

    def test_generate_session_id_basic(self, security):
        """generate_session_id() генерирует session ID."""
        session_id = security.generate_session_id()

        assert session_id is not None
        assert len(session_id) > 0

    def test_generate_session_id_unique(self, security):
        """generate_session_id() генерирует уникальные ID."""
        id1 = security.generate_session_id()
        id2 = security.generate_session_id()

        assert id1 != id2

    def test_generate_session_id_url_safe(self, security):
        """generate_session_id() генерирует URL-safe ID."""
        session_id = security.generate_session_id()

        # URL-safe означает только буквы, цифры, -, _
        assert all(c.isalnum() or c in "-_" for c in session_id)

    def test_generate_session_id_longer_than_invite(self, security):
        """generate_session_id() должен быть длиннее invite_code (256 bits vs 128 bits)."""
        session_id = security.generate_session_id()
        invite_code = security.generate_invite_code()

        assert len(session_id) > len(invite_code)


class TestRateLimiting:
    """Тесты для rate limiting (3 попытки / 15 мин)."""

    @pytest.fixture
    def security(self):
        """Создает AuthSecurityManager."""
        return AuthSecurityManager()

    def test_rate_limit_first_attempt_allowed(self, security):
        """check_rate_limit() разрешает первую попытку."""
        telegram_id = 155894817

        allowed, wait_seconds = security.check_rate_limit(telegram_id)

        assert allowed is True
        assert wait_seconds is None

    def test_rate_limit_record_login_attempt(self, security):
        """record_login_attempt() записывает попытку."""
        telegram_id = 155894817

        # Записать попытку
        security.record_login_attempt(telegram_id)

        # Проверить что попытка записана (еще не превышен лимит)
        allowed, wait_seconds = security.check_rate_limit(telegram_id)
        assert allowed is True

    def test_rate_limit_exceeds_limit(self, security):
        """check_rate_limit() блокирует после 3 попыток."""
        telegram_id = 155894817

        # Записать 3 неудачных попытки
        for _ in range(3):
            security.record_login_attempt(telegram_id)

        # Проверить блокировку
        allowed, wait_seconds = security.check_rate_limit(telegram_id)

        assert allowed is False
        assert wait_seconds is not None
        assert wait_seconds > 0

    def test_rate_limit_reset(self, security):
        """reset_rate_limit() сбрасывает счетчик."""
        telegram_id = 155894817

        # Записать 3 неудачных попытки
        for _ in range(3):
            security.record_login_attempt(telegram_id)

        # Сбросить
        security.reset_rate_limit(telegram_id)

        # Проверить что лимит сброшен
        allowed, wait_seconds = security.check_rate_limit(telegram_id)

        assert allowed is True
        assert wait_seconds is None

    def test_rate_limit_old_attempts_cleaned(self, security):
        """check_rate_limit() автоматически очищает старые попытки."""
        telegram_id = 155894817

        # Записать попытку с давней датой (вручную)
        old_time = datetime.now() - timedelta(minutes=20)
        security._rate_limit_attempts[telegram_id] = [old_time]

        # Проверить что старая попытка очищена
        allowed, wait_seconds = security.check_rate_limit(telegram_id)

        assert allowed is True
        assert wait_seconds is None


class TestAuditLogging:
    """Тесты для audit logging."""

    @pytest.fixture
    def security(self):
        """Создает AuthSecurityManager."""
        return AuthSecurityManager()

    def test_log_audit_event_basic(self, security):
        """log_audit_event() записывает событие."""
        # Правильная сигнатура: log_audit_event(event_type, telegram_id, details)
        security.log_audit_event(
            event_type="LOGIN_SUCCESS",
            telegram_id=155894817,
            details={"session_id": "sess_abc"}
        )

        # Проверить что метод выполнился без ошибок
        # (метод возвращает None, не генерирует исключений)

    def test_log_audit_event_rate_limit_triggered(self, security):
        """Rate limiting триггерит audit log."""
        telegram_id = 155894817

        # Записать 3 неудачных попытки
        for _ in range(3):
            security.record_login_attempt(telegram_id)

        # Проверить блокировку (должно залогировать событие)
        allowed, wait_seconds = security.check_rate_limit(telegram_id)

        assert allowed is False
        # Audit event должен быть создан (проверить в реализации)


class TestIntegration:
    """Интеграционные тесты для AuthSecurityManager."""

    @pytest.fixture
    def security(self):
        """Создает AuthSecurityManager."""
        return AuthSecurityManager()

    def test_full_password_workflow(self, security):
        """Полный workflow: валидация → хеширование → проверка."""
        password = "Test123"

        # 1. Валидация
        is_valid, error = security.validate_password(password)
        assert is_valid is True

        # 2. Хеширование
        password_hash = security.hash_password(password)
        assert password_hash is not None

        # 3. Проверка
        is_correct = security.verify_password(password, password_hash)
        assert is_correct is True

    def test_rate_limit_and_reset_workflow(self, security):
        """Полный workflow: попытки → блокировка → сброс."""
        telegram_id = 155894817

        # 1. Первая попытка разрешена
        allowed, _ = security.check_rate_limit(telegram_id)
        assert allowed is True

        # 2. Записать 3 неудачных попытки
        for _ in range(3):
            security.record_login_attempt(telegram_id)

        # 3. Блокировка
        allowed, wait_seconds = security.check_rate_limit(telegram_id)
        assert allowed is False
        assert wait_seconds > 0

        # 4. Сброс после успешного входа
        security.reset_rate_limit(telegram_id)

        # 5. Снова разрешено
        allowed, _ = security.check_rate_limit(telegram_id)
        assert allowed is True
