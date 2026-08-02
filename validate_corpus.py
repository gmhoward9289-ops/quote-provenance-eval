#!/usr/bin/env python3
"""Validate the corpus: every gt_quote and expect_value must be an exact
substring of its document, and gt_quote should occur exactly once."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "corpus" / "docs"


def main() -> int:
    questions = []
    for qfile in sorted((ROOT / "corpus").glob("questions*.json")):
        questions += json.loads(qfile.read_text(encoding="utf-8"))
    errors = 0
    for q in questions:
        doc_text = (DOCS / q["doc"]).read_text(encoding="utf-8")
        n = doc_text.count(q["gt_quote"])
        if n == 0:
            print(f"FAIL {q['id']}: gt_quote not found in {q['doc']}")
            errors += 1
        elif n > 1:
            print(f"WARN {q['id']}: gt_quote occurs {n} times in {q['doc']}")
        if q["expect_value"] not in q["gt_quote"]:
            print(f"FAIL {q['id']}: expect_value not inside gt_quote")
            errors += 1
        if q["expect_value"] not in doc_text:
            print(f"FAIL {q['id']}: expect_value not found in {q['doc']}")
            errors += 1
    print(f"{len(questions)} questions checked, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
