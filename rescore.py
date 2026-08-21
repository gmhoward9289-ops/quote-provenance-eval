#!/usr/bin/env python3
"""Re-score a saved run offline from its stored raw responses — no model
calls. Useful after improving the locator or the value checker.

Usage: python rescore.py results/run_x.json [more.json ...]
"""
import json
import sys
from pathlib import Path

from anchor import locate, locate_pair
from eval import answer_correct, is_anchor_arm, parse_model_json, summarize
from scoring import score_quote

ROOT = Path(__file__).parent
DOCS = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "corpus" / "docs").glob("*.txt")}
QUESTIONS = {q["id"]: q for f in sorted((ROOT / "corpus").glob("questions*.json"))
             for q in json.loads(f.read_text(encoding="utf-8"))}


def rescore_row(row: dict) -> dict:
    if "raw_response" not in row:
        return row
    q = QUESTIONS[row["id"]]
    if q.get("expect_absent"):
        # absent-question rows keep their original refusal scoring
        return row
    doc = DOCS[row["doc"]]
    expect = q["expect_value"]
    row = dict(row, expect_value=expect)
    parsed = parse_model_json(row["raw_response"])
    if parsed is None:
        return row
    row["answer"] = str(parsed.get("answer", ""))
    if is_anchor_arm(row["arm"]):
        a1 = str(parsed.get("anchor", ""))
        row["anchor"] = a1
        if row["arm"] == "anchor2":
            a2 = str(parsed.get("anchor2", ""))
            row["anchor2"] = a2
            loc = locate_pair(doc, a1, a2)
        else:
            loc = locate(doc, a1)
        row["locate"] = loc
        row["located"] = loc["method"] != "not_found"
        if row["located"]:
            assert loc["sentence"] in doc
            row["value_in_span"] = answer_correct(expect, loc["sentence"])
        else:
            row.pop("value_in_span", None)
        row["answer_correct"] = answer_correct(expect, row["answer"])
    else:
        quote = str(parsed.get("quote", ""))
        row["quote"] = quote
        row["score"] = score_quote(doc, quote)
        row["value_in_quote"] = answer_correct(expect, quote)
        # answer field alone — the quote side is value_in_quote
        row["answer_correct"] = answer_correct(expect, row["answer"])
    return row


def main() -> None:
    for path in sys.argv[1:]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if "corpus" not in data:
            data["corpus"] = ("questions_hard" if "_hard_" in Path(path).name
                              else "questions")
        old = data["summary"]
        rows = [rescore_row(r) for r in data["rows"]]
        new = summarize(rows)
        data["rows"], data["summary"] = rows, new
        out = Path(path).with_name(Path(path).stem + "_rescored.json")
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n=== {data['model']} ===")
        for k in sorted(set(old) | set(new)):
            o, n = old.get(k), new.get(k)
            flag = "   <-- changed" if o != n else ""
            print(f"  {k}: {o} -> {n}{flag}")
        print(f"  saved: {out}")


if __name__ == "__main__":
    main()
