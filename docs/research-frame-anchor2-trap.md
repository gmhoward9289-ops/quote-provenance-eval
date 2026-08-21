# Research frame: dual-anchor (anchor2) vs single-anchor on repeated-anchor trap

**Status:** outline / FRAME only — not a finished blog post.  
**Hardware:** reef RTX 4080 SUPER · Ollama · models on `Z:\ollama\models`

---

## 1. Working title options

1. Dual-Anchor Beats the Repeated-Document Trap (on Weak Local Models)
2. When Documents Repeat, Single-Anchor Coverage Collapses — Dual-Anchor and Fewshot Recover
3. Anchor2: Do You Need a Second Anchor, or Just a Stronger Model?

---

## 2. One-sentence thesis

Weak local models lose provenance coverage when the same anchor document is repeated in-context; dual-anchor (anchor2) or fewshot recovers that coverage on this synthetic trap, while stronger 7B-class models already hit ceiling without dual-anchor.

---

## 3. Motivation / problem

- Provenance systems that “trust but anchor” must still name which document a claim came from.
- A natural failure mode: the same document (or near-duplicate) appears more than once in the retrieved set — a **repeated-anchor trap**.
- Single-anchor prompting may under-specify which occurrence or which doc-id to report when repetition confuses a weak model.
- Dual-anchor (anchor2) and fewshot are candidate mitigations; we need a clean comparison on a controlled corpus before claiming product impact.

---

## 4. Method

### Arms

| Arm | Prompting |
| --- | --- |
| Single-anchor | One anchor instruction / format |
| Dual-anchor (anchor2) | Two-anchor instruction / format |
| Fewshot (granite) | Same model with fewshot exemplars (both single- and dual-anchor arms) |

### Corpus

- `questions_anchor2.json` + `repeated_anchor_trap.txt`
- Designed so documents **repeat** in context (synthetic trap)
- Expanded set: **15 questions** (early exploratory runs used **5**)

### Models (verified here)

- `granite3.3:8b` — primary “weak / sensitive” comparison
- `mistral:7b`, `qwen2.5-coder:7b` — stronger ceiling check (n=15)

### Metrics

- **Coverage** (%) of questions where the run correctly surfaces / binds the expected anchor(s)
- Report **n** next to every percentage; prefer n=45 granite runs over n=15 when both exist
- Note: morning dual-anchor **summaries were empty** due to a `summarize()` bug (fixed); dual-anchor rates below are **rescored from rows**, not from those empty summaries

---

## 5. Results table

| Model | Arm | Coverage | n | Notes |
| --- | --- | --- | ---: | --- |
| granite3.3:8b | single-anchor | ~40% | 15 | early expanded corpus |
| granite3.3:8b | single-anchor | ~93% | 45 | larger run — **sample-size caveat** vs 40% |
| granite3.3:8b | dual-anchor | 80% | 15 | rescored from rows |
| granite3.3:8b | dual-anchor | 100% | 45 | rescored from rows |
| granite3.3:8b | fewshot (both arms) | 100% | 45 | single- and dual-anchor |
| mistral:7b | single-anchor | 100% | 15 | |
| mistral:7b | dual-anchor | 100% | 15 | |
| qwen2.5-coder:7b | single-anchor | 100% | 15 | |
| qwen2.5-coder:7b | dual-anchor | 100% | 15 | |

---

## 6. Interpretation

- On this trap, **granite single-anchor is brittle** at small n (~40% @ n=15); a larger run jumps to ~93% @ n=45 — treat the gap as a **sample-size / variance caveat**, not a second independent claim.
- **Dual-anchor lifts granite** (80% → 100% as n grows from 15 → 45) and reaches full coverage at n=45.
- **Fewshot alone is enough for granite** on both arms (100% @ n=45) — dual-anchor is not the only recovery path.
- **mistral:7b and qwen2.5-coder:7b already at 100%** single- and dual-anchor @ n=15 — stronger models may not need dual-anchor on this synthetic trap.
- Framing claim (working): weak models fail when documents repeat; dual-anchor **or** fewshot recovers; stronger models may not need dual-anchor here.

---

## 7. Limitations / what NOT to claim yet

- Do **not** claim production RAG benefit — corpus is a **synthetic** repeated-anchor trap.
- Do **not** collapse ~40% (n=15) and ~93% (n=45) into one “single-anchor fails” headline without the sample-size caveat.
- Do **not** claim dual-anchor is strictly better than fewshot (both hit 100% on granite @ n=45).
- Do **not** claim mistral/qwen “need no dual-anchor” beyond this trap and n=15.
- Empty morning dual-anchor summaries were a **scoring bug**, not model failure — always cite rescored-from-rows figures.
- No cost / latency / token comparison yet.
- No head-to-head with a dedicated **quote** arm in this frame’s verified numbers.

---

## 8. Follow-up experiments

1. **Real documents** — repeated citations / duplicate chunks from authentic corpora (not trap text).
2. **More models** — other local 3B–14B sizes; confirm who is “weak” vs ceiling.
3. **Quote-arm comparison** — single-anchor vs dual-anchor vs quote-extraction arm on the same trap + real docs.
4. **Stabilize n** — fix protocol at n≥45 (or power analysis) before publishing granite single-anchor rates.
5. **Ablations** — fewshot count / exemplar content vs dual-anchor wording; interaction of fewshot + dual-anchor.
6. **Failure taxonomy** — when single-anchor misses, is it wrong doc-id, empty answer, or confused duplicate?

---

## 9. Artifacts paths

- Frame (this file): `docs/research-frame-anchor2-trap.md`
- Human comparison writeup: `docs/comparison.md` (or nearest sibling comparison note under `docs/`)
- Corpus: `questions_anchor2.json`, `repeated_anchor_trap.txt` (repo data / eval fixtures)
- Run JSON pattern (typical): `runs/**/anchor2*.json`, `runs/**/*granite*`, `runs/**/*mistral*`, `runs/**/*qwen*` — prefer dated run dirs with arm + model in the filename
- Rescored dual-anchor: prefer row-level result files over any pre-fix summary JSON from the morning bug window

*(Adjust glob to the repo’s actual `runs/` layout when linking from the blog.)*

---

## 10. Draft outline — blog + trust page (H2/H3 only)

### Blog

## The repeated-anchor trap
### Why duplicate documents break weak provenance prompts
## What we tested
### Arms: single-anchor, dual-anchor, fewshot
### Corpus: questions_anchor2 / repeated_anchor_trap
### Hardware: reef · Ollama · Z:\ollama\models
## Results
### granite3.3:8b — coverage by arm and n
### mistral:7b and qwen2.5-coder:7b — ceiling on this trap
## What it means
### Weak models need help; stronger models may not
### Dual-anchor and fewshot as alternate recoveries
## What we are not claiming
### Synthetic trap, sample-size caveats, scoring bug
## Next
### Real docs, more models, quote-arm

### Trust page

## Provenance under document repetition
### Evaluation setup
### Coverage table
### Model sensitivity
### Limits of this evidence
### Links to run artifacts
