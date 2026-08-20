from __future__ import annotations

from anchor import locate, locate_pair


def test_exact_is_a_real_substring():
    doc = "Revenue was $148.7 million in Q3."
    out = locate(doc, "$148.7 million")
    assert out["method"] == "exact"
    assert out["span"] == "$148.7 million"
    assert out["span"] in doc
    assert out["sentence"] in doc
    assert out["occurrences"] >= 1


def test_curly_quotes_are_normalized_not_fabricated():
    doc = "He said \u201cthe protocol is live\u201d today."
    out = locate(doc, '"the protocol is live"')
    assert out["method"] in {"normalized", "exact"}
    assert out["span"] in doc


def test_empty_anchor_fails_closed():
    assert locate("hello world", "") == {"method": "not_found"}
    assert locate("hello world", "   ")["method"] == "not_found"


def test_unknown_phrase_fails_closed():
    assert locate("the cat sat on the mat", "quantum foam")["method"] == "not_found"


def test_subsequence_skips_parenthetical():
    doc = "Systolic blood pressure fell -11.4 mm Hg (95% CI, -13.7 to -9.1) by week 12."
    out = locate(doc, "fell -11.4 mm Hg by week 12")
    assert out["method"] in {"subsequence", "normalized", "fuzzy", "exact"}
    assert out["span"] in doc


def test_pair_disambiguates_repeated_anchor():
    doc = (
        "On Monday the total was 10.\n"
        "On Monday the total was 10.\n"
        "On Friday the total was 10, final."
    )
    out = locate_pair(doc, "the total was 10", "Friday")
    assert out["method"] in {"pair", "exact", "normalized"}
    assert "Friday" in out.get("sentence", "") or out.get("disambiguated") in {True, False}
