"""Trusted configuration diagnostics that may be exposed without secret values."""

from typing import Literal

ModelSetting = Literal[
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "LLM_INSTANT__MODEL",
    "LLM_STANDARD__MODEL",
    "LLM_COMPLEX__MODEL",
]


class MissingModelSetting(ValueError):
    def __init__(self, setting: ModelSetting) -> None:
        self.setting = setting
        self.code = "model_configuration_missing"
        self.hint = (
            f"Configure {setting} in apps/agent/.env "
            "(or the process environment), then restart the backend before recovery."
        )
        super().__init__(self.hint)
