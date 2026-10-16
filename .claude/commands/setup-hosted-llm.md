---
description: Add a hosted, pay-per-token LLM provider (cheapest OpenAI-compatible API, e.g. OpenRouter) next to Ollama, evaluate it, and switch only if it wins
argument-hint: "[model id, default: cheapest qualifying model]"
---

Add a hosted LLM as an **optional** backend for the political-leaning analysis, next to the local Ollama one.
Requested model: `$ARGUMENTS`. If that's empty, pick the cheapest model that passes the constraints below.

Read CLAUDE.md first and respect its invariants. Also read `docs/model-research.md` (sections 3 and 5), plus
`analyzer/llm.py`, `analyzer/service.py`, `analyzer/schema.py`, `pipeline.py` (`make_analyzer`), `config.py`,
`__main__.py` (`llm-check`) and `evaluation.py`.

## Why, and what we already know (2026-10-10; re-check prices, they change)

- A hosted API is the cheapest pay-per-article option: about $0.0003 per article (~$0.26–0.37 per 1,000), or
  ~$2–3 a month at ~170–290 articles a day. It's cheaper and simpler than a rented GPU in batch mode
  (~$0.25–0.85 per 1,000), serverless GPU (~$1.5–5 per 1,000) or a GPU rented 24/7.
- OpenRouter prices seen on 2026-10-10 (`https://openrouter.ai/api/v1/models`, $ per M tokens, in/out):
  `google/gemma-4-26b-a4b-it` 0.068/0.225, `google/gemma-4-31b-it` 0.09/0.34, `qwen/qwen3.5-9b` 0.10/0.15,
  `qwen/qwen3-14b` 0.12/0.24.
- A request is ~2.4k input tokens and ~450 output tokens with these tokenizers.
- Hebrew quality: on the Mafat/DICTA Hebrew chat leaderboard the Gemma 4 and Qwen3.5 families score ~2× the Qwen3
  family. Our local `qwen3:8b` is Qwen3.

## Hard constraints

1. **Consent first.** Using a hosted API means article text leaves this machine. This breaks the project's
   "local LLM" premise and the default rule "no article text leaves this machine".
   - Before sending any article text (eval or production), show me the provider, the model, the provider's data
     policy, and the estimated cost for the eval. Then wait for my explicit OK.
   - Until then, send only synthetic text, like the test fixtures.
2. **License.** The model's weights must be under an OSI license (Apache-2.0, MIT…). Verify this on the model
   card, not from memory. A hosted API doesn't excuse a CC-BY-NC or Llama/Gemma-terms model.
3. **Cheapest qualifying model.**
   - Fetch `/api/v1/models` and filter to models that support structured outputs (`response_format` /
     `json_schema` in `supported_parameters`) and that have an OSI license.
   - Rank by cost per article, (2400 × prompt price) + (450 × completion price).
   - Show me the top 3 with prices and the date. Prefer a model whose family has Hebrew evidence.
4. **Privacy settings in every request.**
   - Set OpenRouter's `provider` preferences `{"data_collection": "deny", "require_parameters": true}`, so the
     request only goes to providers that don't train on or retain prompts *and* do honour the JSON schema.
   - Never use `:free` endpoints, because they may log prompts.
5. **Secrets.**
   - The API key comes only from the env var `NA_LLM_API_KEY` (or `.env`, which is git-ignored).
   - Never commit, log, print or put it in an error message. Redact it in `repr` and in `llm-check` output.
   - Tell me to set a monthly spending limit on the key in the provider dashboard. Don't create accounts or keys
     yourself.
6. **Same invariants as local.**
   - The model sees only the headline and body: same `build_messages`, no outlet, byline stripped.
   - Same `LLMAnalysis` schema and validation, same `PROMPT_VERSION` handling.
   - Ratings record the hosted model id in `analyses.model`, e.g. `openrouter:google/gemma-4-26b-a4b-it`, so the UI
     and the eval can tell them apart.
7. **Ollama stays the default.** The new backend is opt-in through env vars. With no new env vars set, behaviour
   must be byte-for-byte what it is today.

