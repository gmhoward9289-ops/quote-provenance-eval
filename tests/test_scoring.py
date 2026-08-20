from scoring import normalize, score_quote


def test_exact_quote():
    doc = "alpha beta gamma"
    assert score_quote(doc, "alpha beta")["level"] == "exact"


def test_empty_quote_is_fabricated():
    assert score_quote("abc", "")["level"] == "fabricated"


def test_normalize_collapses_nbsp_and_case():
    assert normalize("A\u00a0B") == normalize("a b")
