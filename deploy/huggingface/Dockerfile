# Public read-only demo of fonti on a Hugging Face Docker Space (CPU basic: 2 vCPU, 16 GB RAM).
# Code, models, documents and the index are all prepared at build time: the Space starts
# without downloads and needs no network at run time.
FROM ollama/ollama:0.40.14

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/*

# Spaces run the container as uid 1000.
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user

# Pin the fonti commit and the answering model here; FONTI_LLM__MODEL overrides fonti.toml.
ARG FONTI_REF=main
ARG LLM_MODEL=qwen3.5:4b
ENV HOME=/home/user \
    UV_PYTHON_INSTALL_DIR=/home/user/.python \
    UV_FROZEN=1 \
    HF_HOME=/home/user/hf \
    OLLAMA_MODELS=/home/user/ollama \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_KEEP_ALIVE=-1 \
    FONTI_CONFIG=/home/user/demo.toml \
    FONTI_LLM__MODEL=${LLM_MODEL}

RUN git clone https://github.com/rickykubler/fonti.git app && git -C app checkout "$FONTI_REF"
WORKDIR /home/user/app
# The dev group is included on purpose: it renders the synthetic demo documents.
RUN uv sync --extra cpu

COPY --chown=user demo.toml precompute.py start.sh /home/user/
RUN FONTI_OFFLINE=false uv run fonti models pull \
 && uv run fonti eval corpus costituzione gdpr ai-act agid istat contratto verbale manuale \
 && uv run fonti ingest eval/corpus/files

ENV HF_HUB_OFFLINE=1
RUN ollama serve & pid=$! \
 && until ollama list >/dev/null 2>&1; do sleep 1; done \
 && ollama pull "$LLM_MODEL" \
 && uv run python /home/user/precompute.py \
 && kill "$pid"

EXPOSE 7860
ENTRYPOINT []
CMD ["sh", "/home/user/start.sh"]
