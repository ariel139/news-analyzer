---
description: Research and measure how to make news_analyzer's LLM rating faster and more accurate (efficiency, Hebrew models, prompt, GPU rental) and write up a ranked recommendation
argument-hint: "[focus: all | efficiency | models | prompt | gpu, default all]"
---

Find out how to make the political-leaning analysis faster, cheaper and more accurate, and back every recommendation with measurements or cited sources. Read CLAUDE.md first and respect its invariants. Also read the README sections "Model choice" and "Hardware", plus `analyzer/prompt.py`, `analyzer/schema.py`, `analyzer/llm.py` and `evaluation.py`.

Focus: `$ARGUMENTS`. If that's empty, do all four parts in order. Otherwise do only the part named.

## What we already know (measured on 2026-10-10; re-check, don't assume)

**Hardware**
- i5-10500, 6 cores / 12 threads, no GPU. Everything runs in WSL2.
- WSL has 11 GiB RAM (`.wslconfig` sets `memory=12GB`) and 3 GiB swap.
- Ollama 0.40.2 is installed natively in WSL as a systemd service (`/usr/local/bin/ollama`), at `http://localhost:11434`.

**Current model**
- `qwen3:8b`: a 5.2 GB download, 6.7 GB in RAM at `num_ctx` 8192, thinking off, temperature 0.1.
- The article text is truncated to `max_analysis_chars` = 3000.

**Speed per article**
- 370 s when WSL had only 7.9 GB and the model swapped.
- 287 s on a cold start once the model fit in RAM.
- 104–151 s warm, with the model to itself.
- 100–315 s while another job used Ollama at the same time.

**Memory incident**
- Running `eval-run` and the worker at the same time pushed `llama-server` to 10.6 GB RSS.
- Claude Code then killed the background web server and worker for low memory.
- **Never run two LLM jobs at once.** Stop the worker before an eval, then restart it afterwards. `OLLAMA_NUM_PARALLEL=1` is a candidate fix; the user applies service changes, because they need sudo.

**Eval set**
- `eval/data/labels.csv` has 13 labeled rows out of 30.
- The labels were made by Claude, blind (headline and body only, no outlet), not by a human. Treat them as silver labels.
- **v1 prompt:**
  - overall: exact 46%, QWK 0.0;
  - when both sides gave a non-zero rating, the model had the wrong sign in 3 of 5;
  - it gave confident ±2 ratings to neutral news;
  - tone bias +0.6; type accuracy 85%.
- **v2 prompt (commit b40891a):** adds `favored_side` (left/right/none) before the scores, plus a validator that the side agrees with the overall score. Results are in `eval/data/predictions_qwen3_8b.jsonl`; the v1 results are kept in `predictions_qwen3_8b.v1.jsonl`. Run `eval-score --model qwen3:8b` for the current numbers.
- **The prediction cache is keyed only by model name, not by prompt version.** Before re-running after a prompt change, rename the existing predictions file (e.g. to `.v2.jsonl`). Never delete it: older runs are the comparison baseline.

**Known output defect:** `_require_hebrew` only compares Hebrew with Latin letters. Explanations containing Arabic, CJK or stray English words (e.g. "cushions", "報導") pass validation.

## Part 0: Baseline

1. Run `.venv/bin/pytest -q`. It must pass before you change anything.
2. Run `eval-score` for every predictions file that exists, and record the numbers.
3. **Find where the time goes.** Ollama's `/api/chat` response reports:
   - `prompt_eval_count` and `prompt_eval_duration` (prefill)
   - `eval_count` and `eval_duration` (generation)

   Measure them for 2–3 eval articles with a small one-off script in the scratchpad that calls the local Ollama. Report:
   - tokens in and tokens out;
   - prefill speed and generation speed, in tokens per second;
   - **tokens per Hebrew character** (tokenizer fertility; this matters a lot for CPU speed).

## Part 1: Efficiency on this CPU

**How to test.** Test one change at a time against the Part 0 baseline. For each, report seconds per article, tokens per second, peak RSS of `llama-server`, and whether eval quality changed. Every quality check uses the same 13 labeled articles.

**Candidates.** Verify each one exists in the installed Ollama version before you try it.

| Lever | What to check |
|---|---|
| `num_ctx` | Size it to the real prompt plus output (from Part 0) instead of 8192. That saves RAM and may be faster. |
| Output length | Generated tokens dominate on a CPU. Check the `explanation` and `summary` length limits and `num_predict`. Shorter outputs mean faster ratings. |
| Input length | Lower `max_analysis_chars` and measure what it does to quality. |
| `num_thread` | 6 (physical cores) vs 12 (logical). |
| Quantization | Compare q4_K_M with other quants on the Ollama library: speed vs quality. |
| Ollama settings | Flash attention, KV-cache quantization (e.g. `OLLAMA_KV_CACHE_TYPE`), `OLLAMA_NUM_PARALLEL=1`, `keep_alive`. These are service settings: give the user the exact `sudo systemctl edit ollama` lines. |
| Prompt prefix caching | Check that the long static system prompt is reused between requests and not re-processed every time. |

**Rules for this part**
- Changes to code defaults are proposals only. Don't raise `NA_ANALYZE_MAX_PER_RUN` or the time budget.
- Ollama per-request options in `llm.py` are fair game if they're measured, tested, and leave the defaults' behavior safe on this machine.

## Part 2: Hebrew-capable models

Use web search for the current state, as of today. Cite every claim with a link and a date.

