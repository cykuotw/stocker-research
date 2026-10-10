"""Shared provider contract and model-client cache."""

from abc import ABC, abstractmethod
from threading import Lock

from langchain_core.language_models import BaseChatModel

from stocker_agent.config.llm import ModelSettings


class ModelProvider(ABC):
    """Lazily cache unbound clients by model ID for one provider snapshot."""

    def __init__(self, settings: ModelSettings) -> None:
        self.settings = settings
        self._clients: dict[str, BaseChatModel] = {}
        self._lock = Lock()

    def get(self, model_id: str) -> BaseChatModel:
        with self._lock:
            if model_id not in self._clients:
                self._clients[model_id] = self._create(model_id)
            return self._clients[model_id]

    @abstractmethod
    def _create(self, model_id: str) -> BaseChatModel:
        """Construct this provider's LangChain client without invoking it."""
        raise NotImplementedError
