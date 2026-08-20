from anchor import locate
from confidence import score


def test_not_found_has_low_answer_confidence():
    loc = locate("hello", "nope")
    out = score(loc)
    assert loc["method"] == "not_found"
    assert out["answer_confidence"] < 0.1


def test_exact_unique_span_is_high_provenance():
    loc = locate("only once: 42.", "only once: 42")
    out = score(loc, value_in_span=True)
    assert loc["method"] == "exact"
    assert out["provenance_confidence"] >= 0.9
