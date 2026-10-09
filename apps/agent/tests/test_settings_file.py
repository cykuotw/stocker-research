"""Verify source precedence and keep sensitive fields out of tracked settings."""

from pathlib import Path

import pytest
from stocker_agent.config import base
from stocker_agent.config.llm import ModelSettings
from stocker_agent.config.skills import SkillSettings


def test_dotenv_loading_and_precedence(monkeypatch, tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        '[llm-models]\nstandard_model = "from-toml"\n[skills]\nmode = "local"\n'
    )
    dotenv_file = tmp_path / "test-settings.env"
    dotenv_file.write_text(
        "GOOGLE_API_KEY=test-dotenv-key\n"
        "LLM_STANDARD_MODEL=from-dotenv\n"
        "SKILL_MODE=s3\nSKILL_S3_BUCKET=test-bucket\n"
        "UNRELATED_SETTING=ignored\n"
    )
    monkeypatch.setattr(base, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(base, "ENV_FILE", dotenv_file)
    for name in (
        "GOOGLE_API_KEY",
        "LLM_STANDARD_MODEL",
        "SKILL_MODE",
        "SKILL_S3_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path.parent)
    settings = ModelSettings()
    assert settings.standard_model == "from-dotenv"
    assert settings.google_api_key is not None
    assert settings.google_api_key.get_secret_value() == "test-dotenv-key"
    assert "test-dotenv-key" not in repr(settings)
    assert SkillSettings().s3_bucket == "test-bucket"
    monkeypatch.setenv("LLM_STANDARD_MODEL", "from-process")
    assert ModelSettings().standard_model == "from-process"
    assert ModelSettings(standard_model="explicit").standard_model == "explicit"


def test_missing_dotenv_is_optional(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(base, "ENV_FILE", tmp_path / "missing-settings.env")
    assert SkillSettings(mode="local").mode == "local"


def test_file_env_and_explicit_precedence(monkeypatch, tmp_path: Path) -> None:
    file = tmp_path / "settings.toml"
    file.write_text(
        '[llm-models]\nstandard_model = "from-file"\n[skills]\nmode = "s3"\n'
    )
    monkeypatch.setattr(base, "SETTINGS_FILE", file)
    monkeypatch.delenv("LLM_STANDARD_MODEL", raising=False)
    monkeypatch.delenv("SKILL_MODE", raising=False)
    monkeypatch.setenv("SKILL_S3_BUCKET", "test-skills")
    assert ModelSettings().standard_model == "from-file"
    assert SkillSettings().mode == "s3"
    monkeypatch.setenv("LLM_STANDARD_MODEL", "from-env")
    assert ModelSettings().standard_model == "from-env"
    assert ModelSettings(standard_model="explicit").standard_model == "explicit"


@pytest.mark.parametrize(
    "content,settings",
    [
        ('[llm-models]\ngoogle_api_key = "not-allowed"\n', ModelSettings),
        ('[skills]\ns3_bucket = "not-allowed"\n', SkillSettings),
        ('[skills]\ns3_prefix = "not-allowed"\n', SkillSettings),
    ],
)
def test_sensitive_fields_are_rejected_in_file(
    monkeypatch, tmp_path, content, settings
) -> None:
    file = tmp_path / "settings.toml"
    file.write_text(content)
    monkeypatch.setattr(base, "SETTINGS_FILE", file)
    with pytest.raises(ValueError, match="Unsupported fields"):
        settings()
