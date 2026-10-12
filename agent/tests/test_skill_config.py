"""Verify explicit source selection and stable local path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from stocker_agent.config.skills import (
    AGENT_DIRECTORY,
    LocalSkillSource,
    S3SkillSource,
    SkillSettings,
)


@pytest.fixture(autouse=True)
def clean_skill_environment(monkeypatch):
    for name in (
        "SKILL_MODE",
        "SKILL_LOCAL_PATH",
        "SKILL_S3_BUCKET",
        "SKILL_S3_PREFIX",
    ):
        monkeypatch.delenv(name, raising=False)


def test_local_path_is_independent_of_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert SkillSettings().source == LocalSkillSource(AGENT_DIRECTORY / "skills")


def test_s3_configuration_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SKILL_MODE", "s3")
    monkeypatch.setenv("SKILL_S3_BUCKET", "test-skills")
    monkeypatch.setenv("SKILL_S3_PREFIX", "research/skills/")
    assert SkillSettings().source == S3SkillSource("test-skills", "research/skills")


def test_absolute_local_path(tmp_path: Path) -> None:
    assert SkillSettings(local_path=str(tmp_path)).source == LocalSkillSource(tmp_path)


def test_invalid_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILL_MODE", "other")
    with pytest.raises(ValidationError):
        SkillSettings()


@pytest.mark.parametrize(
    "bucket", ["", " ", "s3://bucket", "bucket/path", "bucket?x=1"]
)
def test_invalid_s3_bucket_is_rejected(bucket: str) -> None:
    with pytest.raises(ValidationError):
        SkillSettings(mode="s3", s3_bucket=bucket)


@pytest.mark.parametrize("path", ["", " ", "s3://bucket/skills"])
def test_invalid_local_path_is_rejected(path: str) -> None:
    with pytest.raises(ValidationError):
        SkillSettings(local_path=path)


def test_local_mode_does_not_require_s3_settings() -> None:
    assert isinstance(SkillSettings(mode="local").source, LocalSkillSource)
