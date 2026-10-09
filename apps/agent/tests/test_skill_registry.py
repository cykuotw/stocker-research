"""Validate loading, refresh rollback, and snapshot stability."""

from collections.abc import MutableMapping
from io import BytesIO
from pathlib import Path
from typing import cast

import pytest
from stocker_agent.skills.registry import LoadedSkill, SkillRegistry
from stocker_agent.skills.store import LocalSkillStore, S3SkillStore

DOCUMENT = "---\nname: echo-agent\ndescription: Echo a message.\n---\nReturn Echo: followed by the input.\n"
MANIFEST = "id: echo-agent\nversion: 1.0.0\nrequired_tools: []\nstatus: active\n"


@pytest.fixture(name="skill_dir")
def fixture_skill_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "echo-agent"
    directory.mkdir()
    (directory / "SKILL.md").write_text(DOCUMENT)
    (directory / "manifest.yaml").write_text(MANIFEST)
    return directory


def test_refresh_is_explicit_and_old_snapshot_remains_stable(skill_dir: Path) -> None:
    registry = SkillRegistry(LocalSkillStore(skill_dir.parent))
    old = registry.snapshot()
    (skill_dir / "SKILL.md").write_text(
        DOCUMENT.replace("Return Echo:", "Return Updated:")
    )
    assert registry.get("echo-agent") is old["echo-agent"]
    registry.refresh()
    assert registry.get("echo-agent").content_hash != old["echo-agent"].content_hash
    assert "Return Echo:" in old["echo-agent"].instructions
    # Deliberately bypass the read-only type to verify runtime protection.
    with pytest.raises(TypeError):
        cast(MutableMapping[str, LoadedSkill], old)["new"] = old["echo-agent"]


@pytest.mark.parametrize(
    "document",
    [
        "missing frontmatter",
        DOCUMENT.replace("echo-agent", "wrong-name"),
        DOCUMENT.split("Return", maxsplit=1)[0],
    ],
)
def test_failed_refresh_keeps_previous_snapshot(skill_dir: Path, document: str) -> None:
    registry = SkillRegistry(LocalSkillStore(skill_dir.parent))
    previous = registry.snapshot()
    (skill_dir / "SKILL.md").write_text(document)
    with pytest.raises(ValueError):
        registry.refresh()
    assert registry.snapshot() is previous


def test_inactive_skill_is_not_available(skill_dir: Path) -> None:
    (skill_dir / "manifest.yaml").write_text(MANIFEST.replace("active", "inactive"))
    registry = SkillRegistry(LocalSkillStore(skill_dir.parent))
    with pytest.raises(KeyError):
        registry.get("echo-agent")


def test_symlink_file_is_rejected(skill_dir: Path, tmp_path: Path) -> None:
    document = skill_dir / "SKILL.md"
    document.unlink()
    outside = tmp_path / "outside.md"
    outside.write_text(DOCUMENT)
    document.symlink_to(outside)
    with pytest.raises(ValueError):
        SkillRegistry(LocalSkillStore(skill_dir.parent))


def test_missing_directory_is_not_silently_empty(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        SkillRegistry(LocalSkillStore(tmp_path / "missing"))


class FakeS3:
    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return self

    def paginate(self, **kwargs):
        assert kwargs == {"Bucket": "test-skills", "Prefix": "skills/"}
        yield {"Contents": [{"Key": "skills/echo-agent/SKILL.md"}]}
        yield {"Contents": [{"Key": "skills/echo-agent/manifest.yaml"}]}

    def get_object(self, **kwargs):
        assert kwargs["Bucket"] == "test-skills"
        content = DOCUMENT if kwargs["Key"].endswith("SKILL.md") else MANIFEST
        return {"Body": BytesIO(content.encode())}


def test_s3_store_uses_same_skill_contract() -> None:
    registry = SkillRegistry(S3SkillStore("test-skills", "skills", client=FakeS3()))
    assert list(registry.snapshot()) == ["echo-agent"]
    assert registry.get("echo-agent").manifest.version == "1.0.0"
    assert "Return Echo:" in registry.get("echo-agent").instructions
