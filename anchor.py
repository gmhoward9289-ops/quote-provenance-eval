"""Anchored extraction: the model proposes, code locates.

Instead of trusting the model's quoted text, we ask it only for a short
anchor phrase near the value. Deterministic code then finds that anchor in
the source (exact -> normalized -> fuzzy) and emits the surrounding sentence
FROM THE SOURCE TEXT. Any span this module returns is a real substring of
the document by construction — provenance fidelity is 100% for every
located anchor. The metric that can fail is coverage: did we locate the
anchor, and does the located span contain the expected value?
"""
from __future__ import annotations

import re
from scoring import best_window_ratio, normalize

LOCATE_FUZZY_THRESHOLD = 0.75
SUBSEQ_MAX_STRETCH = 4.0  # located window may be at most 4x the anchor length


def _find_token_subsequence(ndoc: str, tokens: list) -> tuple | None:
    """Find the tightest window in ndoc containing all tokens in order as
    whole words. Returns (start, end) in ndoc coords, or None."""
    import re as _re
    anchor_len = sum(len(t) for t in tokens) + len(tokens) - 1
    max_window = int(anchor_len * SUBSEQ_MAX_STRETCH)
    best = None
    for m0 in _re.finditer(r"(?<![a-z0-9])" + _re.escape(tokens[0]) + r"(?![a-z0-9])", ndoc):
        pos = m0.end()
        ok = True
        for t in tokens[1:]:
            m = _re.search(r"(?<![a-z0-9])" + _re.escape(t) + r"(?![a-z0-9])", ndoc[pos:pos + max_window])
            if not m:
                ok = False
                break
            pos += m.end()
        if ok and pos - m0.start() <= max_window:
            span = (m0.start(), pos)
            if best is None or (span[1] - span[0]) < (best[1] - best[0]):
                best = span
    return best

_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")


def _norm_index_map(doc: str) -> tuple[str, list[int]]:
    """Normalized doc plus a map from normalized index -> original index.

    Mirrors scoring.normalize (NFKC, punctuation map, collapsed whitespace,
    casefold) but preserves per-character provenance so a match in normalized
    space can be projected back onto the original document."""
    import unicodedata
    from scoring import _PUNCT_MAP

    out: list[str] = []
    idx_map: list[int] = []
    pending_space = False
    # Normalize base+combining-mark clusters as units, not single chars —
    # per-char NFKC would leave 'e' + U+0301 decomposed while the full-string
    # normalize() in scoring composes it to 'é', silently breaking matches.
    i, L = 0, len(doc)
    while i < L:
        j = i + 1
        while j < L and unicodedata.combining(doc[j]):
            j += 1
        n = unicodedata.normalize("NFKC", doc[i:j]).translate(_PUNCT_MAP).casefold()
        for c in n:
            if c.isspace():
                pending_space = True
                continue
            if pending_space and out:
                out.append(" ")
                idx_map.append(idx_map[-1])
            pending_space = False
            out.append(c)
            idx_map.append(i)
        i = j
    return "".join(out), idx_map


def _expand_to_sentence(doc: str, start: int, end: int) -> str:
    """Expand [start, end) to containing sentence/line boundaries in the doc."""
    left = 0
    for m in re.finditer(r"[.!?]\s|\n", doc[:start]):
        left = m.end()
    m = re.search(r"[.!?](?=\s|$)|\n", doc[end:])
    right = end + (m.end() if m else len(doc) - end)
    return doc[left:right].strip()


def _all_norm_occurrences(ndoc: str, needle: str) -> list:
    """Every start index of `needle` in the normalized doc."""
    out, start = [], 0
    if not needle:
        return out
    while True:
        i = ndoc.find(needle, start)
        if i == -1:
            return out
        out.append(i)
        start = i + 1


