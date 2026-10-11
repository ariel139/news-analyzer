# CLAUDE.md

POC: a Hebrew (RTL) site that aggregates Israeli news via RSS and shows a local-LLM political-leaning analysis per article. The README has setup, hardware and model rationale. This file covers what you need to work on the code safely.

## Commands

```bash
.venv/bin/pytest -q                                   # all tests; no network, must stay that way
.venv/bin/python -m news_analyzer collect --dry-run   # live feed check, nothing stored
.venv/bin/python -m news_analyzer llm-check           # Ollama reachable + model pulled?
.venv/bin/python -m news_analyzer analyze --limit 1 -v
.venv/bin/python -m news_analyzer stats
.venv/bin/python -m news_analyzer worker              # 15-min collect+analyze loop
cd web && npm test                                    # web: server (node:test) + client (Vitest); no network
cd web && npm run dev                                 # API :8000 + Vite UI :5173 with hot reload
cd web && npm run build && npm start                  # production site on :8000
```

The web side needs Node 24+ (it runs `.ts` directly and uses `node:sqlite`). In WSL here that's `export PATH=~/.local/opt/node-v24.21.0-linux-x64/bin:$PATH`.

Setup: `uv venv .venv -p 3.12 && uv pip install -p .venv -e ".[dev]"`, or use pip. Settings are env vars prefixed `NA_` (`src/news_analyzer/config.py`). Outlets live in `config/outlets.yaml`, one line each.

## Layout

- `collectors/`: `http.py` (PoliteClient: robots.txt via protego, per-host delay), `feeds.py`, `pages.py` (trafilatura), `listing.py` (fallback when no feed exists), `normalize.py`.
- `db.py`: SQLite schema and all writes. The web server only reads. Status flow: `pending → done | failed | skipped(reason)`, plus `paywalled`, which is terminal.
- `analyzer/`:
  - `schema.py`: the Pydantic model is both Ollama's JSON schema and the validator.
  - `prompt.py`: also holds `PROMPT_VERSION`.
  - `llm.py`: Ollama client.
  - `service.py`: retry loop.
- `pipeline.py` orchestrates; `worker.py` runs the schedule; `evaluation.py` does the eval.
- `web/` (Node, TypeScript), its own package:
  - `server/`: Express 5. `app.ts` (routes, query validation), `db.ts` (read-only `node:sqlite`, all read SQL), `serialize.ts` (whitelisted fields), `labels.ts` (Hebrew display strings), `authors.ts`.
  - `src/`: React 19 + react-router + Vite. `pages/` (feed, drawer, article, methodology), `components/`, `styles.css`.
  - Server tests build their DB from the `SCHEMA` string in `db.py`, so a schema change that breaks the web fails `npm test`.

## Invariants: don't break these

- **Never expose article text.** `articles.analysis_text` is LLM input only. Web read queries use `PUBLIC_ARTICLE_COLS` in `web/server/db.ts`, and tests assert the text never appears in API output or the rendered UI. Keep both.
- **Polite collection only.** Every request goes through `PoliteClient`. Never bypass robots.txt or bot protection. Kan and Channel 13 are disabled on purpose because they block bots; don't work around that.
- **Paid articles** are never fetched or analyzed. They're detected by the outlet's `paywall` URL patterns, a feed premium flag, or short extracted text.
- **The model sees only headline and body.** It never sees the outlet, and `strip_author` removes the byline name from the text.
- **Author stats** are aggregates, never labels. Show them only at N ≥ `author_min_articles`, always with N and the caveat.
- **Neutral UI.** No red/blue or good/bad color coding. Scales run low-on-the-left inside `dir="ltr"`. Each axis has one identity hue (`--axis-*` in `style.css`, no red or blue) that stays the same along the whole scale; color may show which axis and how strong, never which side.
- **Hebrew everywhere user-facing.** The LLM's free-text fields are validated as Hebrew. Prompt instructions are in English on purpose.
- **Changing scales or prompt wording means bumping `PROMPT_VERSION`.** A new output field goes in `LLMAnalysis`, `to_db_row`, the `analyses` table, `web/server/db.ts` (`ANALYSIS_COLS`), `web/server/serialize.ts`, `web/src/types.ts` and the tests.
- **`eval/data/` and `data/` are git-ignored.** They hold article text and the DB, so never commit them. `eval-export --overwrite` destroys the user's hand labels; only run it when asked.

## Performance context

The user's PC is CPU-only as far as we know (i5-10500), and Docker Desktop has about 2 GB RAM. qwen3:8b should take about 3–4 minutes per article on CPU, which is why the defaults are 3 articles per cycle and a 600 s budget. Ollama is expected to run on the host (`host.docker.internal:11434` from containers). Don't raise the limits by default.

## Conventions

- Python 3.11+, type hints, small modules, comments only where the reason isn't obvious. Match the existing style.
- Tests use synthetic fixtures in `tests/fixtures/` and `httpx.MockTransport`. Never hit real sites from tests.
- Web: TypeScript only "erasable" syntax on the server (no enums or parameter properties), imports with `.ts` extensions. Keep CSS class names stable; UI tests query by role and text.
- Commit per logical stage, with a descriptive message. The repo-local git identity is already set.
