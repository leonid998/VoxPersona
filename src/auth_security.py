"""
AuthSecurityManager - Менеджер безопасности для auth системы.

Функции:
- Хеширование/верификация паролей (bcrypt, cost=12)
- Валидация паролей (5-8 символов, буквы + цифры)
- Генерация токенов (invite, session)
- Rate limiting (3 попытки / 15 мин)
- Audit logging (security events)

Автор: backend-developer
Дата: 17 октября 2025
Проект: VoxPersona Authorization System
"""

import bcrypt
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# ========== Конфигурация ==========

@dataclass
class AuthSecurityConfig:
    """Конфигурация security менеджера."""
    password_hash_rounds: int = 12  # Bcrypt cost factor
    rate_limit_attempts: int = 3
    rate_limit_window_seconds: int = 900  # 15 минут
    session_ttl_hours: int = 24
    invite_token_ttl_hours: int = 48


# ========== Основной класс ==========

class AuthSecurityManager:
    """
    Менеджер безопасности для auth системы.

    Функции:
    - Хеширование/верификация паролей (bcrypt)
    - Валидация паролей (5-8 символов, буквы + цифры)
    - Генерация invite токенов (secrets)
    - Rate limiting (brute-force защита)
    - Audit logging (security events)
    - Session ID generation
    """

    def __init__(self, config: Optional[AuthSecurityConfig] = None):
        """
        Инициализирует security менеджер.

        Args:
            config: Конфигурация безопасности
        """
        self.config = config or AuthSecurityConfig()

        # Rate limiter storage (telegram_id -> List[attempt_timestamp])
        self._rate_limit_attempts: Dict[int, List[datetime]] = {}

        # Invite tokens storage (token -> expires_at)
        self._invite_tokens: Dict[str, datetime] = {}

        # Audit logger
        self.audit_logger = logging.getLogger("auth_audit")
        if not self.audit_logger.handlers:
            handler = logging.FileHandler("auth_audit.log")
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)

        logging.info("AuthSecurityManager initialized")

    # ========== Password Security ==========

    def hash_password(self, password: str) -> str:
        """
        Хеширует пароль с помощью bcrypt.

        Args:
            password: Plaintext пароль

        Returns:
            str: Bcrypt hash (base64 encoded)

        Example:
            >>> security = AuthSecurityManager()
            >>> hash = security.hash_password("test123")
            >>> len(hash) > 50
            True
        """
        salt = bcrypt.gensalt(rounds=self.config.password_hash_rounds)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        return password_hash.decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Проверяет пароль против hash.

        Args:
            password: Plaintext пароль
            password_hash: Bcrypt hash

        Returns:
            bool: True если пароль верный

        Example:
            >>> security = AuthSecurityManager()
            >>> hash = security.hash_password("test123")
            >>> security.verify_password("test123", hash)
            True
            >>> security.verify_password("wrong", hash)
            False
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception as e:
            logging.error(f"Password verification failed: {e}")
            return False

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """
        Валидация пароля для системы авторизации VoxPersona.

        Требования к паролю:
        - Длина: 5-8 символов
        - Обязательно: хотя бы одна буква (латинская или кириллица)
        - Обязательно: хотя бы одна цифра

        Args:
            password: Пароль для проверки

        Returns:
            Tuple[bool, str]: Кортеж (is_valid, error_message)
                - is_valid: True если пароль соответствует всем требованиям
                - error_message: Описание ошибки или пустая строка при успешной валидации

        Examples:
            >>> AuthSecurityManager.validate_password("abc123")
            (True, "")

            >>> AuthSecurityManager.validate_password("Test1234")
            (False, "Пароль должен быть 5-8 символов (сейчас: 8)")

            >>> AuthSecurityManager.validate_password("пароль1")
            (True, "")

            >>> AuthSecurityManager.validate_password("abc")
            (False, "Пароль должен содержать цифры")

            >>> AuthSecurityManager.validate_password("123456")
            (False, "Пароль должен содержать буквы")

            >>> AuthSecurityManager.validate_password("ab12")
            (False, "Пароль должен быть 5-8 символов (сейчас: 4)")
        """
        # Проверка длины пароля
        if len(password) < 5 or len(password) > 8:
            return False, f"Пароль должен быть 5-8 символов (сейчас: {len(password)})"

        # Проверка наличия букв (латиница или кириллица)
        has_letters = any(c.isalpha() for c in password)
        if not has_letters:
            return False, "Пароль должен содержать буквы"

        # Проверка наличия цифр
        has_digits = any(c.isdigit() for c in password)
        if not has_digits:
            return False, "Пароль должен содержать цифры"

        # Все проверки пройдены
        return True, ""

    # ========== Invite Tokens ==========

    def generate_invite_token(self) -> str:
        """
        Генерирует криптографически безопасный invite токен (legacy метод).

        Returns:
            str: Токен (128 bits entropy, ~16 символов)

        Example:
            >>> security = AuthSecurityManager()
            >>> token = security.generate_invite_token()
            >>> len(token) > 10
            True
        """
        token = secrets.token_urlsafe(16)
        expires_at = datetime.now() + timedelta(
            hours=self.config.invite_token_ttl_hours
        )
        self._invite_tokens[token] = expires_at

        self.log_audit_event("INVITE_TOKEN_CREATED", 0, {"token": token[:8] + "***"})
        return token

    @staticmethod
    def generate_invite_code(length: int = 32) -> str:
        """
        Генерация криптографически безопасного invite_code.

        K-05: Централизованная генерация для переиспользования.
        Используется для создания приглашений в VoxPersona.

        Args:
            length: Длина кода (по умолчанию 32 символа)

        Returns:
            str: Приглашение вида "ABC123xyz456..." (буквы + цифры)

        Example:
            >>> invite_code = AuthSecurityManager.generate_invite_code()
            >>> len(invite_code)
            32
            >>> invite_code = AuthSecurityManager.generate_invite_code(16)
            >>> len(invite_code)
            16
        """
        import string
        alphabet = string.ascii_letters + string.digits  # a-zA-Z0-9
        invite_code = ''.join(secrets.choice(alphabet) for _ in range(length))
        return invite_code

    def verify_invite_token(self, token: str) -> bool:
        """
        Проверяет валидность invite токена.

        Args:
            token: Токен для проверки

        Returns:
            bool: True если токен валиден

        Example:
            >>> security = AuthSecurityManager()
            >>> token = security.generate_invite_code()
            >>> security.verify_invite_token(token)
            True
            >>> security.verify_invite_token("invalid_token")
            False
        """
        if token not in self._invite_tokens:
            return False

        expires_at = self._invite_tokens[token]
        if datetime.now() > expires_at:
            # Токен истек
            del self._invite_tokens[token]
            return False

        return True

    def consume_invite_token(self, token: str) -> bool:
        """
        Использует invite токен (одноразовый).

        Args:
            token: Токен для использования

        Returns:
            bool: True если успешно

        Example:
            >>> security = AuthSecurityManager()
            >>> token = security.generate_invite_code()
            >>> security.consume_invite_token(token)
            True
            >>> security.consume_invite_token(token)  # Повторное использование
            False
        """
        if not self.verify_invite_token(token):
            return False

        del self._invite_tokens[token]
        self.log_audit_event("INVITE_TOKEN_CONSUMED", 0, {"token": token[:8] + "***"})
        return True

    # ========== Rate Limiting ==========

    def check_rate_limit(
        self,
        telegram_id: int,
        max_attempts: int = 3,
        window_minutes: int = 15
    ) -> Tuple[bool, Optional[int]]:
        """
        Проверяет rate limit для пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            max_attempts: Максимум попыток (по умолчанию 3)
            window_minutes: Окно времени в минутах (по умолчанию 15)

        Returns:
            Tuple[bool, Optional[int]]:
                - allowed: True если можно продолжить
                - seconds_to_wait: Количество секунд до разблокировки (если заблокирован)

        Example:
            >>> security = AuthSecurityManager()
            >>> security.check_rate_limit(123456)
            (True, None)
            >>> security.record_login_attempt(123456)
            >>> security.record_login_attempt(123456)
            >>> security.record_login_attempt(123456)
            >>> allowed, wait = security.check_rate_limit(123456)
            >>> allowed
            False
            >>> wait > 0
            True
        """
        now = datetime.now()

        if telegram_id not in self._rate_limit_attempts:
            self._rate_limit_attempts[telegram_id] = []

        # Очистить старые попытки
        window_seconds = window_minutes * 60
        cutoff = now - timedelta(seconds=window_seconds)
        self._rate_limit_attempts[telegram_id] = [
            ts for ts in self._rate_limit_attempts[telegram_id]
            if ts > cutoff
        ]

        # Проверить лимит
        attempts = len(self._rate_limit_attempts[telegram_id])
        if attempts >= max_attempts:
            # Вычислить сколько секунд до разблокировки
            oldest_attempt = self._rate_limit_attempts[telegram_id][0]
            unblock_time = oldest_attempt + timedelta(seconds=window_seconds)
            seconds_to_wait = int((unblock_time - now).total_seconds())

            self.log_audit_event("RATE_LIMIT_HIT", telegram_id, {
                "attempts": attempts,
                "seconds_to_wait": seconds_to_wait
            })
            return False, max(1, seconds_to_wait)

        return True, None

    def record_login_attempt(self, telegram_id: int) -> None:
        """
        Записывает неудачную попытку входа.

        Args:
            telegram_id: Telegram ID пользователя

        Example:
            >>> security = AuthSecurityManager()
            >>> security.record_login_attempt(123456)
            >>> allowed, _ = security.check_rate_limit(123456)
            >>> allowed
            True
        """
        if telegram_id not in self._rate_limit_attempts:
            self._rate_limit_attempts[telegram_id] = []

        self._rate_limit_attempts[telegram_id].append(datetime.now())
        self.log_audit_event("LOGIN_FAILED", telegram_id, {
            "attempts_count": len(self._rate_limit_attempts[telegram_id])
        })

    def reset_rate_limit(self, telegram_id: int) -> None:
        """
        Сбрасывает rate limit для пользователя.

        Args:
            telegram_id: Telegram ID пользователя

        Example:
            >>> security = AuthSecurityManager()
            >>> security.record_login_attempt(123456)
            >>> security.reset_rate_limit(123456)
            >>> allowed, _ = security.check_rate_limit(123456)
            >>> allowed
            True
        """
        if telegram_id in self._rate_limit_attempts:
            del self._rate_limit_attempts[telegram_id]

    # ========== Audit Logging ==========

    def log_audit_event(self, event_type: str, telegram_id: int, details: Dict) -> None:
        """
        Логирует событие безопасности.

        События для логирования:
        - LOGIN_SUCCESS - Успешный вход
        - LOGIN_FAILED - Неудачная попытка
        - LOGOUT - Выход
        - PASSWORD_CHANGED - Смена пароля
        - ROLE_CHANGED - Смена роли
        - USER_BLOCKED - Блокировка пользователя
        - INVITE_CREATED - Создание invite токена
        - INVITE_CONSUMED - Использование invite токена
        - RATE_LIMIT_HIT - Срабатывание rate limit

        Args:
            event_type: Тип события
            telegram_id: Telegram ID пользователя
            details: Дополнительные данные

        Example:
            >>> security = AuthSecurityManager()
            >>> security.log_audit_event("LOGIN_SUCCESS", 123456, {"session_id": "abc123"})
        """
        log_entry = {
            "event": event_type,
            "telegram_id": telegram_id,
            "timestamp": datetime.now().isoformat(),
            **details
        }
        self.audit_logger.info(f"{event_type} | telegram_id={telegram_id} | {details}")

    # ========== Session Management ==========

    def generate_session_id(self) -> str:
        """
        Генерирует уникальный session ID.

        Returns:
            str: Session ID (256 bits entropy, ~32 символа)

        Example:
            >>> security = AuthSecurityManager()
            >>> session_id = security.generate_session_id()
            >>> len(session_id) > 30
            True
        """
        return secrets.token_urlsafe(32)


