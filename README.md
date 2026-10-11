# news_analyzer: Israeli news, rated by a local LLM (POC)

A Hebrew, right-to-left website that aggregates recent articles from major Israeli outlets and shows an AI-generated political-leaning analysis for each one. Everything runs locally with open-source tools and models.

> **Status: experiment.** Ratings are machine-generated and subjective. The site shows titles, metadata, a model-written summary and a link to the original. It never displays article text.

```
 RSS feeds ──► collectors ──► SQLite ◄── analyzer (Ollama, local LLM)
 (+ polite page fetch,           │             ▲
    robots.txt, rate limit)      ▼             │ every 15 min: collect → analyze N newest
                     Express + React ◄── worker (APScheduler)
                     (Node, reads the DB;  Python)
                      Hebrew RTL site + /api)
```

| module | what it does |
|---|---|
| `src/news_analyzer/collectors/` | RSS parsing, a polite HTTP client (robots.txt with wildcards via `protego`, per-host delay, crawl-delay), page text extraction (`trafilatura`), a listing-page fallback, paywall detection |
| `src/news_analyzer/db.py` | SQLite schema, dedup (normalized URL, plus outlet+title), status flow, retention purge, read queries that never select article text |
| `src/news_analyzer/analyzer/` | prompt, Pydantic output schema (also used as Ollama's JSON schema), Ollama client, validate-and-retry loop |
| `src/news_analyzer/pipeline.py`, `worker.py` | orchestration and the 15-minute schedule |
| `web/server/` | Express JSON API (`/api/...`), TypeScript run directly by Node 24. Opens the SQLite DB read-only |
| `web/src/` | React + Vite client: feed, filters, article drawer, article and methodology pages. One component per file, styles in `web/src/styles.css` |
| `src/news_analyzer/evaluation.py`, `eval/` | agreement between the model and your hand labels |
| `config/outlets.yaml` | outlets, one line each |

## Outlets

| outlet | source | notes |
|---|---|---|
| ynet | RSS (news + opinions) | |
| Walla | RSS | feed `1` lags by days; feed `3` is current |
| Maariv | RSS (news + opinions) | `ispremium` flag in the feed is honoured |
| Israel Hayom | RSS | |
| Haaretz | RSS | `.premium` URLs are paywalled → listed, never fetched or analyzed |
| N12 (Mako) | RSS (military/politics, Israel, law) | |
| Globes | RSS | |
| Kan, Channel 13 | **disabled** | both sites block automated clients (Cloudflare challenge / 403), including on robots.txt. Getting around bot protection is not "polite scraping", so they are off. |

To add an outlet, add one line to `config/outlets.yaml`. Use `feeds:` when the outlet has a feed. Otherwise use `listing: {url: ..., link_pattern: ...}`.

Paid articles are never analyzed. They are recognised by URL pattern, by a feed flag, or by extracted text under 400 characters (a teaser or paywall).

## Model choice

**Default: `qwen3:8b` (Qwen3 8B, Apache-2.0) via Ollama, with thinking mode off.**

- **License.** It is truly open source. Gemma 3 and Aya Expanse have good Hebrew but ship under non-OSI licenses (Gemma terms; CC-BY-NC), which this project's constraints rule out.
- **Hebrew.** Qwen3 is trained on 119 languages including Hebrew. Its Hebrew is decent, not native-level.
- **JSON reliability.** It works well with Ollama's schema-constrained decoding.
- **Size.** 8B at 4-bit is about 5 GB, which is the largest that is still usable on a CPU-only PC.
- **Alternatives** (one env var, compare with `eval-run --model ...`):
  - `qwen3:4b`: about twice as fast, with noticeably weaker Hebrew.
  - `qwen3:14b`: better, but needs a GPU to be practical.
  - Dicta's Hebrew-specialised **DictaLM** models are worth trying if you find a GGUF build. They have better Hebrew but are weaker at strict schemas.
- **Don't use `qwen3:0.6b`.** It was tested during development. It passes the schema but writes broken Hebrew.

The eval set (below) is how you should decide. Treat these as priors.

## Hardware

Measured on the development machine: Intel i5-10500 (6C/12T), no GPU, inside Docker Desktop with only 2 GB RAM.

| model | RAM needed | CPU-only speed (estimate) | GPU (≥ 8 GB VRAM) |
|---|---|---|---|
| qwen3:4b | ~4 GB | ~1.5–2 min / article | ~5–10 s |
| **qwen3:8b** | ~7 GB | **~3–4 min / article** | ~10–20 s |
| qwen3:14b | ~11 GB | too slow | ~20–40 s (needs ≥ 12 GB VRAM) |

The CPU figures come from a measured 0.6B run (≈21 tokens/s generation) scaled by model size. Check your real speed with `python -m news_analyzer analyze --limit 1`, which logs the seconds per article.

On a CPU-only machine the defaults are deliberately small: **at most 3 articles per 15-minute cycle, with a 10-minute budget**. Only articles from the last 24 hours are rated, newest first. Sport, weather and lifestyle sections are skipped. That works out to about 10 rated articles per hour.

**Docker Desktop note.** The Docker VM on this PC currently has about 2 GB RAM, which isn't enough for any useful model. Either run Ollama natively on the host (recommended), or raise Docker Desktop → Settings → Resources → Memory to at least 10 GB.

## Setup

### 1. Install Ollama and download the model (on the host)

Install Ollama from https://ollama.com/download (Windows, macOS or Linux), then run:

```bash
ollama pull qwen3:8b        # ~5.2 GB download
ollama run qwen3:8b "שלום" --think=false   # quick sanity check
```

### 2a. Run with Docker Compose (recommended)

```bash
cp .env.example .env        # optional: tweak model / limits
docker compose up -d --build
docker compose logs -f worker
```

Open http://localhost:8000. The worker collects immediately and then every 15 minutes.

To run Ollama inside Docker too:

```bash
NA_OLLAMA_URL=http://ollama:11434 docker compose --profile ollama up -d --build
docker compose exec ollama ollama pull qwen3:8b
```

### 2b. Run without Docker

Needs Python 3.11+ and Node 24+.

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
scripts/run_local.sh        # worker in background + web on http://127.0.0.1:8000
```

### Working on the UI

```bash
cd web && npm install
npm run dev                 # API on :8000 (restarts on change) + Vite on http://localhost:5173 (hot reload)
npm test                    # server (node:test) + client (Vitest) tests
npm run build && npm start  # production build served by Express on :8000
```

The web server reads the same `NA_*` settings and `.env` as the Python side. Relative paths resolve against the repo root. `NA_WEB_HOST` / `NA_WEB_PORT` set where it listens.

## CLI

```bash
python -m news_analyzer collect [--dry-run]       # fetch feeds once (dry-run: print only)
python -m news_analyzer llm-check                 # is Ollama up and the model pulled?
python -m news_analyzer analyze --limit 1         # rate newest pending article(s); logs time per article
python -m news_analyzer analyze --id 42 --reanalyze
python -m news_analyzer stats                     # counts by status/outlet + failure log size
python -m news_analyzer purge                     # drop stored text older than 30 days (worker does this daily)
python -m news_analyzer worker                    # scheduler
python -m news_analyzer eval-export | eval-run | eval-score
```

With Docker, prefix commands with `docker compose exec worker`, e.g. `docker compose exec worker python -m news_analyzer stats`.

## How to check each stage

1. **Collectors.** Run `python -m news_analyzer collect --dry-run`. You should see about 250–300 recent titles across 7 outlets, with Haaretz premium items tagged `[paywall]`.
2. **Database.** Run `collect` twice, then `stats`. The second run should insert about 0 rows (dedup works). Statuses: `pending` / `paywalled` / `skipped`.
3. **Analyzer.**
   - Run `llm-check`, then `analyze --limit 1 -v`.
   - Check the log line `done in Ns (1 attempt): type=... overall=...`.
   - Check `sqlite3 data/news.db "select * from analyses"`.
   - Malformed outputs are listed in `select * from analysis_failures`.
4. **API.**
   - Open http://localhost:8000/api/articles?leaning=0 and http://localhost:8000/api/articles/1.
   - Other endpoints: `/api/meta`, `/api/overview`, `/api/new?since=...`, `/api/methodology`, `/healthz`.
   - No response contains article text.
5. **Frontend.** Open http://localhost:8000 on a phone-width window.
   - Click a title to see its scales, the "why" explanation, the summary and the link.
   - Try the filters.
   - Read `/methodology`.
6. **Evaluation.** Fill `eval/data/labels.csv`, then run `eval-run`. See `eval/README.md`.

Run the Python tests with `pytest` (collectors, robots handling, DB, JSON validation and retry, metrics) and the web tests with `cd web && npm test` (API, including "article text never leaks", and the React UI). None of them make network calls.

## Rating design (short)

- **Axes.**
  - security, religion↔state, economy and overall left↔right are each scored −2…+2 or `n/a`.
  - tone is scored 0…4.
  - Every axis has a confidence of low, medium or high.
- **Other outputs.** Article type (news, analysis or opinion), topic from a fixed list, 1–3 evidence phrases (kept only if they appear verbatim in the text), a 1–2 sentence Hebrew explanation and a 2–3 sentence neutral Hebrew summary.
- **Inputs.** The model sees only the headline and body. The outlet is never sent, and the author's name is removed from the text.
- **Validation.** Output must pass the Pydantic schema, with Hebrew enforced for the explanation and summary. On failure, the error is sent back to the model, up to 3 attempts in total. Every failed attempt is logged.
- **Caching and versioning.** Each article is rated once and the result is cached in `analyses`. `PROMPT_VERSION` is stored with each rating.
- **Author statistics.** Shown only at ≥ 5 rated articles, as "Articles by this author lean X, based on N articles" plus a caveat. Low-confidence ratings and desk bylines are excluded.

## Data and ethics

- RSS first. Article pages are fetched only for articles about to be analyzed, at most one request per host every 2 seconds, and only where robots.txt allows.
- Stored article text is internal: it is never rendered or returned by the API, and it is deleted after 30 days. Metadata and ratings are kept.
- `eval/data/` (frozen article text) is git-ignored.
- No accounts and no comments.
