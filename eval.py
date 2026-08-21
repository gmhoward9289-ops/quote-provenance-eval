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

from anchor import locate, locate_pair
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
    "special characters. Do not shorten with ellipses. Do not fix typos. "
    "If the document does not contain the requested information, respond "
    'with {"answer": "NOT_FOUND", "quote": ""} — never quote text that does '
    "not answer the question."
)

ANCHOR_SYSTEM = (
    "You extract facts from documents. Respond with ONLY a JSON object, no "
    'markdown fences, no commentary: {"answer": "<the answer>", "anchor": '
    '"<location anchor>"}. The anchor is a short distinctive phrase of 3 to 8 '
    "consecutive words copied from the document, from the same sentence as "
    "the answer. Its only job is to let a program find the location — keep it "
    "short and distinctive. If the document does not contain the requested "
    'information, respond with {"answer": "NOT_FOUND", "anchor": ""}.'
)

# Second anchor, for disambiguating documents that repeat themselves.
ANCHOR2_SYSTEM = (
    "You extract facts from documents. Respond with ONLY a JSON object, no "
    'markdown fences, no commentary: {"answer": "<the answer>", "anchor": '
    '"<location anchor>", "anchor2": "<second anchor>"}. Each anchor is a '
    "short distinctive phrase of 3 to 8 consecutive words copied from the "
    "document. The first is from the same sentence as the answer. The second "
    "is from NEARBY BUT DIFFERENT text — a heading, a date line, the previous "
    "or next sentence — chosen so that the pair together occurs in only one "
    "place, even if the document repeats similar wording elsewhere. If the "
    "document does not contain the requested information, respond with "
    '{"answer": "NOT_FOUND", "anchor": "", "anchor2": ""}.'
)

# Prompt variants, tested one variable at a time.
#
#   fewshot  — granite3.3:8b scored 53% coverage by returning *descriptions*
#              of the value ("net income per diluted share in Q3 2025") rather
#              than text copied from the document. The instruction already
#              says "copied"; this tests whether a worked example does what
#              the instruction alone did not.
#   refusal  — refusal rates ranged from 10% to 100% under the base prompt.
#              This tests how much of that is the model and how much is the
#              prompt not making the refusal path vivid enough.
FEWSHOT_SUFFIX = """

EXAMPLE. Suppose the document contains this sentence:

    Consolidated revenue for fiscal 2025 was $2,847.3 million, up 11.2 percent.

and the question is "What was consolidated revenue?".

CORRECT: {"answer": "$2,847.3 million", "anchor": "Consolidated revenue for fiscal 2025"}
    — the anchor is text copied out of the document, so a program can find it.

WRONG:   {"answer": "$2,847.3 million", "anchor": "the consolidated revenue figure"}
    — those words describe the value instead of appearing in the document, so
      no program can find them and the citation is lost."""

REFUSAL_SUFFIX = (
    "\n\nIMPORTANT: many documents do NOT contain the value asked for. When "
    "that happens the only correct response is the NOT_FOUND object. Do not "
    "supply the closest available number, do not estimate, and do not point "
    "at text that is merely on a related topic. Answering when the value is "
    "absent is a worse failure than refusing when it is present."
)

VARIANT_SUFFIX = {"base": "", "fewshot": FEWSHOT_SUFFIX, "refusal": REFUSAL_SUFFIX}

REFUSAL_TOKENS = ("not_found", "not found", "n/a", "none", "unknown")


def is_refusal(answer: str) -> bool:
    a = (answer or "").strip().casefold()
    return a == "" or any(t in a for t in REFUSAL_TOKENS)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (round(max(0.0, center - half), 3), round(min(1.0, center + half), 3))


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


def get_response(provider: str, model: str, arm: str, question: dict, doc_text: str,
                 variant: str = "base") -> str:
    if provider == "mock":
        return mock_response(question, arm, model)
    system = {"quote": QUOTE_SYSTEM, "anchor": ANCHOR_SYSTEM,
              "anchor2": ANCHOR2_SYSTEM}[arm]
    system += VARIANT_SUFFIX.get(variant, "")
    return CALLERS[provider](model, system, user_prompt(doc_text, question["question"]))


def answer_correct(expected: str, *candidates: str) -> bool:
    return any(values_match(expected, c) for c in candidates)


