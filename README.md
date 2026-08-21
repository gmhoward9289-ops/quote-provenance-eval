# Trust, But Anchor

[![ci](https://github.com/gmhoward9289-ops/trust-but-anchor/actions/workflows/ci.yml/badge.svg)](https://github.com/gmhoward9289-ops/trust-but-anchor/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/trust-but-anchor)](https://pypi.org/project/trust-but-anchor/)
[![Discussions](https://img.shields.io/github/discussions/gmhoward9289-ops/trust-but-anchor)](https://github.com/gmhoward9289-ops/trust-but-anchor/discussions)

[Discussions](https://github.com/gmhoward9289-ops/trust-but-anchor/discussions) — questions, ideas, and what you find when you run the harness. Bugs go in Issues.

**On adversarial documents, models produce a character-for-character verbatim quote only 64–73% of the time — even when explicitly told to.** Letting code locate a short model-proposed anchor phrase instead recovers 91–100% coverage, with every emitted span guaranteed to be a real substring of the source. That's the whole argument: don't trust the model's quote — trust its anchor, and verify the anchor in code.

**52 local models measured**, and only 11 clear a usable bar — ≥95% verified coverage *and* a perfect record of refusing when the requested value is absent. Published results, including what each model costs in energy per 100 extractions: **[swamplink.com/data/trust](https://www.swamplink.com/data/trust/)**.

**Question:** when you ask an LLM to justify an extracted value with a *verbatim* quote from the source, how often is the quote actually verbatim — and does "model proposes, code anchors" beat trusting the model's quotes?

**Design:** two arms over the same 30 questions across 6 documents.

- **Quote arm** — the model returns `{answer, quote}` and is told the quote must be copied character-for-character. The quote is scored against the source document:
  - `exact` — character-for-character substring of the source (the only level a naive string-match verifier accepts; this is the headline rate)
  - `normalized` — matches after unicode/whitespace/case normalization (curly quotes, en dashes, NBSP, collapsed spaces)
  - `minor_edit` — fuzzy ratio ≥ 0.90 (a few words changed or dropped)
  - `paraphrase` — fuzzy ratio ≥ 0.70 (derived, but not a quote)
  - `fabricated` — below 0.70 (no plausible source span)
- **Anchor arm** — the model returns `{answer, anchor}` where the anchor is a short phrase (3–8 words) near the value. Deterministic code (`anchor.py`) locates the anchor in the source (exact → normalized → ordered-token subsequence → fuzzy; the subsequence step catches anchors where the model skipped a parenthetical or aside) and emits the containing sentence *from the source text*. Every emitted span is a real substring of the document by construction — provenance fidelity is 100% for anything located. The metric that can fail is **coverage**: anchor located AND located sentence contains the expected value. Fabricated anchors fail closed (`not_found`) instead of producing fake provenance.

The comparison that matters: **quote-arm coverage** vs **anchor-arm coverage**. Both are held to the same bar: the emitted span must be verifiably real *and* contain the expected value. (`quote_coverage` = exact quote AND value present; in every run so far it equals the raw exact rate — models that quote exactly quote the right sentence — but the harness checks rather than assumes.)

## Library (no model required)

```bash
pip install trust-but-anchor
```

```python
from trust_but_anchor import locate, analyze, score

doc = open("source.txt", encoding="utf-8").read()
hit = locate(doc, "working set")
if hit["method"] == "not_found":
    raise SystemExit("no provenance")
print(hit["sentence"])  # exact substring of doc
print(score(hit))
print(analyze(doc, prompt="Return NOT_FOUND if absent.", num_ctx=8192))
```

The eval harness below measures *your* models on *your* docs. The library does not need that table to be useful. Published numbers live at [swamplink.com/data/trust](https://www.swamplink.com/data/trust/).

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

Results are not collected or ranked here: run the harness against your own models, prompts and documents, because that is the only measurement that describes your system. The published numbers are our own runs on our own hardware, and they are reproducible from the stored responses rather than submitted. [Discussions](https://github.com/gmhoward9289-ops/trust-but-anchor/discussions) is open for questions and for what you find.

Everything is stdlib-only Python 3.10+ for the eval harness; the library is `pip install trust-but-anchor`.

```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 eval.py run --provider anthropic --model claude-sonnet-4-5 --verbose

# Ollama (local, free — good for iterating)
python3 eval.py run --provider ollama --model llama3.1:8b --verbose
# non-default host: export OLLAMA_HOST=http://localhost:11434
# context window: pinned via OLLAMA_NUM_CTX (default 8192). The harness
# estimates prompt size and refuses to run a doc that might not fit —
# Ollama truncates silently, and a truncation failure would masquerade as
# a quoting failure.

# OpenRouter (one key, many models — good for the cross-model table)
export OPENROUTER_API_KEY=sk-or-...
python3 eval.py run --provider openrouter --model openai/gpt-4o-mini --verbose
```

Useful flags: `--arm quote|anchor|anchor2|both` (default both), `--variant base|fewshot|refusal`, `--limit N` for a cheap smoke test, `--repeats N` to run the whole set N times (the summary pools across repeats, reports 95% Wilson intervals in `ci95`, and adds a `per_rep` breakdown of the headline rates — publish with `--repeats 3` or more).

### When anchors won't locate (`--variant fewshot`)

Some open-weight models return *descriptions* of the value (`"net income per diluted share in Q3 2025"`) instead of text copied from the document. The base prompt already says "copied"; for those models, add a worked example:

```bash
python3 eval.py run --provider ollama --model granite3.3:8b --variant fewshot --verbose
```

In our runs this took `granite3.3:8b` from **53% → 90%** verified coverage and eliminated all unlocatable anchors; models already at ceiling (97–100%) did not move. Try fewshot before concluding a model cannot anchor.

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

`corpus/questions_absent.json` has 10 **value-absent** questions (`--questions corpus/questions_absent.json`): the document does not contain the requested value, and both system prompts permit an explicit `NOT_FOUND` refusal. The right behavior is refusing; the dangerous failure is a confident invented answer backed by a real-looking span (an exact quote or a located anchor of irrelevant text). The summary reports `*_absent_refusal_rate` and counts of `confident_with_*_span` — fabrication under pressure, measured directly. These rows are excluded from the main coverage rates.

`corpus/questions_anchor2.json` exercises **dual-anchor disambiguation** (`--arm anchor2`): repeated phrases where the first occurrence lacks the expected value (`repeated_anchor_trap.txt`, 15 questions). Blind `locate()` takes the first match and misses; `locate_pair()` should recover when the model supplies a second nearby phrase.

To grow the eval: add a `.txt` to `corpus/docs/`, add question entries, re-run the validator. More docs and more question styles (multi-hop, ambiguous) make the numbers more publishable.

## Interpreting results / writing it up

- The headline gap is `quote_coverage` vs `anchor_coverage` (symmetric: both require a real span containing the expected value). If you want one sentence: *"Told to quote verbatim, the model produced an exactly-verifiable quote X% of the time; letting code locate a model-supplied anchor yielded verified source spans Y% of the time, and every emitted span is guaranteed to exist in the source."*
- The failure taxonomy (`quote_levels`) is the interesting middle of a write-up: how much is trivial normalization loss vs real paraphrase vs outright fabrication.
- Publish with `--repeats 3` or more; temperature is 0 but providers aren't perfectly deterministic. The summary's `ci95` Wilson intervals are the honest error bars for a 30-question pilot — at n=30, an 80% rate carries a ±14-point interval, so don't read single-digit gaps as real.
- All rates are intent-to-treat: a response that arrived but couldn't be parsed counts against the arm (`unparseable` in `quote_levels` / `anchor_methods`) rather than silently dropping out of the denominator. Only provider/network errors (`n_provider_errors`) are excluded from rates.
- `anchor_ambiguous` counts located anchors whose matched span occurs more than once in the (normalized) document — the locator takes the first occurrence, so a value-miss on an ambiguous anchor may be "right anchor, wrong occurrence," not a bad anchor. On documents with heavy internal repetition (quoted-reply email threads, repeated OCR page footers) most anchors are ambiguous; that's a property of the document, and a production locator would want a disambiguation strategy (e.g. require the model to add a second nearby phrase).
- Caveats to state honestly: 30 questions is a pilot, docs are short (single-context), synthetic docs may be easier to quote than scanned/OCR'd real-world text, and thresholds (0.90/0.70) are judgment calls — they're in `scoring.py`, tune and disclose. Value matching (`values_match`) allows benign formatting drift (currency symbols, digit-group commas, number words) and falls back to requiring the expected value's numeric tokens to appear whole and in order — also a judgment call, also in `scoring.py`.

## Predicting failures before you spend a token (`preflight.py`)

Most of what the eval measured after the fact was visible in the document and
the prompt beforehand. `preflight.py` checks for it deterministically — no
model call, no API key:

```bash
python3 preflight.py corpus/docs/*.txt --prompt=my_prompt.txt --num-ctx=8192
```

It reports anchor-ambiguity risk, verbatim-quote hazards (curly quotes, NBSP,
en dashes), prompt-shape problems (no `NOT_FOUND` path, answer and evidence not
separated), and context-overflow risk, each with the concrete fix. Exit code 1
if anything is high-risk, so it works as a CI gate.

The ambiguity metric is calibrated against this repo's own runs rather than
intuition, and the naive version was wrong: whole-document repetition
overpredicts badly. `hard_transcript.txt` repeats 54% of its 5-grams
(conversational filler) yet not one located anchor across 31 runs was
ambiguous — models anchor *near the value*, and value-adjacent text stays
distinctive even in chatty prose. Restricting the count to value-adjacent
n-grams tracks measurement: email thread 75% predicted / 100% measured,
transcript 0% / 0%, annual report 7% / 0%.

## Confidence earned from verification (`confidence.py`)

Asking a model how sure it is returns a number it invented. `confidence.score()`
scores an extraction from what code could confirm — how the anchor was located,
whether that location is unique, whether the span carries the value — and emits
**two** numbers, because the runs show they are different questions:

- `answer_confidence` — will the answer turn out to be right?
- `provenance_confidence` — is the emitted span trustworthy *as evidence*?

An ambiguous exact anchor (phrase occurs more than once, locator silently took
the first) still produced a correct answer 24/24 times. Ambiguity damages the
citation, not the answer. Likewise a located span that lacks the expected value
was still correct 22/22 — the anchor landed a sentence away, a coverage miss
rather than a hallucination. One blended number would hide both.

Priors are measured, not assumed (exact 98% n=1107, normalized 98% n=134, fuzzy
95% n=42, `not_found` 3% n=155 — it fails closed). Re-derive them on your own
data whenever the locator, corpus or model lineup changes:

```bash
python3 confidence.py --calibrate
```

They describe local open-weight models on short synthetic documents. Treat them
as a starting prior, not a universal constant.

## Quality against energy (`nightrun.py`, `profiles.py`)

`nightrun.py` sweeps a list of models unattended, recording throughput (from
Ollama's own `eval_count`/`eval_duration`), GPU residency (from `/api/ps`, never
inferred from `ollama ls`), and sampled GPU power alongside the three corpora.
`profiles.py` joins that with the quality numbers:

```bash
python3 profiles.py "results/run_*.json" results/power_metrics.jsonl
```

Energy is reported as **Wh per 100 extractions**, not per 1k tokens: tokens are
an implementation detail of the model, extractions are what a user buys, and
per-token accounting flatters a reasoning model that burns 40x the tokens to
answer the same question. Power comes from the eval phase, not a short bench —
a few seconds of sampling while the GPU ramps produced a 47–193 W spread on
identical work, which is noise.

Why it matters, from the first three models measured on a 16 GB RTX 4080 SUPER:
`gpt-oss:20b` leads on quality (99% anchor coverage) while drawing the *lowest*
sustained power of the three (77 W vs ~154 W) — and still costs **9x more
energy per extraction** (36.3 vs 3.86 Wh/100), because it runs ~24x longer.
Ranking by watts would have called it the cheap one.

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
preflight.py        deterministic doc + prompt linting before inference
confidence.py       verification-earned confidence, calibrated from runs
nightrun.py         unattended multi-model sweep with power/throughput
profiles.py         quality x energy table (Wh per 100 extractions)
corpus/             documents + questions
results/            run outputs (JSON + CSV), comparison.md, profiles.md,
                    power_metrics.jsonl
```