## Implementation (small, matching the existing style)

1. **`config.py`:**
   - `llm_provider: Literal["ollama", "openai"] = "ollama"`
   - `llm_api_url: str = "https://openrouter.ai/api/v1"`
   - `llm_api_key: SecretStr | None = None`
   - `llm_max_cost_usd_per_run: float = 0.05` (a safety cap per analyze run)
   - Document them in `.env.example`, commented out.
2. **`analyzer/llm.py`:** add `OpenAICompatClient`, implementing the same `ChatClient` protocol as `OllamaClient`:
   `model`, `chat(messages, json_schema) -> str`, `check()`, `close()`.
   - POST to `{api_url}/chat/completions` with `response_format={"type": "json_schema", "json_schema": {"name":
     "analysis", "strict": true, "schema": ollama_json_schema()}}`, `temperature` from settings, the provider
     preferences above, and reasoning/thinking disabled (OpenRouter: `"reasoning": {"enabled": false}`). Check
     that the model accepts that.
   - Map HTTP 401/402/403/404/429/5xx, timeouts and transport errors to `LLMUnavailable`, with a short message
     that never includes the key or the article. A worker run must then stop without marking articles failed,
     exactly like an Ollama outage.
   - Retry 429/5xx at most twice with backoff, and respect `Retry-After`.
   - Read `usage` (tokens, and `cost` if present) from the response and log it at INFO, so cost per article is
     visible.
   - `check()` calls `GET /models` (or `/key` on OpenRouter) to verify the key and that the model exists.
3. **`pipeline.make_analyzer`:** choose the client by `settings.llm_provider`. `llm-check` reports which backend
   is active.
4. **Budget guard:** stop starting new analyses in a run once the logged cost passes
   `llm_max_cost_usd_per_run`.
5. **Tests** (`tests/test_analyzer.py`), with `httpx.MockTransport` and no network:
   - request body: schema, provider prefs, no thinking, Authorization header;
   - key never appears in exceptions or `repr`;
   - 401 and 429 become `LLMUnavailable`;
   - 429 is retried and then succeeds;
   - the cost guard stops a run;
   - with default settings `make_analyzer` still builds `OllamaClient`.

   Run `.venv/bin/pytest -q`; every test must pass.

## Evaluate before switching

1. Get my OK, as in constraint 1. Then `eval-run --model <hosted id>` with `NA_LLM_PROVIDER=openai`, on all 30
   labeled articles.
   - Predictions go to their own `predictions_<model>.jsonl`; never overwrite or delete existing prediction files.
   - It costs well under $0.05, so report the exact cost from `usage`.
2. `eval-score` it and compare with the current local model, split into the tuning set (original 13 ids) and
   the held-out set (the other 17). The scratchpad script `score_split.py` from the model research shows the
   split.
   - Report overall exact/±1/QWK/bias, side agreement, ±2 on neutral articles, tone bias, type accuracy, failed
     outputs and retries, seconds per article, and $ per 1,000 articles.
   - The labels are model-made silver labels. With 13/17 articles, a difference of 1–2 articles is noise; say so.
3. Recommend switch / don't switch / hybrid (e.g. hosted for the backlog, local for the newest). Base it on the
   numbers.

## Rules

- **Ask me before you:**
  - send any real article text;
  - change the default provider;
  - raise `NA_ANALYZE_MAX_PER_RUN` or the time budget;
  - spend more than $0.10 in total;
  - commit.
- One LLM job at a time also applies here: stop the worker before an eval and restart it afterwards. The web server
  keeps running.
- Update the README "Model choice" section and `docs/model-research.md` with the measured results and the privacy
  trade-off.
- Commit per logical stage when I approve, with a descriptive message.

## Deliverable

- A short chat summary: chosen model and why, cost per 1,000 articles (measured), the quality delta vs local
  with the noise caveat, and the exact env lines to switch:
  ```
  NA_LLM_PROVIDER=openai
  NA_LLM_MODEL=<id>
  NA_LLM_API_KEY=...
  ```
- The one thing you'd do next.