def run_arm(arm: str, questions: list, docs: dict, provider: str, model: str,
            verbose: bool, rep: int = 1, variant: str = "base") -> list:
    rows = []
    for i, q in enumerate(questions, 1):
        doc_text = docs[q["doc"]]
        row = {"id": q["id"], "doc": q["doc"], "question": q["question"],
               "expect_value": q.get("expect_value"), "arm": arm, "rep": rep}
        if q.get("expect_absent"):
            row["absent"] = True
        try:
            raw = get_response(provider, model, arm, q, doc_text, variant)
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
            if row.get("absent"):
                # correct behavior: refuse, and offer no quote at all
                row["refused"] = is_refusal(row["answer"]) and not quote.strip()
                if quote.strip():
                    row["score"] = score_quote(doc_text, quote)
                label = "refused" if row["refused"] else "ANSWERED-ABSENT"
            else:
                row["score"] = score_quote(doc_text, quote)
                # symmetric counterpart of the anchor arm's value_in_span: does
                # the quoted text itself contain the expected value?
                row["value_in_quote"] = answer_correct(q["expect_value"], quote)
                # answer field alone — the quote side is value_in_quote
                row["answer_correct"] = answer_correct(q["expect_value"], row["answer"])
                label = row["score"]["level"]
        else:
            anchor_text = str(parsed.get("anchor", ""))
            row["anchor"] = anchor_text
            if arm == "anchor2":
                anchor2_text = str(parsed.get("anchor2", ""))
                row["anchor2"] = anchor2_text
                loc = locate_pair(doc_text, anchor_text, anchor2_text)
            else:
                loc = locate(doc_text, anchor_text)
            row["locate"] = loc
            located = loc["method"] != "not_found"
            row["located"] = located
            if located:
                # invariant: emitted sentence is a real substring of the source
                assert loc["sentence"] in doc_text
            if row.get("absent"):
                row["refused"] = is_refusal(row["answer"])
                label = "refused" if row["refused"] else "ANSWERED-ABSENT"
                label += "/located" if located else ""
            else:
                if located:
                    row["value_in_span"] = answer_correct(q["expect_value"], loc["sentence"])
                row["answer_correct"] = answer_correct(q["expect_value"], row["answer"])
                label = loc["method"] + ("" if not located else
                                         ("/value-hit" if row["value_in_span"] else "/value-miss"))
        if verbose:
            print(f"  [{arm} {i}/{len(questions)}] {q['id']}: {label}")
        rows.append(row)
    return rows


def is_anchor_arm(arm: str) -> bool:
    """Single-anchor and dual-anchor arms share the same coverage metrics."""
    return arm in ("anchor", "anchor2")


