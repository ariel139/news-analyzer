---
description: Bring up news_analyzer end to end (deps, Ollama, collect, one timed analysis, web + worker) and report status
argument-hint: "[ollama-model, default qwen3:8b]"
---

Run the news_analyzer project end to end on this machine and report what works. Read CLAUDE.md first and respect its invariants.

Model to use: `$ARGUMENTS`. If that is empty, use `NA_LLM_MODEL` from `.env`, or `qwen3:8b`.

Go step by step. Stop at the first blocking problem and tell me exactly what I need to do. Don't guess past it.

1. **Environment.**
   - Check Python 3.11+ and that `.venv` exists with the package installed.
   - If it doesn't, run `uv venv .venv -p 3.12 && uv pip install -p .venv -e ".[dev]"` (or the pip equivalent).
   - Check whether `docker compose` is available.
   - Note whether you are running inside a container. Tell from `/.dockerenv` or a linuxkit kernel.
2. **Tests.** Run `.venv/bin/pytest -q`. If anything fails, show me the failures and stop.
3. **Ollama.** Find a reachable Ollama server. Try, in order:
   - `NA_OLLAMA_URL`
   - `http://localhost:11434`
   - `http://host.docker.internal:11434`

   Use `curl -s <url>/api/version`. Export the working URL as `NA_OLLAMA_URL` for the rest of the run, then run `.venv/bin/python -m news_analyzer llm-check`.
   - If no server is reachable, stop. Tell me to install Ollama on the host (https://ollama.com/download) and run `ollama pull <model>`.
   - If the server is up but the model is missing, ask me before pulling it. qwen3:8b is about 5 GB.
   - Don't install Ollama or download models without my OK.
4. **Collect.**
   - Run `.venv/bin/python -m news_analyzer collect`, then `stats`.
   - Report items per outlet.
   - Flag any outlet with 0 items and show its log warning. A feed URL may have changed: verify it with curl and propose a one-line fix to `config/outlets.yaml`, but don't apply it without asking.
5. **One timed analysis.**
   - Run `.venv/bin/python -m news_analyzer analyze --limit 1 -v` and report the seconds per article and the attempt count.
   - Show the stored rating: `sqlite3 data/news.db` or a short Python query over `analyses` joined with `articles.title`. Never print `analysis_text`.
   - If it failed, show the last rows of `analysis_failures`.
   - If one article takes more than 5 minutes, recommend `qwen3:4b` or a GPU. Don't change the defaults yourself.
6. **Start the services.**
   - If Docker is available, use `docker compose up -d --build`. Set `NA_OLLAMA_URL` / `NA_LLM_MODEL` in `.env` only if they differ from the defaults, and tell me what you changed.
   - Otherwise start `python -m news_analyzer worker` and `python -m news_analyzer web --host 127.0.0.1 --port 8000` in the background.
   - Verify that `/healthz`, `/api/articles` and `/` return 200, and that `/fragments/article/<id of the rated article>` contains `למה הדירוג הזה`.
7. **Report.** Give me a short summary with:
   - the URL to open
   - the outlet counts
   - seconds per article, and the resulting articles per hour at the current limits
   - any failures
   - how to stop the services
   - one next step, e.g. labeling `eval/data/labels.csv` and running `eval-run`

Rules:
- Don't edit code or config unless something is actually broken. If you do, explain the fix and run the tests again.
- Never run `eval-export --overwrite`, because it erases my hand labels.
- Don't raise the analysis limits.
- Don't bypass robots.txt or bot protection.
- Don't commit anything unless I ask.