def locate_pair(doc: str, anchor: str, anchor2: str) -> dict:
    """Locate `anchor`, using `anchor2` to choose between repeated occurrences.

    Single-anchor location silently takes the first match, which is fine until
    the document repeats itself — quoted-reply email chains, repeated headers.
    Measured on this corpus, every located anchor in the hard email thread was
    ambiguous. Asking the model for a second, further-away phrase and picking
    the occurrence of the first that sits nearest an occurrence of the second
    is the cheapest fix that doesn't require the model to be more careful.

    Falls back to plain locate() whenever the second anchor doesn't help:
    missing, unfindable, or the first anchor was unique anyway. The returned
    dict carries `disambiguated` so a caller can tell which happened."""
    base = locate(doc, anchor)
    if base.get("method") == "not_found":
        return {**base, "disambiguated": False}
    if (base.get("occurrences") or 0) <= 1 or not (anchor2 or "").strip():
        return {**base, "disambiguated": False}

    ndoc, idx_map = _norm_index_map(doc)
    n1, n2 = normalize(anchor), normalize(anchor2)
    hits1 = _all_norm_occurrences(ndoc, n1)
    hits2 = _all_norm_occurrences(ndoc, n2)
    if len(hits1) <= 1 or not hits2:
        return {**base, "disambiguated": False}

    # the occurrence of anchor1 closest to any occurrence of anchor2
    best = min(hits1, key=lambda p: min(abs(p - q) for q in hits2))
    o_start = idx_map[best]
    o_end = idx_map[min(best + len(n1) - 1, len(idx_map) - 1)] + 1
    return {
        "method": "pair",
        "span": doc[o_start:o_end],
        "occurrences": len(hits1),
        "sentence": _expand_to_sentence(doc, o_start, o_end),
        "disambiguated": True,
        "chose_occurrence": hits1.index(best) + 1,
    }


def locate(doc: str, anchor: str) -> dict:
    """Locate an anchor phrase in the doc. Returns:
    {method, span, sentence, occurrences} — span/sentence are exact doc
    substrings; occurrences counts how often the matched span's normalized
    text appears in the normalized doc (>1 = ambiguous anchor: the locator
    takes the first occurrence, so a value-miss may be "right anchor, wrong
    occurrence") — or {method: 'not_found'}."""
    anchor = (anchor or "").strip().strip('"').strip("'")
    if not anchor:
        return {"method": "not_found"}

    ndoc, idx_map = _norm_index_map(doc)
    nanchor = normalize(anchor)

    def occurrences(nspan: str) -> int:
        return ndoc.count(nspan) if nspan else 0

    # 1. exact
    pos = doc.find(anchor)
    if pos != -1:
        return {"method": "exact", "span": anchor,
                "occurrences": max(doc.count(anchor), occurrences(nanchor)),
                "sentence": _expand_to_sentence(doc, pos, pos + len(anchor))}

    # 2. normalized
    npos = ndoc.find(nanchor)
    if nanchor and npos != -1:
        o_start = idx_map[npos]
        o_end = idx_map[min(npos + len(nanchor) - 1, len(idx_map) - 1)] + 1
        return {"method": "normalized", "span": doc[o_start:o_end],
                "occurrences": occurrences(nanchor),
                "sentence": _expand_to_sentence(doc, o_start, o_end)}

    # 3. ordered token subsequence — anchor words all present, in order,
    # within a tight window (models often drop parentheticals/asides)
    tokens = [t for t in nanchor.split() if t]
    if len(tokens) >= 2:
        hit = _find_token_subsequence(ndoc, tokens)
        if hit:
            npos, nend = hit
            o_start = idx_map[npos]
            o_end = idx_map[min(nend - 1, len(idx_map) - 1)] + 1
            return {"method": "subsequence", "span": doc[o_start:o_end],
                    "occurrences": occurrences(ndoc[npos:nend]),
                    "sentence": _expand_to_sentence(doc, o_start, o_end)}

    # 4. fuzzy — best window, then re-find that window's chars
    ratio, best_win = best_window_ratio(doc, anchor)
    if ratio >= LOCATE_FUZZY_THRESHOLD and best_win:
        wpos = ndoc.find(best_win)
        if wpos != -1:
            o_start = idx_map[wpos]
            o_end = idx_map[min(wpos + len(best_win) - 1, len(idx_map) - 1)] + 1
            return {"method": "fuzzy", "ratio": round(ratio, 3),
                    "span": doc[o_start:o_end],
                    "occurrences": occurrences(best_win),
                    "sentence": _expand_to_sentence(doc, o_start, o_end)}

    return {"method": "not_found"}
