"""Verify config precedence and rejection of copied runtime or secret settings."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from knowledge.config import base
from knowledge.config.app import AppSettings
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


def test_no_implicit_dotenv_or_secret_directory_loading():
    with (
        patch(
            "pydantic_settings.DotEnvSettingsSource.__call__",
            side_effect=AssertionError("dotenv access"),
        ),
        patch(
            "pydantic_settings.SecretsSettingsSource.__call__",
            side_effect=AssertionError("secret-directory access"),
        ),
    ):
        assert AppSettings().cors_origins == []
        assert ModelSettings().google_api_key is None


@pytest.mark.parametrize(
    "content,settings",
    [
        ('[app]\ndb_password="forbidden"\n', AppSettings),
        ("[app]\nruntime_pool_size=5\n", AppSettings),
        ('[llm-models]\ngoogle_api_key="forbidden"\n', ModelSettings),
        ('[llm-models]\nopenrouter_api_key="forbidden"\n', ModelSettings),
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
