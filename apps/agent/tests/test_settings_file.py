"""Verify source precedence and keep sensitive fields out of tracked settings."""

from pathlib import Path

import pytest
from stocker_agent.config import base
from stocker_agent.config.llm import ModelSettings
from stocker_agent.config.skills import SkillSettings


def test_dotenv_loading_and_precedence(monkeypatch, tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        '[llm-models.standard]\nmodel = "from-toml"\n[skills]\nmode = "local"\n'
    )
    dotenv_file = tmp_path / "test-settings.env"
    dotenv_file.write_text(
        "GOOGLE_API_KEY=test-dotenv-key\n"
        "LLM_STANDARD__MODEL=from-dotenv\n"
        "SKILL_MODE=s3\nSKILL_S3_BUCKET=test-bucket\n"
        "UNRELATED_SETTING=ignored\n"
    )
    monkeypatch.setattr(base, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(base, "ENV_FILE", dotenv_file)
    for name in (
        "GOOGLE_API_KEY",
        "LLM_STANDARD__MODEL",
        "SKILL_MODE",
        "SKILL_S3_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path.parent)
    settings = ModelSettings()
    assert settings.standard.model == "from-dotenv"
    assert settings.google_api_key is not None
    assert settings.google_api_key.get_secret_value() == "test-dotenv-key"
    assert "test-dotenv-key" not in repr(settings)
    assert SkillSettings().s3_bucket == "test-bucket"
    monkeypatch.setenv("LLM_STANDARD__MODEL", "from-process")
    assert ModelSettings().standard.model == "from-process"
    assert ModelSettings(standard={"model": "explicit"}).standard.model == "explicit"


def test_missing_dotenv_is_optional(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(base, "ENV_FILE", tmp_path / "missing-settings.env")
    assert SkillSettings(mode="local").mode == "local"


def test_file_env_and_explicit_precedence(monkeypatch, tmp_path: Path) -> None:
    file = tmp_path / "settings.toml"
    file.write_text(
        '[llm-models.standard]\nmodel = "from-file"\n[skills]\nmode = "s3"\n'
    )
    monkeypatch.setattr(base, "SETTINGS_FILE", file)
    monkeypatch.delenv("LLM_STANDARD__MODEL", raising=False)
    monkeypatch.delenv("SKILL_MODE", raising=False)
    monkeypatch.setenv("SKILL_S3_BUCKET", "test-skills")
    assert ModelSettings().standard.model == "from-file"
    assert SkillSettings().mode == "s3"
    monkeypatch.setenv("LLM_STANDARD__MODEL", "from-env")
    assert ModelSettings().standard.model == "from-env"
    assert ModelSettings(standard={"model": "explicit"}).standard.model == "explicit"


@pytest.mark.parametrize(
    "content,settings",
    [
        ('[llm-models]\ngoogle_api_key = "not-allowed"\n', ModelSettings),
        ('[llm-models]\nopenrouter_api_key = "not-allowed"\n', ModelSettings),
        ('[skills]\ns3_bucket = "not-allowed"\n', SkillSettings),
        ('[skills]\ns3_prefix = "not-allowed"\n', SkillSettings),
    ],
)
def test_sensitive_fields_are_rejected_in_file(
    monkeypatch, tmp_path, content, settings
) -> None:
    file = tmp_path / "settings.toml"
    file.write_text(content)
    monkeypatch.setattr(base, "SETTINGS_FILE", file)
    with pytest.raises(ValueError, match="Unsupported fields"):
        settings()


def test_app_uses_shared_sources(monkeypatch, tmp_path: Path) -> None:
    from stocker_agent.config.app import AppSettings

    config = tmp_path / "settings.toml"
    config.write_text("""[app]
poll_seconds = 0.5
runtime_pool_size = 8
checkpoint_pool_size = 3
pool_timeout_seconds = 2
cors_origins = ["http://localhost:5173"]
[llm-models.standard]
model = "toml-model"
[skills]
mode = "local"
""")
    environment = tmp_path / "app-settings-test.env"
    environment.write_text("""DB_HOST=database-test
DB_PORT=5544
DB_USER=app-test
DB_PASSWORD=fixture-password
DB_NAME=stocker_agent_runtime
APP_POLL_SECONDS=0.25
GOOGLE_API_KEY=fixture-model-key
LLM_STANDARD__MODEL=dotenv-model
SKILL_LOCAL_PATH=./test-skills
UNRELATED_SETTING=ignored
""")
    monkeypatch.setattr(base, "SETTINGS_FILE", config)
    monkeypatch.setattr(base, "ENV_FILE", environment)
    for key in (
        "DATABASE_URI",
        "DB_HOST",
        "DB_PUBLIC_HOST",
        "DB_PORT",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
        "APP_POLL_SECONDS",
        "APP_RUNTIME_POOL_SIZE",
        "APP_CHECKPOINT_POOL_SIZE",
        "APP_POOL_TIMEOUT_SECONDS",
        "APP_CORS_ORIGINS",
        "GOOGLE_API_KEY",
        "LLM_STANDARD__MODEL",
        "SKILL_LOCAL_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path.parent)
    settings = AppSettings()
    assert settings.db_host == "database-test"
    assert settings.db_port == 5544
    assert settings.db_password.get_secret_value() == "fixture-password"
    assert settings.poll_seconds == 0.25
    assert settings.runtime_pool_size == 8
    assert settings.checkpoint_pool_size == 3
    assert settings.pool_timeout_seconds == 2
    assert settings.cors_origins == ["http://localhost:5173"]
    assert ModelSettings().standard.model == "dotenv-model"
    assert ModelSettings().google_api_key.get_secret_value() == "fixture-model-key"
    assert SkillSettings().local_path == "./test-skills"
    monkeypatch.setenv("DB_PORT", "6655")
    monkeypatch.setenv("APP_POLL_SECONDS", "0.1")
    assert AppSettings().db_port == 6655
    assert AppSettings().poll_seconds == 0.1
    assert AppSettings(db_port=7766, poll_seconds=0.05).db_port == 7766
    assert AppSettings(db_port=7766, poll_seconds=0.05).poll_seconds == 0.05


def test_app_rejects_credentials_in_toml(monkeypatch, tmp_path):
    from stocker_agent.config.app import AppSettings

    config = tmp_path / "settings.toml"
    config.write_text('[app]\ndb_password="not-allowed"\n')
    monkeypatch.setattr(base, "SETTINGS_FILE", config)
    with pytest.raises(ValueError, match="Unsupported fields"):
        AppSettings()


def test_dotenv_uses_base_file_and_process_precedence(monkeypatch, tmp_path):
    from stocker_agent.config.app import AppSettings

    env = tmp_path / "base-test.env"
    env.write_text(
        "GOOGLE_API_KEY=fixture-key\nLLM_STANDARD__MODEL=base-model\nDB_USER=app-user\nDB_PASSWORD=fixture-password\n"
    )
    monkeypatch.setattr(base, "ENV_FILE", env)
    for name in (
        "GOOGLE_API_KEY",
        "LLM_STANDARD__MODEL",
        "DB_USER",
        "DB_PASSWORD",
        "DATABASE_URI",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path.parent)
    assert ModelSettings().google_api_key.get_secret_value() == "fixture-key"
    assert ModelSettings().standard.model == "base-model"
    assert AppSettings().db_user == "app-user"
    monkeypatch.setenv("LLM_STANDARD__MODEL", "process-model")
    assert ModelSettings().standard.model == "process-model"
    assert (
        ModelSettings(standard={"model": "explicit-model"}).standard.model
        == "explicit-model"
    )


def test_nested_route_merges_provider_and_model_across_sources(monkeypatch, tmp_path):
    config = tmp_path / "route-settings.toml"
    config.write_text(
        '[llm-models.complex]\nprovider="openrouter"\nmodel="file-model"\n'
    )
    env = tmp_path / "route-settings-test.env"
    env.write_text(
        "LLM_COMPLEX__MODEL=dotenv-model\nOPENROUTER_API_KEY=fixture-router-key\n"
    )
    monkeypatch.setattr(base, "SETTINGS_FILE", config)
    monkeypatch.setattr(base, "ENV_FILE", env)
    for name in ("LLM_COMPLEX__MODEL", "LLM_COMPLEX__PROVIDER", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = ModelSettings()
    assert settings.complex.provider == "openrouter"
    assert settings.complex.model == "dotenv-model"
    assert settings.openrouter_api_key.get_secret_value() == "fixture-router-key"
    monkeypatch.setenv("LLM_COMPLEX__MODEL", "process-model")
    assert ModelSettings().complex.model == "process-model"
    assert (
        ModelSettings(complex={"model": "explicit-model"}).complex.provider
        == "openrouter"
    )
    assert (
        ModelSettings(complex={"model": "explicit-model"}).complex.model
        == "explicit-model"
    )
