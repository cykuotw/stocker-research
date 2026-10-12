"""Verify config precedence and rejection of copied runtime or secret settings."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from knowledge.config import base
from knowledge.config.app import AppSettings
from knowledge.config.database import DatabaseSettings
from knowledge.config.llm import ModelSettings


def test_toml_process_and_explicit_precedence(monkeypatch):
    base.SETTINGS_FILE.write_text(
        '[app]\ncors_origins=["https://file.example"]\n'
        '[llm-models.standard]\nprovider="openrouter"\nmodel="file-model"\n'
    )
    assert AppSettings().cors_origins == ["https://file.example"]
    monkeypatch.setenv("LLM_STANDARD__MODEL", "process-model")
    monkeypatch.setenv("KNOWLEDGE_CORS_ORIGINS", '["https://process.example"]')
    assert AppSettings().cors_origins == ["https://process.example"]
    assert ModelSettings().standard.model == "process-model"
    settings = ModelSettings(standard={"model": "explicit-model"})
    assert settings.standard.provider == "openrouter"
    assert settings.standard.model == "explicit-model"


def test_no_secret_directory_loading():
    with (
        patch(
            "pydantic_settings.SecretsSettingsSource.__call__",
            side_effect=AssertionError("secret-directory access"),
        ),
    ):
        assert AppSettings().cors_origins == []
        assert ModelSettings().google_api_key is None


def test_service_local_dotenv_precedence_and_secret_redaction(monkeypatch, tmp_path):
    dotenv = tmp_path / "knowledge-settings.env"
    dotenv.write_text(
        "KNOWLEDGE_DB_PASSWORD=fixture-secret\n"
        "KNOWLEDGE_DB_PORT=5544\n"
        "DB_NAME=stocker_research\n"
        "LLM_STANDARD__MODEL=dotenv-model\n"
    )
    monkeypatch.setattr(base, "ENV_FILE", dotenv)
    base.SETTINGS_FILE.write_text("[database]\npool_size=3\n[llm-models]\n")
    settings = DatabaseSettings()
    assert settings.port == 5544
    assert settings.pool_size == 3
    assert settings.name == "stocker_knowledge"
    assert settings.password.get_secret_value() == "fixture-secret"
    assert "fixture-secret" not in repr(settings)
    assert ModelSettings().standard.model == "dotenv-model"
    monkeypatch.setenv("KNOWLEDGE_DB_PORT", "5545")
    assert DatabaseSettings().port == 5545
    assert DatabaseSettings(port=5546).port == 5546


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "stocker_research"},
        {"database_uri": "postgresql://localhost/stocker_research"},
        {"database_uri": "host=localhost dbname=expense_tracker"},
        {"database_uri": "not a connection string"},
    ],
)
def test_database_target_is_restricted(kwargs):
    with pytest.raises(ValueError):
        DatabaseSettings(**kwargs)


def test_database_uri_precedence_and_timeout():
    from psycopg.conninfo import conninfo_to_dict

    settings = DatabaseSettings(
        database_uri="postgresql://user:fixture-secret@localhost/stocker_knowledge?connect_timeout=90",
        connect_timeout_seconds=3,
    )
    parsed = conninfo_to_dict(settings.conninfo())
    assert parsed["dbname"] == "stocker_knowledge"
    assert parsed["connect_timeout"] == "3"
    assert "fixture-secret" not in repr(settings)


def test_database_password_is_required_only_when_opening():
    settings = DatabaseSettings()
    with pytest.raises(ValueError, match="KNOWLEDGE_DB_PASSWORD"):
        settings.conninfo()


@pytest.mark.parametrize(
    "content,settings",
    [
        ('[app]\ndb_password="forbidden"\n', AppSettings),
        ("[app]\nruntime_pool_size=5\n", AppSettings),
        ('[llm-models]\ngoogle_api_key="forbidden"\n', ModelSettings),
        ('[llm-models]\nopenrouter_api_key="forbidden"\n', ModelSettings),
        ('[database]\npassword="forbidden"\n', DatabaseSettings),
        ('[database]\ndatabase_uri="forbidden"\n', DatabaseSettings),
        ('[database]\nhost="localhost"\n', DatabaseSettings),
        ("[database]\nport=5433\n", DatabaseSettings),
        ('[database]\nname="stocker_knowledge"\n', DatabaseSettings),
        ('[database]\nuser="stocker_knowledge_app"\n', DatabaseSettings),
    ],
)
def test_unsupported_fields_are_rejected_in_toml(content, settings):
    base.SETTINGS_FILE.write_text(content)
    with pytest.raises(ValueError, match="Unsupported fields"):
        settings()


def test_invalid_provider_and_tier_fail_before_model_use(monkeypatch):
    monkeypatch.setenv("LLM_STANDARD__PROVIDER", "unsupported")
    with pytest.raises(ValidationError):
        ModelSettings()


def test_missing_model_error_has_no_agent_recovery_instructions():
    with pytest.raises(ValueError) as error:
        ModelSettings().route("standard")
    assert "LLM_STANDARD__MODEL" in str(error.value)
    assert "apps/agent" not in str(error.value)
    assert "recovery" not in str(error.value)
