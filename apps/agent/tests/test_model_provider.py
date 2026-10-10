"""Verify routing, lazy initialization and manifest tiers without API calls."""

from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import SecretStr, ValidationError
from stocker_agent.config.llm import ModelSettings, ModelTier
from stocker_agent.llm import (
    GeminiProvider,
    ModelProvider,
    ModelRouter,
    OpenRouterProvider,
)
from stocker_agent.skills.registry import SkillManifest


@pytest.fixture(autouse=True)
def clean_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_INSTANT__PROVIDER",
        "LLM_STANDARD__PROVIDER",
        "LLM_COMPLEX__PROVIDER",
        "OPENROUTER_API_KEY",
        "LLM_INSTANT__MODEL",
        "LLM_STANDARD__MODEL",
        "LLM_COMPLEX__MODEL",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_tier_routing_and_client_reuse(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    for tier in ModelTier:
        monkeypatch.setenv(f"LLM_{tier.value.upper()}__PROVIDER", "gemini")
        monkeypatch.setenv(f"LLM_{tier.value.upper()}__MODEL", f"test-{tier.value}")
    fake = FakeListChatModel(responses=["test response"])
    with patch(
        "stocker_agent.llm.gemini.ChatGoogleGenerativeAI", return_value=fake
    ) as build:
        models = ModelRouter()
        assert build.call_count == 0
        for tier in ModelTier:
            assert models.get(tier) is fake
            assert models.get(tier.value) is fake
        assert build.call_count == 3
        assert isinstance(build.call_args.kwargs["api_key"], SecretStr)
        assert isinstance(build.call_args.kwargs["request_timeout"], int)
        assert [call.kwargs["model"] for call in build.call_args_list] == [
            f"test-{t.value}" for t in ModelTier
        ]
        assert models.get("instant").invoke("hello").content == "test response"


def test_missing_selected_model_fails_before_client_creation() -> None:
    with pytest.raises(ValueError, match="LLM_INSTANT__MODEL"):
        ModelRouter(ModelSettings(instant={"model": ""})).get("instant")


def test_missing_credentials_are_reported() -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        ModelRouter(ModelSettings(instant={"model": "test-model"})).get("instant")


def test_provider_and_manifest_reject_unknown_values(monkeypatch) -> None:
    monkeypatch.setenv("LLM_COMPLEX__PROVIDER", "unknown")
    with pytest.raises(ValidationError):
        ModelSettings()
    with pytest.raises(ValidationError):
        SkillManifest.model_validate(
            {"id": "echo-agent", "version": "1", "llm_model": "unknown"}
        )


def test_manifest_tier_default_and_override() -> None:
    base = {"id": "echo-agent", "version": "1"}
    assert SkillManifest.model_validate(base).llm_model == ModelTier.STANDARD
    assert (
        SkillManifest.model_validate({**base, "llm_model": "instant"}).llm_model
        == ModelTier.INSTANT
    )


def test_credentials_are_not_shown_in_settings_repr(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-hidden-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-hidden-router-key")
    assert "test-hidden-key" not in repr(ModelSettings())
    assert "test-hidden-router-key" not in repr(ModelSettings())


def test_mixed_providers_and_shared_model_cache():
    settings = ModelSettings(
        instant={"provider": "gemini", "model": "shared-model"},
        standard={"provider": "gemini", "model": "shared-model"},
        complex={"provider": "openrouter", "model": "shared-model"},
        google_api_key="fake-google-key",
        openrouter_api_key="fake-router-key",
        timeout_seconds=17,
        max_retries=0,
    )
    gemini = FakeListChatModel(responses=["gemini"])
    opus = FakeListChatModel(responses=["opus"])
    with (
        patch(
            "stocker_agent.llm.gemini.ChatGoogleGenerativeAI", return_value=gemini
        ) as google,
        patch(
            "stocker_agent.llm.openrouter.ChatOpenRouter", return_value=opus
        ) as router,
    ):
        models = ModelRouter(settings)
        google.assert_not_called()
        router.assert_not_called()
        assert models.get("instant") is models.get("standard") is gemini
        assert models.get("complex") is opus
        assert models.get(ModelTier.COMPLEX) is opus
        google.assert_called_once()
        router.assert_called_once()
        assert (
            google.call_args.kwargs["api_key"].get_secret_value() == "fake-google-key"
        )
        assert (
            router.call_args.kwargs["api_key"].get_secret_value() == "fake-router-key"
        )
        assert google.call_args.kwargs["request_timeout"] == 17
        assert router.call_args.kwargs["timeout"] == 17000
        assert router.call_args.kwargs["max_retries"] == 0


def test_only_selected_provider_requires_credentials():
    settings = ModelSettings(
        instant={"provider": "gemini", "model": "test-model"},
        complex={"provider": "openrouter", "model": "test-opus"},
        google_api_key="fake-key",
    )
    fake = FakeListChatModel(responses=["ok"])
    with patch("stocker_agent.llm.gemini.ChatGoogleGenerativeAI", return_value=fake):
        models = ModelRouter(settings)
        assert models.get("instant") is fake
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            models.get("complex")


def test_provider_contract_is_abstract():
    import inspect

    assert inspect.isabstract(ModelProvider)
    assert issubclass(GeminiProvider, ModelProvider)
    assert issubclass(OpenRouterProvider, ModelProvider)


def test_openrouter_client_accepts_configuration_without_requests():
    client = OpenRouterProvider(
        ModelSettings(openrouter_api_key="fake-key", timeout_seconds=5, max_retries=0)
    ).get("anthropic/claude-opus-4.6")
    assert client.model_name == "anthropic/claude-opus-4.6"
    assert client.request_timeout == 5000


def test_nested_provider_settings_reject_secrets():
    with pytest.raises(ValidationError):
        ModelSettings(
            complex={"provider": "openrouter", "model": "opus", "api_key": "secret"}
        )


@pytest.mark.asyncio
async def test_missing_model_config_is_persisted_as_safe_actionable_error():
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from stocker_agent.app.services.runner import GraphRunner
    from stocker_agent.config.errors import MissingModelSetting

    missing = MissingModelSetting("GOOGLE_API_KEY")
    run = {"run_id": uuid4(), "session_id": uuid4()}
    repository = Mock(
        get_run=AsyncMock(return_value={"status": "running"}), transition=AsyncMock()
    )
    service = Mock(repository=repository, graph=AsyncMock(side_effect=missing))
    await GraphRunner(service, 0.1).execute(run)
    repository.transition.assert_awaited_once_with(
        run["run_id"],
        "failed",
        {
            "code": "model_configuration_missing",
            "exception_type": "MissingModelSetting",
            "setting": "GOOGLE_API_KEY",
            "message": missing.hint,
        },
    )
