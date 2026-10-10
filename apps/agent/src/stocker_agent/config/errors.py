"""Trusted configuration diagnostics that may be exposed without secret values."""

from typing import Literal

ModelSetting = Literal[
    "GOOGLE_API_KEY", "LLM_INSTANT_MODEL", "LLM_STANDARD_MODEL", "LLM_COMPLEX_MODEL"
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
