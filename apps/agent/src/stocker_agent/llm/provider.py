"""Construct provider clients behind the standard LangChain chat interface."""

from threading import Lock

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from stocker_agent.config.errors import MissingModelSetting
from stocker_agent.config.llm import ModelSettings, ModelTier


class ModelProvider:
    """Lazily create one unbound client per tier for this configuration snapshot."""

    def __init__(self, settings: ModelSettings | None = None) -> None:
        self.settings = settings if settings is not None else ModelSettings()
        self._clients: dict[ModelTier, BaseChatModel] = {}
        self._lock = Lock()

    def get(self, tier: ModelTier | str) -> BaseChatModel:
        selected = ModelTier(tier)
        with self._lock:
            if selected not in self._clients:
                self._clients[selected] = self._create(self.settings.model_id(selected))
            return self._clients[selected]

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
