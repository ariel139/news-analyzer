#!/usr/bin/env bash
# Run without Docker: worker in the background, web in the foreground. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"; }
.venv/bin/python -m news_analyzer llm-check || echo "WARNING: LLM not ready - articles will be collected but not analyzed"
.venv/bin/python -m news_analyzer worker &
WORKER=$!
trap 'kill $WORKER 2>/dev/null' EXIT
.venv/bin/python -m news_analyzer web --host 127.0.0.1 --port 8000
