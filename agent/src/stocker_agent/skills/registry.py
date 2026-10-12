"""Validated, immutable skill snapshots with explicit refresh."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from stocker_agent.config.llm import ModelTier
from stocker_agent.config.skills import LocalSkillSource, SkillSettings
from stocker_agent.skills.store import LocalSkillStore, S3SkillStore, SkillStore

SKILL_ID = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class SkillMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(pattern=SKILL_ID, max_length=64)
    description: str = Field(min_length=1, max_length=1024)


class SkillManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=SKILL_ID, max_length=64)
    version: str = Field(min_length=1)
    llm_model: ModelTier = ModelTier.STANDARD
    required_tools: tuple[str, ...] = ()
    allowed_agents: tuple[str, ...] = ()
    status: Literal["active", "inactive"] = "active"


@dataclass(frozen=True)
class LoadedSkill:
    metadata: SkillMetadata
    manifest: SkillManifest
    instructions: str
    content_hash: str


def load_skill(store: SkillStore, skill_id: str) -> LoadedSkill:
    if not re.fullmatch(SKILL_ID, skill_id) or len(skill_id) > 64:
        raise ValueError(f"Invalid skill directory name: {skill_id!r}")
    document = store.read(skill_id, "SKILL.md")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", document, re.DOTALL)
    if match is None:
        raise ValueError(f"{skill_id}: SKILL.md requires YAML frontmatter")
    metadata = SkillMetadata.model_validate(yaml.safe_load(match[1]))
    manifest = SkillManifest.model_validate(
        yaml.safe_load(store.read(skill_id, "manifest.yaml"))
    )
    instructions = match[2].strip()
    if not instructions:
        raise ValueError(f"{skill_id}: instructions cannot be empty")
    if metadata.name != skill_id or manifest.id != skill_id:
        raise ValueError(
            f"{skill_id}: directory, metadata name and manifest id must match"
        )
    payload = json.dumps(
        [metadata.model_dump(), manifest.model_dump(), instructions],
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return LoadedSkill(
        metadata, manifest, instructions, hashlib.sha256(payload).hexdigest()
    )


class SkillRegistry:
    """Load once, then refresh explicitly. Retain a snapshot to pin a run's skills."""

    def __init__(self, store: SkillStore) -> None:
        self.store = store
        self._refresh_lock = Lock()
        self._snapshot: Mapping[str, LoadedSkill] = MappingProxyType({})
        self.refresh()

    @classmethod
    def from_settings(cls, settings: SkillSettings | None = None) -> SkillRegistry:
        source = (settings if settings is not None else SkillSettings()).source
        store: SkillStore
        if isinstance(source, LocalSkillSource):
            store = LocalSkillStore(source.path)
        else:
            store = S3SkillStore(source.bucket, source.prefix)
        return cls(store)

    def snapshot(self) -> Mapping[str, LoadedSkill]:
        return self._snapshot

    def get(self, skill_id: str) -> LoadedSkill:
        return self._snapshot[skill_id]

    def refresh(self) -> Mapping[str, LoadedSkill]:
        with self._refresh_lock:
            loaded = [
                load_skill(self.store, skill_id) for skill_id in self.store.discover()
            ]
            replacement = {
                s.manifest.id: s for s in loaded if s.manifest.status == "active"
            }
            self._snapshot = MappingProxyType(replacement)
            return self._snapshot
