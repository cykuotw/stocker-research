"""Google Gemini provider implementation."""

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from knowledge.config.errors import MissingModelSetting
from knowledge.llm.provider import ModelProvider


class GeminiProvider(ModelProvider):
    def _create(self, model_id: str) -> BaseChatModel:
        key = self.settings.google_api_key
        if key is None or not key.get_secret_value().strip():
            raise MissingModelSetting("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model=model_id,
            api_key=key,
            vertexai=False,
            request_timeout=self.settings.timeout_seconds,
            retries=self.settings.max_retries,
        )
