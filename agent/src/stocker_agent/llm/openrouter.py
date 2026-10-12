"""OpenRouter provider implementation."""

from langchain_core.language_models import BaseChatModel
from langchain_openrouter import ChatOpenRouter

from stocker_agent.config.errors import MissingModelSetting
from stocker_agent.llm.provider import ModelProvider


class OpenRouterProvider(ModelProvider):
    def _create(self, model_id: str) -> BaseChatModel:
        key = self.settings.openrouter_api_key
        if key is None or not key.get_secret_value().strip():
            raise MissingModelSetting("OPENROUTER_API_KEY")
        return ChatOpenRouter(
            model=model_id,
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            # The OpenRouter SDK measures timeout in milliseconds.
            timeout=self.settings.timeout_seconds * 1000,
            max_retries=self.settings.max_retries,
        )
