"""
Auth Models - Модели данных для системы авторизации VoxPersona.

Модуль содержит dataclass модели для пользователей, сессий, приглашений,
ролей и настроек, а также Pydantic модели для индексных файлов.

Автор: backend-developer
Дата: 17 октября 2025
Задача: T06 (#00005_20251014_HRYHG)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict, field_serializer


# ========== USER MODELS (dataclass) ==========

@dataclass
class UserSettings:
    """Настройки пользователя."""
    language: str = "ru"
    timezone: str = "UTC+3"
    notifications_enabled: bool = True


@dataclass
class UserMetadata:
    """Метаданные пользователя для дополнительной информации."""
    registration_source: Literal["invite", "manual", "migration"] = "invite"
    invite_code_used: Optional[str] = None
    notes: str = ""


@dataclass
class User:
    """
    Основная модель пользователя.

    КРИТИЧНО: Поля для принудительной смены пароля:
    - must_change_password: bool - требуется ли смена пароля
    - temp_password_expires_at: Optional[datetime] - срок действия временного пароля (TTL=3 дня)
    """
    user_id: str
    telegram_id: int
    username: str
    password_hash: str
    role: Literal["super_admin", "admin", "user", "guest"] = "user"

    # КРИТИЧНЫЕ ПОЛЯ для принудительной смены пароля
    must_change_password: bool = False
    temp_password_expires_at: Optional[datetime] = None

    # Статусы
    is_active: bool = True
    is_blocked: bool = False

    # Временные метки
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by_user_id: Optional[str] = None

    # Информация о входах
    last_login: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    login_count: int = 0
    failed_login_attempts: int = 0
    last_failed_login: Optional[datetime] = None

    # Пароль
    password_changed_at: datetime = field(default_factory=datetime.now)

    # Вложенные объекты
    settings: UserSettings = field(default_factory=UserSettings)
    metadata: UserMetadata = field(default_factory=UserMetadata)


# ========== INVITATION MODELS (dataclass) ==========

@dataclass
class InvitationMetadata:
    """Метаданные приглашения."""
    purpose: str = ""
    contact_info: str = ""


@dataclass
class Invitation:
    """
    Модель приглашения (invite код).

    Используется для регистрации новых пользователей.
    TTL по умолчанию: 48 часов.
    """
    invite_code: str
    invite_type: Literal["user", "admin"]
    created_by_user_id: str
    target_role: Literal["super_admin", "admin", "user", "guest"]

    # Временные метки
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=datetime.now)

    # Использование
    max_uses: int = 1
    uses_count: int = 0
    is_active: bool = True
    is_consumed: bool = False
    consumed_at: Optional[datetime] = None
    consumed_by_user_id: Optional[str] = None

    # Метаданные
    metadata: InvitationMetadata = field(default_factory=InvitationMetadata)

    def is_valid(self) -> bool:
        """
        Проверяет валидность invite кода.

        Returns:
            bool: True если код действителен, False иначе
        """
        if not self.is_active:
            return False
        if self.is_consumed and self.max_uses == 1:
            return False
        if self.uses_count >= self.max_uses:
            return False
        if datetime.now() > self.expires_at:
            return False
        return True


# ========== SESSION MODELS (dataclass) ==========

@dataclass
class SessionMetadata:
    """Метаданные сессии."""
    device: str = "unknown"
    location: str = "Unknown"


@dataclass
class Session:
    """
    Модель пользовательской сессии.

    TTL по умолчанию: 24 часа.
    Поддерживает автопродление при активности.
    """
    session_id: str
    user_id: str

    # Временные метки
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Статус
    is_active: bool = True

    # Информация о подключении
    ip_address: Optional[str] = None
    user_agent: Optional[str] = "Telegram Bot"

    # Метаданные
    metadata: SessionMetadata = field(default_factory=SessionMetadata)

    def is_valid(self) -> bool:
        """
        Проверяет валидность сессии.

        Returns:
            bool: True если сессия действительна, False иначе
        """
        return self.is_active and datetime.now() < self.expires_at

    def refresh(self) -> None:
        """Обновляет last_activity до текущего времени."""
        self.last_activity = datetime.now()


# ========== ROLE MODELS (dataclass) ==========

@dataclass
class RoleUIAccess:
    """Доступ к элементам пользовательского интерфейса."""
    menu_access_management: bool = False
    menu_system: bool = False
    menu_chats: bool = True
    menu_reports: bool = True
    menu_help: bool = True


@dataclass
class Role:
    """
    Модель роли для RBAC (Role-Based Access Control).

    Определяет разрешения и доступ к функциям системы.
    """
    role_id: str
    display_name: str
    description: str
    priority: int = 50

    # Разрешения в формате "resource.action"
    permissions: List[str] = field(default_factory=list)

    # Доступ к UI
    ui_access: RoleUIAccess = field(default_factory=RoleUIAccess)


# ========== AUTH SETTINGS MODELS (dataclass) ==========

@dataclass
class PasswordPolicy:
    """Политика паролей."""
    min_length: int = 5
    max_length: int = 8
    require_uppercase: bool = False
    require_lowercase: bool = False
    require_numbers: bool = True
    require_special: bool = False
    require_letters: bool = True
    bcrypt_rounds: int = 12


@dataclass
class SessionPolicy:
    """Политика управления сессиями."""
    ttl_hours: int = 24
    max_sessions_per_user: int = 3
    auto_extend_on_activity: bool = True
    extend_by_hours: int = 1


@dataclass
class RateLimiting:
    """Настройки защиты от brute-force атак."""
    enabled: bool = True
    max_login_attempts: int = 3
    lockout_duration_minutes: int = 15
    window_minutes: int = 15


@dataclass
class InvitePolicy:
    """Политика invite кодов."""
    enabled: bool = True
    default_ttl_hours: int = 48
    default_max_uses: int = 1
    require_approval: bool = False


@dataclass
class RegistrationSettings:
    """Настройки регистрации новых пользователей."""
    enabled: bool = True
    require_invite: bool = True
    default_role: Literal["super_admin", "admin", "user", "guest"] = "user"
    email_verification: bool = False


@dataclass
class SecuritySettings:
    """Настройки безопасности и аудита."""
    audit_logging_enabled: bool = True
    log_retention_days: int = 90
    ip_whitelist_enabled: bool = False
    ip_whitelist: List[str] = field(default_factory=list)
    force_password_change_days: int = 90


@dataclass
class AuthSettings:
    """
    Главные настройки системы авторизации.

    Объединяет все политики безопасности в одну структуру.
    """
    password_policy: PasswordPolicy = field(default_factory=PasswordPolicy)
    session_policy: SessionPolicy = field(default_factory=SessionPolicy)
    rate_limiting: RateLimiting = field(default_factory=RateLimiting)
    invite_policy: InvitePolicy = field(default_factory=InvitePolicy)
    registration: RegistrationSettings = field(default_factory=RegistrationSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)


# ========== AUDIT LOG MODEL (dataclass) ==========

@dataclass
class AuthAuditEvent:
    """
    Модель события для audit logging.

    Используется для записи всех событий безопасности:
    - LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT
    - USER_CREATED, USER_BLOCKED, USER_UNBLOCKED
    - PASSWORD_CHANGED, ROLE_CHANGED
    - INVITE_CREATED, INVITE_CONSUMED, INVITE_REVOKED
    - SESSION_CREATED, SESSION_EXPIRED, SESSION_REVOKED
    - RATE_LIMIT_HIT
    """
    event_id: str
    event_type: str
    user_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    details: Dict = field(default_factory=dict)


# ========== PYDANTIC INDEX MODELS ==========

class UsersIndex(BaseModel):
    """
    Индекс пользователей (users.json).

    Pydantic модель для валидации при чтении/записи JSON.
    """
    version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime
    next_user_id: int = Field(default=1, ge=1)
    telegram_id_to_user_id: Dict[str, str] = Field(default_factory=dict)
    users: Dict[str, Dict] = Field(default_factory=dict)

    model_config = ConfigDict()

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализация datetime в ISO формат."""
        return value.isoformat()


