"""Verify routing, lazy initialization and manifest tiers without API calls."""

from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import SecretStr, ValidationError
from stocker_agent.config.llm import ModelSettings, ModelTier
from stocker_agent.llm import ModelProvider
from stocker_agent.skills.registry import SkillManifest


@pytest.fixture(autouse=True)
def clean_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_PROVIDER",
        "LLM_INSTANT_MODEL",
        "LLM_STANDARD_MODEL",
        "LLM_COMPLEX_MODEL",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_tier_routing_and_client_reuse(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    for tier in ModelTier:
        monkeypatch.setenv(f"LLM_{tier.value.upper()}_MODEL", f"test-{tier.value}")
    fake = FakeListChatModel(responses=["test response"])
    with patch(
        "stocker_agent.llm.provider.ChatGoogleGenerativeAI", return_value=fake
    ) as build:
        models = ModelProvider()
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
    with pytest.raises(ValueError, match="LLM_INSTANT_MODEL"):
        ModelProvider(ModelSettings(instant_model="")).get("instant")


def test_missing_credentials_are_reported() -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        ModelProvider(ModelSettings(instant_model="test-model")).get("instant")


def test_provider_and_manifest_reject_unknown_values(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
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
    assert "test-hidden-key" not in repr(ModelSettings())
