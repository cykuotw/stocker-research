"""Application settings from shared environment, dotenv, and non-secret TOML sources."""

from pathlib import Path

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from stocker_agent.config.base import AGENT_DIRECTORY, FileSettings


class AppOptions(FileSettings):
    settings_section = "app"
    file_fields = frozenset(
        {"cors_origins", "static_directory", "poll_seconds", "max_pool_size"}
    )
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=None,
        hide_input_in_errors=True,
        extra="forbid",
        populate_by_name=True,
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    static_directory: Path | None = None
    poll_seconds: float = Field(default=0.2, gt=0, le=10)
    max_pool_size: int = Field(default=5, ge=2, le=20)

    @model_validator(mode="after")
    def resolve_static(self):
        if self.static_directory and not self.static_directory.is_absolute():
            self.static_directory = (AGENT_DIRECTORY / self.static_directory).resolve()
        return self


class AppSettings(AppOptions):
    database_uri: SecretStr | None = Field(
        default=None, validation_alias="DATABASE_URI"
    )
    db_host: str = Field(
        default="127.0.0.1", validation_alias=AliasChoices("DB_HOST", "DB_PUBLIC_HOST")
    )
    db_port: int = Field(default=5433, ge=1, le=65535, validation_alias="DB_PORT")
    db_user: str = Field(default="stocker_agent_app", validation_alias="DB_USER")
    db_password: SecretStr | None = Field(default=None, validation_alias="DB_PASSWORD")
    db_name: str = Field(default="stocker_agent_runtime", validation_alias="DB_NAME")

    @model_validator(mode="after")
    def validate_database(self):
        if self.database_uri:
            try:
                target = conninfo_to_dict(self.database_uri.get_secret_value()).get(
                    "dbname"
                )
            except ProgrammingError:
                raise ValueError("DATABASE_URI is invalid") from None
        else:
            target = self.db_name
        if target != "stocker_agent_runtime":
            raise ValueError("Runtime may connect only to stocker_agent_runtime")
        return self

    def conninfo(self) -> str:
        if self.database_uri:
            return self.database_uri.get_secret_value()
        if not self.db_password:
            raise ValueError("Set DB_PASSWORD or DATABASE_URI in environment or .env")
        return make_conninfo(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_password.get_secret_value() if self.db_password else "",
            dbname=self.db_name,
            connect_timeout=5,
        )
