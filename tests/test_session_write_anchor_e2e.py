"""End-to-end: transcript Read → Write with locate() on the written body."""

from __future__ import annotations

import json
from pathlib import Path

from trust_but_anchor import locate

FIXTURE = Path(__file__).parent / "fixtures" / "read_write_anchor.jsonl"


def _tool_results(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        if doc.get("type") != "user":
            continue
        for block in doc.get("message", {}).get("content", []):
            if block.get("type") == "tool_result" and block.get("tool_use_id"):
                out[block["tool_use_id"]] = block.get("content", "")
    return out


def _write_contents(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        if doc.get("type") != "assistant":
            continue
        for block in doc.get("message", {}).get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "Write":
                return block["input"]["contents"]
    raise AssertionError("no Write in fixture")


def test_write_body_is_anchored_in_prior_read_result():
    results = _tool_results(FIXTURE)
    read_id = next(iter(results))
    source = results[read_id]
    written = _write_contents(FIXTURE)
    hit = locate(source, written)
    assert hit.get("method") != "not_found"
    assert hit.get("span")