def summarize(rows: list) -> dict:
    # Intent-to-treat: a response the model produced but we could not parse
    # is a failure of the arm (a naive pipeline gets no provenance from it),
    # so parse failures stay IN the denominators — as 'unparseable' for the
    # quote arm and as not-located for the anchor arm. Only provider/network
    # errors (no response at all) are excluded from the rates; they are
    # infrastructure, not model behavior, and are reported separately.
    def attempted(arm: str) -> list:
        return [r for r in rows if r["arm"] == arm and not r.get("absent")
                and "raw_response" in r]

    def attempted_anchor_family() -> list:
        # --arm anchor2 writes arm="anchor2"; treat it like anchor for rates
        return [r for r in rows if is_anchor_arm(r["arm"]) and not r.get("absent")
                and "raw_response" in r]

    quote_rows = attempted("quote")
    anchor_rows = attempted_anchor_family()
    provider_errors = [r for r in rows if "error" in r]
    unparseable = [r for r in rows if r.get("parse_error")]
    s: dict = {"n_quote": len(quote_rows), "n_anchor": len(anchor_rows),
               "n_provider_errors": len(provider_errors),
               "n_unparseable": len(unparseable)}
    ci: dict = {}

    if quote_rows:
        n = len(quote_rows)
        levels = {}
        for r in quote_rows:
            lvl = r["score"]["level"] if "score" in r else "unparseable"
            levels[lvl] = levels.get(lvl, 0) + 1
        s["quote_levels"] = levels
        exact = levels.get("exact", 0)
        s["quote_exact_rate"] = round(exact / n, 3)
        ci["quote_exact_rate"] = wilson_ci(exact, n)
        # apples-to-apples with anchor_coverage: exact quote AND the quote
        # contains the expected value (anchor_coverage requires located AND
        # value in the located sentence)
        cov = sum(1 for r in quote_rows
                  if "score" in r and r["score"]["level"] == "exact"
                  and r.get("value_in_quote"))
        s["quote_coverage"] = round(cov / n, 3)
        ci["quote_coverage"] = wilson_ci(cov, n)
        s["quote_recoverable_rate"] = round((exact + levels.get("normalized", 0)) / n, 3)
        s["quote_fabricated_rate"] = round(levels.get("fabricated", 0) / n, 3)
        s["quote_answer_accuracy"] = round(
            sum(r.get("answer_correct", False) for r in quote_rows) / n, 3)

    if anchor_rows:
        n = len(anchor_rows)
        located = [r for r in anchor_rows if r.get("located")]
        s["anchor_located_rate"] = round(len(located) / n, 3)
        cov = sum(1 for r in located if r.get("value_in_span"))
        s["anchor_coverage"] = round(cov / n, 3)
        ci["anchor_coverage"] = wilson_ci(cov, n)
        s["anchor_methods"] = {}
        for r in anchor_rows:
            m = r["locate"]["method"] if "locate" in r else "unparseable"
            s["anchor_methods"][m] = s["anchor_methods"].get(m, 0) + 1
        # located anchors whose matched span occurs more than once in the
        # (normalized) doc — a value-miss on these may be "right anchor,
        # wrong occurrence" rather than a bad anchor
        s["anchor_ambiguous"] = sum(
            1 for r in located if r["locate"].get("occurrences", 1) > 1)
        s["anchor_answer_accuracy"] = round(
            sum(r.get("answer_correct", False) for r in anchor_rows) / n, 3)
        # by construction — every located span passed the substring assert
        s["anchor_provenance_fidelity_of_located"] = 1.0

    if ci:
        s["ci95"] = ci

    # value-absent questions: the right answer is a refusal with no span.
    # The dangerous failure is a confident answer backed by real-looking
    # provenance (an exact quote / a located anchor of irrelevant text).
    # Unparseable responses count in the denominator (not a clean refusal).
    abs_q = [r for r in rows if r.get("absent") and r["arm"] == "quote"
             and ("refused" in r or r.get("parse_error"))]
    abs_a = [r for r in rows if r.get("absent") and is_anchor_arm(r["arm"])
             and ("refused" in r or r.get("parse_error"))]
    if abs_q:
        n = len(abs_q)
        s["n_absent_quote"] = n
        s["quote_absent_refusal_rate"] = round(
            sum(r.get("refused", False) for r in abs_q) / n, 3)
        s["quote_absent_confident_with_exact_span"] = sum(
            1 for r in abs_q
            if not r.get("refused") and r.get("score", {}).get("level") == "exact")
    if abs_a:
        n = len(abs_a)
        s["n_absent_anchor"] = n
        s["anchor_absent_refusal_rate"] = round(
            sum(r.get("refused", False) for r in abs_a) / n, 3)
        s["anchor_absent_confident_with_located_span"] = sum(
            1 for r in abs_a if not r.get("refused") and r.get("located"))

    # per-repeat breakdown of the headline rates (only present for --repeats > 1)
    reps = sorted({r.get("rep", 1) for r in rows})
    if len(reps) > 1:
        per: dict = {}
        for rep in reps:
            sub = summarize([r for r in rows if r.get("rep", 1) == rep])
            for k in ("quote_exact_rate", "quote_coverage", "anchor_coverage"):
                if k in sub:
                    per.setdefault(k, []).append(sub[k])
        s["per_rep"] = per
    return s


def filter_questions_by_docs(questions: list, docs_csv: str) -> list:
    """Keep questions whose ``doc`` basename is in a comma-separated list.

    Raises ValueError with available basenames when any requested doc is unknown
    for the loaded questions file.
    """
    wanted = {d.strip() for d in docs_csv.split(",") if d.strip()}
    if not wanted:
        return questions
    available = sorted({q["doc"] for q in questions})
    unknown = sorted(wanted - set(available))
    if unknown:
        raise ValueError(
            f"unknown doc(s): {', '.join(unknown)}. "
            f"Available in this questions file: {', '.join(available)}"
        )
    return [q for q in questions if q["doc"] in wanted]


def _run_label(r: dict) -> str:
    """Short corpus/variant/arm label matching the comparison table."""
    corpus = r["corpus"].replace("questions_", "").replace("questions", "clean")
    arms = r.get("arms") or []
    if arms == ["anchor2"]:
        corpus = f"{corpus}/anchor2"
    elif arms == ["anchor"]:
        corpus = f"{corpus}/anchor"
    elif arms and arms != ["quote", "anchor"]:
        corpus = f"{corpus}/{'+'.join(arms)}"
    variant = r.get("variant") or "base"
    if variant != "base":
        corpus = f"{corpus}/{variant}"
    return corpus


