"""
AuthManager - Главный API для работы с системой авторизации VoxPersona.

Класс предоставляет публичный API для:
- Аутентификации пользователей
- Регистрации новых пользователей
- Управления пользователями (блокировка, смена роли, удаление)
- Проверки прав доступа (RBAC)
- Управления приглашениями
- Смены паролей (включая принудительную смену)

Использует:
- AuthStorageManager для CRUD операций (T07)
- Модели из auth_models (T06)
- Функцию validate_password() из T05 (временно встроена, будет в auth_security в T09)

Автор: backend-developer
Дата: 17 октября 2025
Задача: T08 (#00005_20251014_HRYHG)
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from auth_storage import AuthStorageManager
from auth_security import AuthSecurityManager
from auth_models import (
    User, Session, Invitation, Role, AuthAuditEvent,
    UserSettings, UserMetadata, SessionMetadata, InvitationMetadata
)

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Главный API для работы с системой авторизации.

    Предоставляет 15+ методов для управления пользователями, сессиями,
    приглашениями и проверки прав доступа (RBAC).

    Attributes:
        storage (AuthStorageManager): Storage manager для CRUD операций
        security (AuthSecurityManager): Security manager для bcrypt и генерации токенов
        _roles_cache (dict): Кэш ролей для быстрого доступа к правам
    """

    def __init__(self, base_path: Path):
        """
        Инициализация AuthManager.

        Args:
            base_path: Путь к директории auth_data/
        """
        self.storage = AuthStorageManager(base_path)
        self.security = AuthSecurityManager()
        self._roles_cache: dict[str, Role] = {}

        # Инициализировать роли по умолчанию
        self._initialize_default_roles()

        logger.info(f"AuthManager initialized with base_path: {base_path}")

    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """
        Валидация пароля (из T05_password_validation_spec.md).

        Требования к паролю:
        - Длина: 5-8 символов
        - Обязательно: хотя бы одна буква (латинская или кириллица)
        - Обязательно: хотя бы одна цифра

        TODO (T09): Переместить в AuthSecurityManager.validate_password()

        Args:
            password: Пароль для проверки

        Returns:
            tuple[bool, str]: Кортеж (is_valid, error_message)
                - is_valid: True если пароль соответствует всем требованиям
                - error_message: Описание ошибки или пустая строка при успешной валидации

        Examples:
            >>> _validate_password("abc123")
            (True, "")

            >>> _validate_password("Test1234")
            (False, "Пароль должен быть 5-8 символов (сейчас: 8)")

            >>> _validate_password("abc")
            (False, "Пароль должен содержать цифры")
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

    def _generate_session_id(self) -> str:
        """
        TEMPORARY: Генерация session_id через secrets.token_urlsafe().

        TODO (T09): Переместить в AuthSecurityManager.generate_session_id()

        Returns:
            str: Уникальный session_id (32 символа)
        """
        return secrets.token_urlsafe(32)

    def _generate_invite_code(self) -> str:
        """
        TEMPORARY: Генерация invite_code через secrets.token_urlsafe().

        TODO (T09): Переместить в AuthSecurityManager.generate_invite_code()

        Returns:
            str: Уникальный invite_code (16 символов)
        """
        return secrets.token_urlsafe(16)

    # ========== ИНИЦИАЛИЗАЦИЯ РОЛЕЙ ==========

    def _initialize_default_roles(self) -> None:
        """
        Инициализирует роли по умолчанию (super_admin, admin, user, guest).

        Создает структуру прав доступа согласно RBAC модели:
        - super_admin: Полный доступ ко всем функциям
        - admin: Управление пользователями и приглашениями
        - user: Базовый доступ к функционалу бота
        - guest: Минимальный доступ (только чтение)
        """
        default_roles = [
            Role(
                role_id="super_admin",
                display_name="Супер Администратор",
                description="Полный доступ ко всем функциям системы",
                priority=100,
                permissions=[
                    # Пользователи
                    "users.create", "users.read", "users.update", "users.delete",
                    "users.block", "users.unblock", "users.change_role",
                    "users.reset_password", "users.list",
                    # Приглашения
                    "invitations.create_admin", "invitations.create_user",
                    "invitations.read", "invitations.revoke", "invitations.list",
                    # Сессии
                    "sessions.create", "sessions.read", "sessions.revoke", "sessions.list",
                    # Настройки
                    "settings.read", "settings.update",
                    # Аудит
                    "audit.read",
                    # Файловые операции
                    "files.upload", "files.download", "files.delete", "files.read",
                    # Разговоры
                    "conversations.create", "conversations.read", "conversations.update", "conversations.delete",
                    # Отчеты
                    "reports.create", "reports.read", "reports.update", "reports.delete",
                ]
            ),
            Role(
                role_id="admin",
                display_name="Администратор",
                description="Управление пользователями и приглашениями",
                priority=70,
                permissions=[
                    # Пользователи
                    "users.read", "users.list", "users.block", "users.unblock",
                    # Приглашения
                    "invitations.create_user", "invitations.read", "invitations.list",
                    # Сессии
                    "sessions.read", "sessions.list",
                    # Файловые операции
                    "files.upload", "files.download", "files.read",
                    # Разговоры
                    "conversations.create", "conversations.read", "conversations.update",
                    # Отчеты
                    "reports.create", "reports.read", "reports.update",
                ]
            ),
            Role(
                role_id="user",
                display_name="Пользователь",
                description="Базовый доступ к функционалу бота",
                priority=50,
                permissions=[
                    # Файловые операции
                    "files.upload", "files.download", "files.read",
                    # Разговоры
                    "conversations.create", "conversations.read", "conversations.update",
                    # Отчеты
                    "reports.create", "reports.read",
                ]
            ),
            Role(
                role_id="guest",
                display_name="Гость",
                description="Минимальный доступ (только чтение)",
                priority=10,
                permissions=[
                    # Файловые операции
                    "files.read",
                    # Разговоры
                    "conversations.read",
                ]
            ),
        ]

        # Сохранить роли в кэш
        for role in default_roles:
            self._roles_cache[role.role_id] = role

        logger.info(f"Initialized {len(default_roles)} default roles")

    # ========== 1. АУТЕНТИФИКАЦИЯ (2 метода) ==========

    async def authenticate(self, telegram_id: int, password: str) -> Optional[Session]:
        """
        Аутентификация пользователя по telegram_id и паролю.

        КРИТИЧНО:
        - Проверяет must_change_password и temp_password_expires_at
        - Если temp_password_expires_at истек, аутентификация не проходит
        - Создает новую сессию при успешной аутентификации
        - Обновляет last_login, login_count
        - Сбрасывает failed_login_attempts при успехе
        - Увеличивает failed_login_attempts при провале

        Args:
            telegram_id: Telegram ID пользователя
            password: Пароль для проверки

        Returns:
            Optional[Session]: Объект Session при успешной аутентификации, None при провале
        """
        # Найти пользователя по telegram_id
        user = self.storage.get_user_by_telegram_id(telegram_id)

        if not user:
            logger.warning(f"Authentication failed: user not found (telegram_id={telegram_id})")
            return None

        # Проверка блокировки
        if user.is_blocked:
            logger.warning(f"Authentication failed: user is blocked (user_id={user.user_id})")

            # Audit log
            event = AuthAuditEvent(
                event_id=str(uuid4()),
                event_type="LOGIN_FAILED",
                user_id=user.user_id,
                details={"reason": "user_blocked", "telegram_id": telegram_id}
            )
            self.storage.log_auth_event(event)

            return None

        # Проверка активности
        if not user.is_active:
            logger.warning(f"Authentication failed: user is inactive (user_id={user.user_id})")
            return None

        # КРИТИЧНО: Проверка истечения временного пароля
        if user.temp_password_expires_at and datetime.now() > user.temp_password_expires_at:
            logger.warning(
                f"Authentication failed: temporary password expired "
                f"(user_id={user.user_id}, expired_at={user.temp_password_expires_at.isoformat()})"
            )

            # Audit log
            event = AuthAuditEvent(
                event_id=str(uuid4()),
                event_type="LOGIN_FAILED",
                user_id=user.user_id,
                details={
                    "reason": "temp_password_expired",
                    "expired_at": user.temp_password_expires_at.isoformat()
                }
            )
            self.storage.log_auth_event(event)

            return None

        # Проверка пароля через bcrypt
        if not self.security.verify_password(password, user.password_hash):
            # Увеличить счетчик неудачных попыток
            user.failed_login_attempts += 1
            user.last_failed_login = datetime.now()
            self.storage.update_user(user)

            logger.warning(
                f"Authentication failed: invalid password "
                f"(user_id={user.user_id}, failed_attempts={user.failed_login_attempts})"
            )

            # Audit log
            event = AuthAuditEvent(
                event_id=str(uuid4()),
                event_type="LOGIN_FAILED",
                user_id=user.user_id,
                details={
                    "reason": "invalid_password",
                    "failed_attempts": user.failed_login_attempts
                }
            )
            self.storage.log_auth_event(event)

            return None

        # ✅ АУТЕНТИФИКАЦИЯ УСПЕШНА

        # Обновить информацию о входе
        user.last_login = datetime.now()
        user.login_count += 1
        user.failed_login_attempts = 0  # Сбросить счетчик неудачных попыток
        self.storage.update_user(user)

        # Создать новую сессию
        session = Session(
            session_id=self._generate_session_id(),
            user_id=user.user_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),  # TTL=24 часа
            last_activity=datetime.now(),
            is_active=True,
            ip_address=None,  # TODO: Получить IP из Telegram (если возможно)
            user_agent="Telegram Bot",
            metadata=SessionMetadata(device="Telegram", location="Unknown")
        )

        # Сохранить сессию
        if not self.storage.create_session(user.user_id, session):
            logger.error(f"Failed to create session for user {user.user_id}")
            return None

        # Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="LOGIN_SUCCESS",
            user_id=user.user_id,
            details={
                "telegram_id": telegram_id,
                "session_id": session.session_id,
                "must_change_password": user.must_change_password
            }
        )
        self.storage.log_auth_event(event)

        logger.info(
            f"User authenticated successfully: {user.user_id} (telegram_id={telegram_id}, "
            f"must_change_password={user.must_change_password})"
        )

        return session

    async def logout(self, session_id: str) -> bool:
        """
        Выход пользователя (удаление сессии).

        Args:
            session_id: ID сессии для удаления

        Returns:
            bool: True если выход успешен, False при ошибке
        """
        # Получить сессию
        session = self.storage.get_session(session_id)

        if not session:
            logger.warning(f"Logout failed: session not found (session_id={session_id})")
            return False

        # Удалить сессию
        if not self.storage.revoke_session(session_id):
            logger.error(f"Failed to revoke session {session_id}")
            return False

        # Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="LOGOUT",
            user_id=session.user_id,
            details={"session_id": session_id}
        )
        self.storage.log_auth_event(event)

        logger.info(f"User logged out: {session.user_id} (session_id={session_id})")
        return True

    # ========== 2. РЕГИСТРАЦИЯ (1 метод) ==========

    async def register_user(
        self,
        telegram_id: int,
        username: str,
        password: str,
        invite_code: str
    ) -> User:
        """
        Регистрация нового пользователя.

        КРИТИЧНО:
        - Валидировать пароль через validate_password() из T05
        - Проверить invite_code через storage.validate_invitation()
        - Установить must_change_password = False (регулярная регистрация)
        - Хешировать пароль перед сохранением
        - Consume invitation после успешной регистрации

        Args:
            telegram_id: Telegram ID пользователя
            username: Имя пользователя
            password: Пароль (будет провалидирован)
            invite_code: Код приглашения

        Returns:
            User: Созданный пользователь

        Raises:
            ValueError: Если пароль не соответствует требованиям
            ValueError: Если invite_code невалиден
            ValueError: Если пользователь уже существует
        """
        # 1. Валидация пароля (из T05)
        is_valid, error_msg = self._validate_password(password)
        if not is_valid:
            logger.warning(f"Registration failed: invalid password (error={error_msg})")
            raise ValueError(f"Невалидный пароль: {error_msg}")

        # 2. Проверка invite_code
        invitation = self.storage.validate_invitation(invite_code)
        if not invitation:
            logger.warning(f"Registration failed: invalid invite_code ({invite_code})")
            raise ValueError("Недействительный код приглашения")

        # 3. Проверка существования пользователя
        existing_user = self.storage.get_user_by_telegram_id(telegram_id)
        if existing_user:
            logger.warning(f"Registration failed: user already exists (telegram_id={telegram_id})")
            raise ValueError("Пользователь с таким Telegram ID уже существует")

        # 4. Хеширование пароля через bcrypt
        password_hash = self.security.hash_password(password)

        # 5. Создать пользователя
        user = User(
            user_id=str(uuid4()),
            telegram_id=telegram_id,
            username=username,
            password_hash=password_hash,
            role=invitation.target_role,  # Роль из приглашения
            must_change_password=False,  # КРИТИЧНО: Регулярная регистрация, не требуется смена
            temp_password_expires_at=None,
            is_active=True,
            is_blocked=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by_user_id=invitation.created_by_user_id,
            last_login=None,
            last_login_ip=None,
            login_count=0,
            failed_login_attempts=0,
            last_failed_login=None,
            password_changed_at=datetime.now(),
            settings=UserSettings(),
            metadata=UserMetadata(
                registration_source="invite",
                invite_code_used=invite_code,
                notes=""
            )
        )

        # 6. Сохранить пользователя
        if not self.storage.create_user(user):
            logger.error(f"Failed to create user (telegram_id={telegram_id})")
            raise RuntimeError("Не удалось создать пользователя")

        # 7. Consume invitation
        if not self.storage.consume_invitation(invite_code, user.user_id):
            logger.warning(f"Failed to consume invitation {invite_code} after user creation")

        # 8. Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="USER_CREATED",
            user_id=user.user_id,
            details={
                "telegram_id": telegram_id,
                "username": username,
                "role": user.role,
                "invite_code": invite_code,
                "created_by": invitation.created_by_user_id
            }
        )
        self.storage.log_auth_event(event)

        logger.info(
            f"User registered successfully: {user.user_id} (telegram_id={telegram_id}, "
            f"role={user.role}, invite_code={invite_code})"
        )

        return user

    # ========== 3. RBAC (Rights Based Access Control) (3 метода) ==========

    async def has_permission(self, user_id: str, permission: str) -> bool:
        """
        Проверяет наличие прав доступа у пользователя.

        Покрывает ВСЕ права, включая файловые операции:
        - users.* (create, read, update, delete, block, unblock, change_role, etc.)
        - invitations.* (create_admin, create_user, read, revoke, list)
        - sessions.* (create, read, revoke, list)
        - files.* (upload, download, delete, read)
        - conversations.* (create, read, update, delete)
        - reports.* (create, read, update, delete)
        - settings.* (read, update)
        - audit.* (read)

        Args:
            user_id: ID пользователя
            permission: Право доступа в формате "resource.action"

        Returns:
            bool: True если у пользователя есть право, False иначе
        """
        # Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.debug(f"Permission check failed: user not found (user_id={user_id})")
            return False

        # Проверка активности и блокировки
        if not user.is_active or user.is_blocked:
            logger.debug(
                f"Permission check failed: user is inactive or blocked "
                f"(user_id={user_id}, is_active={user.is_active}, is_blocked={user.is_blocked})"
            )
            return False

        # Получить роль из кэша
        role = self._roles_cache.get(user.role)

        if not role:
            logger.warning(f"Permission check failed: role not found in cache (role={user.role})")
            return False

        # Проверить наличие права в роли
        has_perm = permission in role.permissions

        logger.debug(
            f"Permission check: user_id={user_id}, permission={permission}, "
            f"role={user.role}, result={has_perm}"
        )

        return has_perm

    async def has_role(self, user_id: str, role: str) -> bool:
        """
        Проверяет наличие роли у пользователя.

        Args:
            user_id: ID пользователя
            role: Название роли (super_admin, admin, user, guest)

        Returns:
            bool: True если у пользователя есть роль, False иначе
        """
        # Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.debug(f"Role check failed: user not found (user_id={user_id})")
            return False

        # Проверка активности и блокировки
        if not user.is_active or user.is_blocked:
            logger.debug(
                f"Role check failed: user is inactive or blocked "
                f"(user_id={user_id}, is_active={user.is_active}, is_blocked={user.is_blocked})"
            )
            return False

        # Проверить роль
        has_role_result = user.role == role

        logger.debug(
            f"Role check: user_id={user_id}, required_role={role}, "
            f"user_role={user.role}, result={has_role_result}"
        )

        return has_role_result

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Возвращает список всех прав доступа пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            List[str]: Список прав доступа в формате "resource.action"
        """
        # Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.debug(f"Get permissions failed: user not found (user_id={user_id})")
            return []

        # Проверка активности и блокировки
        if not user.is_active or user.is_blocked:
            logger.debug(
                f"Get permissions failed: user is inactive or blocked (user_id={user_id})"
            )
            return []

        # Получить роль из кэша
        role = self._roles_cache.get(user.role)

        if not role:
            logger.warning(f"Get permissions failed: role not found in cache (role={user.role})")
            return []

        logger.debug(
            f"Get permissions: user_id={user_id}, role={user.role}, "
            f"permissions_count={len(role.permissions)}"
        )

        return role.permissions.copy()

    # ========== 4. УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (8 методов) ==========

    async def list_users(self, include_inactive: bool = False) -> List[User]:
        """
        Возвращает список всех пользователей.

        Args:
            include_inactive: Если True, включает пользователей с is_active=False

        Returns:
            List[User]: Список объектов User
        """
        users = self.storage.list_users(include_inactive=include_inactive)

        logger.info(f"Listed {len(users)} users (include_inactive={include_inactive})")

        return users

    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Получает пользователя по user_id.

        Args:
            user_id: ID пользователя

        Returns:
            Optional[User]: Объект User или None если не найден
        """
        return self.storage.get_user(user_id)

    async def block_user(self, user_id: str, blocked_by_user_id: str) -> bool:
        """
        Блокирует пользователя.

        Args:
            user_id: ID пользователя для блокировки
            blocked_by_user_id: ID пользователя, который блокирует

        Returns:
            bool: True если блокировка успешна, False при ошибке
        """
        # Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.warning(f"Block user failed: user not found (user_id={user_id})")
            return False

        # Установить is_blocked=True и синхронизировать is_active
        # СИНХРОНИЗАЦИЯ: is_active и is_blocked должны быть инверсны
        user.is_blocked = True
        user.is_active = False  # Блокировка = делаем неактивным
        user.updated_at = datetime.now()

        if not self.storage.update_user(user):
            logger.error(f"Failed to update user during block (user_id={user_id})")
            return False

        # Завершить все активные сессии заблокированного пользователя
        # ВАЖНО: Удаление сессий предотвращает технический долг в БД (sessions.json)
        # - Уменьшает размер файла sessions.json
        # - Исключает путаницу при отладке ("почему у заблокированного пользователя есть сессии?")
        # - Соблюдает принцип "чистой БД" (нет висячих записей)
        #
        # Примечание: Даже если сессии останутся, auth_filter будет блокировать доступ
        # (проверка is_blocked при каждом запросе), но удаление сессий — правильная
        # практика управления жизненным циклом данных.
        try:
            sessions_deleted = self.storage.delete_all_sessions(user_id)
            logger.info(f"Deleted {sessions_deleted} session(s) for blocked user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete sessions for blocked user {user_id}: {e}")
            sessions_deleted = 0

        # Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="USER_BLOCKED",
            user_id=user_id,
            details={
                "blocked_by": blocked_by_user_id,
                "sessions_deleted": sessions_deleted  # Добавляем в audit trail
            }
        )
        self.storage.log_auth_event(event)

        logger.info(
            f"User blocked: {user_id} (blocked_by={blocked_by_user_id}, "
            f"sessions_deleted={sessions_deleted})"
        )
        return True

    async def unblock_user(self, user_id: str) -> bool:
        """
        Разблокирует пользователя.

        ВАЖНО: Сессии НЕ создаются автоматически после разблокировки.
        Пользователь должен заново войти в систему через /login для создания новой сессии.
        Это сделано намеренно для безопасности - разблокировка не означает автоматический вход.

        Args:
            user_id: ID пользователя для разблокировки

        Returns:
            bool: True если разблокировка успешна, False при ошибке

        Note:
            После разблокировки пользователь может войти через команду /login.
            Auth filter будет пропускать запросы только после создания новой сессии при входе.
        """
        # Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.warning(f"Unblock user failed: user not found (user_id={user_id})")
            return False

        # Установить is_blocked=False и синхронизировать is_active
        # СИНХРОНИЗАЦИЯ: is_active и is_blocked должны быть инверсны
        user.is_blocked = False
        user.is_active = True  # Разблокировка = делаем активным
        user.updated_at = datetime.now()

        if not self.storage.update_user(user):
            logger.error(f"Failed to update user during unblock (user_id={user_id})")
            return False

        # Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="USER_UNBLOCKED",
            user_id=user_id,
            details={}
        )
        self.storage.log_auth_event(event)

        logger.info(f"User unblocked: {user_id}")
        return True

    async def change_role(self, user_id: str, new_role: str, changed_by_user_id: str) -> bool:
        """
        Изменяет роль пользователя.

        Args:
            user_id: ID пользователя
            new_role: Новая роль (super_admin, admin, user, guest)
            changed_by_user_id: ID пользователя, который изменил роль

        Returns:
            bool: True если смена роли успешна, False при ошибке
        """
        # Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.warning(f"Change role failed: user not found (user_id={user_id})")
            return False

        # Валидация новой роли
        if new_role not in self._roles_cache:
            logger.warning(f"Change role failed: invalid role ({new_role})")
            return False

        old_role = user.role

        # Установить новую роль
        user.role = new_role
        user.updated_at = datetime.now()

        if not self.storage.update_user(user):
            logger.error(f"Failed to update user during change role (user_id={user_id})")
            return False

        # Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="ROLE_CHANGED",
            user_id=user_id,
            details={
                "old_role": old_role,
                "new_role": new_role,
                "changed_by": changed_by_user_id
            }
        )
        self.storage.log_auth_event(event)

        logger.info(
            f"User role changed: {user_id} (old_role={old_role}, new_role={new_role}, "
            f"changed_by={changed_by_user_id})"
        )
        return True

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Смена пароля пользователем.

        КРИТИЧНО:
        - Валидировать new_password через validate_password() из T05
        - Проверить old_password перед сменой
        - Сбросить must_change_password = False после успешной смены
        - Сбросить temp_password_expires_at = None
        - Обновить password_changed_at

        Args:
            user_id: ID пользователя
            old_password: Старый пароль для проверки
            new_password: Новый пароль

        Returns:
            bool: True если смена пароля успешна, False при ошибке

        Raises:
            ValueError: Если new_password не соответствует требованиям
            ValueError: Если old_password неверен
        """
        # 1. Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.warning(f"Change password failed: user not found (user_id={user_id})")
            return False

        # 2. Проверить старый пароль через bcrypt
        if not self.security.verify_password(old_password, user.password_hash):
            logger.warning(f"Change password failed: invalid old password (user_id={user_id})")
            raise ValueError("Неверный старый пароль")

        # 3. Валидация нового пароля (из T05)
        is_valid, error_msg = self._validate_password(new_password)
        if not is_valid:
            logger.warning(
                f"Change password failed: invalid new password (user_id={user_id}, error={error_msg})"
            )
            raise ValueError(f"Невалидный новый пароль: {error_msg}")

        # 4. Хеширование нового пароля через bcrypt
        new_password_hash = self.security.hash_password(new_password)

        # 5. Обновить пароль и связанные поля
        user.password_hash = new_password_hash
        user.password_changed_at = datetime.now()
        user.must_change_password = False  # КРИТИЧНО: Сброс флага после смены
        user.temp_password_expires_at = None  # КРИТИЧНО: Сброс временного пароля
        user.updated_at = datetime.now()

        if not self.storage.update_user(user):
            logger.error(f"Failed to update user during change password (user_id={user_id})")
            return False

        # 6. Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="PASSWORD_CHANGED",
            user_id=user_id,
            details={"changed_by": user_id}  # Пользователь сам изменил пароль
        )
        self.storage.log_auth_event(event)

        logger.info(f"User password changed: {user_id}")
        return True

    async def reset_password(
        self,
        user_id: str,
        new_password: str,
        reset_by_user_id: str
    ) -> str:
        """
        Сброс пароля администратором.

        КРИТИЧНО:
        - Валидировать new_password через validate_password() из T05
        - Установить must_change_password = True
        - Установить temp_password_expires_at = now() + 3 дня
        - Вернуть временный пароль

        Args:
            user_id: ID пользователя
            new_password: Новый временный пароль
            reset_by_user_id: ID администратора, который сбросил пароль

        Returns:
            str: Временный пароль (для отправки пользователю)

        Raises:
            ValueError: Если new_password не соответствует требованиям
        """
        # 1. Получить пользователя
        user = self.storage.get_user(user_id)

        if not user:
            logger.warning(f"Reset password failed: user not found (user_id={user_id})")
            raise ValueError("Пользователь не найден")

        # 2. Валидация нового пароля (из T05)
        is_valid, error_msg = self._validate_password(new_password)
        if not is_valid:
            logger.warning(
                f"Reset password failed: invalid password (user_id={user_id}, error={error_msg})"
            )
            raise ValueError(f"Невалидный пароль: {error_msg}")

        # 3. Хеширование нового пароля через bcrypt
        new_password_hash = self.security.hash_password(new_password)

        # 4. Обновить пароль и установить флаги принудительной смены
        user.password_hash = new_password_hash
        user.password_changed_at = datetime.now()
        user.must_change_password = True  # КРИТИЧНО: Требовать смену пароля
        user.temp_password_expires_at = datetime.now() + timedelta(days=3)  # КРИТИЧНО: TTL=3 дня
        user.updated_at = datetime.now()

        if not self.storage.update_user(user):
            logger.error(f"Failed to update user during reset password (user_id={user_id})")
            raise RuntimeError("Не удалось обновить пользователя")

        # 5. Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="PASSWORD_RESET",
            user_id=user_id,
            details={
                "reset_by": reset_by_user_id,
                "temp_password_expires_at": user.temp_password_expires_at.isoformat()
            }
        )
        self.storage.log_auth_event(event)

        logger.info(
            f"User password reset: {user_id} (reset_by={reset_by_user_id}, "
            f"expires_at={user.temp_password_expires_at.isoformat()})"
        )

        # 6. Вернуть временный пароль
        return new_password


    async def delete_user(self, user_id: str, deleted_by_user_id: str) -> None:
        """
        Безвозвратно удаляет пользователя и все его данные.

        ВАЖНО: Можно удалить только soft-deleted пользователей (is_active=False).
        Для удаления активного пользователя сначала используйте block_user().

        Операции (в порядке выполнения):
        1. Проверка существования пользователя
        2. Проверка что пользователь уже заблокирован (is_active=False)
        3. Сохранение данных для audit log
        4. Удаление всех сессий
        5. Запись audit event
        6. Физическое удаление директории пользователя

        Args:
            user_id: ID удаляемого пользователя
            deleted_by_user_id: ID администратора, выполняющего удаление

        Raises:
            ValueError: Если пользователь не найден или активен
            RuntimeError: Если не удалось физически удалить данные

        Returns:
            None
        """
        # 1. Проверка существования пользователя
        # Получаем объект пользователя из хранилища для валидации его существования
        user = self.storage.get_user(user_id)
        if not user:
            # Логируем ошибку и выбрасываем исключение, т.к. нельзя удалить несуществующего пользователя
            logger.error(f"Delete user failed: user not found (user_id={user_id})")
            raise ValueError(f"Пользователь не найден: {user_id}")

        # 2. Проверка что пользователь soft-deleted (is_active=False)
        # КРИТИЧНО: Безопасность - запрещаем удаление активных пользователей
        # Это защищает от случайного удаления работающих учетных записей
        # Требуем сначала блокировку через block_user(), что создает audit trail
        if user.is_active:
            logger.warning(
                f"Delete user failed: user is active (user_id={user_id}, is_active={user.is_active})"
            )
            raise ValueError(
                f"Нельзя удалить активного пользователя. Используйте block_user() сначала."
            )

        # 3. Сохранение данных пользователя для audit log
        # КРИТИЧНО: Сохраняем ПЕРЕД удалением, т.к. после удаления данные будут потеряны
        # Эти данные необходимы для audit trail и возможного восстановления информации
        user_data = {
            "username": user.username,
            "role": user.role,
            "telegram_id": user.telegram_id,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }

        # 4. Удаление всех сессий
        # Очищаем все активные сессии перед удалением пользователя
        # Это предотвращает "зависшие" сессии и освобождает ресурсы
        sessions_deleted = self.storage.delete_all_sessions(user_id)
        logger.info(f"Deleted sessions for user {user_id}: {sessions_deleted}")

        # 5. Запись audit event (ПЕРЕД физическим удалением!)
        # КРИТИЧНО: Записываем событие ПЕРЕД удалением, чтобы гарантировать его сохранение
        # Если удаление не удастся, у нас будет запись о попытке
        # Если удаление удастся, у нас будет полная история с данными пользователя
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="USER_DELETED",  # Новый тип события для физического удаления
            user_id=user_id,
            details={
                "deleted_by": deleted_by_user_id,  # Кто выполнил удаление (для accountability)
                "user_data": user_data,  # Сохраненные данные пользователя
                "sessions_deleted": sessions_deleted  # Количество удаленных сессий
            }
        )
        self.storage.log_auth_event(event)

        # 6. Вызов физического удаления
        # Физически удаляем директорию пользователя и все его данные
        # Это необратимая операция - после этого данные восстановить невозможно
        success = self.storage.hard_delete_user(user_id)
        if not success:
            # Логируем критическую ошибку и выбрасываем RuntimeError
            # Это означает проблемы с файловой системой или правами доступа
            logger.error(f"Failed to physically delete user {user_id}")
            raise RuntimeError(f"Не удалось физически удалить пользователя {user_id}")

        # 7. Финальное логирование
        # Подтверждаем успешное завершение операции с полным контекстом
        logger.info(
            f"User permanently deleted: {user_id} (deleted_by={deleted_by_user_id}, "
            f"username={user_data['username']})"
        )

    # ========== 5. УПРАВЛЕНИЕ ПРИГЛАШЕНИЯМИ (2 метода) ==========

    async def create_invitation(
        self,
        invite_type: str,
        created_by_user_id: str,
        target_role: str
    ) -> Invitation:
        """
        Создает новое приглашение.

        Args:
            invite_type: Тип приглашения (user, admin)
            created_by_user_id: ID пользователя, создавшего приглашение
            target_role: Роль для нового пользователя (super_admin, admin, user, guest)

        Returns:
            Invitation: Созданное приглашение

        Raises:
            ValueError: Если target_role невалиден
        """
        # 1. Валидация target_role
        if target_role not in self._roles_cache:
            logger.warning(f"Create invitation failed: invalid target_role ({target_role})")
            raise ValueError(f"Недействительная роль: {target_role}")

        # 2. Генерация invite_code
        invite_code = self._generate_invite_code()

        # 3. Создать приглашение
        invitation = Invitation(
            invite_code=invite_code,
            invite_type=invite_type,
            created_by_user_id=created_by_user_id,
            target_role=target_role,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=48),  # TTL=48 часов
            max_uses=1,
            uses_count=0,
            is_active=True,
            is_consumed=False,
            consumed_at=None,
            consumed_by_user_id=None,
            metadata=InvitationMetadata(purpose="", contact_info="")
        )

        # 4. Сохранить приглашение
        if not self.storage.create_invitation(invitation):
            logger.error(f"Failed to create invitation (code={invite_code})")
            raise RuntimeError("Не удалось создать приглашение")

        # 5. Audit log
        event = AuthAuditEvent(
            event_id=str(uuid4()),
            event_type="INVITE_CREATED",
            user_id=created_by_user_id,
            details={
                "invite_code": invite_code,
                "invite_type": invite_type,
                "target_role": target_role,
                "expires_at": invitation.expires_at.isoformat()
            }
        )
        self.storage.log_auth_event(event)

        logger.info(
            f"Invitation created: {invite_code} (type={invite_type}, target_role={target_role}, "
            f"created_by={created_by_user_id})"
        )

        return invitation

    async def validate_invitation(self, invite_code: str) -> bool:
        """
        Валидирует приглашение (проверяет срок действия, использование, активность).

        Args:
            invite_code: Код приглашения

        Returns:
            bool: True если приглашение валидно, False иначе
        """
        invitation = self.storage.validate_invitation(invite_code)
        return invitation is not None


# ========== ЭКСПОРТ ==========

__all__ = ["AuthManager"]
