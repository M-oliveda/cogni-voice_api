# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the validated application configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import (
    AIProviderName,
    AppEnv,
    MigrationSettings,
    Settings,
    TaskQueueBackend,
    get_settings,
)
from tests.conftest import make_settings

CLOUD_TASKS = {
    "task_queue_backend": "cloud_tasks",
    "gcp_project_id": "project",
    "cloud_tasks_queue": "queue",
    "cloud_tasks_invoker_sa": "invoker@project.iam.gserviceaccount.com",
    "service_url": "https://api.example.com",
}
GEMINI = {"ai_provider": "gemini", "gemini_api_key": "key"}


def test_defaults_match_the_masterplan() -> None:
    settings = make_settings()

    assert settings.app_env is AppEnv.LOCAL
    assert settings.db_pool_size == 5
    assert settings.db_pool_max_overflow == 5
    assert settings.db_pool_timeout == 10
    assert settings.db_statement_timeout_ms == 5000
    assert settings.embedding_dimensions == 768
    assert settings.max_interaction_chars == 1000


def test_reads_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/postgres")
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://a.test, ,http://b.test")

    settings = Settings(_env_file=None)

    assert settings.db_pool_size == 7
    assert settings.cors_allowed_origins == ["http://a.test", "http://b.test"]


def test_origins_accept_a_list() -> None:
    assert make_settings(cors_allowed_origins=["http://a.test"]).cors_allowed_origins


def test_empty_optional_values_are_unset() -> None:
    settings = make_settings(gemini_api_key="", service_url="")

    assert settings.gemini_api_key is None
    assert settings.service_url is None


def test_secrets_are_hidden_from_repr() -> None:
    settings = make_settings(gemini_api_key="super-secret-key")

    assert "super-secret-key" not in repr(settings)
    assert "x@127.0.0.1" not in repr(settings)


@pytest.mark.parametrize("field", ["database_url", "database_migration_url"])
def test_database_urls_require_asyncpg(field: str) -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        make_settings(**{field: "postgresql://u:p@db/postgres"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("db_pool_size", 0),
        ("db_pool_max_overflow", -1),
        ("db_pool_timeout", 0),
        ("db_statement_timeout_ms", 10),
        ("max_interaction_chars", 1001),
    ],
)
def test_pool_and_limit_values_are_bounded(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


@pytest.mark.parametrize("provider", ["fake", "ollama"])
def test_local_only_providers_are_rejected_in_the_cloud(provider: str) -> None:
    with pytest.raises(ValidationError, match=f"AI_PROVIDER={provider}"):
        make_settings(app_env="development", ai_provider=provider, **CLOUD_TASKS)


def test_gemini_requires_an_api_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        make_settings(ai_provider="gemini")


def test_db_queue_is_rejected_in_the_cloud() -> None:
    with pytest.raises(ValidationError, match="TASK_QUEUE_BACKEND=db"):
        make_settings(app_env="staging", **GEMINI)


def test_cloud_tasks_requires_its_identifiers() -> None:
    with pytest.raises(ValidationError, match="SERVICE_URL") as error:
        make_settings(task_queue_backend="cloud_tasks", gcp_project_id="project")

    assert "GCP_PROJECT_ID" not in str(error.value)
    assert "CLOUD_TASKS_QUEUE" in str(error.value)


def test_production_configuration_is_accepted() -> None:
    settings = make_settings(app_env="production", **GEMINI, **CLOUD_TASKS)

    assert settings.ai_provider is AIProviderName.GEMINI
    assert settings.task_queue_backend is TaskQueueBackend.CLOUD_TASKS


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/postgres")
    monkeypatch.chdir("/")  # no .env here
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()


def test_migration_settings_require_asyncpg() -> None:
    url = "postgresql+asyncpg://postgres:p@db/postgres"
    settings = MigrationSettings(_env_file=None, database_migration_url=url)

    assert settings.database_migration_url.get_secret_value() == url
    with pytest.raises(ValidationError):
        MigrationSettings(_env_file=None, database_migration_url="sqlite://")
