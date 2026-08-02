# Quote-Provenance Eval

**Question:** when you ask an LLM to justify an extracted value with a *verbatim* quote from the source, how often is the quote actually verbatim — and does "model proposes, code anchors" beat trusting the model's quotes?

**Design:** two arms over the same 30 questions across 6 documents.

- **Quote arm** — the model returns `{answer, quote}` and is told the quote must be copied character-for-character. The quote is scored against the source document:
  - `exact` — character-for-character substring of the source (the only level a naive string-match verifier accepts; this is the headline rate)
  - `normalized` — matches after unicode/whitespace/case normalization (curly quotes, en dashes, NBSP, collapsed spaces)
  - `minor_edit` — fuzzy ratio ≥ 0.90 (a few words changed or dropped)
  - `paraphrase` — fuzzy ratio ≥ 0.70 (derived, but not a quote)
  - `fabricated` — below 0.70 (no plausible source span)
- **Anchor arm** — the model returns `{answer, anchor}` where the anchor is a short phrase (3–8 words) near the value. Deterministic code (`anchor.py`) locates the anchor in the source (exact → normalized → ordered-token subsequence → fuzzy; the subsequence step catches anchors where the model skipped a parenthetical or aside) and emits the containing sentence *from the source text*. Every emitted span is a real substring of the document by construction — provenance fidelity is 100% for anything located. The metric that can fail is **coverage**: anchor located AND located sentence contains the expected value. Fabricated anchors fail closed (`not_found`) instead of producing fake provenance.

The comparison that matters: **quote-arm exact rate** vs **anchor-arm coverage**.

## Quickstart (no API key needed)

```bash
python3 eval.py run --provider mock --model sloppy --verbose
```

The mock provider simulates a model with controllable sloppiness (`faithful`, `sloppy`, `chaotic`) so you can verify the whole pipeline. Example output from the three profiles:

| provider | model | quote exact | +normalized | fabricated | anchor located | anchor coverage |
|---|---|---|---|---|---|---|
| mock | faithful | 93% | 100% | 0% | 100% | 100% |
| mock | sloppy | 80% | 87% | 3% | 93% | 90% |
| mock | chaotic | 37% | 60% | 13% | 97% | 93% |

Even the chaotic profile recovers 93% coverage through anchoring — that's the whole argument in one row.

## Running against real models

Everything is stdlib-only Python 3.10+; nothing to install.

```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 eval.py run --provider anthropic --model claude-sonnet-4-5 --verbose

# Ollama (local, free — good for iterating)
python3 eval.py run --provider ollama --model llama3.1:8b --verbose
# non-default host: export OLLAMA_HOST=http://localhost:11434

# OpenRouter (one key, many models — good for the cross-model table)
export OPENROUTER_API_KEY=sk-or-...
python3 eval.py run --provider openrouter --model openai/gpt-4o-mini --verbose
```

Useful flags: `--arm quote|anchor|both` (default both), `--limit N` for a cheap smoke test.

Each run writes `results/run_<provider>_<model>_<stamp>.json` (full raw responses included, so you can re-inspect anything) and a per-question `.csv`. Build the cross-model table with:

```bash
python3 eval.py report results/run_*.json     # writes results/comparison.md
```

## The corpus

Six synthetic documents in `corpus/docs/` — synthetic so ground truth is exact by construction, and salted with realistic quoting traps:

- `quarterly_report.txt` — dense financial figures ($148.7 million, $0.42/share)
- `clinical_trial.txt` — stats with parentheticals and CIs (-11.4 mm Hg; 95% CI, -13.7 to -9.1)
- `news_article.txt` — nested quotes, en-dash vote tallies (6–3)
- `incident_postmortem.txt` — timestamps, version strings (rl-2.14.0)
- `victorian_essay.txt` — long clause-heavy sentences, em dashes, semicolons
- `messy_memo.txt` — double spaces, typos, curly apostrophes, en dashes, NBSP — the normalization gauntlet

`corpus/questions.json` has 30 questions with ground-truth spans. Run `python3 validate_corpus.py` after any edit — it verifies every ground-truth quote is an exact, unique substring of its document (eat your own dog food: never trust an unverified span, including mine).

To grow the eval: add a `.txt` to `corpus/docs/`, add question entries, re-run the validator. More docs and more question styles (multi-hop, ambiguous, value-absent) make the numbers more publishable.

## Interpreting results / writing it up

- The headline gap is `quote_exact_rate` vs `anchor_coverage`. If you want one sentence: *"Told to quote verbatim, the model produced an exactly-verifiable quote X% of the time; letting code locate a model-supplied anchor yielded verified source spans Y% of the time, and every emitted span is guaranteed to exist in the source."*
- The failure taxonomy (`quote_levels`) is the interesting middle of a write-up: how much is trivial normalization loss vs real paraphrase vs outright fabrication.
- Report medians over ≥3 runs per model if you publish numbers; temperature is 0 but providers aren't perfectly deterministic.
- Caveats to state honestly: 30 questions is a pilot, docs are short (single-context), synthetic docs may be easier to quote than scanned/OCR'd real-world text, and thresholds (0.90/0.70) are judgment calls — they're in `scoring.py`, tune and disclose.

## Files

```
eval.py             CLI: run + report
providers.py        anthropic / openrouter / ollama backends (stdlib HTTP)
mock.py             keyless simulated model with corruption profiles
scoring.py          quote-fidelity scoring + normalization
anchor.py           deterministic anchor location + sentence expansion
validate_corpus.py  ground-truth integrity check
rescore.py          re-score saved runs offline from stored raw responses
                    (no model calls) after improving locator/checker code
corpus/             documents + questions
results/            run outputs (JSON + CSV) and comparison.md
```
