# Anchor library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing locator into an importable stdlib-only package without breaking `python3 eval.py`.

**Architecture:** Move `anchor.py`, `scoring.py`, `confidence.py`, and `preflight.py` under `src/trust_but_anchor/`. Leave thin shim modules at the repo root so `eval.py` / `rescore.py` / `validate_corpus.py` keep working. Public API is `locate`, `locate_pair`, `score` (confidence), `analyze` (preflight), `score_quote`, `normalize`. Eval harness, providers, nightrun, and corpus stay out of the installed wheel.

**Tech Stack:** Python 3.10+, hatchling, pytest (dev extra only), existing stdlib locator (`difflib`, `unicodedata`). No runtime dependencies.

## Global Constraints

- Runtime: stdlib only. `requires-python = ">=3.10"`.
- Do not change locate semantics. Same ladder: exact → normalized → subsequence → fuzzy → `not_found`.
- `locate` / `locate_pair` return dicts with the keys they already return (`method`, `span`, `sentence`, `occurrences`, optional `ratio` / `disambiguated` / `chose_occurrence`).
- Fail closed: empty or missing anchor → `{"method": "not_found"}`.
- Root shims must remain so `from scoring import normalize` and `from anchor import locate` still work for `eval.py`.
- Do not add nightrun, providers, or energy accounting to the package.
- Work in `C:\Users\gmhow\dev\trust-but-anchor`.
- License Apache-2.0 (`LICENSE` already in repo).
- Do not commit `.env` or API keys. `results/` stays gitignored as today.

---

### File map (locked)

- Create: `src/trust_but_anchor/__init__.py`
- Create: `src/trust_but_anchor/locate.py` (today’s `anchor.py`)
- Create: `src/trust_but_anchor/scoring.py` (today’s `scoring.py`)
- Create: `src/trust_but_anchor/confidence.py`
- Create: `src/trust_but_anchor/preflight.py`
- Create: `pyproject.toml`
- Create: `tests/test_locate.py`, `tests/test_scoring.py`, `tests/test_confidence.py`, `tests/test_preflight.py`, `tests/test_shims.py`
- Create: `.github/workflows/ci.yml`
- Modify: root `anchor.py`, `scoring.py`, `confidence.py`, `preflight.py` → re-export shims
- Modify: `README.md` — install + import above the eval quickstart
- Do not move: `eval.py`, `mock.py`, `providers.py`, `corpus/`, `nightrun*.py`

---

### Task 1: Pin current locate behaviour with tests (before moving files)

**Files:**
- Create: `tests/test_locate.py`
- Test: `tests/test_locate.py`

**Interfaces:**
- Consumes: `anchor.locate`, `anchor.locate_pair` (root modules, current layout)
- Produces: a failing-then-passing suite that later tasks must keep green after the move

- [ ] **Step 1: Write the failing tests** (they will fail only if pytest isn’t collecting; implementation already exists)

```python
# tests/test_locate.py
from __future__ import annotations

from anchor import locate, locate_pair


def test_exact_is_a_real_substring():
    doc = "Revenue was $148.7 million in Q3."
    out = locate(doc, "$148.7 million")
    assert out["method"] == "exact"
    assert out["span"] == "$148.7 million"
    assert out["span"] in doc
    assert out["sentence"] in doc
    assert out["occurrences"] >= 1


def test_curly_quotes_are_normalized_not_fabricated():
    doc = "He said \u201cthe protocol is live\u201d today."
    out = locate(doc, '"the protocol is live"')
    assert out["method"] in {"normalized", "exact"}
    assert out["span"] in doc


def test_empty_anchor_fails_closed():
    assert locate("hello world", "") == {"method": "not_found"}
    assert locate("hello world", "   ")["method"] == "not_found"


def test_unknown_phrase_fails_closed():
    assert locate("the cat sat on the mat", "quantum foam")["method"] == "not_found"


def test_subsequence_skips_parenthetical():
    doc = "Systolic blood pressure fell -11.4 mm Hg (95% CI, -13.7 to -9.1) by week 12."
    out = locate(doc, "fell -11.4 mm Hg by week 12")
    assert out["method"] in {"subsequence", "normalized", "fuzzy", "exact"}
    assert out["span"] in doc


def test_pair_disambiguates_repeated_anchor():
    doc = (
        "On Monday the total was 10.\n"
        "On Monday the total was 10.\n"
        "On Friday the total was 10, final."
    )
    out = locate_pair(doc, "the total was 10", "Friday")
    assert out["method"] in {"pair", "exact", "normalized"}
    assert "Friday" in out.get("sentence", "") or out.get("disambiguated") in {True, False}
```