def format_anchor_breakdown_lines(runs: list) -> list[str]:
    """Markdown section: per-run anchor_methods and ambiguity (issue #7)."""
    lines = [
        "## Anchor methods and ambiguity",
        "",
        "Per run with anchor data. *Methods* are how `locate` resolved the "
        "model's phrase (exact / normalized / subsequence / fuzzy / not_found / "
        "unparseable). *Ambiguous* counts located anchors whose matched span "
        "occurs more than once in the normalized document — not a locator "
        "defect by itself; common on repeated OCR footers or quoted-reply threads.",
        "",
    ]
    any_anchor = False
    for r in runs:
        s = r["summary"]
        methods = s.get("anchor_methods")
        if not methods:
            continue
        any_anchor = True
        n = s.get("n_anchor") or sum(methods.values())
        parts = []
        for method, count in sorted(methods.items(), key=lambda kv: (-kv[1], kv[0])):
            share = f"{count / n:.0%}" if n else "—"
            parts.append(f"{method} {count} ({share})")
        label = _run_label(r)
        lines.append(f"### `{r['provider']}` `{r['model']}` — `{label}`")
        lines.append("")
        lines.append(f"- **methods:** {'; '.join(parts)}")
        if "anchor_ambiguous" in s:
            amb = s["anchor_ambiguous"]
            located = sum(
                c for m, c in methods.items()
                if m not in ("not_found", "unparseable")
            )
            if located:
                lines.append(
                    f"- **ambiguous:** {amb} / {located} located "
                    f"({amb / located:.0%})"
                )
            else:
                lines.append(f"- **ambiguous:** {amb} (none located)")
        lines.append("")
    if not any_anchor:
        lines.append("_No runs in this report include anchor-arm summary data._")
        lines.append("")
    return lines


