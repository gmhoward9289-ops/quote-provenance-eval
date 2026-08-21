# Tested models / provider matrix

What this harness has actually been run against in-repo (or on the reef
sweep), versus what the README examples only illustrate. Post new results in
[Discussions](https://github.com/gmhoward9289-ops/trust-but-anchor/discussions)
or open a PR that adds `results/run_*.json` — gaps below are the most useful
submissions.

## Providers

| provider | status | notes |
|---|---|---|
| `mock` | validated | keyless profiles `faithful` / `sloppy` / `chaotic` for pipeline smoke |
| `ollama` | validated | local OpenAI-compatible API; most `results/` history is here |
| `anthropic` | supported | example in README (`claude-sonnet-4-5`); no committed run JSON yet |
| `openrouter` | supported | example in README (`openai/gpt-4o-mini`); no committed run JSON yet |

## Models with real results under `results/`

Ollama tags seen in saved runs (basename of `run_ollama_*`):

| model | corpora / arms seen | notes |
|---|---|---|
| `granite3.3:8b` | clean, hard, absent, **anchor2** (incl. fewshot) | reef sweep on `questions_anchor2`; fewshot lifts coverage when base returns descriptions |
| `mistral:7b` | clean, hard, absent, **anchor2** | reef `questions_anchor2` |
| `qwen2.5-coder:7b` | clean, hard, absent, **anchor2** | reef `questions_anchor2` |
| `qwen2.5:14b` | clean, hard, absent | comparison history |
| `gemma4:latest` / `gemma4:12b` | clean, hard, absent | comparison history |
| `gpt-oss:20b` | clean | energy/profile write-ups |
| `hermes3:8b` | hard, absent | recent local sweeps |
| `deepseek-r1:8b` | hard, absent | recent local sweeps |
| `qwen3.5:9b` | hard | sparse |

Mock profiles with saved runs: `faithful`, `sloppy`, `chaotic` (including
`questions_anchor2` / dual-anchor filenames).

Cross-model tables: [`results/comparison.md`](../results/comparison.md),
[`results/comparison_anchor2.md`](../results/comparison_anchor2.md). Published
52-model sweep + energy: [swamplink.com/data/trust](https://swamplink.com/data/trust/).

## Caveats

- **`OLLAMA_NUM_CTX`** — harness default context is 8192. Docs that might not
  fit are refused up front; Ollama truncates silently if you bypass that, and
  truncation looks like a quoting failure.
- **`OLLAMA_HOST`** — must include the scheme, e.g.
  `export OLLAMA_HOST=http://localhost:11434` (not a bare host:port).
- **Rate limits / spend** — Anthropic and OpenRouter are pay-per-token; use
  `--limit`, `--docs`, or `--arm` when iterating. Local Ollama avoids API
  quotas but still ties up GPU/CPU for long sweeps.
- **Illustrative ≠ validated** — README one-liners for Anthropic/OpenRouter
  show how to invoke the provider; treat them as templates until a run JSON
  lands in `results/`.
