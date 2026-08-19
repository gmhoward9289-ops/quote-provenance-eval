"""Preflight: predict provenance failure modes BEFORE spending a token.

The eval measures what went wrong after the fact. Most of it was predictable
from the document and the prompt alone:

  - anchor ambiguity came from documents that repeat themselves (quoted-reply
    email chains, repeated page footers), not from bad anchors
  - exact-quote loss came from documents salted with curly quotes, NBSP and
    en dashes, not from models refusing to copy
  - confident invented answers came from prompts with no explicit refusal path
  - and a doc that overflows the context window fails as a *quoting* failure,
    which is the most misleading failure of all

None of that needs a model to detect. Everything here is deterministic: same
input, same findings, no API key, no inference. Each finding carries the
concrete fix, because a warning you don't know how to act on is just noise.

Rates reported here are *hazard rates*, not predicted accuracy: they say how
much of this document is structurally risky, not how often a given model will
trip on it. Compare them across documents, not against an eval score.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

from scoring import _PUNCT_MAP, normalize

# A model asked for a 3-8 word anchor phrase lands most often around 5 words;
# the fraction of 5-grams that are non-unique is the closest deterministic
# proxy we have for "the locator will have more than one place to put this".
ANCHOR_NGRAM = 5

# Thresholds are judgment calls, stated here rather than buried, so they can be
# tuned and disclosed (same posture as scoring.py's 0.90/0.70).
AMBIGUITY_HIGH = 0.20
AMBIGUITY_MED = 0.05
HAZARD_HIGH = 2.0   # hazard chars per 100 chars
HAZARD_MED = 0.5
CHARS_PER_TOKEN = 4  # deliberately conservative English estimate
CONTEXT_HEADROOM = 0.80  # doc+prompt should fit inside this share of num_ctx

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(doc: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(doc) if len(s.strip()) > 20]


def _ngrams(words: list[str], n: int) -> list[str]:
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def repetition_report(doc: str) -> dict:
    """How much of this document repeats itself?

    The headline number is *value-adjacent* n-gram duplication, not overall
    duplication. Measured against the eval's own runs, whole-document
    repetition badly overpredicts: hard_transcript.txt repeats 54% of its
    5-grams (conversational filler — "yeah, I think that's right") yet not one
    located anchor across 31 runs was ambiguous, because models anchor on
    phrases *near the value*, and value-adjacent text is distinctive even in a
    chatty document. hard_email_thread.txt repeats its figures along with the
    quoted replies — 75% value-adjacent — and measured 100% ambiguous.

    So: restrict the count to n-grams containing a digit, which is where
    anchors actually land. Overall rate is kept as secondary context."""
    ndoc = normalize(doc)
    words = ndoc.split()
    grams = _ngrams(words, ANCHOR_NGRAM)
    counts = Counter(grams)
    dup_grams = sum(1 for g in grams if counts[g] > 1)
    overall_rate = dup_grams / len(grams) if grams else 0.0

    value_grams = [g for g in grams if re.search(r"\d", g)]
    dup_value = sum(1 for g in value_grams if counts[g] > 1)
    gram_rate = (dup_value / len(value_grams)) if value_grams else 0.0

    sents = [normalize(s) for s in _sentences(doc)]
    scounts = Counter(sents)
    dup_sents = sum(1 for s in sents if scounts[s] > 1)
    sent_rate = dup_sents / len(sents) if sents else 0.0

    worst = [(txt, n) for txt, n in scounts.most_common(3) if n > 1]
    return {
        "ngram_ambiguity_rate": round(gram_rate, 4),
        "overall_ngram_repetition": round(overall_rate, 4),
        "n_value_ngrams": len(value_grams),
        "sentence_duplication_rate": round(sent_rate, 4),
        "n_sentences": len(sents),
        "most_repeated": [{"text": t[:80], "occurrences": n} for t, n in worst],
    }


def normalization_report(doc: str) -> dict:
    """Characters that break character-for-character quoting.

    Every one of these survives a model's paraphrase-free copy attempt only if
    the model reproduces the exact codepoint. Most don't."""
    # _PUNCT_MAP is a str.maketrans table: its keys are ordinals, not
    # characters. Testing `ch in _PUNCT_MAP` is always False and silently
    # reports zero hazards on a document full of them.
    hazards = Counter()
    for ch in doc:
        if ord(ch) in _PUNCT_MAP:
            hazards[ch] += 1
    double_spaces = len(re.findall(r"(?<=\S)  +(?=\S)", doc))
    total = sum(hazards.values()) + double_spaces
    per_100 = (total / len(doc) * 100) if doc else 0.0
    named = {
        "curly quotes": sum(hazards[c] for c in "‘’‚‛“”„‟"),
        "dashes": sum(hazards[c] for c in "–—‒―−"),
        "non-breaking / thin spaces": sum(
            hazards[c] for c in "    ⁠"),
        "ellipsis": hazards["…"],
        "double spaces": double_spaces,
    }
    return {
        "hazards_per_100_chars": round(per_100, 3),
        "total_hazards": total,
        "by_kind": {k: v for k, v in named.items() if v},
    }


