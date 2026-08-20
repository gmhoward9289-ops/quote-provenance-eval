# Proof stack — project layout

> Four libraries. One sentence: the model proposes; code locates, records, and checks; fail closed.
> Cost ledger is out of scope. xycalc stays a corpus product.

**For agentic workers:** implement in this order. Each numbered plan is independently testable. Do not start plan N+1 until plan N has a public import or a frozen JSON schema the next plan can pin.

| # | Project | Repo (today) | Plan | Depends on |
|---|---------|--------------|------|------------|
| 1 | Anchor library | `C:\Users\gmhow\dev\trust-but-anchor` | [2026-08-19-anchor-library.md](./2026-08-19-anchor-library.md) | — |
| 2 | henhouse session schema | extract from `C:\Users\gmhow\dev\leghorn\henhouse.py`; new package repo `henhouse` | [2026-08-19-henhouse-schema.md](./2026-08-19-henhouse-schema.md) | — (parallel with 1 after schema freeze) |
| 3 | Session → pytest | **new** repo `pytest-session-trace` | [2026-08-19-session-pytest.md](./2026-08-19-session-pytest.md) | henhouse v1 |
| 4 | MCP domain contracts | `pytest-mcp-contract` on PyPI; dogfood `swamp-ops` | [2026-08-19-mcp-contracts.md](./2026-08-19-mcp-contracts.md) | optional henhouse, optional trust-but-anchor |

## Stack status (2026-08-20)

| Lane | PyPI | swamp-ops dogfood |
| --- | --- | --- |
| 1 trust-but-anchor | yes | optional `[anchor]` extra |
| 2 henhouse | yes (0.1.2) | JSONL fixtures parse in `test_session_trace.py` |
| 3 pytest-session-trace | yes (0.1.5+) | `test_session_trace.py` + live capture script |
| 4 pytest-mcp-contract | yes (0.1.4+) | `test_mcp_contract.py` — all 14 tool schemas, prefix + non-destructive write pins |

`swamp-ops/requirements-dev.txt` pins all three pytest-stack packages from PyPI.
Each library has `packaging/publish-doctor.sh` (daily CI) verifying the registry
matches `__version__`.

```
trust_but_anchor (stdlib)          henhouse (stdlib)
        |                                  |
        |                     roost / leghorn  (link + emit schema; no pip dep)
        |                                  |
        +-------- pytest-session-trace ----+
        |                  |
        +-- pytest-mcp-contract -- swamp-ops tests
```

## Shared constraints

- Python 3.10+ for new packages (`list[str]`, `X | None` already used in `anchor.py`). roost/leghorn stay 3.9 and **must not** gain a pip dependency — they keep one-file / two-file installs. They *link* henhouse and emit the same JSON keys.
- Library code: stdlib only. pytest is a test/plugin extra, never a runtime dep of `trust_but_anchor` or `henhouse`.
- License: Apache-2.0 to match the source repos (roost is MIT; henhouse extracted from Apache-2.0 leghorn stays Apache-2.0).
- Fail closed. No LLM in CI. No security exploit payloads in MCP tests.
- Do not chase official MCP conformance (`npx @modelcontextprotocol/conformance`). Do not build a cost ledger.

## What “done” means for the stack

1. `pip install trust-but-anchor` → `from trust_but_anchor import locate` works; `python3 eval.py` still works via shims.
2. `pip install henhouse` → parse a Claude JSONL into typed events; roost/leghorn READMEs point at it; `--json` grows a `"schema": "henhouse.session.v1"` field without breaking existing keys.
3. `pip install pytest-session-trace` → a recorded session becomes pass/fail tool-call assertions with no model.
4. `pip install pytest-mcp-contract` → swamp-ops CI asserts tool names, schemas, and one round-trip without standing stdio.

## Execution order for a single worker

Do **1** to a tagged v0.1. Start **2** as soon as the henhouse JSON key list in that plan is frozen (does not wait for PyPI of 1). Start **3** when henhouse can `iter_tool_calls`. Start **4** last.

## Local remotes

- **Folder + GitHub + swamplink:** `C:\Users\gmhow\dev\trust-but-anchor` → `origin` = `swamplink:/srv/git/trust-but-anchor.git`, `github` = `gmhoward9289-ops/trust-but-anchor`
