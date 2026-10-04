"""Settings, by increasing priority: code defaults, `fonti.toml`, `.env`, `FONTI_*` variables."""

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_data_path
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from fonti.errors import FontiError

CONFIG_ENV_VAR = "FONTI_CONFIG"
DEFAULT_CONFIG_FILE = Path("fonti.toml")

KeywordMode = Literal["plain", "stemmed"]


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


class ParserSettings(_Section):
    # "fast": PDF text layer only; "docling": layout, tables and OCR for every PDF;
    # "auto": docling only for PDFs with scanned pages (and for .docx).
    mode: Literal["fast", "docling", "auto"] = "fast"
    ocr: bool = True
    ocr_engine: Literal["easyocr", "rapidocr", "tesseract"] = "easyocr"
    ocr_languages: list[str] = Field(default_factory=list)  # engine codes; empty = Italian+English
    force_ocr: bool = False  # OCR every page, for PDFs with a broken text layer
    # EasyOCR drops lines below this confidence; its default (0.5) lost ~40% of the text of
    # noisy Italian scans in our evaluation, 0.2 keeps the CER around 3-5%.
    ocr_confidence: float = Field(default=0.2, ge=0.0, le=1.0)
    tables: bool = True


class ChunkingSettings(_Section):
    max_chars: int = Field(default=1500, ge=200)
    overlap_chars: int = Field(default=200, ge=0)


class RetrievalSettings(_Section):
    bm25_k: int = Field(default=50, ge=1)
    dense_k: int = Field(default=50, ge=1)
    fused_k: int = Field(default=30, ge=1)
    final_k: int = Field(default=6, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    # "stemmed": Italian Snowball stems without stopwords; "plain": lowercase words.
    keyword_terms: KeywordMode = "plain"


class RerankSettings(_Section):
    enabled: bool = False
    model: str = "BAAI/bge-reranker-v2-m3"
    revision: str | None = None
    device: str = "auto"
    batch_size: int = Field(default=16, ge=1)
    max_length: int = Field(default=512, ge=64)
    # Relevance gate: when the best reranked passage scores below this, the system abstains
    # without calling the LLM. 0 disables the gate.
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


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
    parser: ParserSettings = ParserSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    chunking: ChunkingSettings = ChunkingSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    rerank: RerankSettings = RerankSettings()
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


class ConfigError(FontiError):
    pass


def load_settings(config_file: Path | None = None) -> Settings:
    """Load settings from `config_file`, `$FONTI_CONFIG` or `./fonti.toml` when present."""
    if config_file is None:
        config_file = Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_FILE))
        required = CONFIG_ENV_VAR in os.environ
    else:
        required = True

    values: dict[str, Any] = {}
    if config_file.is_file():
        try:
            with config_file.open("rb") as f:
                values = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{config_file} non è un file TOML valido: {exc}") from exc
    elif required:
        raise ConfigError(f"File di configurazione non trovato: {config_file}")
    try:
        return Settings(**values)
    except ValidationError as exc:
        raise ConfigError(f"Configurazione non valida:\n{exc}") from exc
