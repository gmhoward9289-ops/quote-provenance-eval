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
    for i, ch in enumerate(doc):
        n = unicodedata.normalize("NFKC", ch).translate(_PUNCT_MAP).casefold()
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
    return "".join(out), idx_map


def _expand_to_sentence(doc: str, start: int, end: int) -> str:
    """Expand [start, end) to containing sentence/line boundaries in the doc."""
    left = 0
    for m in re.finditer(r"[.!?]\s|\n", doc[:start]):
        left = m.end()
    m = re.search(r"[.!?](?=\s|$)|\n", doc[end:])
    right = end + (m.end() if m else len(doc) - end)
    return doc[left:right].strip()


def locate(doc: str, anchor: str) -> dict:
    """Locate an anchor phrase in the doc. Returns:
    {method, span, sentence} — span/sentence are exact doc substrings —
    or {method: 'not_found'}."""
    anchor = (anchor or "").strip().strip('"').strip("'")
    if not anchor:
        return {"method": "not_found"}

    # 1. exact
    pos = doc.find(anchor)
    if pos != -1:
        return {"method": "exact", "span": anchor,
                "sentence": _expand_to_sentence(doc, pos, pos + len(anchor))}

    # 2. normalized
    ndoc, idx_map = _norm_index_map(doc)
    nanchor = normalize(anchor)
    npos = ndoc.find(nanchor)
    if nanchor and npos != -1:
        o_start = idx_map[npos]
        o_end = idx_map[min(npos + len(nanchor) - 1, len(idx_map) - 1)] + 1
        return {"method": "normalized", "span": doc[o_start:o_end],
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
                    "sentence": _expand_to_sentence(doc, o_start, o_end)}

    return {"method": "not_found"}
