"""Service-local environment, dotenv, and non-secret TOML configuration."""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

SERVICE_DIRECTORY = Path(__file__).resolve().parents[3]
SETTINGS_FILE = SERVICE_DIRECTORY / "settings.toml"
ENV_FILE: Path | None = SERVICE_DIRECTORY / ".env"


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

        local_env = DotEnvSettingsSource(
            settings_cls,
            env_file=ENV_FILE,
            env_file_encoding="utf-8",
            dotenv_filtering="only_existing",
        )
        # Service-local credentials only; no Agent dotenv or secret-directory reads.
        return init_settings, env_settings, local_env, file_source
