# Model research: faster, cheaper, more accurate leaning analysis

Measured on 2026-10-10 on the dev PC: i5-10500 (6C/12T), no GPU, WSL2 with 11 GiB RAM, Ollama 0.40.2
(native systemd service), `qwen3:8b` Q4_K_M. All web facts are cited with the date they were checked
(2026-10-10 unless stated otherwise).

> **About the labels.** All 30 eval labels were made by Claude, blind: headline plus the first 3000
> characters with the byline removed, which is exactly what the model sees. Nobody human checked them. Treat
> them as silver labels. With 13 or 17 articles per set, a difference of one or two articles is noise.

<!-- SUMMARY -->

## 2. Baseline: where the time goes (Part 0)

Tests: 83/83 passed before any change.

**Method.** A scratch script sent the app's exact `/api/chat` request (same messages, JSON schema, options) for
eval articles and recorded Ollama's counters plus `llama-server`'s own `print_timing` log lines. The log lines
matter because Ollama's `prompt_eval_count` *includes cached tokens* and its `prompt_eval_duration` includes cache
bookkeeping, so dividing them gives meaningless "prefill speed" figures (we saw 40–7700 tok/s).

| measure (qwen3:8b Q4_K_M, 6 threads, ctx 8192) | value |
|---|---|
| system prompt | 980 tokens (Qwen3 tokenizer), **reused between requests** (`cached n_tokens = 980`) |
| user message (headline + ≤3000 chars) | 683–1210 new tokens per article (median ~1100) |
| tokenizer fertility, Qwen3 | **0.52 tokens per Hebrew letter**, 2.39 per word (all 30 articles, offline; matches live counts) |
| prefill speed (new tokens) | **19–23.6 tok/s**, i.e. ~45 ms per token |
| generation speed | **3.3–4.2 tok/s** (3.9 typical), i.e. ~255 ms per token |
| output length | 289–487 tokens (median ~400) |
| time per new article | **130–175 s** = ~4 s cache bookkeeping + ~50 s prefill + ~100 s generation |
| re-rating an article already in the cache | restoring the saved state took 21 s + 41 s, *slower* than recomputing |
| validation retry (v2) | +~115 s each (a full new generation) |

**Generation is two-thirds of the time.** That makes output tokens the main lever. Each output token costs ~255 ms
even when the JSON grammar forces it (keys, braces), because llama.cpp still runs a forward pass per token.

| output part (v1 outputs, Qwen3 tokens, median) | tokens |
|---|---|
| JSON structure, compact | 103 |
| JSON structure as the model actually writes it (indented, 31 newlines) | **~190** |
| explanation | 91 |
| summary | 65 |
| evidence phrases | 34 |

The ~87 tokens of indentation are **~22 s per article (~15%)** of pure whitespace. A leaner schema (n/a as `null`,
confidence only on `overall`) would be 59 tokens compact; that needs a DB/UI change, so it's only a proposal.

### Memory: the cause of the "two LLM jobs" incident

Ollama 0.40.2 runs llama.cpp's `llama-server` with `-np 1`, so it already serves one request at a time.
`OLLAMA_NUM_PARALLEL=1` would change nothing. It also runs with the default **`--cache-ram 8192`**. After every
request the server saves that request's KV state to host RAM: 295–462 MiB per article (~140 KB/token). Measured
in this session:

- `llama-server` RSS grew from 6.7 GB to **11.2 GB** over ~12 requests (`cache state: 12 prompts, 4423 MiB`).
- With WSL at 229 MB available, Claude Code reaped the eval for low memory. That happened with **only one** LLM job
  running.
- Bookkeeping cost 0.3–21 s per request ("prompt cache update took …").

For this workload the cache buys nothing: every article is new, and the system-prompt prefix is still reused by
the live slot without it. Retries also extend the live slot's prompt.

### Eval baseline

| prompt | set | n ok / labeled | failed | overall exact | ±1 | QWK | side agree | ±2 on neutral | tone bias | type acc. | s/article |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 | tuning | 13/13 | 0 | 46% | 62% | 0.00 | 6/13 | 2/6 | +0.62 | 85% | 219 |
<!-- V2ROW -->

v1 failure analysis (tuning set), from the model's own `explanation`/`evidence_phrases`:

