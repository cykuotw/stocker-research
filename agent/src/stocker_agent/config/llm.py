"""Per-tier provider/model routing from shared configuration sources."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from stocker_agent.config.base import FileSettings
from stocker_agent.config.errors import MissingModelSetting, ModelSetting

ProviderName = Literal["gemini", "openrouter"]


class ModelTier(StrEnum):
    INSTANT = "instant"
    STANDARD = "standard"
    COMPLEX = "complex"


class ModelRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    provider: ProviderName = "gemini"
    model: str = ""


class ModelSettings(FileSettings):
    settings_section = "llm-models"
    file_fields = frozenset(
        {"instant", "standard", "complex", "timeout_seconds", "max_retries"}
    )
    model_config = SettingsConfigDict(
        env_prefix="LLM_", env_nested_delimiter="__", env_file=None, frozen=True
    )

    instant: ModelRoute = Field(default_factory=ModelRoute)
    standard: ModelRoute = Field(default_factory=ModelRoute)
    complex: ModelRoute = Field(default_factory=ModelRoute)
    timeout_seconds: int = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0)
    google_api_key: SecretStr | None = Field(
        default=None, validation_alias="GOOGLE_API_KEY", repr=False
    )
    openrouter_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY", repr=False
    )

    def route(self, tier: ModelTier | str) -> ModelRoute:
        selected = ModelTier(tier)
        route = {
            ModelTier.INSTANT: self.instant,
            ModelTier.STANDARD: self.standard,
            ModelTier.COMPLEX: self.complex,
        }[selected]
        if not route.model:
            setting_names: dict[ModelTier, ModelSetting] = {
                ModelTier.INSTANT: "LLM_INSTANT__MODEL",
                ModelTier.STANDARD: "LLM_STANDARD__MODEL",
                ModelTier.COMPLEX: "LLM_COMPLEX__MODEL",
            }
            raise MissingModelSetting(setting_names[selected])
        return route

    def model_id(self, tier: ModelTier | str) -> str:
        return self.route(tier).model
