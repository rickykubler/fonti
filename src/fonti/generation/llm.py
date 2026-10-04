"""Chat clients for local LLM servers: Ollama's native API or any OpenAI-compatible server.

Both refuse non-local endpoints unless `llm.allow_remote` is set.
"""

import ipaddress
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Literal, Protocol, TypedDict
from urllib.parse import urlsplit

import httpx

from fonti.config import LLMSettings
from fonti.errors import FontiError


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatClient(Protocol):
    @property
    def model_id(self) -> str: ...

    def complete(self, messages: Sequence[Message]) -> str: ...

    def stream(self, messages: Sequence[Message]) -> Iterator[str]: ...


class LLMError(FontiError):
    """The model server could not produce an answer; the message is meant for the user."""


class RemoteEndpointError(LLMError):
    """A non-local endpoint or a cloud model was configured without `allow_remote`."""


def ensure_local(settings: LLMSettings) -> None:
    if settings.allow_remote:
        return
    host = urlsplit(settings.base_url).hostname or ""
    if not is_loopback(host):
        raise RemoteEndpointError(
            f"L'endpoint {settings.base_url} non è locale: le domande e i documenti uscirebbero "
            "dal computer. Per usarlo imposta llm.allow_remote = true."
        )
    if settings.provider == "ollama" and _is_ollama_cloud_model(settings.model):
        raise RemoteEndpointError(
            f"Il modello {settings.model} gira nel cloud di Ollama. "
            "Per usarlo imposta llm.allow_remote = true."
        )


def create_chat_client(
    settings: LLMSettings, *, transport: httpx.BaseTransport | None = None
) -> ChatClient:
    if settings.provider == "ollama":
        return OllamaClient(settings, transport=transport)
    return OpenAICompatibleClient(settings, transport=transport)


class OllamaClient:
    """Ollama's native /api/chat, which can set the context window and disable thinking."""

    def __init__(
        self, settings: LLMSettings, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        ensure_local(settings)
        self._settings = settings
        self._http = httpx.Client(
            base_url=settings.base_url, timeout=settings.timeout_s, transport=transport
        )

    @property
    def model_id(self) -> str:
        return f"ollama:{self._settings.model}"

    def complete(self, messages: Sequence[Message]) -> str:
        with _translate_errors(self._settings):
            response = self._http.post("/api/chat", json=self._payload(messages, stream=False))
            _check(response, self._settings)
            return str(response.json()["message"]["content"])

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        payload = self._payload(messages, stream=True)
        with (
            _translate_errors(self._settings),
            self._http.stream("POST", "/api/chat", json=payload) as response,
        ):
            _check(response, self._settings)
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if "error" in event:
                    raise LLMError(f"Errore dal server LLM: {event['error']}")
                content = event.get("message", {}).get("content", "")
                if content:
                    yield content
                if event.get("done"):
                    return

    def _payload(self, messages: Sequence[Message], *, stream: bool) -> dict[str, Any]:
        settings = self._settings
        payload: dict[str, Any] = {
            "model": settings.model,
            "messages": list(messages),
            "stream": stream,
            "options": {
                "temperature": settings.temperature,
                "seed": settings.seed,
                "num_ctx": settings.context_window,
                "num_predict": settings.max_answer_tokens,
            },
        }
        if settings.think is not None:
            payload["think"] = settings.think
        return payload


class OpenAICompatibleClient:
    """Chat Completions API: llama.cpp server, LM Studio, vLLM or (opt-in) cloud providers."""

    def __init__(
        self, settings: LLMSettings, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        ensure_local(settings)
        self._settings = settings
        headers = {}
        if settings.api_key is not None:
            headers["Authorization"] = f"Bearer {settings.api_key.get_secret_value()}"
        self._http = httpx.Client(
            base_url=settings.base_url,
            headers=headers,
            timeout=settings.timeout_s,
            transport=transport,
        )

    @property
    def model_id(self) -> str:
        return f"openai:{self._settings.model}"

    def complete(self, messages: Sequence[Message]) -> str:
        with _translate_errors(self._settings):
            response = self._http.post(
                "/chat/completions", json=self._payload(messages, stream=False)
            )
            _check(response, self._settings)
            return str(response.json()["choices"][0]["message"]["content"] or "")

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        payload = self._payload(messages, stream=True)
        with (
            _translate_errors(self._settings),
            self._http.stream("POST", "/chat/completions", json=payload) as response,
        ):
            _check(response, self._settings)
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    return
                choices = json.loads(data).get("choices") or [{}]
                content = (choices[0].get("delta") or {}).get("content")
                if content:
                    yield content

    def _payload(self, messages: Sequence[Message], *, stream: bool) -> dict[str, Any]:
        settings = self._settings
        return {
            "model": settings.model,
            "messages": list(messages),
            "temperature": settings.temperature,
            "seed": settings.seed,
            "max_tokens": settings.max_answer_tokens,
            "stream": stream,
        }


@contextmanager
def _translate_errors(settings: LLMSettings) -> Iterator[None]:
    try:
        yield
    except httpx.ConnectError as exc:
        hint = (
            " (per Ollama: avvia l'app o `ollama serve`)" if settings.provider == "ollama" else ""
        )
        raise LLMError(
            f"Impossibile contattare il server LLM su {settings.base_url}{hint}."
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMError(
            f"Il modello non ha risposto entro {settings.timeout_s:.0f} secondi."
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"Errore di comunicazione con il server LLM: {exc}") from exc


def _check(response: httpx.Response, settings: LLMSettings) -> None:
    if response.is_success:
        return
    detail = response.read().decode("utf-8", errors="replace")[:300]
    if response.status_code == 404 and settings.provider == "ollama":
        model = settings.model
        raise LLMError(f"Modello {model} non trovato in Ollama: esegui `ollama pull {model}`.")
    raise LLMError(f"Errore {response.status_code} dal server LLM: {detail}")


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_ollama_cloud_model(model: str) -> bool:
    _, _, tag = model.partition(":")
    return tag == "cloud" or tag.endswith("-cloud")