**Constraints, from the README**
- **License:** must be OSI-approved (Apache-2.0, MIT, etc.). Gemma's terms, CC-BY-NC models (like Aya) and Llama's license are excluded. Verify each license from its model card, not from memory.
- **Runnable here:**
  - a CPU tier: about 8B parameters at 4-bit or less, using no more than about 7 GB of RAM;
  - optionally a GPU tier: up to 24 GB of VRAM.
- **Available:** as an Ollama tag or a GGUF build.
- **Evidence of real Hebrew quality:** Hebrew benchmarks or leaderboards if any exist, or the model card's language list, plus reports on JSON or structured-output reliability.

**Candidates to check, not conclusions:**
- newer Qwen releases and sizes;
- Dicta's DictaLM models and other Hebrew fine-tunes;
- Mistral/Ministral, Phi, OLMo and Granite families;
- anything newer you find.

**Output:** a table of model, license, size and RAM, Ollama tag, Hebrew evidence and source links. Then shortlist at most 3.

**Before pulling any model**, list the shortlist with download sizes and ask me. Don't pull without my OK. Then, with the worker stopped, run `eval-run --model <tag>` for each, then `eval-score`, and compare with qwen3:8b on quality and seconds per article.

## Part 3: A better prompt

1. **Failure analysis.** Start from the latest `eval-score` and the per-article predictions. For every wrong article, say what went wrong, using the model's own `explanation` and `evidence_phrases`:
   - wrong side;
   - a neutral article rated strongly;
   - an over-rated tone;
   - news classified as opinion.

   Don't print article text. Short Hebrew phrases of up to about 8 words are fine.
2. **Avoid overfitting.** 13 silver labels is a tiny sample.
   - Before tuning, label the 17 unlabeled rows the same way (blind: headline and the first 3000 characters with the byline removed, which is exactly what the model sees). Keep them as a held-out test set.
   - Tune on the first 13 and report on the held-out set.
   - Leave `notes` empty and never overwrite existing labels.
   - Say clearly in the report that the labels are model-made.
3. **Ideas to try, measured one at a time:**
   - clearer direction anchors;
   - a rule against confident ±2 on attributed news;
   - calibrating tone;
   - an article-type checklist;
   - one or two very short few-shot examples (weigh the token cost from Part 0);
   - thinking mode only for articles where `favored_side` isn't `none`, comparing quality against the time cost;
   - a stricter Hebrew validator that rejects Arabic and CJK characters (weigh the extra retries).
4. **Rules for every prompt change**
   - Instructions stay in English and outputs in Hebrew. The model never sees the outlet.
   - Bump `PROMPT_VERSION` for every wording or scale change.
   - A new output field goes in `LLMAnalysis`, `to_db_row`, the `analyses` table with a migration in `db._migrate`, `serialize.py` and the tests.
   - Rename the predictions file before each re-run.
5. **Output:** the best prompt as a diff, with before/after metrics on both the tuning set and the held-out set.

## Part 4: Cheap GPU rental

Search current offers. Prices change, so record the date and source for every number.

1. **Providers.** Compare vast.ai, RunPod, TensorDock, Lambda, Paperspace, Salad and any other relevant provider on:
   - price per hour for GPUs with 16–24 GB of VRAM (RTX 3090/4090, A4000/A5000, L4 or similar);
   - billing granularity, and storage costs while stopped;
   - interruptible vs on-demand instances;
   - datacenter ("secure") vs community hosts;
   - how easy it is to set up Ollama.
2. **Cost per 1,000 articles.** Estimate it with GPU throughput from the README table, or from a measurement if I've rented an instance. Compare:
   - a batch mode (rent, clear the backlog, destroy the instance);
   - running 24/7.
3. **Hosted APIs.** For comparison, include API pricing for the same open models, e.g. OpenRouter. Note that this breaks the project's "local LLM" premise and would need a new client next to `OllamaClient`.
4. **Security and privacy**
   - Reach the rented machine only through an SSH tunnel (`-L 11434:localhost:11434`). Never expose Ollama's port; it has no authentication.
   - Article text leaves the PC, so community hosts are a privacy trade-off.
5. **Hands off:** don't create accounts, rent anything or spend money.

## Rules

- **No article text leaves this machine.** Never paste article text (from `eval/data/` or `articles.analysis_text`) into web searches, web fetches or any external API. Research queries contain only generic terms.
- **Ask me before you:**
  - pull a model;
  - change Ollama's service config (give me the commands instead);
  - change analysis limits or defaults;
  - rent anything;
  - commit.
- **One LLM job at a time.**
  - Stop the worker before an eval and restart it afterwards.
  - Keep the web server running so the site stays up.
  - Run long jobs (an eval of 13 articles takes about 25–40 minutes on this CPU) in the background.
- **Tests:** run `.venv/bin/pytest -q` after any code change. Tests never touch the network.
- **Labels:** never run `eval-export --overwrite`.
- **Report numbers, not impressions.** With 13–30 articles, a difference of one or two articles is noise, so say so.

## Deliverable

Write `docs/model-research.md` (don't commit it unless I ask) with:

1. **Summary:** the top 3 recommendations, ranked by expected gain per effort and cost. For each, give the measured or cited evidence and the exact change: a command, a config line or a diff.
2. **Baseline vs best:** a table of speed (seconds per article and articles per hour at the current limits), memory, and eval metrics for each configuration you tried.
3. **Hebrew model table** and shortlist results, if you did Part 2.
4. **Prompt changes** with before/after metrics on the tuning and held-out sets, if you did Part 3.
5. **GPU and API cost table** with dates and sources, if you did Part 4.
6. **Open questions and what you need from me.**

Then give me a short summary in chat, plus the one thing you'd do next.
