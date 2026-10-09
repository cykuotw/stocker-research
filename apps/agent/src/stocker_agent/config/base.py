"""Shared TOML source with explicit non-secret field allowlists."""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, TomlConfigSettingsSource

SETTINGS_FILE = Path(__file__).resolve().parents[3] / "settings.toml"


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

        # Explicit arguments > environment > TOML > field defaults.
        # No dotenv source: the launcher supplies process environment.
        return init_settings, env_settings, file_source
