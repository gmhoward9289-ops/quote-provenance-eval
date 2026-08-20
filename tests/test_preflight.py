from preflight import analyze


def test_analyze_returns_findings_and_reports():
    out = analyze("The value is 12. The value is 12.", prompt="Return NOT_FOUND if absent.")
    assert set(out) == {"metrics", "findings", "risk"}
    assert set(out["metrics"]) == {"repetition", "normalization", "prompt", "context"}
    assert isinstance(out["findings"], list)
    assert out["risk"] in {"high", "medium", "low"}
