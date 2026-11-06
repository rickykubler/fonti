#!/bin/sh
# Starts Ollama, loads the answering model into memory and serves the read-only demo.
set -e

ollama serve &
until ollama list >/dev/null 2>&1; do sleep 1; done

# Load the model now, so the first visitor does not wait for it.
curl -s http://127.0.0.1:11434/api/generate \
  -d "{\"model\": \"$FONTI_LLM__MODEL\", \"keep_alive\": -1}" >/dev/null || true

exec /home/user/app/.venv/bin/fonti serve
