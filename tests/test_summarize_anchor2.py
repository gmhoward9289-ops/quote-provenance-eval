"""summarize() must count arm=anchor2 rows in n_anchor / coverage."""

from eval import summarize


def _row(arm: str, located: bool = True, value_in_span: bool = True) -> dict:
    return {
        "arm": arm,
        "raw_response": "{}",
        "located": located,
        "value_in_span": value_in_span,
        "locate": {"method": "exact" if located else "not_found", "occurrences": 1},
        "answer_correct": True,
        "rep": 1,
    }


def test_summarize_counts_anchor2_as_anchor_family():
    rows = [_row("anchor2") for _ in range(5)]
    s = summarize(rows)
    assert s["n_anchor"] == 5
    assert s["n_quote"] == 0
    assert s["anchor_located_rate"] == 1.0
    assert s["anchor_coverage"] == 1.0
    assert "ci95" in s and "anchor_coverage" in s["ci95"]


def test_summarize_mixes_anchor_and_anchor2():
    rows = [_row("anchor"), _row("anchor2", located=False, value_in_span=False)]
    s = summarize(rows)
    assert s["n_anchor"] == 2
    assert s["anchor_located_rate"] == 0.5
    assert s["anchor_coverage"] == 0.5