def prompt_report(prompt: str) -> dict:
    """Shape checks on the extraction prompt itself."""
    p = (prompt or "").casefold()
    return {
        "asks_verbatim_quote": bool(
            re.search(r"verbatim|word[- ]for[- ]word|character[- ]for[- ]character"
                      r"|exact(ly)? (as|copy)|copy .{0,20}exact", p)),
        "asks_anchor": "anchor" in p,
        "has_refusal_path": bool(
            re.search(r"not_found|not found|if .{0,40}(absent|missing|isn't|is not)"
                      r"|say so|refuse|unable to find|no such value", p)),
        "separates_answer_and_evidence": bool(
            re.search(r"\banswer\b", p) and
            re.search(r"\bquote\b|\banchor\b|\bevidence\b|\bcitation\b", p)),
        "requests_json": bool(re.search(r"\bjson\b|\{.*\}", p, re.S)),
    }


def context_report(doc: str, prompt: str, num_ctx: int) -> dict:
    est = (len(doc) + len(prompt or "")) // CHARS_PER_TOKEN
    return {
        "estimated_prompt_tokens": est,
        "num_ctx": num_ctx,
        "fits": est <= num_ctx * CONTEXT_HEADROOM,
        "headroom_share": round(est / num_ctx, 3) if num_ctx else None,
    }


def _finding(sev: str, code: str, message: str, fix: str, evidence=None) -> dict:
    f = {"severity": sev, "code": code, "message": message, "fix": fix}
    if evidence is not None:
        f["evidence"] = evidence
    return f