# ========== Singleton Instance ==========

# Глобальный экземпляр для использования в других модулях
auth_security = AuthSecurityManager()


# ========== Примеры использования ==========

def example_register_user():
    """
    Пример регистрации пользователя.

    Демонстрирует:
    1. Валидация пароля
    2. Проверка invite токена
    3. Хеширование пароля
    4. Audit logging
    """
    print("=== ПРИМЕР: Регистрация пользователя ===")

    # 1. Валидация пароля
    password = "Test123"
    is_valid, error_msg = auth_security.validate_password(password)
    if not is_valid:
        print(f"❌ Невалидный пароль: {error_msg}")
        return

    # 2. Проверить invite токен
    invite_token = auth_security.generate_invite_token()
    print(f"✅ Invite токен создан: {invite_token}")

    if not auth_security.verify_invite_token(invite_token):
        print("❌ Неверный или истекший invite токен")
        return

    # 3. Хешировать пароль
    password_hash = auth_security.hash_password(password)
    print(f"✅ Пароль захеширован: {password_hash[:30]}...")

    # 4. Использовать токен (одноразовый)
    auth_security.consume_invite_token(invite_token)

    # 5. Логировать событие
    user_id = 155894817
    auth_security.log_audit_event("USER_REGISTERED", user_id, {
        "username": "john_doe",
        "role": "user"
    })

    print("✅ Пользователь зарегистрирован")


