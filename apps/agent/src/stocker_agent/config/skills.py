"""Research skill settings read from process environment, without dotenv files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_DIRECTORY = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class LocalSkillSource:
    path: Path


@dataclass(frozen=True)
class S3SkillSource:
    bucket: str
    prefix: str


class SkillSettings(BaseSettings):
    """Select local or S3 storage; refreshing is an explicit future operation."""

    model_config = SettingsConfigDict(env_prefix="SKILL_", env_file=None, frozen=True)

    mode: Literal["local", "s3"] = "local"
    local_path: str = "./skills"
    s3_bucket: str = ""
    s3_prefix: str = "skills"

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if self.mode == "local":
            if not self.local_path.strip() or "://" in self.local_path:
                raise ValueError("SKILL_LOCAL_PATH must be a non-empty filesystem path")
        elif (
            not self.s3_bucket.strip()
            or any(c in self.s3_bucket for c in "/:@?# ")
            or self.s3_bucket != self.s3_bucket.strip()
        ):
            raise ValueError("SKILL_S3_BUCKET must be a bucket name, not a URL")
        return self

    @property
    def source(self) -> LocalSkillSource | S3SkillSource:
        if self.mode == "s3":
            return S3SkillSource(self.s3_bucket, self.s3_prefix.strip("/"))
        path = Path(self.local_path)
        if not path.is_absolute():
            path = AGENT_DIRECTORY / path
        return LocalSkillSource(path.resolve())
