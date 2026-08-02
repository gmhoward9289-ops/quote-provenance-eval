#!/usr/bin/env python3
"""Quote-provenance eval: can a model quote its source verbatim, and does
'model proposes, code anchors' beat trusting the model's quotes?

Usage:
  python eval.py run --provider mock --model sloppy
  python eval.py run --provider anthropic --model claude-sonnet-4-5
  python eval.py run --provider ollama --model llama3.1:8b
  python eval.py run --provider openrouter --model openai/gpt-4o-mini
  python eval.py report results/*.json        # cross-run comparison table

Arms:
  quote  — model returns answer + a 'verbatim' quote; we score the quote
           against the source (exact / normalized / minor_edit / paraphrase /
           fabricated).
  anchor — model returns answer + a short anchor phrase; deterministic code
           locates the anchor and emits the containing sentence FROM THE
           SOURCE. Emitted provenance is exact by construction; the metric
           is coverage.
Both arms run by default.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from anchor import locate
from mock import mock_response
from providers import CALLERS, ProviderError
from scoring import score_quote, values_match

ROOT = Path(__file__).parent
DOCS = ROOT / "corpus" / "docs"

QUOTE_SYSTEM = (
    "You extract facts from documents. Respond with ONLY a JSON object, no "
    'markdown fences, no commentary: {"answer": "<the answer>", "quote": '
    '"<supporting quote>"}. The quote MUST be copied character-for-character '
    "from the document — identical punctuation, capitalization, spacing, and "
    "special characters. Do not shorten with ellipses. Do not fix typos."
)

ANCHOR_SYSTEM = (
    "You extract facts from documents. Respond with ONLY a JSON object, no "
    'markdown fences, no commentary: {"answer": "<the answer>", "anchor": '
    '"<location anchor>"}. The anchor is a short distinctive phrase of 3 to 8 '
    "consecutive words copied from the document, from the same sentence as "
    "the answer. Its only job is to let a program find the location — keep it "
    "short and distinctive."
)


def user_prompt(doc_text: str, question: str) -> str:
    return f"DOCUMENT:\n{doc_text}\n\nQUESTION: {question}\n\nRespond with only the JSON object."


def parse_model_json(raw: str) -> dict | None:
    """Best-effort extraction of the first JSON object in a response."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def get_response(provider: str, model: str, arm: str, question: dict, doc_text: str) -> str:
    if provider == "mock":
        return mock_response(question, arm, model)
    system = QUOTE_SYSTEM if arm == "quote" else ANCHOR_SYSTEM
    return CALLERS[provider](model, system, user_prompt(doc_text, question["question"]))


def answer_correct(expected: str, *candidates: str) -> bool:
    return any(values_match(expected, c) for c in candidates)


def run_arm(arm: str, questions: list, docs: dict, provider: str, model: str, verbose: bool) -> list:
    rows = []
    for i, q in enumerate(questions, 1):
        doc_text = docs[q["doc"]]
        row = {"id": q["id"], "doc": q["doc"], "question": q["question"],
               "expect_value": q["expect_value"], "arm": arm}
        try:
            raw = get_response(provider, model, arm, q, doc_text)
        except ProviderError as e:
            row.update({"error": str(e)})
            rows.append(row)
            print(f"  [{arm} {i}/{len(questions)}] {q['id']}: ERROR {e}", file=sys.stderr)
            continue
        row["raw_response"] = raw
        parsed = parse_model_json(raw)
        if parsed is None:
            row["parse_error"] = True
            rows.append(row)
            if verbose:
                print(f"  [{arm} {i}/{len(questions)}] {q['id']}: unparseable response")
            continue
        row["answer"] = str(parsed.get("answer", ""))

        if arm == "quote":
            quote = str(parsed.get("quote", ""))
            row["quote"] = quote
            row["score"] = score_quote(doc_text, quote)
            row["answer_correct"] = answer_correct(q["expect_value"], row["answer"], quote)
            label = row["score"]["level"]
        else:
            anchor_text = str(parsed.get("anchor", ""))
            row["anchor"] = anchor_text
            loc = locate(doc_text, anchor_text)
            row["locate"] = loc
            located = loc["method"] != "not_found"
            row["located"] = located
            if located:
                # invariant: emitted sentence is a real substring of the source
                assert loc["sentence"] in doc_text
                row["value_in_span"] = answer_correct(q["expect_value"], loc["sentence"])
            row["answer_correct"] = answer_correct(q["expect_value"], row["answer"])
            label = loc["method"] + ("" if not located else
                                     ("/value-hit" if row["value_in_span"] else "/value-miss"))
        if verbose:
            print(f"  [{arm} {i}/{len(questions)}] {q['id']}: {label}")
        rows.append(row)
    return rows


