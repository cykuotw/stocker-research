"""Shared environment, dotenv and TOML sources for application settings."""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    TomlConfigSettingsSource,
)

AGENT_DIRECTORY = Path(__file__).resolve().parents[3]
SETTINGS_FILE = AGENT_DIRECTORY / "settings.toml"
ENV_FILE: Path | None = AGENT_DIRECTORY / ".env"


class FileSettings(BaseSettings):
    settings_section: ClassVar[str]
    file_fields: ClassVar[frozenset[str]]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        def file_source():
            values = TomlConfigSettingsSource(
                settings_cls,
                toml_file=SETTINGS_FILE,
                toml_table_header=(cls.settings_section,),
            )()
            unexpected = values.keys() - cls.file_fields
            if unexpected:
                raise ValueError(
                    f"Unsupported fields in settings.toml [{cls.settings_section}]: "
                    + ", ".join(sorted(unexpected))
                )
            return values

        local_env = DotEnvSettingsSource(
            settings_cls,
            env_file=ENV_FILE,
            env_file_encoding="utf-8",
            dotenv_filtering="only_existing",
        )
        # Explicit arguments > process environment > .env > TOML > defaults.
        return init_settings, env_settings, local_env, file_source
