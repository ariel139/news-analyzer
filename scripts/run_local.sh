#!/usr/bin/env bash
# Run without Docker: Python worker in the background, Node web in the foreground. Ctrl+C stops both.
# Needs Python 3.11+ and Node 24+.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"; }
[ -d web/node_modules ] || (cd web && npm ci)
(cd web && npm run build)
.venv/bin/python -m news_analyzer llm-check || echo "WARNING: LLM not ready - articles will be collected but not analyzed"
.venv/bin/python -m news_analyzer worker &
WORKER=$!
trap 'kill $WORKER 2>/dev/null' EXIT
cd web && NA_WEB_HOST=127.0.0.1 NA_WEB_PORT=8000 node server/index.ts
