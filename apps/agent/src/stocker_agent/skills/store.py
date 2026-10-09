"""Read-only skill stores. Stores never execute skill content."""

from pathlib import Path
from typing import Any, Protocol

import boto3


class SkillStore(Protocol):
    def discover(self) -> list[str]: ...

    def read(self, skill_id: str, filename: str) -> str: ...


class LocalSkillStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def discover(self) -> list[str]:
        if not self.root.is_dir():
            raise FileNotFoundError(f"Skill directory does not exist: {self.root}")
        return sorted(
            entry.name
            for entry in self.root.iterdir()
            if entry.is_dir()
            and not entry.is_symlink()
            and not entry.name.startswith(".")
        )

    def read(self, skill_id: str, filename: str) -> str:
        path = self.root / skill_id / filename
        if filename not in {"SKILL.md", "manifest.yaml"}:
            raise ValueError("Only skill documents and manifests may be read")
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Skill files must stay inside the local skill directory")
        return path.read_text(encoding="utf-8")


class S3SkillStore:
    def __init__(self, bucket: str, prefix: str, client: Any = None) -> None:
        self.bucket = bucket
        self.prefix = f"{prefix.strip('/')}/" if prefix.strip("/") else ""
        self.client = client if client is not None else boto3.client("s3")

    def discover(self) -> list[str]:
        ids: set[str] = set()
        for page in self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=self.prefix
        ):
            for item in page.get("Contents", []):
                relative = item["Key"][len(self.prefix) :]
                parts = relative.split("/")
                if len(parts) == 2 and parts[1] in {"SKILL.md", "manifest.yaml"}:
                    ids.add(parts[0])
        return sorted(ids)

    def read(self, skill_id: str, filename: str) -> str:
        if filename not in {"SKILL.md", "manifest.yaml"}:
            raise ValueError("Only skill documents and manifests may be read")
        response = self.client.get_object(
            Bucket=self.bucket, Key=f"{self.prefix}{skill_id}/{filename}"
        )
        body = response["Body"]
        try:
            return body.read().decode("utf-8")
        finally:
            body.close()
