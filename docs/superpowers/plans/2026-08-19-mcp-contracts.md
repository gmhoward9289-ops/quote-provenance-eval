# MCP domain contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pytest plugin that asserts *our* MCP tools (names, schemas, snapshots, annotations). Not protocol conformance. Fourth in the stack; dogfood on swamp-ops.

**Architecture:** New repo `C:\Users\gmhow\dev\pytest-mcp-contract`. Plugin talks to whatever in-memory client the test supplies (factory fixture). swamp-ops already splits `tools.py` (no mcp import) from `server.py` (`MCPServer` from MCP Python SDK 2.x). Contracts test the **server registration** layer; logic stays in `test_tools.py`. Optional extras: henhouse (skip unless a test wants it), trust-but-anchor (assert a tool result quote locates in a fixture source).

**Tech Stack:** Python 3.10+, pytest, `mcp` SDK as extra `mcp`, hatchling. Apache-2.0.

## Global Constraints

- Do not wrap `npx @modelcontextprotocol/conformance`.
- Do not ship security payload packs or exploit strings.
- No LLM in CI.
- Do not import `mcp` inside swamp-ops `tools.py` (existing invariant in `tests/test_server.py`).
- Plugin works with SDK 2.x `MCPServer` (what swamp-ops uses today), not only FastMCP 1.x `Client`.
- In-memory only for v1. No stdio subprocess tests in v1 (Windows signal/pid issues documented in henhouse).

---

### File map (locked)

New repo `pytest-mcp-contract`:

- Create: `src/mcp_contract/__init__.py`
- Create: `src/mcp_contract/plugin.py`
- Create: `src/mcp_contract/assert_mcp.py` — `assert_tools_named`, `assert_tool_annotated_read_only`, `assert_call_equals`
- Create: `tests/test_assert_mcp.py`
- Create: `tests/fake_server.py` — tiny `MCPServer` with one `echo` tool for plugin tests
- Create: `pyproject.toml` entry point `pytest11` → `mcp_contract.plugin`

Modify swamp-ops:

- Create: `C:\Users\gmhow\dev\swamp-ops\tests\test_mcp_contract.py`
- Modify: `C:\Users\gmhow\dev\swamp-ops\requirements-dev.txt` — `pytest-mcp-contract` path extra

---

### Task 1: Assertion helpers (no MCP SDK required)

**Files:**
- Create: `src/mcp_contract/assert_mcp.py`
- Test: `tests/test_assert_mcp.py`

**Interfaces:**
- Consumes: a mapping `name -> info` where `info` has `.name`, `.annotations` or a dict with `"readOnlyHint"`
- Produces:

```python
def assert_tools_named(names: set[str], expected: set[str]) -> None:
    missing = expected - names
    extra = names - expected
    assert not missing and not extra, f"missing={missing} extra={extra}"

def assert_subset_named(names: set[str], required: set[str]) -> None:
    missing = required - names
    assert not missing, f"missing={missing}"
```

swamp-ops expected set (from `tests/test_server.py`):

```python
SWAMP_TOOLS = {
    "swamp_estate_status",
    "swamp_whats_down",
    "swamp_findings",
    "swamp_service_history",
    "swamp_portal_status",
    "swamp_scheduled_tasks",
    "swamp_jobs_status",
    "swamp_kb_search",
    "swamp_enqueue_job",
    "swamp_run_repo_backup",
    "swamp_backup_build_image",
    "swamp_open_maintenance_window",
    "swamp_discussions_status",
    "swamp_post_discussion",
}
```

- [ ] **Step 1: Tests for exact set vs subset**

- [ ] **Step 2: FAIL then implement**

- [ ] **Step 3: Commit** `feat: tool name set assertions`

---

### Task 2: In-memory list/call against MCPServer

**Files:**
- Create: `tests/fake_server.py`
- Create: `src/mcp_contract/session.py`
- Test: `tests/test_inmemory.py`

**Interfaces:**
- Produces:

```python
async def list_tool_names(server) -> set[str]:
    """Use whatever public API MCP SDK 2.x exposes on MCPServer for listing tools.
    If only `_tool_manager._tools` exists (swamp-ops already skips when missing),
    wrap that behind one function and test it against fake_server."""
```

