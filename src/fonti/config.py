"""Settings, by increasing priority: code defaults, `fonti.toml`, `.env`, `FONTI_*` variables."""

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_data_path
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

CONFIG_ENV_VAR = "FONTI_CONFIG"
DEFAULT_CONFIG_FILE = Path("fonti.toml")


class _Section(BaseModel):
    # Reject typos in the configuration instead of silently ignoring them.
    model_config = ConfigDict(extra="forbid")


class EmbeddingSettings(_Section):
    model: str = "BAAI/bge-m3"  # or "hashing" for a lexical, download-free embedder
    revision: str | None = None
    device: str = "auto"
    batch_size: int = Field(default=16, ge=1)
    query_prefix: str = ""
    document_prefix: str = ""


class ChunkingSettings(_Section):
    max_chars: int = Field(default=1500, ge=200)
    overlap_chars: int = Field(default=200, ge=0)


class RetrievalSettings(_Section):
    bm25_k: int = Field(default=50, ge=1)
    dense_k: int = Field(default=50, ge=1)
    fused_k: int = Field(default=30, ge=1)
    final_k: int = Field(default=6, ge=1)
    rrf_k: int = Field(default=60, ge=1)


class LLMSettings(_Section):
    provider: Literal["ollama", "openai"] = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:14b"
    api_key: SecretStr | None = None
    allow_remote: bool = False
    think: bool | None = None  # Ollama only; None leaves the model default
    context_window: int = Field(default=8192, ge=1024)
    max_answer_tokens: int = Field(default=800, ge=16)
    temperature: float = Field(default=0.0, ge=0.0)
    seed: int = 42
    timeout_s: float = Field(default=300.0, gt=0)


class CitationSettings(_Section):
    min_support: float = Field(default=0.3, ge=0.0, le=1.0)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FONTI_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="forbid",
    )

    data_dir: Path = Field(default_factory=lambda: user_data_path("fonti", appauthor=False))
    offline: bool = False
    embedding: EmbeddingSettings = EmbeddingSettings()
    chunking: ChunkingSettings = ChunkingSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    llm: LLMSettings = LLMSettings()
    citations: CitationSettings = CitationSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Init values come from the TOML file, so .env and environment variables override them.
        return env_settings, dotenv_settings, init_settings


def load_settings(config_file: Path | None = None) -> Settings:
    """Load settings from `config_file`, `$FONTI_CONFIG` or `./fonti.toml` when present."""
    if config_file is None:
        config_file = Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_FILE))
        required = CONFIG_ENV_VAR in os.environ
    else:
        required = True

    values: dict[str, Any] = {}
    if config_file.is_file():
        with config_file.open("rb") as f:
            values = tomllib.load(f)
    elif required:
        raise FileNotFoundError(f"File di configurazione non trovato: {config_file}")
    return Settings(**values)
