"""HTTP settings without dependencies on Agent runtime configuration."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from knowledge.config.base import FileSettings


class AppSettings(FileSettings):
    settings_section = "app"
    file_fields = frozenset({"cors_origins"})
    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_",
        env_file=None,
        extra="forbid",
        hide_input_in_errors=True,
    )

    cors_origins: list[str] = Field(default_factory=list)
