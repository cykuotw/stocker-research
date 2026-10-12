"""Keep tests independent of operator environment and configuration."""

import pytest

from knowledge.config import base


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(base, "SETTINGS_FILE", tmp_path / "settings.toml")
    for name in (
        "KNOWLEDGE_CORS_ORIGINS",
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
