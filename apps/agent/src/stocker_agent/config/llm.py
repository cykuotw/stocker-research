"""Provider and model-tier settings from process environment."""

from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from stocker_agent.config.base import FileSettings


class ModelTier(StrEnum):
    INSTANT = "instant"
    STANDARD = "standard"
    COMPLEX = "complex"


class ModelSettings(FileSettings):
    settings_section = "llm-models"
    file_fields = frozenset(
        {
            "provider",
            "instant_model",
            "standard_model",
            "complex_model",
            "timeout_seconds",
            "max_retries",
        }
    )
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=None, frozen=True)

    provider: Literal["gemini"] = "gemini"
    instant_model: str = ""
    standard_model: str = ""
    complex_model: str = ""
    timeout_seconds: int = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0)
    google_api_key: SecretStr | None = Field(
        default=None, validation_alias="GOOGLE_API_KEY", repr=False
    )

    def model_id(self, tier: ModelTier) -> str:
        model = {
            ModelTier.INSTANT: self.instant_model,
            ModelTier.STANDARD: self.standard_model,
            ModelTier.COMPLEX: self.complex_model,
        }[tier].strip()
        if not model:
            raise ValueError(f"LLM_{tier.value.upper()}_MODEL must be configured")
        return model
