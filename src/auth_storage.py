"""
AuthStorageManager - Storage Manager с threading.Lock для системы авторизации VoxPersona.

Класс реализует CRUD операции для users/sessions/invitations с thread-safety
через per-user locks по паттерну MDStorageManager.

Наследует BaseStorageManager для atomic write/read операций через .tmp файлы.

Структура хранилища:
    auth_data/
        user_{user_id}/
            user.json              # Данные пользователя
            sessions.json          # Сессии пользователя
        invitations.json           # Глобальные приглашения
        roles.json                 # Глобальные роли
        settings.json              # Глобальные настройки
        auth_audit.log             # Глобальный audit log

Автор: backend-developer
Дата: 17 октября 2025
Задача: T07 (#00005_20251014_HRYHG)
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from managers.base_storage_manager import BaseStorageManager
from auth_models import (
    User, Session, Invitation, Role, AuthSettings, AuthAuditEvent,
    UsersIndex, SessionsIndex, InvitationsIndex, RolesIndex, SettingsIndex,
    datetime_to_iso, iso_to_datetime,
    UserSettings, UserMetadata, SessionMetadata, InvitationMetadata,
    RoleUIAccess, PasswordPolicy, SessionPolicy, RateLimiting,
    InvitePolicy, RegistrationSettings, SecuritySettings
)

logger = logging.getLogger(__name__)


class AuthStorageManager(BaseStorageManager):
    """
    Storage Manager для системы авторизации с thread-safety.

    Реализует per-user locks по паттерну MDStorageManager для предотвращения
    race conditions при многопоточной работе (Pyrogram workers > 1).

    Наследует BaseStorageManager:
        - atomic_write() - Two-Phase Commit через .tmp файлы
        - atomic_read() - Безопасное чтение JSON
        - file_exists(), delete_file(), cleanup_temp_files()

    Attributes:
        base_path (Path): Базовая директория auth_data/
        _user_locks (Dict[str, threading.Lock]): Per-user locks для thread-safety
        _lock_manager (threading.Lock): Lock для управления _user_locks словарем
        _global_lock (threading.Lock): Lock для глобальных файлов (invitations, roles, settings)
    """

    def __init__(self, base_path: Path):
        """
        Инициализация AuthStorageManager.

        Args:
            base_path: Путь к директории auth_data/

        Raises:
            OSError: Если не удалось создать директорию
        """
        super().__init__(base_path)

        # Threading.Lock по паттерну MDStorageManager
        self._user_locks: Dict[str, threading.Lock] = {}
        self._lock_manager = threading.Lock()
        self._global_lock = threading.Lock()  # Для invitations.json, roles.json, settings.json

        # Инициализация глобальных файлов
        self._ensure_global_files()

        logger.info(f"AuthStorageManager initialized with base_path: {base_path}")

    def _get_user_lock(self, user_id: str) -> threading.Lock:
        """
        Получить или создать lock для пользователя (thread-safe).

        Паттерн из MDStorageManager._get_user_lock().

        Args:
            user_id: ID пользователя (строка)

        Returns:
            threading.Lock: Per-user lock
        """
        with self._lock_manager:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = threading.Lock()
            return self._user_locks[user_id]

    def _ensure_global_files(self) -> None:
        """
        Создает глобальные файлы (invitations.json, roles.json, settings.json) если не существуют.

        Вызывается при инициализации AuthStorageManager.
        """
        # invitations.json
        invitations_file = self.base_path / "invitations.json"
        if not invitations_file.exists():
            initial_data = {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "invitations": {}
            }
            self.atomic_write(invitations_file, initial_data)
            logger.info(f"Created invitations.json: {invitations_file}")

        # roles.json
        roles_file = self.base_path / "roles.json"
        if not roles_file.exists():
            initial_data = {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "roles": {}
            }
            self.atomic_write(roles_file, initial_data)
            logger.info(f"Created roles.json: {roles_file}")

        # settings.json
        settings_file = self.base_path / "settings.json"
        if not settings_file.exists():
            default_settings = AuthSettings()
            initial_data = {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "auth_settings": asdict(default_settings)
            }
            self.atomic_write(settings_file, initial_data)
            logger.info(f"Created settings.json: {settings_file}")

    # ========== USER METHODS (6 методов) ==========

    def create_user(self, user: User) -> bool:
        """
        Создает нового пользователя.

        Thread-safe операция с использованием per-user lock.

        Args:
            user: Объект User с данными пользователя

        Returns:
            bool: True если создание успешно, False при ошибке
        """
        lock = self._get_user_lock(user.user_id)

        with lock:
            user_dir = self.base_path / f"user_{user.user_id}"
            user_file = user_dir / "user.json"

            # Проверка существования пользователя
            if user_file.exists():
                logger.warning(f"User already exists: {user.user_id}")
                return False

            try:
                # Создать директорию пользователя
                user_dir.mkdir(parents=True, exist_ok=True)

                # Конвертировать User в dict с ISO датами
                user_data = asdict(user)
                user_data["created_at"] = datetime_to_iso(user.created_at)
                user_data["updated_at"] = datetime_to_iso(user.updated_at)
                user_data["last_login"] = datetime_to_iso(user.last_login)
                user_data["last_failed_login"] = datetime_to_iso(user.last_failed_login)
                user_data["password_changed_at"] = datetime_to_iso(user.password_changed_at)
                user_data["temp_password_expires_at"] = datetime_to_iso(user.temp_password_expires_at)

                # Сохранить user.json
                if not self.atomic_write(user_file, user_data):
                    logger.error(f"Failed to write user.json for user {user.user_id}")
                    return False

                # Создать пустой sessions.json
                sessions_file = user_dir / "sessions.json"
                sessions_data = {
                    "schema_version": "1.0",
                    "sessions": []
                }
                self.atomic_write(sessions_file, sessions_data)

                logger.info(f"User created: {user.user_id} (telegram_id={user.telegram_id})")
                return True

            except Exception as e:
                logger.error(f"Failed to create user {user.user_id}: {e}")
                return False

    def get_user(self, user_id: str) -> Optional[User]:
        """
        Получает пользователя по user_id.

        Args:
            user_id: ID пользователя

        Returns:
            Optional[User]: Объект User или None если не найден
        """
        lock = self._get_user_lock(user_id)

        with lock:
            user_dir = self.base_path / f"user_{user_id}"
            user_file = user_dir / "user.json"

            if not user_file.exists():
                logger.debug(f"User not found: {user_id}")
                return None

            try:
                user_data = self.atomic_read(user_file)

                if not user_data:
                    return None

                # Конвертировать ISO даты в datetime
                user_data["created_at"] = iso_to_datetime(user_data.get("created_at"))
                user_data["updated_at"] = iso_to_datetime(user_data.get("updated_at"))
                user_data["last_login"] = iso_to_datetime(user_data.get("last_login"))
                user_data["last_failed_login"] = iso_to_datetime(user_data.get("last_failed_login"))
                user_data["password_changed_at"] = iso_to_datetime(user_data.get("password_changed_at"))
                user_data["temp_password_expires_at"] = iso_to_datetime(user_data.get("temp_password_expires_at"))

                # Конвертировать вложенные dict в dataclass объекты
                if "settings" in user_data and isinstance(user_data["settings"], dict):
                    user_data["settings"] = UserSettings(**user_data["settings"])
                if "metadata" in user_data and isinstance(user_data["metadata"], dict):
                    user_data["metadata"] = UserMetadata(**user_data["metadata"])

                user = User(**user_data)
                return user

            except Exception as e:
                logger.error(f"Failed to get user {user_id}: {e}")
                return None

    def update_user(self, user: User) -> bool:
        """
        Обновляет данные пользователя.

        Thread-safe операция с использованием per-user lock.

        Args:
            user: Объект User с обновленными данными

        Returns:
            bool: True если обновление успешно, False при ошибке
        """
        lock = self._get_user_lock(user.user_id)

        with lock:
            user_dir = self.base_path / f"user_{user.user_id}"
            user_file = user_dir / "user.json"

            if not user_file.exists():
                logger.warning(f"Cannot update non-existent user: {user.user_id}")
                return False

            try:
                # Обновить updated_at
                user.updated_at = datetime.now()

                # Конвертировать User в dict с ISO датами
                user_data = asdict(user)
                user_data["created_at"] = datetime_to_iso(user.created_at)
                user_data["updated_at"] = datetime_to_iso(user.updated_at)
                user_data["last_login"] = datetime_to_iso(user.last_login)
                user_data["last_failed_login"] = datetime_to_iso(user.last_failed_login)
                user_data["password_changed_at"] = datetime_to_iso(user.password_changed_at)
                user_data["temp_password_expires_at"] = datetime_to_iso(user.temp_password_expires_at)

                # Сохранить обновленный user.json
                if not self.atomic_write(user_file, user_data):
                    logger.error(f"Failed to write updated user.json for user {user.user_id}")
                    return False

                logger.info(f"User updated: {user.user_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to update user {user.user_id}: {e}")
                return False

    def update_user_password(
        self,
        user_id: str,
        new_password: str,
        must_change_password: bool = False,
        temp_password_expires_at: Optional[str] = None
    ) -> bool:
        """
        Обновить пароль пользователя.

        Args:
            user_id: ID пользователя
            new_password: Новый пароль (PLAINTEXT, будет захеширован)
            must_change_password: Требовать смену при входе
            temp_password_expires_at: Срок действия временного пароля (ISO string)

        Returns:
            bool: True если успешно
        """
        from auth_security import auth_security
        from utils import iso_to_datetime
        from datetime import datetime

        user = self.get_user(user_id)
        if not user:
            return False

        # Хеширование через bcrypt
        user.password_hash = auth_security.hash_password(new_password)
        user.must_change_password = must_change_password
        user.temp_password_expires_at = iso_to_datetime(temp_password_expires_at) if temp_password_expires_at else None
        user.password_changed_at = datetime.now()
        user.updated_at = datetime.now()

        return self.update_user(user)

    def delete_user(self, user_id: str) -> bool:
        """
        Удаляет пользователя (помечает как is_active=False, НЕ удаляет физически).

        Thread-safe операция с использованием per-user lock.

        Args:
            user_id: ID пользователя

        Returns:
            bool: True если удаление успешно, False при ошибке
        """
        lock = self._get_user_lock(user_id)

        with lock:
            user_dir = self.base_path / f"user_{user_id}"
            user_file = user_dir / "user.json"

            if not user_file.exists():
                logger.warning(f"Cannot delete non-existent user: {user_id}")
                return False

            try:
                # Загрузить пользователя
                user_data = self.atomic_read(user_file)
                if not user_data:
                    return False

                # Soft delete - установить is_active=False
                user_data["is_active"] = False
                user_data["updated_at"] = datetime.now().isoformat()

                # Сохранить напрямую (НЕ через update_user() - избежать deadlock)
                if not self.atomic_write(user_file, user_data):
                    logger.error(f"Failed to write user.json during soft delete for user {user_id}")
                    return False

                logger.info(f"User soft deleted (is_active=False): {user_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to soft delete user {user_id}: {e}")
                return False

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получает пользователя по telegram_id.

        Поиск среди всех user_* директорий.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            Optional[User]: Объект User или None если не найден
        """
        try:
            # Поиск среди всех user_* директорий
            for user_dir in self.base_path.glob("user_*"):
                if not user_dir.is_dir():
                    continue

                user_file = user_dir / "user.json"
                if not user_file.exists():
                    continue

                user_data = self.atomic_read(user_file)
                if user_data.get("telegram_id") == telegram_id:
                    # Найден пользователь, вернуть через get_user() для корректной конвертации
                    user_id = user_data.get("user_id")
                    return self.get_user(user_id)

            logger.debug(f"User not found by telegram_id: {telegram_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get user by telegram_id {telegram_id}: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Получает пользователя по username.

        Поиск среди всех user_* директорий.

        Args:
            username: Username пользователя

        Returns:
            Optional[User]: Объект User или None если не найден

        Автор: agent-organizer
        Дата: 2025-11-05
        Задача: K-03 (#00007_20251105_YEIJEG/01_bag_8563784537)
        """
        try:
            # Поиск среди всех user_* директорий
            for user_dir in self.base_path.glob("user_*"):
                if not user_dir.is_dir():
                    continue

                user_file = user_dir / "user.json"
                if not user_file.exists():
                    continue

                user_data = self.atomic_read(user_file)
                if user_data.get("username") == username:
                    # Найден пользователь, вернуть через get_user() для корректной конвертации
                    user_id = user_data.get("user_id")
                    return self.get_user(user_id)

            logger.debug(f"User not found by username: {username}")
            return None

        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {e}")
            return None

    def list_users(self, include_inactive: bool = False) -> List[User]:
        """
        Возвращает список всех пользователей.

        Args:
            include_inactive: Если True, включает пользователей с is_active=False

        Returns:
            List[User]: Список объектов User
        """
        users = []

        try:
            # Поиск всех user_* директорий
            for user_dir in self.base_path.glob("user_*"):
                if not user_dir.is_dir():
                    continue

                user_file = user_dir / "user.json"
                if not user_file.exists():
                    continue

                user_data = self.atomic_read(user_file)
                if not user_data:
                    continue

                # Фильтровать неактивных пользователей
                if not include_inactive and not user_data.get("is_active", True):
                    continue

                # Получить через get_user() для корректной конвертации
                user_id = user_data.get("user_id")
                user = self.get_user(user_id)
                if user:
                    users.append(user)

            logger.debug(f"Listed {len(users)} users (include_inactive={include_inactive})")
            return users

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

    # ========== INVITATION METHODS (4 метода) ==========

    def create_invitation(self, invitation: Invitation) -> bool:
        """
        Создает новое приглашение.

        Thread-safe операция с использованием global lock.

        Args:
            invitation: Объект Invitation

        Returns:
            bool: True если создание успешно, False при ошибке
        """
        with self._global_lock:
            invitations_file = self.base_path / "invitations.json"

            try:
                # Загрузить существующие приглашения
                data = self.atomic_read(invitations_file)
                invitations = data.get("invitations", {})

                # Проверка существования кода
                if invitation.invite_code in invitations:
                    logger.warning(f"Invitation code already exists: {invitation.invite_code}")
                    return False

                # Конвертировать Invitation в dict с ISO датами
                inv_data = asdict(invitation)
                inv_data["created_at"] = datetime_to_iso(invitation.created_at)
                inv_data["expires_at"] = datetime_to_iso(invitation.expires_at)
                inv_data["consumed_at"] = datetime_to_iso(invitation.consumed_at)

                # Добавить в invitations
                invitations[invitation.invite_code] = inv_data

                # Обновить invitations.json
                data["invitations"] = invitations
                data["updated_at"] = datetime.now().isoformat()

                if not self.atomic_write(invitations_file, data):
                    logger.error(f"Failed to write invitations.json for code {invitation.invite_code}")
                    return False

                logger.info(f"Invitation created: {invitation.invite_code} (type={invitation.invite_type})")
                return True

            except Exception as e:
                logger.error(f"Failed to create invitation {invitation.invite_code}: {e}")
                return False

    def get_invitation(self, code: str) -> Optional[Invitation]:
        """
        Получает приглашение по коду.

        Args:
            code: Invite код

        Returns:
            Optional[Invitation]: Объект Invitation или None если не найден
        """
        with self._global_lock:
            invitations_file = self.base_path / "invitations.json"

            try:
                data = self.atomic_read(invitations_file)
                invitations = data.get("invitations", {})

                if code not in invitations:
                    logger.debug(f"Invitation not found: {code}")
                    return None

                inv_data = invitations[code]

                # Конвертировать ISO даты в datetime
                inv_data["created_at"] = iso_to_datetime(inv_data.get("created_at"))
                inv_data["expires_at"] = iso_to_datetime(inv_data.get("expires_at"))
                inv_data["consumed_at"] = iso_to_datetime(inv_data.get("consumed_at"))

                # Конвертировать вложенный dict в dataclass
                if "metadata" in inv_data and isinstance(inv_data["metadata"], dict):
                    inv_data["metadata"] = InvitationMetadata(**inv_data["metadata"])

                invitation = Invitation(**inv_data)
                return invitation

            except Exception as e:
                logger.error(f"Failed to get invitation {code}: {e}")
                return None

    def validate_invitation(self, code: str) -> Optional[Invitation]:
        """
        Валидирует приглашение (проверяет срок действия, использование, активность).

        Args:
            code: Invite код

        Returns:
            Optional[Invitation]: Объект Invitation если валиден, None если невалиден
        """
        invitation = self.get_invitation(code)

        if not invitation:
            logger.debug(f"Invitation validation failed: code not found ({code})")
            return None

        if not invitation.is_valid():
            logger.warning(
                f"Invitation validation failed: {code} "
                f"(is_active={invitation.is_active}, "
                f"is_consumed={invitation.is_consumed}, "
                f"uses_count={invitation.uses_count}/{invitation.max_uses}, "
                f"expired={datetime.now() > invitation.expires_at})"
            )
            return None

        logger.info(f"Invitation validated successfully: {code}")
        return invitation

    def consume_invitation(self, code: str, consumed_by_user_id: str) -> bool:
        """
        Помечает приглашение как использованное.

        Thread-safe операция с использованием global lock.

        Args:
            code: Invite код
            consumed_by_user_id: ID пользователя, который использовал код

        Returns:
            bool: True если успешно, False при ошибке
        """
        with self._global_lock:
            invitations_file = self.base_path / "invitations.json"

            try:
                # Загрузить приглашения
                data = self.atomic_read(invitations_file)
                invitations = data.get("invitations", {})

                if code not in invitations:
                    logger.warning(f"Cannot consume non-existent invitation: {code}")
                    return False

                inv_data = invitations[code]

                # Конвертировать в Invitation для валидации
                inv_data_copy = inv_data.copy()
                inv_data_copy["created_at"] = iso_to_datetime(inv_data_copy.get("created_at"))
                inv_data_copy["expires_at"] = iso_to_datetime(inv_data_copy.get("expires_at"))
                inv_data_copy["consumed_at"] = iso_to_datetime(inv_data_copy.get("consumed_at"))

                if "metadata" in inv_data_copy and isinstance(inv_data_copy["metadata"], dict):
                    inv_data_copy["metadata"] = InvitationMetadata(**inv_data_copy["metadata"])

                invitation = Invitation(**inv_data_copy)

                if not invitation.is_valid():
                    logger.warning(f"Cannot consume invalid invitation: {code}")
                    return False

                # Обновить поля использования напрямую в dict
                inv_data["uses_count"] = inv_data.get("uses_count", 0) + 1
                inv_data["consumed_at"] = datetime.now().isoformat()
                inv_data["consumed_by_user_id"] = consumed_by_user_id

                # Если достигнут max_uses, установить is_consumed=True
                if inv_data["uses_count"] >= inv_data.get("max_uses", 1):
                    inv_data["is_consumed"] = True

                # Сохранить обратно в invitations.json (НЕ через update_invitation() - избежать deadlock)
                invitations[code] = inv_data
                data["invitations"] = invitations
                data["updated_at"] = datetime.now().isoformat()

                if not self.atomic_write(invitations_file, data):
                    logger.error(f"Failed to write invitations.json after consuming {code}")
                    return False

                logger.info(
                    f"Invitation consumed: {code} (uses_count={invitation.uses_count}/{invitation.max_uses}, "
                    f"consumed_by={consumed_by_user_id})"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to consume invitation {code}: {e}")
                return False

    # ========== SESSION METHODS (4 метода) ==========

    def cleanup_expired_sessions(self, user_id: str) -> int:
        """
        Удаляет истекшие сессии из sessions.json пользователя.

        Thread-safe операция с использованием per-user lock.
        Использует atomic write для безопасности данных.

        Интегрировано из T04_session_cleanup_spec.md (строки 63-139).

        Args:
            user_id: ID пользователя

        Returns:
            int: Количество удаленных сессий

        Example:
            >>> storage = AuthStorageManager(Path("auth_data"))
            >>> deleted_count = storage.cleanup_expired_sessions(user_id="12345")
            >>> print(f"Удалено истекших сессий: {deleted_count}")
        """
        lock = self._get_user_lock(user_id)

        with lock:
            user_dir = self.base_path / f"user_{user_id}"
            sessions_file = user_dir / "sessions.json"

            # Проверка существования файла
            if not sessions_file.exists():
                logger.debug(f"Sessions file not found for user {user_id}")
                return 0

            try:
                # Загрузить все сессии
                sessions_data = self.atomic_read(sessions_file)
                sessions = sessions_data.get("sessions", [])

                if not sessions:
                    return 0

                # Фильтровать только актуальные сессии
                now = datetime.now()
                active_sessions = []
                expired_count = 0

                for session in sessions:
                    expires_at_str = session.get("expires_at")
                    if not expires_at_str:
                        # Сессия без expires_at считается истекшей
                        expired_count += 1
                        continue

                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at > now:
                            # Сессия еще активна
                            active_sessions.append(session)
                        else:
                            # Сессия истекла
                            expired_count += 1
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid expires_at format in session: {e}")
                        expired_count += 1
                        continue

                # Сохранить только активные сессии (если были изменения)
                if expired_count > 0:
                    sessions_data["sessions"] = active_sessions
                    self.atomic_write(sessions_file, sessions_data)
                    logger.info(
                        f"Cleaned up {expired_count} expired sessions for user {user_id}. "
                        f"Active sessions: {len(active_sessions)}"
                    )

                return expired_count

            except Exception as e:
                logger.error(f"Failed to cleanup expired sessions for user {user_id}: {e}")
                return 0

    def create_session(self, user_id: str, session: Session) -> bool:
        """
        Создает новую сессию для пользователя.

        КРИТИЧНО: Автоматически очищает истекшие сессии перед созданием новой (из T04).

        Thread-safe операция с использованием per-user lock.

        Args:
            user_id: ID пользователя
            session: Объект Session

        Returns:
            bool: True если создание успешно, False при ошибке
        """
        # 1. ОЧИСТКА ИСТЕКШИХ СЕССИЙ (из T04) - ДО захвата lock
        self.cleanup_expired_sessions(user_id)

        lock = self._get_user_lock(user_id)

        with lock:

            # 2. Создание новой сессии
            user_dir = self.base_path / f"user_{user_id}"
            sessions_file = user_dir / "sessions.json"

            try:
                # Загрузить существующие сессии
                sessions_data = self.atomic_read(sessions_file)
                sessions = sessions_data.get("sessions", [])

                # Конвертировать Session в dict с ISO датами
                session_data = asdict(session)
                session_data["created_at"] = datetime_to_iso(session.created_at)
                session_data["expires_at"] = datetime_to_iso(session.expires_at)
                session_data["last_activity"] = datetime_to_iso(session.last_activity)

                # Добавить новую сессию
                sessions.append(session_data)

                # Сохранить обновленный sessions.json
                sessions_data["sessions"] = sessions
                if not self.atomic_write(sessions_file, sessions_data):
                    logger.error(f"Failed to write sessions.json for user {user_id}")
                    return False

                logger.info(
                    f"Session created: {session.session_id} for user {user_id} "
                    f"(expires_at={session.expires_at.isoformat()})"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to create session for user {user_id}: {e}")
                return False

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Получает сессию по session_id.

        Поиск среди всех user_*/sessions.json.

        Args:
            session_id: ID сессии

        Returns:
            Optional[Session]: Объект Session или None если не найден
        """
        try:
            # Поиск среди всех user_* директорий
            for user_dir in self.base_path.glob("user_*"):
                if not user_dir.is_dir():
                    continue

                sessions_file = user_dir / "sessions.json"
                if not sessions_file.exists():
                    continue

                sessions_data = self.atomic_read(sessions_file)
                sessions = sessions_data.get("sessions", [])

                for session_data in sessions:
                    if session_data.get("session_id") == session_id:
                        # Найдена сессия, конвертировать в Session объект
                        session_data["created_at"] = iso_to_datetime(session_data.get("created_at"))
                        session_data["expires_at"] = iso_to_datetime(session_data.get("expires_at"))
                        session_data["last_activity"] = iso_to_datetime(session_data.get("last_activity"))

                        # Конвертировать вложенный dict в dataclass
                        if "metadata" in session_data and isinstance(session_data["metadata"], dict):
                            session_data["metadata"] = SessionMetadata(**session_data["metadata"])

                        session = Session(**session_data)
                        return session

            logger.debug(f"Session not found: {session_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def revoke_session(self, session_id: str) -> bool:
        """
        Отзывает (удаляет) сессию.

        Thread-safe операция с использованием per-user lock.

        Args:
            session_id: ID сессии

        Returns:
            bool: True если отзыв успешен, False при ошибке
        """
        try:
            # Найти пользователя сессии
            session = self.get_session(session_id)
            if not session:
                logger.warning(f"Cannot revoke non-existent session: {session_id}")
                return False

            user_id = session.user_id
            lock = self._get_user_lock(user_id)

            with lock:
                user_dir = self.base_path / f"user_{user_id}"
                sessions_file = user_dir / "sessions.json"

                # Загрузить сессии
                sessions_data = self.atomic_read(sessions_file)
                sessions = sessions_data.get("sessions", [])

                # Фильтровать сессию для удаления
                filtered_sessions = [s for s in sessions if s.get("session_id") != session_id]

                if len(filtered_sessions) == len(sessions):
                    logger.warning(f"Session not found in sessions.json: {session_id}")
                    return False

                # Сохранить обновленный список сессий
                sessions_data["sessions"] = filtered_sessions
                if not self.atomic_write(sessions_file, sessions_data):
                    logger.error(f"Failed to write sessions.json after revoking session {session_id}")
                    return False

                logger.info(f"Session revoked: {session_id} (user={user_id})")
                return True

        except Exception as e:
            logger.error(f"Failed to revoke session {session_id}: {e}")
            return False

    # ========== AUDIT LOG METHOD (1 метод) ==========

    def log_auth_event(self, event: AuthAuditEvent) -> bool:
        """
        Записывает событие аудита в auth_audit.log.

        Thread-safe операция с использованием global lock.

        Args:
            event: Объект AuthAuditEvent с данными события

        Returns:
            bool: True если запись успешна, False при ошибке
        """
        with self._global_lock:
            audit_file = self.base_path / "auth_audit.log"

            try:
                # Конвертировать AuthAuditEvent в JSON строку
                event_data = asdict(event)
                event_data["timestamp"] = datetime_to_iso(event.timestamp)
                event_json = json.dumps(event_data, ensure_ascii=False)

                # Добавить в лог файл (append mode)
                with open(audit_file, 'a', encoding='utf-8') as f:
                    f.write(event_json + "\n")

                logger.debug(
                    f"Audit event logged: {event.event_type} for user {event.user_id} "
                    f"(event_id={event.event_id})"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to log audit event {event.event_id}: {e}")
                return False

    # ========== ДОПОЛНИТЕЛЬНЫЕ ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    def get_user_sessions(self, user_id: str, include_expired: bool = False) -> List[Session]:
        """
        Возвращает список сессий пользователя.

        Args:
            user_id: ID пользователя
            include_expired: Если True, включает истекшие сессии

        Returns:
            List[Session]: Список объектов Session
        """
        lock = self._get_user_lock(user_id)

        with lock:
            user_dir = self.base_path / f"user_{user_id}"
            sessions_file = user_dir / "sessions.json"

            if not sessions_file.exists():
                logger.debug(f"Sessions file not found for user {user_id}")
                return []

            try:
                sessions_data = self.atomic_read(sessions_file)
                sessions_list = sessions_data.get("sessions", [])

                result = []
                now = datetime.now()

                for session_data in sessions_list:
                    # Конвертировать в Session объект
                    session_data["created_at"] = iso_to_datetime(session_data.get("created_at"))
                    session_data["expires_at"] = iso_to_datetime(session_data.get("expires_at"))
                    session_data["last_activity"] = iso_to_datetime(session_data.get("last_activity"))

                    if "metadata" in session_data and isinstance(session_data["metadata"], dict):
                        session_data["metadata"] = SessionMetadata(**session_data["metadata"])

                    session = Session(**session_data)

                    # Фильтровать истекшие сессии
                    if not include_expired and session.expires_at <= now:
                        continue

                    result.append(session)

                logger.debug(f"Retrieved {len(result)} sessions for user {user_id}")
                return result

            except Exception as e:
                logger.error(f"Failed to get sessions for user {user_id}: {e}")
                return []

    def get_active_session_by_telegram_id(self, telegram_id: int) -> Optional[Session]:
        """
        Получает активную сессию пользователя по telegram_id.

        Поиск среди всех user_*/sessions.json. Возвращает первую активную сессию.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            Optional[Session]: Активная сессия или None если не найдена
        """
        try:
            # Сначала найти пользователя по telegram_id
            user = self.get_user_by_telegram_id(telegram_id)
            if not user:
                logger.debug(f"User not found by telegram_id: {telegram_id}")
                return None

            # Получить активные сессии пользователя
            sessions = self.get_user_sessions(user.user_id, include_expired=False)

            # Вернуть первую активную сессию
            now = datetime.now()
            for session in sessions:
                if session.is_active and session.expires_at > now:
                    logger.debug(
                        f"Active session found for telegram_id={telegram_id}: "
                        f"session_id={session.session_id}"
                    )
                    return session

            logger.debug(f"No active session found for telegram_id: {telegram_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get active session by telegram_id {telegram_id}: {e}")
            return None

    def list_invitations(self, include_consumed: bool = False) -> List[Invitation]:
        """
        Возвращает список всех приглашений.

        Args:
            include_consumed: Если True, включает использованные приглашения

        Returns:
            List[Invitation]: Список объектов Invitation
        """
        with self._global_lock:
            invitations_file = self.base_path / "invitations.json"

            try:
                data = self.atomic_read(invitations_file)
                invitations_dict = data.get("invitations", {})

                result = []
                for code, inv_data in invitations_dict.items():
                    # Фильтровать использованные
                    if not include_consumed and inv_data.get("is_consumed", False):
                        continue

                    # Конвертировать в Invitation объект
                    inv_data["created_at"] = iso_to_datetime(inv_data.get("created_at"))
                    inv_data["expires_at"] = iso_to_datetime(inv_data.get("expires_at"))
                    inv_data["consumed_at"] = iso_to_datetime(inv_data.get("consumed_at"))

                    if "metadata" in inv_data and isinstance(inv_data["metadata"], dict):
                        inv_data["metadata"] = InvitationMetadata(**inv_data["metadata"])

                    invitation = Invitation(**inv_data)
                    result.append(invitation)

                logger.debug(f"Listed {len(result)} invitations (include_consumed={include_consumed})")
                return result

            except Exception as e:
                logger.error(f"Failed to list invitations: {e}")
                return []

    def update_invitation(self, invitation: Invitation) -> bool:
        """
        Обновляет приглашение.

        Thread-safe операция с использованием global lock.

        Args:
            invitation: Объект Invitation с обновленными данными

        Returns:
            bool: True если обновление успешно, False при ошибке
        """
        with self._global_lock:
            invitations_file = self.base_path / "invitations.json"

            try:
                data = self.atomic_read(invitations_file)
                invitations = data.get("invitations", {})

                if invitation.invite_code not in invitations:
                    logger.warning(f"Cannot update non-existent invitation: {invitation.invite_code}")
                    return False

                # Конвертировать Invitation в dict с ISO датами
                inv_data = asdict(invitation)
                inv_data["created_at"] = datetime_to_iso(invitation.created_at)
                inv_data["expires_at"] = datetime_to_iso(invitation.expires_at)
                inv_data["consumed_at"] = datetime_to_iso(invitation.consumed_at)

                # Обновить в invitations
                invitations[invitation.invite_code] = inv_data
                data["invitations"] = invitations
                data["updated_at"] = datetime.now().isoformat()

                if not self.atomic_write(invitations_file, data):
                    logger.error(f"Failed to write invitations.json for code {invitation.invite_code}")
                    return False

                logger.info(f"Invitation updated: {invitation.invite_code}")
                return True

            except Exception as e:
                logger.error(f"Failed to update invitation {invitation.invite_code}: {e}")
                return False

    def get_auth_settings(self) -> AuthSettings:
        """
        Получает настройки системы авторизации.

        Returns:
            AuthSettings: Объект AuthSettings с настройками
        """
        with self._global_lock:
            settings_file = self.base_path / "settings.json"

            try:
                data = self.atomic_read(settings_file)
                auth_settings_data = data.get("auth_settings", {})

                if not auth_settings_data:
                    # Вернуть настройки по умолчанию
                    logger.warning("Auth settings not found, returning defaults")
                    return AuthSettings()

                # Конвертировать вложенные dict в dataclass объекты
                if "password_policy" in auth_settings_data:
                    auth_settings_data["password_policy"] = PasswordPolicy(**auth_settings_data["password_policy"])
                if "session_policy" in auth_settings_data:
                    auth_settings_data["session_policy"] = SessionPolicy(**auth_settings_data["session_policy"])
                if "rate_limiting" in auth_settings_data:
                    auth_settings_data["rate_limiting"] = RateLimiting(**auth_settings_data["rate_limiting"])
                if "invite_policy" in auth_settings_data:
                    auth_settings_data["invite_policy"] = InvitePolicy(**auth_settings_data["invite_policy"])
                if "registration" in auth_settings_data:
                    auth_settings_data["registration"] = RegistrationSettings(**auth_settings_data["registration"])
                if "security" in auth_settings_data:
                    auth_settings_data["security"] = SecuritySettings(**auth_settings_data["security"])

                settings = AuthSettings(**auth_settings_data)
                return settings

            except Exception as e:
                logger.error(f"Failed to get auth settings: {e}")
                return AuthSettings()

    def update_auth_settings(self, settings: AuthSettings) -> bool:
        """
        Обновляет настройки системы авторизации.

        Thread-safe операция с использованием global lock.

        Args:
            settings: Объект AuthSettings с обновленными настройками

        Returns:
            bool: True если обновление успешно, False при ошибке
        """
        with self._global_lock:
            settings_file = self.base_path / "settings.json"

            try:
                data = self.atomic_read(settings_file)

                # Конвертировать AuthSettings в dict
                data["auth_settings"] = asdict(settings)
                data["updated_at"] = datetime.now().isoformat()

                if not self.atomic_write(settings_file, data):
                    logger.error("Failed to write settings.json")
                    return False

                logger.info("Auth settings updated")
                return True

            except Exception as e:
                logger.error(f"Failed to update auth settings: {e}")
                return False


# ========== ЭКСПОРТ ==========

__all__ = ["AuthStorageManager"]