def cmd_run(args: argparse.Namespace) -> None:
    qpath = Path(args.questions)
    questions = json.loads(qpath.read_text(encoding="utf-8"))
    if getattr(args, "docs", None):
        try:
            questions = filter_questions_by_docs(questions, args.docs)
        except ValueError as e:
            raise SystemExit(f"error: {e}") from e
        if not questions:
            raise SystemExit("error: --docs matched no questions")
    if args.limit:
        questions = questions[: args.limit]
    docs = {p.name: p.read_text(encoding="utf-8") for p in DOCS.glob("*.txt")}
    arms = ["quote", "anchor"] if args.arm == "both" else [args.arm]

    all_rows = []
    for rep in range(1, args.repeats + 1):
        for arm in arms:
            rep_tag = f" rep={rep}/{args.repeats}" if args.repeats > 1 else ""
            print(f"Running arm={arm} provider={args.provider} model={args.model} "
                  f"({len(questions)} questions){rep_tag}")
            all_rows += run_arm(arm, questions, docs, args.provider, args.model,
                                args.verbose, rep, args.variant)

    summary = summarize(all_rows)
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tag = "" if qpath.stem == "questions" else f"_{qpath.stem.replace('questions_', '')}"
    # variant and non-default arms go in the filename: without them a fewshot
    # run and a base run of the same model+corpus are indistinguishable, and
    # anything globbing results/ silently mixes them.
    vtag = "" if args.variant == "base" else f"_{args.variant}"
    atag = "_anchor2" if args.arm == "anchor2" else ""
    out = out_dir / f"run_{args.provider}_{safe_model}{tag}{vtag}{atag}_{stamp}.json"
    out.write_text(json.dumps({
        "provider": args.provider, "model": args.model, "timestamp": stamp,
        "corpus": qpath.stem, "variant": args.variant,
        "arms": arms, "summary": summary, "rows": all_rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "arm", "rep", "outcome", "ratio", "answer_correct", "detail"])
        for r in all_rows:
            rep = r.get("rep", 1)
            if "refused" in r:
                outcome = "refused" if r["refused"] else "answered-absent"
                detail = r.get("score", {}).get("level", "")
                if r.get("located"):
                    detail = (detail + " located").strip()
                w.writerow([r["id"], r["arm"], rep, outcome, "", "", detail])
            elif "score" in r:
                w.writerow([r["id"], r["arm"], rep, r["score"]["level"], r["score"]["ratio"],
                            r.get("answer_correct"), r["score"]["detail"]])
            elif "locate" in r:
                outcome = r["locate"]["method"]
                if r["located"]:
                    outcome += "/value-hit" if r.get("value_in_span") else "/value-miss"
                w.writerow([r["id"], r["arm"], rep, outcome, r["locate"].get("ratio", ""),
                            r.get("answer_correct"), ""])
            else:
                w.writerow([r["id"], r["arm"], rep, "call_failed", "", "", r.get("error", "parse error")])

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved: {out}\n       {csv_path}")
    if "quote_coverage" in summary and "anchor_coverage" in summary:
        ci = summary.get("ci95", {})
        def with_ci(key):
            v = f"{summary[key]:.0%}"
            if key in ci:
                lo, hi = ci[key]
                v += f" (95% CI {lo:.0%}–{hi:.0%})"
            return v
        print(f"\nHeadline: verbatim-quote coverage (exact quote containing the value) "
              f"{with_ci('quote_coverage')} vs anchored-extraction coverage "
              f"{with_ci('anchor_coverage')} (anchored spans are exact by construction).")


def cmd_report(args: argparse.Namespace) -> None:
    runs = []
    for path in args.results:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if "corpus" not in data:
            # older runs: recover the corpus tag from the filename
            m = re.search(r"_hard_\d{8}-\d{6}", Path(path).name)
            data["corpus"] = "questions_hard" if m else "questions"
        runs.append(data)
    lines = [
        "# Quote-provenance eval — cross-run comparison", "",
        "| provider | model | corpus | n | unparseable | quote exact | quote coverage | +normalized | fabricated | anchor located | anchor coverage |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        s = r["summary"]
        ci = s.get("ci95", {})
        corpus = _run_label(r)
        def pct(key):
            return f"{s[key]:.0%}" if key in s else "—"
        def pct_ci(key):
            if key not in s:
                return "—"
            v = f"{s[key]:.0%}"
            if key in ci:
                lo, hi = ci[key]
                v += f" <sub>{lo:.0%}–{hi:.0%}</sub>"
            return v
        nq, na = s.get("n_quote", 0), s.get("n_anchor", 0)
        if nq and na and nq != na:
            n_col = f"{nq}/{na}"
        elif na:
            n_col = str(na)
        else:
            n_col = str(nq)
        bad = s.get("n_unparseable", s.get("n_failed_calls", 0))
        lines.append(
            f"| {r['provider']} | {r['model']} | {corpus} | {n_col} | {bad} | "
            f"{pct('quote_exact_rate')} | "
            f"{pct_ci('quote_coverage')} | "
            f"{pct('quote_recoverable_rate')} | {pct('quote_fabricated_rate')} | "
            f"{pct('anchor_located_rate')} | {pct_ci('anchor_coverage')} |")
    lines += [
        "",
        "**How to read this:** *quote exact* is the share of model-produced "
        "'verbatim' quotes that actually appear character-for-character in the "
        "source — the only kind a naive string-match verifier accepts. "
        "*quote coverage* additionally requires the exact quote to contain the "
        "expected value — the apples-to-apples comparator for *anchor coverage*. "
        "*+normalized* adds quotes recoverable with cheap unicode/whitespace "
        "normalization. *anchor coverage* is the share of questions where the "
        "anchored-extraction arm located the model's anchor AND the located "
        "source sentence contains the expected value — and every span it emits "
        "is a real substring of the source by construction. All rates are "
        "intent-to-treat: responses that arrived but could not be parsed stay "
        "in the denominators (*unparseable* column); only provider/network "
        "errors are excluded.",
        "",
    ]
    lines += format_anchor_breakdown_lines(runs)
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
    pr.add_argument("--arm", default="both", choices=["both", "quote", "anchor", "anchor2"])
    pr.add_argument("--variant", default="base", choices=sorted(VARIANT_SUFFIX),
                    help="system-prompt variant: base, fewshot (worked anchor example), "
                         "refusal (emphatic absent-value instruction)")
    pr.add_argument("--limit", type=int, default=0, help="only run the first N questions")
    pr.add_argument("--repeats", type=int, default=1,
                    help="run the whole question set N times; summary pools "
                         "across repeats and adds a per-repeat breakdown")
    pr.add_argument("--questions", default=str(ROOT / "corpus" / "questions.json"),
                    help="questions file (e.g. corpus/questions_hard.json)")
    pr.add_argument("--docs", default="",
                    help="comma-separated document basenames (match question "
                         "`doc` field); only those questions run")
    pr.add_argument("--verbose", action="store_true", help="per-question progress lines")
    pr.set_defaults(func=cmd_run)

    pp = sub.add_parser("report", help="build a markdown comparison from result JSONs")
    pp.add_argument("results", nargs="+", help="paths to run_*.json files")
    pp.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