def summarize(rows: list) -> dict:
    quote_rows = [r for r in rows if r["arm"] == "quote" and "score" in r]
    anchor_rows = [r for r in rows if r["arm"] == "anchor" and "locate" in r]
    errors = [r for r in rows if "error" in r or r.get("parse_error")]
    s: dict = {"n_quote": len(quote_rows), "n_anchor": len(anchor_rows), "n_failed_calls": len(errors)}

    if quote_rows:
        n = len(quote_rows)
        levels = {}
        for r in quote_rows:
            levels[r["score"]["level"]] = levels.get(r["score"]["level"], 0) + 1
        s["quote_levels"] = levels
        exact = levels.get("exact", 0)
        s["quote_exact_rate"] = round(exact / n, 3)
        s["quote_recoverable_rate"] = round((exact + levels.get("normalized", 0)) / n, 3)
        s["quote_fabricated_rate"] = round(levels.get("fabricated", 0) / n, 3)
        s["quote_answer_accuracy"] = round(sum(r["answer_correct"] for r in quote_rows) / n, 3)

    if anchor_rows:
        n = len(anchor_rows)
        located = [r for r in anchor_rows if r["located"]]
        s["anchor_located_rate"] = round(len(located) / n, 3)
        s["anchor_coverage"] = round(sum(1 for r in located if r.get("value_in_span")) / n, 3)
        s["anchor_methods"] = {}
        for r in anchor_rows:
            m = r["locate"]["method"]
            s["anchor_methods"][m] = s["anchor_methods"].get(m, 0) + 1
        s["anchor_answer_accuracy"] = round(sum(r["answer_correct"] for r in anchor_rows) / n, 3)
        # by construction — every located span passed the substring assert
        s["anchor_provenance_fidelity_of_located"] = 1.0
    return s


def cmd_run(args: argparse.Namespace) -> None:
    qpath = Path(args.questions)
    questions = json.loads(qpath.read_text(encoding="utf-8"))
    if args.limit:
        questions = questions[: args.limit]
    docs = {p.name: p.read_text(encoding="utf-8") for p in DOCS.glob("*.txt")}
    arms = ["quote", "anchor"] if args.arm == "both" else [args.arm]

    all_rows = []
    for arm in arms:
        print(f"Running arm={arm} provider={args.provider} model={args.model} "
              f"({len(questions)} questions)")
        all_rows += run_arm(arm, questions, docs, args.provider, args.model, args.verbose)

    summary = summarize(all_rows)
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tag = "" if qpath.stem == "questions" else f"_{qpath.stem.replace('questions_', '')}"
    out = out_dir / f"run_{args.provider}_{safe_model}{tag}_{stamp}.json"
    out.write_text(json.dumps({
        "provider": args.provider, "model": args.model, "timestamp": stamp,
        "summary": summary, "rows": all_rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "arm", "outcome", "ratio", "answer_correct", "detail"])
        for r in all_rows:
            if "score" in r:
                w.writerow([r["id"], r["arm"], r["score"]["level"], r["score"]["ratio"],
                            r.get("answer_correct"), r["score"]["detail"]])
            elif "locate" in r:
                outcome = r["locate"]["method"]
                if r["located"]:
                    outcome += "/value-hit" if r.get("value_in_span") else "/value-miss"
                w.writerow([r["id"], r["arm"], outcome, r["locate"].get("ratio", ""),
                            r.get("answer_correct"), ""])
            else:
                w.writerow([r["id"], r["arm"], "call_failed", "", "", r.get("error", "parse error")])

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved: {out}\n       {csv_path}")
    if "quote_exact_rate" in summary and "anchor_coverage" in summary:
        print(f"\nHeadline: verbatim-quote exact-match rate "
              f"{summary['quote_exact_rate']:.0%} vs anchored-extraction coverage "
              f"{summary['anchor_coverage']:.0%} (anchored spans are exact by construction).")


def cmd_report(args: argparse.Namespace) -> None:
    runs = []
    for path in args.results:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        runs.append(data)
    lines = [
        "# Quote-provenance eval — cross-run comparison", "",
        "| provider | model | quote exact | +normalized | fabricated | anchor located | anchor coverage |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        s = r["summary"]
        def pct(key):
            return f"{s[key]:.0%}" if key in s else "—"
        lines.append(
            f"| {r['provider']} | {r['model']} | {pct('quote_exact_rate')} | "
            f"{pct('quote_recoverable_rate')} | {pct('quote_fabricated_rate')} | "
            f"{pct('anchor_located_rate')} | {pct('anchor_coverage')} |")
    lines += [
        "",
        "**How to read this:** *quote exact* is the share of model-produced "
        "'verbatim' quotes that actually appear character-for-character in the "
        "source — the only kind a naive string-match verifier accepts. "
        "*+normalized* adds quotes recoverable with cheap unicode/whitespace "
        "normalization. *anchor coverage* is the share of questions where the "
        "anchored-extraction arm located the model's anchor AND the located "
        "source sentence contains the expected value — and every span it emits "
        "is a real substring of the source by construction.", "",
    ]
    out = ROOT / "results" / "comparison.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved: {out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="run the eval against one provider/model")
    pr.add_argument("--provider", required=True, choices=["anthropic", "ollama", "openrouter", "mock"])
    pr.add_argument("--model", required=True,
                    help="model id, or mock profile (faithful|sloppy|chaotic)")
    pr.add_argument("--arm", default="both", choices=["both", "quote", "anchor"])
    pr.add_argument("--limit", type=int, default=0, help="only run the first N questions")
    pr.add_argument("--questions", default=str(ROOT / "corpus" / "questions.json"),
                    help="questions file (e.g. corpus/questions_hard.json)")
    pr.add_argument("--verbose", action="store_true", help="per-question progress lines")
    pr.set_defaults(func=cmd_run)

    pp = sub.add_parser("report", help="build a markdown comparison from result JSONs")
    pp.add_argument("results", nargs="+", help="paths to run_*.json files")
    pp.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