- **Wrong side, 3/13: the topic was scored, not the side.**
  - #275 attacks "השמאל הרדיקלי" (labelled +2) → −2.
  - #285 attacks the government ("למחוק את הטבח", labelled −1) → +2.
  - #32 economic analysis (+1) → −2.
- **An attributed quote was taken as the article's voice.**
  - #73 news: "ישראל 'מציבה מכשולים'" → −2 with high confidence (labelled 0).
  - #2 news: a politician's quote "הכי הייתי רוצה לסגור את משרד החינוך" → typed *opinion*, −2 (labelled news, 0).
- **Tone over-rated** by +0.6 on average: loaded words in quotes counted as the article's tone.
- **Script leaks** in 7/33 outputs (v1 + v2 + DB): CJK (e.g. "ת석יס"), Arabic ("انتخابים", "לرئيس") and Latin
  glued into Hebrew words ("המilitאריות", "cushions").

## 3. Hebrew-capable models (Part 2)

### What "Hebrew-capable" can be measured with

- **Hebrew chat leaderboard** by Mafat/DICTA ([dataset `hebrew-llm-leaderboard/chat-results`](https://huggingface.co/datasets/hebrew-llm-leaderboard/chat-results),
  last updated 2026-08-31; [announcement](https://huggingface.co/blog/leaderboard-hebrew)). Its five tasks are nikud,
  summarization (pairwise), translation (pairwise), Israeli trivia and Winograd. **It lists no model smaller than
  24B**, so it can only tell us which *families* are good at Hebrew.
- **Tokenizer fertility**, measured here. It's the number of tokens per Hebrew letter on our real model input: the 30
  eval articles, built by `build_messages` with max 3000 chars. On a CPU, prefill time grows linearly with input tokens.

| family (leaderboard entry) | Nikud | Summ. | Transl. | Trivia | Winograd | mean |
|---|---|---|---|---|---|---|
| Qwen3.5-397B-A17B | 78.2 | 47.3 | 42.9 | 72.1 | 86.7 | **65.4** |
| DictaLM-3.0-24B-Thinking | 86.9 | 56.9 | 30.1 | 60.1 | 78.1 | **62.4** |
| Qwen3.5-122B-A10B | 67.1 | 46.2 | 31.0 | 70.1 | 93.2 | **61.5** |
| Gemma-4-31B-it | 73.4 | 48.5 | 33.3 | 58.5 | 86.0 | **59.9** |
| Gemma-4-26B-A4B-it | 68.1 | 46.0 | 27.3 | 44.5 | 78.1 | **52.8** |
| Gemma-3-27B-it (reference) | 60.2 | 44.5 | 26.7 | 45.5 | 79.9 | 51.4 |
| Aya-Expanse-32B (reference, CC-BY-NC) | 45.4 | 29.5 | 17.1 | 53.8 | 80.6 | 45.3 |
| **Qwen3-30B-A3B-Thinking-2507** (closest to our qwen3:8b) | 15.8 | 12.4 | 1.0 | 43.5 | 77.0 | **29.9** |

The Qwen3 generation scores near the bottom on Hebrew *generation* (summary 12.4, translation 1.0). The Qwen3.5 and
Gemma 4 families and DictaLM 3.0 are 2× better. The DictaLM 3.0 technical report agrees for small sizes: Qwen3-14B
(thinking) scores 15.8 on summarization and 0.9 on translation, against 39.5 / 16.5 for Gemma-3-12B
([arXiv:2602.02104, Table 8](https://arxiv.org/html/2602.02104)).

**Tokenizer fertility (measured, Hebrew letters → tokens, median over 30 articles):**

| tokenizer | vocab | tokens / Hebrew letter | user-message tokens (median) | vs qwen3 |
|---|---|---|---|---|
| Phi-4-mini | 200k | 0.504 | 1074 | −2% |
| **Qwen3 (current)** | 152k | **0.518** | **1091** | — |
| Ministral 3 / DictaLM 3.0 (Mistral tekken) | 131k | 0.576 | 1266 | +16% |
| DictaLM 2.0 (Hebrew-extended Mistral) | 33k | 0.582 | 1286 | +18% |
| Gemma 4 | 262k | 0.607 | 1334 | +22% |
| Qwen3.5 | 248k | 0.643 | 1400 | +28% |
| OLMo 3 / Granite 4 | 100k | 1.232 | 2720 | +149% |

Check against the live server: for article 279, Ollama counted 1689 prompt tokens. That's 980 system-prompt
tokens plus ~709 for 1333 Hebrew letters, i.e. 0.53 per letter, which matches the offline count. Newer tokenizers are
*not* more efficient for Hebrew. Qwen3.5 needs 28% more input tokens than Qwen3, which is about +12 s of
prefill per article at the measured 22.5 tok/s.

### Candidate table

Licenses were read from each model card's license field (HF API) on 2026-10-10. RAM is the Q4_K_M file size;
the KV cache and runtime come on top (~1 GB at 8k context for an 8B).

| model | license | params | Q4 size | Ollama / GGUF | Hebrew evidence | fits CPU tier (≤ ~7 GB)? |
|---|---|---|---|---|---|---|
| **qwen3:8b** (current) | Apache-2.0 | 8.2B | 5.2 GB | `qwen3:8b` | Hebrew in its 119-language list ([blog](https://qwenlm.github.io/blog/qwen3/)); family weak on leaderboard (29.9) | yes (6.7 GB loaded) |
| **Qwen3.5-9B** | Apache-2.0 ([card](https://huggingface.co/Qwen/Qwen3.5-9B)) | 9.0B + 0.46B vision | 6.6 GB | `qwen3.5:9b`, also `-mtp` variants ([tags](https://ollama.com/library/qwen3.5/tags)) | 201 languages; family 61–65 on leaderboard; MMMLU 81.2 (card) | borderline: 6.6 GB file incl. vision projector |
| **Qwen3.5-4B** | Apache-2.0 | 4.7B | 3.3 GB | `qwen3.5:4b` | as above, smaller | yes |
| **Gemma 4 E4B** | **Apache-2.0** ([card](https://huggingface.co/google/gemma-4-E4B-it); first Apache Gemma, released 2026-04-02, [the-decoder](https://the-decoder.com/googles-gemma-4-is-now-available-with-apache-2-0-licensing-for-the-first-time/)) | 8B total / 4.5B effective | 6.6 GB | `gemma4:e4b` ([tags](https://ollama.com/library/gemma4/tags)) | MMMLU 76.6 (card); family 53–60 on leaderboard | borderline |
| Gemma 4 12B | Apache-2.0 | 12B | 8.0 GB | `gemma4:12b` | family 53–60 | no → GPU tier |
| **DictaLM 2.0-instruct** | Apache-2.0 ([card](https://huggingface.co/dicta-il/dictalm2.0-instruct)) | 7.3B | 4.4 GB | [`hf.co/dicta-il/dictalm2.0-instruct-GGUF`](https://huggingface.co/dicta-il/dictalm2.0-instruct-GGUF) | Hebrew-specialised, Hebrew-extended vocab ([arXiv:2407.07080](https://arxiv.org/abs/2407.07080)); from 2024 | yes |
| DictaLM 3.0-1.7B | Apache-2.0 | 1.7B | 1.1 GB | [`dicta-il/DictaLM-3.0-1.7B-Thinking-GGUF`](https://huggingface.co/dicta-il/DictaLM-3.0-1.7B-Thinking-GGUF) | report Table 8: summ. 9.7, transl. 2.2 → too weak | yes, but too weak |
| DictaLM 3.0-Nemotron-12B | **NVIDIA Open Model License** ([card](https://huggingface.co/dicta-il/DictaLM-3.0-Nemotron-12B-Instruct)) | 12B | — | official GGUF | summ. 33.3 | **excluded (license)** |
| **DictaLM 3.0-24B-Thinking** | Apache-2.0 ([card](https://huggingface.co/dicta-il/DictaLM-3.0-24B-Thinking)) | 24B | 14.3 GB | [`dicta-il/DictaLM-3.0-24B-Thinking-GGUF`](https://huggingface.co/dicta-il/DictaLM-3.0-24B-Thinking-GGUF) | leaderboard 62.4, best open model at Hebrew summarization (56.9) | no → **GPU tier** (thinking model: slower) |
| Gemma 4 26B-A4B / 31B | Apache-2.0 | 26B MoE / 31B | 16–20 GB | `gemma4:26b`, `gemma4:31b` | leaderboard 52.8 / 59.9 | no → GPU tier |
| Ministral 3 8B | Apache-2.0 ([card](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512)) | 8.4B + 0.4B vision | ~6 GB | `ministral-3:8b` | **Hebrew not in its language list** | yes, not recommended |
| Phi-4-mini | MIT ([card](https://huggingface.co/microsoft/Phi-4-mini-instruct)) | 3.8B | ~2.5 GB | `phi4-mini` | Hebrew listed; multilingual MMLU 49.3 (card) | yes, likely too weak |
| Granite 4.0 micro / h-tiny | Apache-2.0 ([card](https://huggingface.co/ibm-granite/granite-4.0-micro)) | 3.4B / 7B | — | `granite4` | Hebrew **not** listed; 2.4× worse fertility | no |
| OLMo 3 7B | Apache-2.0 | 7.3B | — | `olmo-3` | English-centric; 2.4× worse fertility | no |
| HEBATRON (30B-A3B) | **CC BY-NC-ND 4.0** ([arXiv:2605.11255](https://arxiv.org/html/2605.11255v1)) | 30B MoE | — | — | Hebrew avg 73.8 | **excluded (license)** |
| Aya Expanse 8B | **CC-BY-NC-4.0** | 8B | — | — | — | **excluded (license)** |

<!-- SHORTLIST -->

<!-- PROMPT -->

## 5. GPU rental and hosted APIs (Part 4)

All prices checked 2026-10-10. Marketplace prices (vast.ai, TensorDock, Salad) move daily.

### Providers, 16–24 GB GPUs

| provider | GPU | $/h | type | billing | stopped-instance storage | source |
|---|---|---|---|---|---|---|
| vast.ai | RTX 3090 | 0.14 on-demand, 0.09 interruptible | community marketplace (some datacenter hosts) | per second | **still billed while stopped**; only destroying stops it | [computeprices](https://computeprices.com/providers/vast/gpus/rtx3090), [getdeploying](https://getdeploying.com/gpus/nvidia-rtx-3090), [vast docs](https://docs.vast.ai/documentation/reference/billing) |
| vast.ai | RTX 4090 | 0.36 on-demand, 0.24 interruptible | as above | per second | as above | [getdeploying](https://getdeploying.com/gpus/nvidia-rtx-4090) |
| RunPod | RTX 3090 | 0.22 community / 0.50 secure | community or datacenter | per second | container disk $0.10/GB/mo, volume $0.07/GB/mo | [runpod.io/pricing](https://www.runpod.io/pricing) |
| RunPod | RTX 4090 | 0.34 community / 0.74 secure | as above | per second | as above | [runpod.io/pricing](https://www.runpod.io/pricing) |
| RunPod | RTX A5000 | 0.16 community / 0.27 secure | as above | per second | as above | [runpod.io/pricing](https://www.runpod.io/pricing) |
| RunPod | L4 | 0.44 / 0.49 | as above | per second | as above | [runpod.io/pricing](https://www.runpod.io/pricing) |
| TensorDock | RTX 4090 | from ~0.35 (marketplace; cheaper residential hosts exist) | marketplace | hourly | — | [tensordock](https://tensordock.com/cloud-gpus.html), [deploybase](https://deploybase.ai/articles/tensordock-gpu-pricing) |
| Salad | RTX 4090 | 0.16–0.33 by priority | **consumer PCs**, preemptible below "high" priority | per second | none (containers only) | [salad.com/pricing](https://salad.com/pricing) |
| Lambda | Quadro RTX 6000 24 GB | 0.69 | datacenter | per minute | included disk | [lambda.ai/pricing](https://lambda.ai/pricing) |
| Paperspace (DigitalOcean) | A4000 16 GB / A5000 | 0.76 / 1.38 (+plan) | datacenter | per hour | — | [DO docs](https://docs.digitalocean.com/products/paperspace/pricing) |

**Ease of Ollama setup.** RunPod and vast.ai both have one-click PyTorch/CUDA images with SSH: `curl -fsSL
https://ollama.com/install.sh | sh && ollama pull qwen3:8b` is all it takes. Salad runs containers only (no
SSH), so you'd ship a container that pulls the model on start; it can't be reached through an SSH tunnel.

### GPU throughput and cost per 1,000 articles

The llama.cpp CUDA benchmark ([discussion #15013](https://github.com/ggml-org/llama.cpp/discussions/15013), Llama-2-7B
Q4_0, flash attention on) gives **RTX 3090: 5560 t/s prefill, 162 t/s generation; RTX 4090: 14770 / 189;
A5000: 4552 / 136; A4000: 2808 / 85**. An 8B Q4_K_M is about 20–40% slower: ~92 t/s on a 3090 and ~145 on a 4090,
per [markaicode](https://markaicode.com/benchmarks/llamacpp-rtx-4090-benchmark/). Our measured workload per article:
~1100 new prompt tokens plus ~400 output tokens (Part 0). So on a 3090, an article takes 0.2 s prefill + ~4.3 s
generation ≈ **5 s/article ≈ 700 articles/hour**. The README estimate of 10–20 s is pessimistic.

| scenario | assumptions | cost / 1,000 articles |
|---|---|---|
| **Batch, vast.ai 3090** | 1.4 h GPU + 0.25 h setup (boot, install, 5.2 GB pull) at $0.14 | **≈ $0.23** |
| Batch, RunPod 3090 community | same at $0.22 | ≈ $0.36 |
| Batch, RunPod 3090 secure | same at $0.50 | ≈ $0.83 |
| 24/7, vast.ai 3090 | $0.14 × 730 h = $102/month; current volume ~170–290 articles/day (DB: 169 published on 2026-10-10) ≈ 5–9k/month | **≈ $11–20** |
| 24/7, RunPod 3090 community | $161/month | ≈ $18–32 |
| CPU at home (today) | electricity only; ~150 s/article at the cap of 3 per 15 min | ~$0 extra, but capped at ~290/day |

Batch mode is 50–100× cheaper per article than 24/7 because the GPU would sit idle >95% of the time at our
volume. A sensible hybrid is to keep the CPU for the freshest articles and rent a GPU for an hour when the
backlog grows.

### Hosted APIs (same open models)

OpenRouter prices from its public [`/api/v1/models`](https://openrouter.ai/api/v1/models) endpoint, 2026-10-10. Per
article: ~2.4k input tokens (Qwen3.5/Gemma tokenizers, see fertility table) plus ~450 output tokens.

| model | $/M in | $/M out | ≈ cost / 1,000 articles |
|---|---|---|---|
| qwen/qwen3.5-9b | 0.10 | 0.15 | **$0.31** |
| google/gemma-4-26b-a4b-it | 0.068 | 0.225 | $0.26 |
| google/gemma-4-31b-it | 0.09 | 0.34 | $0.37 |
| qwen/qwen3-14b | 0.12 | 0.24 | $0.35 |
| mistralai/ministral-8b-2512 | 0.15 | 0.15 | $0.43 |

### Hosted backend: implemented and measured (2026-10-10/11)

`NA_LLM_PROVIDER=openai` switches to `OpenAICompatClient` (`analyzer/llm.py`); Ollama stays the default.

**Model choice.** Filtered `/api/v1/models` to structured-output support plus an OSI license read from each HF model
card, ranked by 2400 × prompt + 450 × completion price. The cheapest three were `inclusionai/ling-3.0-flash-vl`
(MIT), `mistralai/mistral-nemo` (Apache-2.0) and `openai/gpt-oss-20b` (Apache-2.0), all ~$0.08/1,000. None has
Hebrew evidence, and gpt-oss can't turn reasoning off. **Chosen: `google/gemma-4-26b-a4b-it`** (Apache-2.0, Hebrew
leaderboard 52.8, i.e. ~1.8× the Qwen3 family's 29.9).

**Most upstream providers accept `json_schema` but don't enforce it.** `require_parameters: true` is not enough. Probe
with a synthetic article and a system prompt that asks the model to break the schema (English text, a missing field,
a literal `"`), two trials per provider pinned with `order` + `allow_fallbacks: false`:

| provider (gemma-4-26b-a4b-it) | result |
|---|---|
| **DeepInfra** (fp8) | structure, required fields and the character `pattern` all enforced; only our extra Hebrew-ratio check failed (the prompt asked for English) |
| Darkbloom | structure kept, `pattern` ignored |
| SiliconFlow, Google Vertex | invalid JSON (unescaped `"`) |
| NextBit, Venice, Parasail | no JSON at all, 10–105 s (runaway generation) |
| CoreWeave | HTTP 400 |

Unpinned, a first eval run hit those providers: invalid JSON, missing fields, a failed article, and one request that
never ended (OpenRouter keeps a slow non-streamed request alive with whitespace, so httpx's per-read timeout never
fires). Fixes: `NA_LLM_API_PROVIDERS=deepinfra` (no fallback), a 180 s deadline on the whole response, and
`max_tokens: 2000`.

**Eval, all 30 labeled articles, prompt v3, DeepInfra** (local `qwen3:8b` has predictions for only 17 of them, mixed
prompt versions, so it's a rough baseline):

| | gemma-4-26b (hosted) | qwen3:8b (local) | same 17 articles: gemma vs qwen |
|---|---|---|---|
| failed outputs / needed a retry | 1 / 0 (#256: summary < 30 chars, 3×) | 3 / 2 | 1/0 vs 3/2 |
| overall exact / ±1 | 46% / **100%** | 20% / 30% | 29%/100% vs 20%/30% |
| overall QWK / bias | **0.71 / +0.04** | 0.33 / +1.5 | 0.71/+0.14 vs 0.33/+1.5 |
| side agreement | 66% | 43% | 56% vs 43% |
| neutral article rated ±2 | **0/22** | 5/8 | 0/10 vs 5/8 |
| tone bias | +0.34 | +0.50 | +0.38 vs +0.50 |
| article type accuracy | 90% | 64% | 88% vs 64% |
| s / article | **~6** | ~215 | |
| $ / 1,000 articles (measured) | **$0.28** ($0.00846 for 30 incl. retries; 71k in + 10k out tokens) | ~$0 | |

Tuning (13) vs held-out (17), gemma: ±1 is 100% on both, bias +0.08 vs 0.00, type accuracy 77% vs 100%. Held-out QWK
is 0.0 only because 16 of the 17 held-out labels are neutral, so QWK is undefined there in practice. The labels are
Claude-made silver labels, and with 13/17 articles a difference of 1–2 articles is noise; the gaps above (±1 100% vs
30%, neutral→±2 0 vs 5, bias +0.04 vs +1.5) are far larger than that.

Total spent on the whole investigation: ~$0.03 (two partial runs, the provider probe, the final run).

**Privacy trade-off.** This breaks the project's "local LLM" premise: headline and body (byline stripped, no outlet)
go to OpenRouter and to DeepInfra. Every request sends `data_collection: deny`, so OpenRouter only routes to providers
that *declare* they don't retain or train on prompts; we can't verify that. `:free` endpoints are never used. The key
comes only from `NA_LLM_API_KEY`/`.env`, is never logged, and should have a monthly spending limit set in the
OpenRouter dashboard.

**Recommendation.** Switch if the privacy trade-off is acceptable: clearly more accurate (above all on neutral news,
where qwen3:8b invents a slant), ~35× faster so the 3-per-cycle CPU cap stops limiting coverage, and ~$1–3/month at
~170–290 articles/day. Otherwise run a hybrid: Ollama by default, hosted for clearing a backlog.

### Security and privacy for a rented GPU

- Never expose port 11434. Ollama has no authentication. Keep `OLLAMA_HOST=127.0.0.1` on the instance and connect with
  `ssh -N -L 11434:localhost:11434 -p <port> root@<host>`. Then run the worker with
  `NA_OLLAMA_URL=http://localhost:11434`; note that this collides with the local Ollama port, so use e.g. `-L 11435:localhost:11434`
  and `NA_OLLAMA_URL=http://localhost:11435`.
- Article text leaves the PC. On community hosts (vast.ai community, RunPod community, TensorDock, Salad) the
  machine belongs to an unknown third party who can read memory and disk. The text is public news, but
  `analysis_text` is still copyrighted content we promised to keep internal. Prefer "secure"/datacenter tiers, and
  destroy (not stop) instances after a batch.

<!-- OPEN -->
