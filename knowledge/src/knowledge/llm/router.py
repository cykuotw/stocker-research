"""Route model tiers to registered provider implementations."""

from langchain_core.language_models import BaseChatModel

from knowledge.config.llm import ModelSettings, ModelTier, ProviderName
from knowledge.llm.gemini import GeminiProvider
from knowledge.llm.openrouter import OpenRouterProvider
from knowledge.llm.provider import ModelProvider


class ModelRouter:
    def __init__(
        self,
        settings: ModelSettings | None = None,
        providers: dict[ProviderName, ModelProvider] | None = None,
    ) -> None:
        self.settings = settings if settings is not None else ModelSettings()
        self.providers: dict[ProviderName, ModelProvider] = (
            dict(providers)
            if providers is not None
            else {
                "gemini": GeminiProvider(self.settings),
                "openrouter": OpenRouterProvider(self.settings),
            }
        )
        missing = {
            self.settings.instant.provider,
            self.settings.standard.provider,
            self.settings.complex.provider,
        } - self.providers.keys()
        if missing:
            raise ValueError(
                f"Unregistered model providers: {', '.join(sorted(missing))}"
            )

    def get(self, tier: ModelTier | str) -> BaseChatModel:
        route = self.settings.route(tier)
        return self.providers[route.provider].get(route.model)
