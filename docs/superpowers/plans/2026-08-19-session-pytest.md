# Session → pytest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pytest plugin that turns a recorded agent session (JSONL or henhouse JSON) into deterministic tool-call assertions. No LLM in CI.

**Architecture:** New repo `C:\Users\gmhow\dev\pytest-session-trace`. Depends on `henhouse` for parsing. Plugin provides a fixture and assertion helpers. Optional CLI writes a starter test file from a transcript (copy-pasteable, not a daemon). Optional extra `[anchor]` uses `trust_but_anchor.locate` when a tool argument claims a quote from a source file.

**Tech Stack:** Python 3.10+, pytest plugin (`pytest11` entry point), henhouse, hatchling.

## Global Constraints

- Depends on henhouse v1 (`iter_tool_calls`, `read_tail`, `ToolCall`). Do not re-parse JSONL here.
- No LLM, no network, no MCP SDK.
- Do not generate unbounded test files in-repo during CI of *this* package; the CLI is opt-in for users.
- Plugin package name: `pytest-session-trace`. Import package: `session_trace`.
- License Apache-2.0.

---

### File map (locked)

- Create: `src/session_trace/__init__.py`
- Create: `src/session_trace/plugin.py` — pytest hook + fixtures
- Create: `src/session_trace/assert_tools.py` — `assert_tool_called`, `assert_tool_order`, `assert_no_tool`, `assert_write_path`
- Create: `src/session_trace/codegen.py` — `render_test(calls) -> str`
- Create: `src/session_trace/__main__.py` — `python -m session_trace path.jsonl > test_session.py`
- Create: `tests/test_assert_tools.py`, `tests/test_plugin.py`, `tests/test_codegen.py`
- Create: `pyproject.toml` with

```toml
[project.entry-points.pytest11]
session_trace = "session_trace.plugin"
```

---

### Task 1: Assertion helpers on `list[ToolCall]`

**Files:**
- Create: `src/session_trace/assert_tools.py`
- Test: `tests/test_assert_tools.py`

**Interfaces:**
- Consumes: `henhouse.types.ToolCall`
- Produces:

```python
def assert_tool_called(calls: list, name: str) -> None: ...
def assert_no_tool(calls: list, name: str) -> None: ...
def assert_tool_order(calls: list, names: list[str]) -> None:
    """names is a subsequence of [c.name for c in calls], not necessarily adjacent."""
def assert_write_path(calls: list, path_suffix: str) -> None:
    """A Write/Edit tool_use input.file_path endswith path_suffix."""
```

- [ ] **Step 1: Failing tests**

```python
import pytest
from henhouse.types import ToolCall
from session_trace.assert_tools import (
    assert_tool_called, assert_no_tool, assert_tool_order, assert_write_path,
)

def _calls():
    return [
        ToolCall(name="Read", input={"file_path": "a.py"}),
        ToolCall(name="Write", input={"file_path": "src/foo.py"}),
        ToolCall(name="Bash", input={"command": "pytest"}),
    ]

def test_called():
    assert_tool_called(_calls(), "Write")

def test_not_called():
    with pytest.raises(AssertionError):
        assert_tool_called(_calls(), "NotebookEdit")

def test_order_subsequence():
    assert_tool_order(_calls(), ["Read", "Bash"])

def test_write_path():
    assert_write_path(_calls(), "foo.py")
```

- [ ] **Step 2: Run FAIL**

- [ ] **Step 3: Implement helpers** — `AssertionError` messages must include the actual name list.

- [ ] **Step 4: PASS + commit** `feat: tool-call assertions`

---

### Task 2: pytest fixture `session_trace`

**Files:**
- Create: `src/session_trace/plugin.py`
- Test: `tests/test_plugin.py`

**Interfaces:**
- Consumes: `henhouse.transcripts.read_tail`, `iter_tool_calls`
- Produces: fixture `session_trace` that reads path from `--session-trace` option or env `SESSION_TRACE`

```python
# plugin.py
import os
from pathlib import Path
import pytest
from henhouse.transcripts import iter_tool_calls, read_tail

def pytest_addoption(parser):
    parser.addoption("--session-trace", action="store", default=None)

@pytest.fixture
def session_trace(request):
    path = request.config.getoption("--session-trace") or os.environ.get("SESSION_TRACE")
    if not path:
        pytest.skip("no --session-trace / SESSION_TRACE")
    p = Path(path)
    records = read_tail(p, tail_bytes=p.stat().st_size)  # whole file in tests
    return iter_tool_calls(records, session_id=p.stem, is_subagent=p.name.startswith("agent-"))
```

- [ ] **Step 1: Write a tiny JSONL fixture file under `tests/fixtures/one_write.jsonl`**

One line, Claude-shaped assistant record with a Write tool_use (same shape as leghorn tests).

- [ ] **Step 2: Test via `testdir` or `pytest.main`:**

```python
def test_plugin_loads_fixture(pytester):
    pytester.makepyfile("""
        def test_wrote(session_trace):
            from session_trace.assert_tools import assert_tool_called
            assert_tool_called(session_trace, "Write")
    """)
    result = pytester.runpytest("--session-trace", str(FIXTURE), "-q")
    result.assert_outcomes(passed=1)
```

`FIXTURE` is `Path(__file__).parent / "fixtures" / "one_write.jsonl"`.

- [ ] **Step 3: Implement plugin + entry point in pyproject.toml**

- [ ] **Step 4: PASS + commit** `feat: pytest plugin session_trace fixture`

---

### Task 3: Codegen CLI

**Files:**
- Create: `src/session_trace/codegen.py`, `src/session_trace/__main__.py`
- Test: `tests/test_codegen.py`

**Interfaces:**
- Produces a string that is valid pytest source:

```python
def render_test(calls, test_name: str = "test_session") -> str:
    names = [c.name for c in calls]
    return (
        "from session_trace.assert_tools import assert_tool_order, assert_tool_called\n\n"
        f"def {test_name}(session_trace):\n"
        f"    assert_tool_order(session_trace, {names!r})\n"
    )
```

- [ ] **Step 1: Test `render_test` contains `assert_tool_order` and is `compile()`-able**

- [ ] **Step 2: `__main__.py` reads a JSONL path, prints the test, exit 0**

- [ ] **Step 3: Commit** `feat: emit a starter pytest file from a transcript`

---

### Task 4: Optional anchor extra (after trust-but-anchor is installable)

**Files:**
- Create: `src/session_trace/assert_anchor.py`
- Test: `tests/test_assert_anchor.py`

**Interfaces:**
- Consumes: `trust_but_anchor.locate`
- Produces: `assert_arg_anchored(source_text: str, quoted: str) -> None` which fails if `locate(source_text, quoted)["method"] == "not_found"`

pyproject extra: `anchor = ["trust-but-anchor"]`

Skip this task if plan 1 is not on PyPI yet — implement against a path install: `pip install -e ../quote-provenance-eval`.

- [ ] **Step 1–4:** TDD as above. Commit `feat: optional quote anchoring on tool arguments`

---

### Task 5: README + CI + link from henhouse/roost/leghorn

README: one example test, `--session-trace`, “no LLM”. Link henhouse. Mention roost/leghorn as recorders.

CI: pytest 3.10/3.12/3.13.

Add a sentence to henhouse README “Used by pytest-session-trace”.

---

## Self-review

- Does not duplicate JSONL parsing.
- Fixture skip when no path given (so the plugin can be installed globally without breaking unrelated suites).
- Codegen is a starter, not a required CI step for this repo.