class InvitationsIndex(BaseModel):
    """
    Индекс приглашений (invitations.json).

    Pydantic модель для валидации при чтении/записи JSON.
    """
    version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime
    invitations: Dict[str, Dict] = Field(default_factory=dict)

    model_config = ConfigDict()

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализация datetime в ISO формат."""
        return value.isoformat()


class SessionsIndex(BaseModel):
    """
    Индекс сессий (sessions.json).

    Pydantic модель для валидации при чтении/записи JSON.
    """
    version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime
    sessions: Dict[str, Dict] = Field(default_factory=dict)

    model_config = ConfigDict()

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализация datetime в ISO формат."""
        return value.isoformat()


class RolesIndex(BaseModel):
    """
    Индекс ролей (roles.json).

    Pydantic модель для валидации при чтении/записи JSON.
    """
    version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime
    roles: Dict[str, Dict] = Field(default_factory=dict)

    model_config = ConfigDict()

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализация datetime в ISO формат."""
        return value.isoformat()


class SettingsIndex(BaseModel):
    """
    Индекс настроек (settings.json).

    Pydantic модель для валидации при чтении/записи JSON.
    """
    version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime
    auth_settings: Dict = Field(default_factory=dict)

    model_config = ConfigDict()

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Сериализация datetime в ISO формат."""
        return value.isoformat()


# ========== СЛУЖЕБНЫЕ ФУНКЦИИ ==========

def datetime_to_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Конвертирует datetime в ISO8601 строку для JSON.

    Args:
        dt: Объект datetime или None

    Returns:
        str: ISO8601 строка или None
    """
    return dt.isoformat() if dt else None


def iso_to_datetime(iso_str: Optional[str]) -> Optional[datetime]:
    """
    Конвертирует ISO8601 строку в datetime.

    Args:
        iso_str: ISO8601 строка или None

    Returns:
        datetime: Объект datetime или None
    """
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return None


# ========== ЭКСПОРТ ==========

__all__ = [
    # User models
    "User",
    "UserSettings",
    "UserMetadata",

    # Invitation models
    "Invitation",
    "InvitationMetadata",

    # Session models
    "Session",
    "SessionMetadata",

    # Role models
    "Role",
    "RoleUIAccess",

    # Auth settings models
    "AuthSettings",
    "PasswordPolicy",
    "SessionPolicy",
    "RateLimiting",
    "InvitePolicy",
    "RegistrationSettings",
    "SecuritySettings",

    # Audit model
    "AuthAuditEvent",

    # Index models (Pydantic)
    "UsersIndex",
    "InvitationsIndex",
    "SessionsIndex",
    "RolesIndex",
    "SettingsIndex",

    # Utility functions
    "datetime_to_iso",
    "iso_to_datetime",
]