def analyze(doc: str, prompt: str = "", num_ctx: int = 8192) -> dict:
    """Full preflight. Returns metrics plus actionable findings."""
    rep = repetition_report(doc)
    norm = normalization_report(doc)
    pr = prompt_report(prompt) if prompt else None
    ctx = context_report(doc, prompt, num_ctx)
    findings: list[dict] = []

    # --- anchor ambiguity ------------------------------------------------
    ar = rep["ngram_ambiguity_rate"]
    if ar >= AMBIGUITY_HIGH:
        findings.append(_finding(
            "high", "anchor_ambiguity",
            f"{ar:.0%} of value-adjacent {ANCHOR_NGRAM}-word phrases occur more "
            "than once — that is where models put anchors. A "
            "locator takes the first occurrence, so a wrong-value result here "
            "is likely 'right anchor, wrong occurrence' rather than a bad anchor.",
            "Require a second, further-away anchor phrase (or a section/line "
            "heading) and locate on the pair; treat single-anchor hits in this "
            "document as unverified.",
            rep["most_repeated"]))
    elif ar >= AMBIGUITY_MED:
        findings.append(_finding(
            "medium", "anchor_ambiguity",
            f"{ar:.0%} of value-adjacent {ANCHOR_NGRAM}-word phrases repeat — "
            "some anchors will be ambiguous.",
            "Report occurrence counts alongside each located span and review "
            "any span whose anchor matched more than once.",
            rep["most_repeated"]))

    if rep["sentence_duplication_rate"] >= AMBIGUITY_MED:
        findings.append(_finding(
            "medium", "sentence_duplication",
            f"{rep['sentence_duplication_rate']:.0%} of sentences appear more "
            "than once (quoted-reply chains, repeated headers/footers).",
            "Deduplicate or tag repeated blocks before extraction, so a located "
            "sentence can be traced to one place in the source."))

    # --- verbatim quoting hazards ---------------------------------------
    hz = norm["hazards_per_100_chars"]
    if hz >= HAZARD_HIGH:
        findings.append(_finding(
            "high", "normalization_hazard",
            f"{norm['total_hazards']} quote-breaking characters "
            f"({hz:.1f} per 100 chars): {', '.join(norm['by_kind'])}. Asking for "
            "character-for-character quotes against this text will fail on "
            "cosmetic differences a reader would never notice.",
            "Use the anchor pattern (model proposes a short phrase, code locates "
            "and emits the sentence from the source) instead of trusting quotes; "
            "if you must verify quotes, compare after unicode normalization.",
            norm["by_kind"]))
    elif hz >= HAZARD_MED:
        findings.append(_finding(
            "medium", "normalization_hazard",
            f"{norm['total_hazards']} quote-breaking characters present "
            f"({hz:.1f} per 100 chars).",
            "Normalize both sides before comparing quotes, or prefer anchors.",
            norm["by_kind"]))

    # --- prompt shape ----------------------------------------------------
    if pr:
        if pr["asks_verbatim_quote"] and hz >= HAZARD_MED:
            findings.append(_finding(
                "high", "verbatim_on_hazardous_doc",
                "The prompt demands a verbatim quote and the document is full of "
                "characters models silently substitute. This combination is the "
                "single most common source of 'the quote isn't in the document'.",
                "Switch to anchors, or accept normalized matches as valid "
                "provenance."))
        if not pr["has_refusal_path"]:
            findings.append(_finding(
                "high", "no_refusal_path",
                "The prompt offers no way to say the value is absent. Asked for "
                "a value that isn't there, a model's most likely output is a "
                "confident answer attached to a real-looking span.",
                "Add an explicit sentinel: 'If the document does not contain the "
                "value, return {\"answer\": \"NOT_FOUND\"} and nothing else.'"))
        if not pr["separates_answer_and_evidence"]:
            findings.append(_finding(
                "medium", "answer_evidence_not_separated",
                "The prompt doesn't clearly request the answer and its evidence "
                "as distinct fields. Merged fields make it easy to score (or "
                "trust) a wrong answer that happens to carry a good quote.",
                "Request strict JSON with separate 'answer' and 'anchor' keys, "
                "and check the answer field alone for correctness."))
        if not pr["requests_json"]:
            findings.append(_finding(
                "low", "unstructured_output",
                "No structured-output instruction found; free-text responses "
                "raise the unparseable rate, which honest scoring counts as a "
                "failure rather than dropping.",
                "Ask for a single JSON object and nothing else."))

    # --- context fit -----------------------------------------------------
    if not ctx["fits"]:
        findings.append(_finding(
            "high", "context_overflow",
            f"Estimated {ctx['estimated_prompt_tokens']} tokens against a "
            f"num_ctx of {num_ctx}. Ollama truncates silently, and a truncated "
            "document fails as a quoting failure — the misleading kind.",
            f"Raise num_ctx (OLLAMA_NUM_CTX) above "
            f"{int(ctx['estimated_prompt_tokens'] / CONTEXT_HEADROOM)}, or chunk "
            "the document and extract per chunk.",
            ctx))

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    return {
        "metrics": {"repetition": rep, "normalization": norm,
                    "prompt": pr, "context": ctx},
        "findings": findings,
        "risk": ("high" if any(f["severity"] == "high" for f in findings)
                 else "medium" if findings else "low"),
    }


def format_report(name: str, result: dict) -> str:
    icons = {"high": "!!", "medium": " !", "low": "  "}
    rep = result["metrics"]["repetition"]
    norm = result["metrics"]["normalization"]
    lines = [f"=== {name}  [risk: {result['risk']}]",
             f"    anchor ambiguity {rep['ngram_ambiguity_rate']:.1%}"
             f" | repeated sentences {rep['sentence_duplication_rate']:.1%}"
             f" | quote hazards {norm['hazards_per_100_chars']:.2f}/100ch"]
    if not result["findings"]:
        lines.append("    no findings - safe for verbatim-quote extraction")
    for f in result["findings"]:
        lines.append(f"  {icons[f['severity']]} [{f['code']}] {f['message']}")
        lines.append(f"       fix: {f['fix']}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]
    as_json = "--json" in flags
    prompt = ""
    for fl in flags:
        if fl.startswith("--prompt="):
            with open(fl.split("=", 1)[1], encoding="utf-8") as fh:
                prompt = fh.read()
    num_ctx = 8192
    for fl in flags:
        if fl.startswith("--num-ctx="):
            num_ctx = int(fl.split("=", 1)[1])
    if not args:
        print("usage: python preflight.py DOC.txt [DOC2.txt ...] "
              "[--prompt=FILE] [--num-ctx=N] [--json]", file=sys.stderr)
        return 2
    out = {}
    worst = "low"
    for path in args:
        with open(path, encoding="utf-8") as fh:
            doc = fh.read()
        res = analyze(doc, prompt, num_ctx)
        out[path] = res
        if res["risk"] == "high" or (res["risk"] == "medium" and worst == "low"):
            worst = res["risk"]
        if not as_json:
            print(format_report(path, res))
            print()
    if as_json:
        print(json.dumps(out, indent=2))
    return 1 if worst == "high" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
