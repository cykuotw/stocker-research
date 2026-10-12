"""Process environment and non-secret TOML configuration for this service."""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

SERVICE_DIRECTORY = Path(__file__).resolve().parents[3]
SETTINGS_FILE = SERVICE_DIRECTORY / "settings.toml"


class FileSettings(BaseSettings):
    settings_section: ClassVar[str]
    file_fields: ClassVar[frozenset[str]]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        class ValidatedTomlSource(TomlConfigSettingsSource):
            def __call__(self) -> dict[str, object]:
                values = super().__call__()
                unexpected = values.keys() - cls.file_fields
                if unexpected:
                    raise ValueError(
                        f"Unsupported fields in settings.toml [{cls.settings_section}]: "
                        + ", ".join(sorted(unexpected))
                    )
                return values

        file_source = ValidatedTomlSource(
            settings_cls,
            toml_file=SETTINGS_FILE,
            toml_table_header=(cls.settings_section,),
        )

        # No implicit access to copied dotenv files or secret directories.
        return init_settings, env_settings, file_source
