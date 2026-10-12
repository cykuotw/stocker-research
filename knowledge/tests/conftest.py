"""Keep tests independent of operator environment and configuration."""

import pytest

from knowledge.config import base

# Disable local credential reads before collection as well as inside tests.
base.ENV_FILE = None


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(base, "SETTINGS_FILE", tmp_path / "settings.toml")
    monkeypatch.setattr(base, "ENV_FILE", None)
    for name in (
        "KNOWLEDGE_CORS_ORIGINS",
        "KNOWLEDGE_DATABASE_URI",
        "KNOWLEDGE_DB_HOST",
        "KNOWLEDGE_DB_PORT",
        "KNOWLEDGE_DB_NAME",
        "KNOWLEDGE_DB_USER",
        "KNOWLEDGE_DB_PASSWORD",
        "KNOWLEDGE_DB_POOL_SIZE",
        "KNOWLEDGE_DB_CONNECT_TIMEOUT_SECONDS",
        "KNOWLEDGE_DB_POOL_TIMEOUT_SECONDS",
        "KNOWLEDGE_DB_STATEMENT_TIMEOUT_SECONDS",
        "KNOWLEDGE_DB_LOCK_TIMEOUT_SECONDS",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_RETRIES",
        "LLM_INSTANT__MODEL",
        "LLM_INSTANT__PROVIDER",
        "LLM_STANDARD__MODEL",
        "LLM_STANDARD__PROVIDER",
        "LLM_COMPLEX__MODEL",
        "LLM_COMPLEX__PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)
