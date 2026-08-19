"""Confidence earned from verification, not self-reported by the model.

Asking a model how sure it is produces a number it made up. This module scores
an extraction from what deterministic code could actually confirm about it:
how the anchor was located, whether that location is unique in the document,
and whether the located span carries the expected value.

Two scores, because the runs show they are different questions:

  answer_confidence      — will the answer turn out to be right?
  provenance_confidence  — is the emitted span trustworthy AS EVIDENCE,
                           i.e. can a reader check it and land in one place?

Splitting them is not tidiness. Measured over this repo's stored runs
(local 7-20B models, 1,400+ anchor-arm rows), an *ambiguous* exact anchor —
one whose phrase occurs more than once, so the locator silently took the
first hit — still yielded a correct answer 24/24 times. Ambiguity did not
damage the answer; it damaged the citation, because the sentence shown to
the reader may be the wrong instance of a repeated phrase. A single blended
number would have hidden that entirely.

The other measured surprise: an exact anchor whose located span did NOT
contain the expected value still had a correct answer 22/22 times. So
`value_in_span` is a coverage metric for the eval, not evidence the answer
is wrong — it means the anchor landed a sentence away, not that the model
hallucinated. It lowers provenance confidence, not answer confidence.

CALIBRATION SOURCE AND ITS LIMITS
---------------------------------
Rates below are pooled across this repo's non-mock runs. They describe local
open-weight models on short synthetic documents; a frontier model on scanned
OCR text will not have these rates. Treat them as a starting prior to be
re-derived on your own data with `calibrate()`, not as universal constants.
Cells with n < 20 are marked and rounded conservatively.
"""
from __future__ import annotations

import ast
import glob
import json
from collections import defaultdict

# P(answer correct | locate method), measured. n is carried so a caller can
# see which cells are thin rather than trusting a bare probability.
METHOD_PRIOR = {
    "exact":       (0.98, 1104),
    "normalized":  (0.97, 131),
    "subsequence": (0.99, 23),   # thin: n<20 per-cell in places, rounded down
    "fuzzy":       (0.94, 38),
    "not_found":   (0.03, 155),  # fails closed, and correctly so
}

# Located-but-ambiguous anchors: the locator took the first of several
# identical spans. Answer is untouched; the citation is a coin-flip over
# however many occurrences there were.
AMBIGUITY_PROVENANCE_PENALTY = 0.45

# Located span didn't carry the expected value: the anchor landed near, not on.
VALUE_MISSING_PROVENANCE_PENALTY = 0.35

REVIEW_THRESHOLD = 0.80


def score(locate: dict, value_in_span: bool | None = None,
          expected_value: str | None = None) -> dict:
    """Score one anchored extraction.

    `locate` is anchor.locate()'s return value. Returns both confidences, the
    signals they came from, and a plain-English reason — the reason is the
    point: a number a reviewer can't interrogate is only marginally better
    than the model's own guess."""
    method = (locate or {}).get("method", "not_found")
    occurrences = (locate or {}).get("occurrences")
    prior, n = METHOD_PRIOR.get(method, (0.5, 0))

    answer = prior
    prov = prior
    reasons = []

    if method == "not_found":
        return {
            "answer_confidence": round(prior, 3),
            "provenance_confidence": 0.0,
            "needs_review": True,
            "signals": {"method": method, "occurrences": occurrences},
            "reason": "The anchor could not be located in the source. Nothing "
                      "here is verified: no span was emitted, and answers in "
                      "this state were correct only 3% of the time.",
            "calibration_n": n,
        }

    reasons.append(f"anchor located by {method} match"
                   + (f" (measured {prior:.0%} correct over n={n})" if n else ""))

    if occurrences is None:
        prov *= 0.9
        reasons.append("occurrence count unavailable, so uniqueness of the "
                       "citation is unverified")
    elif occurrences > 1:
        prov *= AMBIGUITY_PROVENANCE_PENALTY
        reasons.append(f"the anchor phrase occurs {occurrences} times and the "
                       "locator took the first — the answer is unaffected but "
                       "the sentence shown may be the wrong instance")

    if value_in_span is False:
        prov *= VALUE_MISSING_PROVENANCE_PENALTY
        reasons.append("the located sentence does not contain the expected "
                       "value, so it supports the answer only indirectly")
    elif value_in_span is True:
        reasons.append("the located sentence contains the value")

    return {
        "answer_confidence": round(min(answer, 1.0), 3),
        "provenance_confidence": round(min(prov, 1.0), 3),
        "needs_review": min(answer, prov) < REVIEW_THRESHOLD,
        "signals": {"method": method, "occurrences": occurrences,
                    "value_in_span": value_in_span},
        "reason": "; ".join(reasons) + ".",
        "calibration_n": n,
    }


def calibrate(pattern: str = "results/run_*.json",
              include_mock: bool = False) -> dict:
    """Re-derive METHOD_PRIOR from stored runs.

    This is the whole reason raw responses are kept: priors that came from
    measurement can be re-measured when the locator, the corpus, or the model
    lineup changes. Returns {method: {rate, n}} plus ambiguity breakdown."""
    by_method = defaultdict(lambda: [0, 0])
    by_amb = defaultdict(lambda: [0, 0])
    for path in glob.glob(pattern):
        if not include_mock and "mock" in path:
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for row in data.get("rows", []):
            if row.get("arm") != "anchor":
                continue
            loc = row.get("locate")
            if isinstance(loc, str):
                try:
                    loc = ast.literal_eval(loc)
                except (ValueError, SyntaxError):
                    continue
            if not isinstance(loc, dict):
                continue
            ok = str(row.get("answer_correct")) == "True"
            m = loc.get("method", "none")
            by_method[m][1] += 1
            by_method[m][0] += ok
            occ = loc.get("occurrences")
            if occ is not None and m != "not_found":
                key = "ambiguous" if occ > 1 else "unique"
                by_amb[key][1] += 1
                by_amb[key][0] += ok
    return {
        "by_method": {m: {"rate": round(c / n, 4), "n": n}
                      for m, (c, n) in sorted(by_method.items()) if n},
        "by_ambiguity": {k: {"rate": round(c / n, 4), "n": n}
                         for k, (c, n) in by_amb.items() if n},
    }


if __name__ == "__main__":
    import sys
    if "--calibrate" in sys.argv:
        print(json.dumps(calibrate(), indent=2))
    else:
        demo = [
            ({"method": "exact", "occurrences": 1}, True),
            ({"method": "exact", "occurrences": 7}, True),
            ({"method": "fuzzy", "occurrences": 1}, False),
            ({"method": "not_found"}, None),
        ]
        for loc, vis in demo:
            r = score(loc, vis)
            print(f"{loc.get('method'):11s} occ={str(loc.get('occurrences')):4s} "
                  f"val={str(vis):5s} -> answer {r['answer_confidence']:.2f} "
                  f"provenance {r['provenance_confidence']:.2f} "
                  f"{'REVIEW' if r['needs_review'] else 'ok'}")
            print(f"    {r['reason']}")