- [ ] **Step 2: Run pytest on the new file**

Run: `cd C:\Users\gmhow\dev\trust-but-anchor && python -m pytest tests/test_locate.py -v`

Expected: PASS (locator already works). If pytest is missing: `python -m pip install pytest` in a venv, then re-run. Do not change `anchor.py` in this task.

- [ ] **Step 3: Commit**

```bash
git add tests/test_locate.py
git commit -m "test: pin locate() behaviour before packaging"
```

---

### Task 2: Pin scoring, confidence, and preflight

**Files:**
- Create: `tests/test_scoring.py`, `tests/test_confidence.py`, `tests/test_preflight.py`

**Interfaces:**
- Consumes: `scoring.score_quote`, `scoring.normalize`, `confidence.score`, `preflight.analyze`
- Produces: tests later tasks must keep green

- [ ] **Step 1: Write tests**

```python
# tests/test_scoring.py
from scoring import normalize, score_quote

def test_exact_quote():
    doc = "alpha beta gamma"
    assert score_quote(doc, "alpha beta")["level"] == "exact"

def test_empty_quote_is_fabricated():
    assert score_quote("abc", "")["level"] == "fabricated"

def test_normalize_collapses_nbsp_and_case():
    assert normalize("A\u00a0B") == normalize("a b")
```

```python
# tests/test_confidence.py
from anchor import locate
from confidence import score

def test_not_found_has_low_answer_confidence():
    loc = locate("hello", "nope")
    out = score(loc)
    assert loc["method"] == "not_found"
    assert out["answer_confidence"] < 0.1

def test_exact_unique_span_is_high_provenance():
    loc = locate("only once: 42.", "only once: 42")
    out = score(loc, value_in_span=True)
    assert loc["method"] == "exact"
    assert out["provenance_confidence"] >= 0.9
```

```python
# tests/test_preflight.py
from preflight import analyze

def test_analyze_returns_findings_and_reports():
    out = analyze("The value is 12. The value is 12.", prompt="Return NOT_FOUND if absent.")
    assert set(out) >= {"metrics", "findings", "risk"}
    assert isinstance(out["findings"], list)
    assert out["risk"] in {"high", "medium", "low"}
```

Inspect `preflight.analyze` return keys if the last test is too loose — pin the real keys from `analyze()` (`findings`, `repetition`, etc.) rather than `or` chains. Open `preflight.py` around `def analyze` and assert the actual dict keys.

- [ ] **Step 2: Run**

Run: `python -m pytest tests/test_scoring.py tests/test_confidence.py tests/test_preflight.py -v`

Expected: PASS. Tighten the preflight test to exact keys.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scoring.py tests/test_confidence.py tests/test_preflight.py
git commit -m "test: pin scoring, confidence, and preflight before the move"
```

---

### Task 3: Add the package layout and move modules

**Files:**
- Create: `src/trust_but_anchor/__init__.py`, `locate.py`, `scoring.py`, `confidence.py`, `preflight.py`
- Modify: root `anchor.py`, `scoring.py`, `confidence.py`, `preflight.py` into shims
- Create: `pyproject.toml`
- Test: `tests/test_shims.py`

**Interfaces:**
- Consumes: Task 1–2 tests
- Produces:

```python
# src/trust_but_anchor/__init__.py
from .locate import locate, locate_pair
from .scoring import normalize, score_quote
from .confidence import score
from .preflight import analyze

__all__ = [
    "locate",
    "locate_pair",
    "normalize",
    "score_quote",
    "score",
    "analyze",
]
```

Root shim example (`anchor.py` entire file after move):

```python
"""Shim — implementation lives in trust_but_anchor.locate."""
from trust_but_anchor.locate import locate, locate_pair  # noqa: F401
```

`locate.py` must import normalize from `.scoring`, not `from scoring import`.

- [ ] **Step 1: Write `tests/test_shims.py`**

```python
def test_package_and_shims_export_the_same_locate():
    import anchor
    import trust_but_anchor
    from trust_but_anchor import locate
    assert locate is trust_but_anchor.locate
    assert locate is anchor.locate
