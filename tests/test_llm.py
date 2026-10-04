import json

import httpx
import pytest
from pydantic import SecretStr

from fonti.config import LLMSettings
from fonti.generation.llm import (
    LLMError,
    Message,
    OllamaClient,
    OpenAICompatibleClient,
    RemoteEndpointError,
    create_chat_client,
    ensure_local,
)

MESSAGES: list[Message] = [{"role": "user", "content": "Ciao"}]


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:8080/v1"]
)
def test_loopback_endpoints_are_allowed(url: str) -> None:
    ensure_local(LLMSettings(base_url=url))


@pytest.mark.parametrize(
    "url", ["http://192.168.1.10:11434", "https://api.example.com/v1", "http://ollama:11434"]
)
def test_remote_endpoints_are_refused_by_default(url: str) -> None:
    with pytest.raises(RemoteEndpointError, match="allow_remote"):
        ensure_local(LLMSettings(base_url=url))

    ensure_local(LLMSettings(base_url=url, allow_remote=True))


def test_ollama_cloud_models_are_refused_by_default() -> None:
    with pytest.raises(RemoteEndpointError, match="cloud"):
        create_chat_client(LLMSettings(model="gpt-oss:120b-cloud"))


def test_ollama_complete_sends_options_and_returns_content() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "Ciao!"}})

    client = OllamaClient(
        LLMSettings(context_window=4096, think=False), transport=httpx.MockTransport(handler)
    )

    assert client.complete(MESSAGES) == "Ciao!"
    assert seen["path"] == "/api/chat"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["temperature"] == 0.0


def test_ollama_stream_yields_chunks() -> None:
    lines = [
        {"message": {"content": "Buon"}, "done": False},
        {"message": {"content": "giorno"}, "done": False},
        {"message": {"content": ""}, "done": True},
    ]
    body = "\n".join(json.dumps(line) for line in lines)
    client = OllamaClient(
        LLMSettings(), transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body))
    )

    assert list(client.stream(MESSAGES)) == ["Buon", "giorno"]


def test_missing_ollama_model_suggests_pull() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(404, json={"error": "not found"}))
    client = OllamaClient(LLMSettings(model="qwen2.5:14b"), transport=transport)

    with pytest.raises(LLMError, match=r"ollama pull qwen2\.5:14b"):
        client.complete(MESSAGES)


def test_unreachable_server_gives_a_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = OllamaClient(LLMSettings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMError, match="Impossibile contattare"):
        client.complete(MESSAGES)


def test_openai_compatible_client_uses_base_path_and_api_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"choices": [{"message": {"content": "Sì"}}]})

    settings = LLMSettings(
        provider="openai", base_url="http://127.0.0.1:8080/v1", api_key=SecretStr("k")
    )
    client = OpenAICompatibleClient(settings, transport=httpx.MockTransport(handler))

    assert client.complete(MESSAGES) == "Sì"
    assert seen == {"path": "/v1/chat/completions", "auth": "Bearer k"}


def test_openai_compatible_stream_parses_server_sent_events() -> None:
    events = [
        'data: {"choices": [{"delta": {"content": "Buon"}}]}',
        'data: {"choices": [{"delta": {"content": "giorno"}}]}',
        "data: [DONE]",
    ]
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text="\n\n".join(events)))
    client = OpenAICompatibleClient(
        LLMSettings(provider="openai", base_url="http://127.0.0.1:8080/v1"), transport=transport
    )

    assert list(client.stream(MESSAGES)) == ["Buon", "giorno"]
