# Evaluation: model vs. hand labels

`eval/data/` is git-ignored because it contains article text. Treat it as private.

## 1. Export a set (already done once)

```bash
python -m news_analyzer eval-export            # ~30 articles, round-robin over outlets
python -m news_analyzer eval-export --overwrite # pick a fresh set (DESTROYS existing labels.csv)
```

This writes:
- `eval/data/articles.jsonl`: the frozen text the model will see, so later runs and other models are compared on identical input.
- `eval/data/labels.csv`: one row per article, with empty label columns for you to fill.

## 2. Label

Open `labels.csv` in a spreadsheet. LibreOffice and Excel both handle the UTF-8 BOM, so Hebrew displays correctly. Open the `url`, read the article, and fill in:

| column | allowed values | meaning |
|---|---|---|
| `type` | `news` / `analysis` / `opinion` | news report, commentary, or opinion piece |
| `security` | `-2 … 2` or `na` | −2 dovish ↔ +2 hawkish |
| `religion` | `-2 … 2` or `na` | −2 liberal/secular ↔ +2 religious/traditional |
| `economy` | `-2 … 2` or `na` | −2 state-interventionist ↔ +2 free-market |
| `tone` | `0 … 4` | 0 neutral ↔ 4 inflammatory |
| `overall` | `-2 … 2` or `na` | −2 left ↔ +2 right (Israeli sense); `0` = balanced/no leaning; `na` = not political at all |

Guidelines. These match the model's instructions; see `src/news_analyzer/analyzer/prompt.py`.
- Judge the text, not the outlet or author.
- For news, rate the framing. For opinion and analysis, rate the position argued.
- Use `na` when the article does not touch the issue. Use `0` when it touches the issue but is balanced.
- Leave a cell empty if you are unsure. Empty cells are ignored, and a row with all cells empty is skipped.
- `notes` is free text for yourself.

## 3. Run the model and score

```bash
python -m news_analyzer eval-run                     # uses NA_LLM_MODEL (default qwen3:8b)
python -m news_analyzer eval-run --model qwen3:4b    # compare another model
python -m news_analyzer eval-score --model qwen3:8b  # re-print scores without re-running
```

Predictions are cached in `eval/data/predictions_<model>.jsonl`. The run can be resumed: if you stop it, it continues where it left off. To re-run after changing the prompt, delete that file.

## Metrics

Each axis is scored on articles where both you and the model gave a number.

- **N/A agree %**: how often you and the model agree on whether the axis applies at all.
- **exact %** and **±1 %**: identical score, or within one step.
- **MAE**: mean absolute difference.
- **bias**: mean of (model − you). A positive value means the model systematically rates higher (more right, hawkish, religious, free-market or loaded). This number matters most for a leaning tool.
- **QWK**: quadratic-weighted Cohen's kappa, the standard agreement statistic for ordinal scales. 1 is perfect agreement and 0 is chance level; values above 0.6 usually count as substantial.
- **Article type**: accuracy plus a `label->prediction` confusion count.

With about 30 articles these numbers are noisy. A difference of 10 points between two models is not meaningful. Use the results to catch gross failures and systematic bias, not to rank models finely.
