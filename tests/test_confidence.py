from anchor import locate
from confidence import score
from trust_but_anchor.confidence import (
    AMBIGUITY_PROVENANCE_PENALTY,
    AMBIGUITY_TARGET_PROV,
    METHOD_PRIOR,
)


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


def test_ambiguity_penalty_targets_exact_prov_044():
    """exact+ambiguous → C_prov = 0.44 (factor ≈ 0.449 on exact prior)."""
    exact_prior = METHOD_PRIOR["exact"][0]
    assert AMBIGUITY_TARGET_PROV == 0.44
    assert AMBIGUITY_PROVENANCE_PENALTY == AMBIGUITY_TARGET_PROV / exact_prior

    doc = "the rate is fine. later the rate is fine again."
    loc = locate(doc, "the rate is fine")
    assert loc["method"] == "exact"
    assert loc.get("occurrences", 0) > 1
    out = score(loc, value_in_span=True)
    assert out["answer_confidence"] == round(exact_prior, 3)
    assert out["provenance_confidence"] == AMBIGUITY_TARGET_PROV
    assert out["needs_review"] is True
