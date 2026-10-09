"""Verify source precedence and keep sensitive fields out of tracked settings."""

from pathlib import Path

import pytest
from stocker_agent.config import base
from stocker_agent.config.llm import ModelSettings
from stocker_agent.config.skills import SkillSettings


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