```

- [ ] **Step 2: Run test — expect FAIL** (`No module named trust_but_anchor`)

Run: `python -m pytest tests/test_shims.py -v`

- [ ] **Step 3: Add `pyproject.toml` and move files**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "trust-but-anchor"
version = "0.1.0"
description = "The model proposes a short anchor; code locates a real source span. Fail closed."
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
authors = [{ name = "George M. Howard", email = "dev@swamplink.com" }]
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.urls]
Homepage = "https://github.com/gmhoward9289-ops/trust-but-anchor"

[project.scripts]
tba-preflight = "trust_but_anchor.preflight:console_main"

[tool.hatch.build.targets.wheel]
packages = ["src/trust_but_anchor"]
```

If hatchling cannot find the package, set `packages = ["trust_but_anchor"]` and keep the code under `src/trust_but_anchor` with:

```toml
[tool.hatch.build.targets.wheel]
only-include = ["trust_but_anchor"]
```

Confirm `[project.urls]` points at `https://github.com/gmhoward9289-ops/trust-but-anchor` (done in pyproject.toml).

Move the four modules. Change internal imports:

- `locate.py`: `from .scoring import best_window_ratio, normalize` and `from .scoring import _PUNCT_MAP` where needed
- `preflight.py`: `from .scoring import _PUNCT_MAP, normalize`
- `confidence.py`: no locate import required if it only accepts the dict

Root shims as above. `eval.py` keeps `from anchor import locate`.

- [ ] **Step 4: Editable install and run the full suite**

Run:

```
cd C:\Users\gmhow\dev\trust-but-anchor
python -m pip install -e ".[dev]"
python -m pytest tests -v
python eval.py run --provider mock --model sloppy --limit 2
```

Expected: pytest PASS; mock eval still prints a table.

- [ ] **Step 5: Commit**

```bash
git add src tests pyproject.toml anchor.py scoring.py confidence.py preflight.py
git commit -m "feat: package locate/preflight/confidence as trust-but-anchor"
```

---

### Task 4: README, console script, CI

**Files:**
- Modify: `README.md`
- Create: `.github/workflows/ci.yml`
- Modify: `src/trust_but_anchor/preflight.py` so `main` is safe as a console script (`if __name__` already exists; ensure `tba-preflight` calls `main`)

- [ ] **Step 1: Add an install section at the top of README.md**, above the eval quickstart:

```markdown
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

The eval harness below measures *your* models on *your* docs. The library does not need that table to be useful.
```

Keep the existing eval sections. Link `https://www.swamplink.com/data/trust/`.

- [ ] **Step 2: CI workflow**

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main, master]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest -q
      - run: python eval.py run --provider mock --model sloppy --limit 3
```

- [ ] **Step 3: Run locally**

```
python -m pytest -q
tba-preflight --help
```

If `tba-preflight` needs argv, match `preflight.main` (it takes `argv: list[str]`). Wire:

```python
def console_main() -> None:
    raise SystemExit(main(sys.argv[1:]))
```

and set `tba-preflight = "trust_but_anchor.preflight:console_main"`.

- [ ] **Step 4: Commit**

```bash
git add README.md .github/workflows/ci.yml src/trust_but_anchor/preflight.py pyproject.toml
git commit -m "docs: install path for the library; add CI"
```

---

### Task 5: Publish dry-run (no upload unless George says so)

**Files:** none required beyond version tag later

- [ ] **Step 1: Build**

```
python -m pip install build
python -m build
```

Expected: `dist/trust_but_anchor-0.1.0-py3-none-any.whl` (or `trust-but-anchor`).

- [ ] **Step 2: Confirm the wheel does not contain `eval.py`, `providers.py`, or `results/`**

```
python -c "import zipfile; z=zipfile.ZipFile('dist/' + __import__('os').listdir('dist')[0]); print('\n'.join(z.namelist()))"
```

Expected: only `trust_but_anchor/*` and metadata.

- [ ] **Step 3: Stop.** Do not `twine upload` or tag a GitHub release until George asks. Report the wheel path.

---

## Self-review

- Spec coverage: locate + pair, shims, pyproject, tests, CI, README, wheel contents, no eval-in-wheel.
- No TBD left except the GitHub URL fork (explicit check, not a placeholder).
- Types: `locate` still returns `dict`; `score(locate: dict, ...)`; `analyze(doc, prompt="", num_ctx=8192)`.
