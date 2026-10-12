"""Independent Knowledge database settings and validated connection parameters."""

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from knowledge.config.base import FileSettings


class DatabaseSettings(FileSettings):
    settings_section = "database"
    file_fields = frozenset(
        {
            "pool_size",
            "connect_timeout_seconds",
            "pool_timeout_seconds",
            "statement_timeout_seconds",
            "lock_timeout_seconds",
        }
    )
    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_DB_",
        env_file=None,
        extra="forbid",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    host: str = "127.0.0.1"
    port: int = Field(default=5433, ge=1, le=65535)
    name: str = "stocker_knowledge"
    user: str = "stocker_knowledge_app"
    password: SecretStr | None = Field(default=None, repr=False)
    database_uri: SecretStr | None = Field(
        default=None,
        validation_alias="KNOWLEDGE_DATABASE_URI",
        repr=False,
    )
    pool_size: int = Field(default=2, ge=1, le=20)
    connect_timeout_seconds: int = Field(default=5, ge=2, le=60)
    pool_timeout_seconds: float = Field(default=5, gt=0, le=120)
    statement_timeout_seconds: float = Field(default=30, gt=0, le=600)
    lock_timeout_seconds: float = Field(default=5, gt=0, le=120)

    @model_validator(mode="after")
    def validate_database(self) -> DatabaseSettings:
        target: str | int | None = self.name
        if self.database_uri:
            try:
                target = conninfo_to_dict(self.database_uri.get_secret_value()).get(
                    "dbname"
                )
            except ProgrammingError:
                raise ValueError("KNOWLEDGE_DATABASE_URI is invalid") from None
        if target != "stocker_knowledge":
            raise ValueError("Knowledge may connect only to stocker_knowledge")
        return self

    def conninfo(self) -> str:
        if self.database_uri:
            return make_conninfo(
                self.database_uri.get_secret_value(),
                connect_timeout=self.connect_timeout_seconds,
            )
        if not self.password:
            raise ValueError("Set KNOWLEDGE_DB_PASSWORD or KNOWLEDGE_DATABASE_URI")
        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.name,
            user=self.user,
            password=self.password.get_secret_value(),
            connect_timeout=self.connect_timeout_seconds,
        )
