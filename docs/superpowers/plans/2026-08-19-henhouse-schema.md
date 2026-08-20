# henhouse session schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a stdlib-only package that turns Claude Code / Cursor JSONL into typed session and tool-call events, without making roost or leghorn take a pip dependency.

**Architecture:** New repo `C:\Users\gmhow\dev\henhouse` (package `henhouse`). Copy and split the transcript parser out of `leghorn/henhouse.py`. v1 is parse + JSON schema, not the TUI, not git-roost, not GitHub. roost and leghorn keep their current files; they add a `"schema": "henhouse.session.v1"` (or `henhouse.tools.v1`) field to `--json` and README links. pytest-session-trace (plan 3) imports this package.

**Tech Stack:** Python 3.10+, hatchling, pytest (dev), stdlib `json` / `dataclasses`. Apache-2.0 (from leghorn).

## Global Constraints

- Runtime: stdlib only. No `windows-curses`, no `mcp`, no network.
- Read-only. Never write a transcript, registry, or git tree.
- roost (`C:\Users\gmhow\dev\roost`) and leghorn (`C:\Users\gmhow\dev\leghorn`) stay 3.9-capable and dependency-free. They **link**; they do not `pip install henhouse` in v1.
- Do not put the curses dashboard in this package.
- `cost_usd` stays `None` on purpose (leghorn comment: subscription is not API list price). Do not invent money.
- Subagent JSONL (`agent-*.jsonl`) is a first-class event stream, not silently dropped — expose `iter_tool_calls` for both session and subagent files.

---

### File map (locked)

New repo `C:\Users\gmhow\dev\henhouse`:

- Create: `src/henhouse/__init__.py`
- Create: `src/henhouse/types.py` — `ToolCall`, `TranscriptSummary`, `SessionRecord`
- Create: `src/henhouse/transcripts.py` — `read_tail`, `summarize`, `iter_tool_calls`, `transcript_index` (ported from leghorn `henhouse.py` lines 108–228)
- Create: `src/henhouse/schema.py` — `SCHEMA_SESSION = "henhouse.session.v1"`, `SCHEMA_TOOLS = "henhouse.tools.v1"`
- Create: `tests/test_transcripts.py` (port `leghorn/tests/test_henhouse_transcripts.py` plus tool-call tests)
- Create: `pyproject.toml`, `README.md`, `LICENSE` (copy Apache-2.0 from leghorn), `.github/workflows/ci.yml`

Modify later (same PR series, different repos):

- `C:\Users\gmhow\dev\leghorn\README.md` — “data layer also published as henhouse”
- `C:\Users\gmhow\dev\roost\README.md` — `--json` schema note + link
- `C:\Users\gmhow\dev\leghorn\henhouse.py` `render()` JSON branch — wrap with `{"schema": "henhouse.session.v1", "rows": rows}` **only if** existing consumers are checked. Safer v1: add `"schema"` as a **key on a wrapper** behind `--json-schema` OR add `"schema"` alongside existing list. **Locked decision:** keep emitting a JSON **list** of rows (leghorn today). Add `"schema"` on each row as `"henhouse.session.v1"` would pollute rows. Instead emit:

```python
{"schema": "henhouse.session.v1", "rows": rows}
```

That **breaks** anyone piping `henhouse --json` as a list. roost `--json` is already an object with `workers`. **Locked:** henhouse CLI wrapper object; document the break in CHANGELOG. `python -m henhouse` in leghorn currently prints a list — add `--legacy-json` that prints the bare list.

---

### Task 1: Freeze the tool-call event type with tests (new repo)

Create the repo directory and git init only if George has not already. Prefer: `cd C:\Users\gmhow\dev && git clone` from GitHub after `gh repo create gmhoward9289-ops/henhouse --public --license apache-2.0`. If creating locally first, `git init` in `C:\Users\gmhow\dev\henhouse`.

**Files:**
- Create: `src/henhouse/types.py`
- Create: `tests/test_types.py`

**Interfaces:**
- Produces:

```python
# src/henhouse/types.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class ToolCall:
    name: str
    input: dict[str, Any]
    id: str | None = None
    session_id: str | None = None
    source: str = "claude"  # "claude" | "cursor"
    is_subagent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 1: Write failing test**

```python
from henhouse.types import ToolCall

def test_tool_call_roundtrip():
    tc = ToolCall(name="Write", input={"file_path": "a.py"}, id="t1", session_id="s1")
    d = tc.to_dict()
    assert d["name"] == "Write"
    assert d["input"]["file_path"] == "a.py"
    assert d["is_subagent"] is False