Pin the SDK the way swamp-ops does: read `C:\Users\gmhow\dev\swamp-ops\requirements.txt` for the `mcp` pin and use the same pin.

`fake_server.py`:

```python
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

server = MCPServer(name="fake", title="Fake", version="0.0.1")

@server.tool(name="echo", annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False, idempotentHint=True))
def echo(text: str) -> str:
    return text
```

If `@server.tool` is not the 2.x decorator, copy the registration style from `C:\Users\gmhow\dev\swamp-ops\swamp_ops\server.py` exactly.

- [ ] **Step 1: Write async test `list_tool_names(fake_server.server) == {"echo"}`**

- [ ] **Step 2: Implement `session.py` using the same registry access as swamp-ops `test_server.py` `_tool_registry()`, but fail (don’t skip) if the shape is unknown — this plugin’s job is to notice registry drift.

- [ ] **Step 3: Add `assert_call_echo`**: invoke the underlying function or in-memory client. Prefer calling the registered handler if a full Client session is unstable. Document which path you used in a 5-line comment in `session.py`.

- [ ] **Step 4: PASS + commit** `feat: list tools on MCPServer`

---

### Task 3: pytest plugin fixture `mcp_server`

**Files:**
- Create: `src/mcp_contract/plugin.py`

**Interfaces:**
- Produces: fixture `mcp_server` that tests override:

```python
# in user tests
@pytest.fixture
def mcp_server():
    from swamp_ops.server import server
    return server
```

The plugin does not import swamp-ops. It only provides assertion helpers and optional `mcp_tool_names(mcp_server)` fixture if `mcp_server` exists.

```python
@pytest.fixture
def mcp_tool_names(mcp_server):
    from mcp_contract.session import list_tool_names
    return list_tool_names(mcp_server)
```

If `mcp_server` is missing, do not define a default — tests that need it declare the fixture.

- [ ] **Step 1: Plugin test with fake_server**

- [ ] **Step 2: entry point in pyproject.toml**

- [ ] **Step 3: Commit** `feat: pytest plugin fixtures`

---

### Task 4: Dogfood swamp-ops

**Files:**
- Create: `C:\Users\gmhow\dev\swamp-ops\tests\test_mcp_contract.py`

```python
import pytest
from mcp_contract.assert_mcp import assert_tools_named

SWAMP_TOOLS = { ... }  # copy from test_server.py

@pytest.fixture
def mcp_server():
    from swamp_ops.server import server
    return server

def test_swamp_tool_names(mcp_server):
    from mcp_contract.session import list_tool_names
    assert_tools_named(list_tool_names(mcp_server), SWAMP_TOOLS)
```

Keep `test_server.py` as the cheap registry test. This file is the plugin dogfood.

- [ ] **Step 1: Add path dep** in `requirements-dev.txt`: `-e ../pytest-mcp-contract` (or after publish, `pytest-mcp-contract`).

- [ ] **Step 2: Run `pytest tests/test_mcp_contract.py -v` from swamp-ops**

Expected: PASS, same names as `test_registered_tool_names_are_swamp_prefixed`.

- [ ] **Step 3: Commit in swamp-ops** `test: dogfood pytest-mcp-contract on tool names`

---

### Task 5: Optional extras (do not block v1)

- `mcp_contract.anchor`: `assert_text_anchored(source, snippet)` wrapping `trust_but_anchor.locate` — only if a tool returns a quote. No swamp-ops tool does that today; skip until there is a caller.
- henhouse: not required for MCP contracts v1.

README: “domain contracts, not conformance”; link FastMCP/python-sdk testing docs in a see-also, do not claim to replace them.

CI on the new repo: pytest 3.10/3.12/3.13 with `mcp` extra.

---

## Self-review

- Fourth in sequence: does not block 1–3.
- swamp-ops `tools.py` remains mcp-free.
- Name-set assertion is the first useful CI gate; snapshots of full JSON Schema can wait for v1.1 (`assert_tool_schema(name, required_keys)`).
