from pathlib import Path

import pytest

from fonti.config import ConfigError, load_settings


def test_defaults_are_local_only() -> None:
    settings = load_settings()

    assert settings.llm.allow_remote is False
    assert settings.llm.base_url.startswith("http://127.0.0.1")


def test_toml_file_in_working_directory_is_loaded(tmp_path: Path) -> None:
    (tmp_path / "fonti.toml").write_text('[llm]\nmodel = "gemma"\n', encoding="utf-8")

    assert load_settings().llm.model == "gemma"


def test_environment_overrides_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "fonti.toml").write_text(
        '[llm]\nmodel = "gemma"\ntemperature = 0.5\n', encoding="utf-8"
    )
    monkeypatch.setenv("FONTI_LLM__MODEL", "qwen")

    settings = load_settings()

    assert settings.llm.model == "qwen"
    assert settings.llm.temperature == 0.5


def test_config_file_from_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "custom.toml"
    config.write_text("[retrieval]\nfinal_k = 3\n", encoding="utf-8")
    monkeypatch.setenv("FONTI_CONFIG", str(config))

    assert load_settings().retrieval.final_k == 3


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "fonti.toml").write_text('[llm]\nmodle = "typo"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="modle"):
        load_settings()


def test_explicit_missing_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="non trovato"):
        load_settings(tmp_path / "missing.toml")


def test_api_key_is_not_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FONTI_LLM__API_KEY", "sk-secret")

    settings = load_settings()

    assert "sk-secret" not in repr(settings)
    assert settings.llm.api_key is not None
    assert settings.llm.api_key.get_secret_value() == "sk-secret"