```

- [ ] **Step 2: Run — expect FAIL** (`No module named henhouse`)

Run: `cd C:\Users\gmhow\dev\henhouse && python -m pytest tests/test_types.py -v`

- [ ] **Step 3: Add `types.py` + empty `__init__.py` + `pyproject.toml`** (same hatchling pattern as trust-but-anchor, `name = "henhouse"` — if PyPI name is taken, use `henhouse-trace` and import stays `henhouse` via `packages`).

Check PyPI: `python -c "import urllib.request; print(urllib.request.urlopen('https://pypi.org/pypi/henhouse/json').status)"` — 404 means the name is free; 200 means use `henhouse-trace`.

- [ ] **Step 4: `pip install -e ".[dev]"` and re-run — PASS**

- [ ] **Step 5: Commit** `feat: add ToolCall type`

---

### Task 2: Port `read_tail` / `summarize` and add `iter_tool_calls`

**Files:**
- Create: `src/henhouse/transcripts.py`
- Create: `tests/test_transcripts.py`

**Interfaces:**
- Consumes: `ToolCall`
- Produces:

```python
def read_tail(path, tail_bytes: int = 256 * 1024) -> list[dict]:
    """Port of leghorn henhouse.read_tail — drop first line if seek landed mid-record."""

def summarize(records: list[dict], mtime: float) -> dict:
    """Port of leghorn henhouse.summarize. Keys: status, context_pct, model, burn_tokens, files_modified, cost_usd=None, active_subagents, estimate."""

def iter_tool_calls(records: list[dict], *, session_id: str | None = None, is_subagent: bool = False) -> list[ToolCall]:
    """Every assistant tool_use block, including Read. Order preserved."""
```

Copy the assistant record helper from `leghorn/tests/test_henhouse_transcripts.py` (`assistant()`, `USAGE`).

- [ ] **Step 1: Write tests** including:

```python
def test_iter_tool_calls_keeps_read_and_write():
    recs = [assistant(USAGE, tools=[("Read", "a.py"), ("Write", "b.py")])]
    calls = iter_tool_calls(recs, session_id="s")
    assert [c.name for c in calls] == ["Read", "Write"]


def test_context_is_last_turn_not_sum():
    # copy from leghorn tests/test_henhouse_transcripts.py::test_context_is_the_last_turn_not_the_sum
    ...
```

Port `assistant()` so `tools` can be a list of (name, path) as in leghorn.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Port implementation from `C:\Users\gmhow\dev\leghorn\henhouse.py`** (`read_tail`, `summarize`, `context_window`, `WRITE_TOOLS`). New `iter_tool_calls` walks `message.content` for `type == "tool_use"`.

- [ ] **Step 4: PASS + commit** `feat: parse transcript tails and tool_use lists`

---

### Task 3: Public exports, CLI, README, CI

**Files:**
- Modify: `src/henhouse/__init__.py`
- Create: `src/henhouse/__main__.py` — `python -m henhouse path.jsonl` prints `{"schema": "henhouse.tools.v1", "calls": [...]}`
- Create: `README.md` — one-file install, link roost + leghorn, “format can change; treat breakage as expected”
- Create: `.github/workflows/ci.yml` (3.10, 3.12, 3.13)

**Interfaces:**
- Produces: `from henhouse import iter_tool_calls, summarize, read_tail, ToolCall, SCHEMA_TOOLS`

- [ ] **Step 1: Test `__main__` on a temp JSONL of one assistant Write**

- [ ] **Step 2: Implement `__main__.py`**

- [ ] **Step 3: CI + README**

README must include:

```markdown
## Used by

- [leghorn](https://github.com/gmhoward9289-ops/leghorn) — live git/CI dashboard
- [roost](https://github.com/gmhoward9289-ops/roost) — `top` for sessions
- [pytest-session-trace](https://github.com/gmhoward9289-ops/pytest-session-trace) — CI assertions (plan 3)
```

- [ ] **Step 4: Commit** `feat: henhouse CLI and docs`

---

### Task 4: Link from roost and leghorn (no pip dep)

**Files:**
- Modify: `C:\Users\gmhow\dev\leghorn\README.md` (after install, a “Library” sentence pointing at henhouse)
- Modify: `C:\Users\gmhow\dev\leghorn\CLAUDE.md` — one line: transcript parsing source of truth is the henhouse package; this file remains the vendored copy until a later optional import
- Modify: `C:\Users\gmhow\dev\roost\README.md` — `--json` documents keys + link henhouse
- Modify: `C:\Users\gmhow\dev\leghorn\henhouse.py` `render()` when `--json`: emit wrapper object; `--legacy-json` keeps a bare list

- [ ] **Step 1: Add a leghorn test that `--json` includes `"schema": "henhouse.session.v1"`** (extend `tests/test_henhouse_*.py`)

- [ ] **Step 2: Implement wrapper; `--legacy-json` for the list**

- [ ] **Step 3: Commit in leghorn and roost separately** (`docs: link henhouse schema` / `feat: wrap --json with henhouse.session.v1`)

Do not `pip install henhouse` inside roost.

---

## Self-review

- Tool-call list is the missing piece summarize() currently throws away (only Write/Edit paths kept). Plan 3 needs Read/Bash/etc.
- roost/leghorn no-deps invariant preserved.
- Schema break for henhouse CLI JSON is explicit (`--legacy-json`).
