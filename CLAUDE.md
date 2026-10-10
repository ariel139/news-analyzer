# CLAUDE.md

POC: a Hebrew (RTL) site that aggregates Israeli news via RSS and shows a local-LLM political-leaning analysis per article. The README has setup, hardware and model rationale. This file covers what you need to work on the code safely.

## Commands

```bash
.venv/bin/pytest -q                                   # all tests; no network, must stay that way
.venv/bin/python -m news_analyzer collect --dry-run   # live feed check, nothing stored
.venv/bin/python -m news_analyzer llm-check           # Ollama reachable + model pulled?
.venv/bin/python -m news_analyzer analyze --limit 1 -v
.venv/bin/python -m news_analyzer stats
.venv/bin/python -m news_analyzer web --port 8000     # site + /api/docs
.venv/bin/python -m news_analyzer worker              # 15-min collect+analyze loop
```

Setup: `uv venv .venv -p 3.12 && uv pip install -p .venv -e ".[dev]"`, or use pip. Settings are env vars prefixed `NA_` (`src/news_analyzer/config.py`). Outlets live in `config/outlets.yaml`, one line each.

## Layout

- `collectors/`: `http.py` (PoliteClient: robots.txt via protego, per-host delay), `feeds.py`, `pages.py` (trafilatura), `listing.py` (fallback when no feed exists), `normalize.py`.
- `db.py`: SQLite schema and all SQL. Status flow: `pending → done | failed | skipped(reason)`, plus `paywalled`, which is terminal.
- `analyzer/`:
  - `schema.py`: the Pydantic model is both Ollama's JSON schema and the validator.
  - `prompt.py`: also holds `PROMPT_VERSION`.
  - `llm.py`: Ollama client.
  - `service.py`: retry loop.
- `pipeline.py` orchestrates; `worker.py` runs the schedule; `evaluation.py` does the eval; `labels.py` holds Hebrew display strings.
- `web/`: `app.py` (JSON API and HTMX routes), `serialize.py` (whitelisted fields), Jinja templates, `static/` (vendored htmx 2.0.4).

## Invariants: don't break these

- **Never expose article text.** `articles.analysis_text` is LLM input only. Read queries use `PUBLIC_ARTICLE_COLS` in `db.py`, and tests assert the text never appears in API or HTML output. Keep both.
- **Polite collection only.** Every request goes through `PoliteClient`. Never bypass robots.txt or bot protection. Kan and Channel 13 are disabled on purpose because they block bots; don't work around that.
- **Paid articles** are never fetched or analyzed. They're detected by the outlet's `paywall` URL patterns, a feed premium flag, or short extracted text.
- **The model sees only headline and body.** It never sees the outlet, and `strip_author` removes the byline name from the text.
- **Author stats** are aggregates, never labels. Show them only at N ≥ `author_min_articles`, always with N and the caveat.
- **Neutral UI.** No red/blue or good/bad color coding. Scales run low-on-the-left inside `dir="ltr"`.
- **Hebrew everywhere user-facing.** The LLM's free-text fields are validated as Hebrew. Prompt instructions are in English on purpose.
- **Changing scales or prompt wording means bumping `PROMPT_VERSION`.** A new output field goes in `LLMAnalysis`, `to_db_row`, the `analyses` table, `serialize.py` and the tests.
- **`eval/data/` and `data/` are git-ignored.** They hold article text and the DB, so never commit them. `eval-export --overwrite` destroys the user's hand labels; only run it when asked.

## Performance context

The user's PC is CPU-only as far as we know (i5-10500), and Docker Desktop has about 2 GB RAM. qwen3:8b should take about 3–4 minutes per article on CPU, which is why the defaults are 3 articles per cycle and a 600 s budget. Ollama is expected to run on the host (`host.docker.internal:11434` from containers). Don't raise the limits by default.

## Conventions

- Python 3.11+, type hints, small modules, comments only where the reason isn't obvious. Match the existing style.
- Tests use synthetic fixtures in `tests/fixtures/` and `httpx.MockTransport`. Never hit real sites from tests.
- Commit per logical stage, with a descriptive message. The repo-local git identity is already set.
