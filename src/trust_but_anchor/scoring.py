"""Scoring: how faithful is a model-produced 'verbatim' quote to the source?

Fidelity levels (mutually exclusive, best wins):
  exact       — quote is a character-for-character substring of the source
  normalized  — matches after unicode/whitespace/case normalization
                (curly quotes, en/em dashes, NBSP, collapsed whitespace, casefold)
  minor_edit  — best fuzzy window ratio >= 0.90 (a few words changed/dropped)
  paraphrase  — best fuzzy window ratio >= 0.70 (recognizably derived, not a quote)
  fabricated  — below 0.70; no plausible source span

'exact' is the only level a naive string-match verifier would accept — that
rate is the headline number. 'normalized' is recoverable with cheap code.
Everything below that is unusable as provenance.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_PUNCT_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "‒": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "…": "...",
})

FUZZY_MINOR = 0.90
FUZZY_PARAPHRASE = 0.70


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_PUNCT_MAP)
    s = re.sub(r"\s+", " ", s)
    return s.strip().casefold()


def best_window_ratio(doc: str, quote: str) -> tuple[float, str]:
    """Best SequenceMatcher ratio of the (normalized) quote against sliding
    windows of the (normalized) doc. Returns (ratio, best_window_text)."""
    nq, nd = normalize(quote), normalize(doc)
    if not nq or not nd:
        return 0.0, ""
    wlen = len(nq)
    if wlen >= len(nd):
        return SequenceMatcher(None, nd, nq).ratio(), nd
    step = max(1, wlen // 5)
    best, best_win = 0.0, ""
    # coarse pass
    coarse_hits = []
    for start in range(0, len(nd) - wlen + 1, step):
        win = nd[start:start + wlen]
        r = SequenceMatcher(None, win, nq).ratio()
        coarse_hits.append((r, start))
    coarse_hits.sort(reverse=True)
    # refine around the top coarse hits
    for r0, s0 in coarse_hits[:3]:
        lo = max(0, s0 - step)
        hi = min(len(nd) - wlen, s0 + step)
        for start in range(lo, hi + 1):
            win = nd[start:start + wlen]
            r = SequenceMatcher(None, win, nq).ratio()
            if r > best:
                best, best_win = r, win
    return best, best_win


def score_quote(doc: str, quote: str) -> dict:
    quote = (quote or "").strip()
    if not quote:
        return {"level": "fabricated", "ratio": 0.0, "detail": "empty quote"}
    if quote in doc:
        return {"level": "exact", "ratio": 1.0, "detail": ""}
    if normalize(quote) and normalize(quote) in normalize(doc):
        return {"level": "normalized", "ratio": 1.0,
                "detail": diff_detail(doc, quote)}
    ratio, _ = best_window_ratio(doc, quote)
    if ratio >= FUZZY_MINOR:
        return {"level": "minor_edit", "ratio": round(ratio, 3),
                "detail": "small word-level edits"}
    if ratio >= FUZZY_PARAPHRASE:
        return {"level": "paraphrase", "ratio": round(ratio, 3),
                "detail": "recognizably derived but rewritten"}
    return {"level": "fabricated", "ratio": round(ratio, 3),
            "detail": "no plausible source span"}


_WORD_NUMBERS = [
    ("four thousand", "4000"), ("twenty", "20"), ("thirty", "30"), ("forty", "40"),
    ("fifty", "50"), ("sixty", "60"), ("seventy", "70"), ("eighty", "80"),
    ("ninety", "90"), ("eleven", "11"), ("twelve", "12"), ("ten", "10"),
    ("nine", "9"), ("eight", "8"), ("seven", "7"), ("six", "6"), ("five", "5"),
    ("four", "4"), ("three", "3"), ("two", "2"), ("one", "1"),
]


def canon_value(s: str) -> str:
    """Canonical form for VALUE comparison: normalized, currency symbols and
    digit-group commas stripped, common number words as digits."""
    s = normalize(s)
    s = re.sub(r"[$€£]", "", s)
    s = re.sub(r"(?<=\d),(?=\d)", "", s)
    for word, digit in _WORD_NUMBERS:
        s = re.sub(rf"(?<![a-z0-9]){word}(?![a-z0-9])", digit, s)
    return s.strip()


def values_match(expected: str, candidate: str) -> bool:
    """Does the candidate text contain the expected value, allowing benign
    formatting drift (commas, $, digit words, dash style)? Fall back to
    'the numeric tokens of the expected value appear, whole and in order'.
    Ordered whole-token matching keeps '6-3' from matching a sentence that
    merely mentions a 3 and then a 6, or '63' — but still accepts
    'six votes to three'."""
    ne, nc = canon_value(expected), canon_value(candidate or "")
    if not ne or not nc:
        return False
    if ne in nc:
        return True
    nums = re.findall(r"\d+(?:\.\d+)?", ne)
    if nums:
        cand_nums = re.findall(r"\d+(?:\.\d+)?", nc)
        it = iter(cand_nums)
        return all(n in it for n in nums)
    return False


def diff_detail(doc: str, quote: str) -> str:
    """Why did a normalized-but-not-exact quote miss? Best-effort labels."""
    reasons = []
    if re.sub(r"\s+", " ", quote) != quote:
        reasons.append("whitespace")
    if quote.translate(_PUNCT_MAP) != quote:
        reasons.append("unicode punctuation in quote")
    else:
        # quote used straight chars where doc had curly/en-dash, or vice versa
        reasons.append("unicode punctuation / case")
    return ", ".join(reasons)
