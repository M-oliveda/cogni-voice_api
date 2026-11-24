# SPDX-License-Identifier: GPL-2.0-or-later
"""Validated application configuration (MASTERPLAN.md §12.2).

Every value comes from the environment (or the git-ignored ``.env`` locally).
Startup fails fast on an invalid combination, for example the ``fake`` AI
provider outside ``local``. Variables for later phases (authentication, agent,
demo) are added with those phases.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ASYNCPG_SCHEME = "postgresql+asyncpg://"


def require_asyncpg(url: SecretStr) -> SecretStr:
    """Check that a database URL uses the asyncpg driver.

    Args:
        url: The database URL.

    Returns:
        The unchanged URL.

    Raises:
        ValueError: When the URL does not start with ``postgresql+asyncpg://``.
    """
    if not url.get_secret_value().startswith(ASYNCPG_SCHEME):
        raise ValueError(f"must start with {ASYNCPG_SCHEME}")
    return url


class AppEnv(StrEnum):
    """Deployment environment (MASTERPLAN.md §12.1)."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Accepted ``LOG_LEVEL`` values."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AIProviderName(StrEnum):
    """Accepted ``AI_PROVIDER`` values (MASTERPLAN.md §9.1)."""

    GEMINI = "gemini"
    OLLAMA = "ollama"
    FAKE = "fake"


class TaskQueueBackend(StrEnum):
    """Accepted ``TASK_QUEUE_BACKEND`` values (MASTERPLAN.md §8)."""

    DB = "db"
    CLOUD_TASKS = "cloud_tasks"


class Settings(BaseSettings):
    """Application settings read from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: AppEnv = AppEnv.LOCAL
    log_level: LogLevel = LogLevel.INFO
    docs_enabled: bool = True
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Database (§20.2)
    database_url: SecretStr
    database_migration_url: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_pool_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_timeout: float = Field(default=10, gt=0, le=60)
    db_statement_timeout_ms: int = Field(default=5000, ge=100, le=600_000)
    db_echo: bool = False

    # AI providers (§9.1)
    ai_provider: AIProviderName = AIProviderName.OLLAMA
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = Field(default=768, ge=1, le=4096)
    max_interaction_chars: int = Field(default=1000, ge=1, le=1000)

    # Task queue (§8)
    task_queue_backend: TaskQueueBackend = TaskQueueBackend.DB
    gcp_project_id: str | None = None
    gcp_region: str = "us-central1"
    cloud_tasks_queue: str | None = None
    cloud_tasks_invoker_sa: str | None = None
    service_url: str | None = None

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string, as written in ``.env``.

        Args:
            value: The raw value.

        Returns:
            A list of trimmed, non-empty origins, or ``value`` unchanged.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "gcp_project_id",
        "cloud_tasks_queue",
        "cloud_tasks_invoker_sa",
        "service_url",
        "database_migration_url",
        "gemini_api_key",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        """Treat an empty variable (``NAME=`` in ``.env``) as unset.

        Args:
            value: The raw value.

        Returns:
            ``None`` for an empty string, otherwise ``value``.
        """
        if value == "":
            return None
        return value

    @field_validator("database_url", "database_migration_url")
    @classmethod
    def _require_asyncpg(cls, value: SecretStr | None) -> SecretStr | None:
        """Require the asyncpg driver, which the async engine uses.

        Args:
            value: The database URL.

        Returns:
            The unchanged URL.
        """
        return None if value is None else require_asyncpg(value)

    @model_validator(mode="after")
    def _check_environment_rules(self) -> Self:
        """Reject combinations that are unsafe for the environment.

        Returns:
            The validated settings.

        Raises:
            ValueError: When a rule of MASTERPLAN.md §9.1 or §12 is broken.
        """
        is_local = self.app_env is AppEnv.LOCAL
        if self.ai_provider is AIProviderName.FAKE and not is_local:
            raise ValueError("AI_PROVIDER=fake is only allowed when APP_ENV=local")
        if self.ai_provider is AIProviderName.OLLAMA and not is_local:
            raise ValueError("AI_PROVIDER=ollama is only allowed when APP_ENV=local")
        if self.ai_provider is AIProviderName.GEMINI and self.gemini_api_key is None:
            raise ValueError("AI_PROVIDER=gemini requires GEMINI_API_KEY")
        if self.task_queue_backend is TaskQueueBackend.DB and not is_local:
            raise ValueError("TASK_QUEUE_BACKEND=db is only allowed when APP_ENV=local")
        if self.task_queue_backend is TaskQueueBackend.CLOUD_TASKS:
            missing = [
                name.upper()
                for name in (
                    "gcp_project_id",
                    "cloud_tasks_queue",
                    "cloud_tasks_invoker_sa",
                    "service_url",
                )
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    "TASK_QUEUE_BACKEND=cloud_tasks requires " + ", ".join(missing)
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, read once from the environment.

    Returns:
        The cached settings.
    """
    return Settings()


class MigrationSettings(BaseSettings):
    """The only setting Alembic needs (MASTERPLAN.md §13.5).

    Kept apart from :class:`Settings` so a migration run does not depend on
    unrelated application configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_migration_url: SecretStr

    @field_validator("database_migration_url")
    @classmethod
    def _require_asyncpg(cls, value: SecretStr) -> SecretStr:
        """Require the asyncpg driver.

        Args:
            value: The migration URL.

        Returns:
            The unchanged URL.
        """
        return require_asyncpg(value)