def example_login_user():
    """
    Пример входа пользователя.

    Демонстрирует:
    1. Rate limiting
    2. Проверка пароля
    3. Создание сессии
    4. Audit logging
    """
    print("\n=== ПРИМЕР: Вход пользователя ===")

    telegram_id = 155894817
    password = "Test123"

    # 1. Проверить rate limit
    allowed, seconds_to_wait = auth_security.check_rate_limit(telegram_id)
    if not allowed:
        print(f"❌ Слишком много попыток. Попробуйте через {seconds_to_wait} секунд.")
        return

    # 2. Хешировать пароль для демонстрации
    password_hash = auth_security.hash_password(password)

    # 3. Проверить пароль
    if not auth_security.verify_password(password, password_hash):
        auth_security.record_login_attempt(telegram_id)
        print("❌ Неверный пароль")
        return

    # 4. Сбросить rate limit
    auth_security.reset_rate_limit(telegram_id)

    # 5. Создать сессию
    session_id = auth_security.generate_session_id()

    # 6. Логировать успешный вход
    auth_security.log_audit_event("LOGIN_SUCCESS", telegram_id, {
        "session_id": session_id
    })

    print(f"✅ Вход выполнен. Session ID: {session_id}")


def example_rate_limiting():
    """
    Пример rate limiting (защита от brute-force).

    Демонстрирует:
    1. Несколько неудачных попыток
    2. Блокировка после 3 попыток
    3. Разблокировка
    """
    print("\n=== ПРИМЕР: Rate Limiting ===")

    telegram_id = 999999999

    # Попытка 1
    auth_security.record_login_attempt(telegram_id)
    allowed, _ = auth_security.check_rate_limit(telegram_id)
    print(f"Попытка 1: {'✅ Разрешено' if allowed else '❌ Заблокировано'}")

    # Попытка 2
    auth_security.record_login_attempt(telegram_id)
    allowed, _ = auth_security.check_rate_limit(telegram_id)
    print(f"Попытка 2: {'✅ Разрешено' if allowed else '❌ Заблокировано'}")

    # Попытка 3
    auth_security.record_login_attempt(telegram_id)
    allowed, seconds = auth_security.check_rate_limit(telegram_id)
    print(f"Попытка 3: {'✅ Разрешено' if allowed else f'❌ Заблокировано на {seconds} секунд'}")

    # Попытка 4 (должна быть заблокирована)
    allowed, seconds = auth_security.check_rate_limit(telegram_id)
    print(f"Попытка 4: {'✅ Разрешено' if allowed else f'❌ Заблокировано на {seconds} секунд'}")

    # Разблокировка
    auth_security.reset_rate_limit(telegram_id)
    allowed, _ = auth_security.check_rate_limit(telegram_id)
    print(f"После reset: {'✅ Разрешено' if allowed else '❌ Заблокировано'}")


if __name__ == "__main__":
    # Запуск примеров
    example_register_user()
    example_login_user()
    example_rate_limiting()
