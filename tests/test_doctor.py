from pathlib import Path

import httpx
import pytest

from fonti.config import EmbeddingSettings, LLMSettings, Settings
from fonti.doctor import Status, run_checks


def statuses(settings: Settings, transport: httpx.BaseTransport) -> dict[str, Status]:
    return {check.name: check.status for check in run_checks(settings, transport=transport)}


def tags(*names: str) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda _: httpx.Response(200, json={"models": [{"name": name} for name in names]})
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, embedding=EmbeddingSettings(model="hashing"))


def test_reports_available_ollama_model(settings: Settings) -> None:
    result = statuses(settings, tags("qwen2.5:14b"))

    assert result["Ollama"] is Status.OK
    assert result["Privacy"] is Status.OK
    assert result["Embedding"] is Status.WARNING  # hashing is for tests only


def test_reports_missing_model_and_unreachable_server(settings: Settings) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert statuses(settings, tags("llama3:8b"))["Ollama"] is Status.FAILED
    assert statuses(settings, httpx.MockTransport(refuse))["Ollama"] is Status.FAILED


def test_warns_about_remote_llm(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        embedding=EmbeddingSettings(model="hashing"),
        llm=LLMSettings(base_url="https://api.example.com/v1", provider="openai"),
    )

    assert statuses(settings, tags())["Privacy"] is Status.WARNING
