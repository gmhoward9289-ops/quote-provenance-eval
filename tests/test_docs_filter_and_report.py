"""Tests for --docs filtering and report anchor-method breakdowns (#7, #8)."""

import json
import tempfile
from pathlib import Path

import pytest

from eval import (
    filter_questions_by_docs,
    format_anchor_breakdown_lines,
    summarize,
)


QUESTIONS = [
    {"id": "q1", "doc": "messy_memo.txt", "question": "x"},
    {"id": "q2", "doc": "quarterly_report.txt", "question": "y"},
    {"id": "q3", "doc": "messy_memo.txt", "question": "z"},
]


def test_filter_docs_keeps_matching_basenames():
    out = filter_questions_by_docs(QUESTIONS, "messy_memo.txt")
    assert [q["id"] for q in out] == ["q1", "q3"]


def test_filter_docs_comma_separated():
    out = filter_questions_by_docs(
        QUESTIONS, "quarterly_report.txt, messy_memo.txt"
    )
    assert len(out) == 3


def test_filter_docs_unknown_lists_available():
    with pytest.raises(ValueError, match="unknown doc") as ei:
        filter_questions_by_docs(QUESTIONS, "no_such.txt,messy_memo.txt")
    msg = str(ei.value)
    assert "no_such.txt" in msg
    assert "messy_memo.txt" in msg
    assert "quarterly_report.txt" in msg


def test_filter_docs_empty_passthrough():
    assert filter_questions_by_docs(QUESTIONS, "") is QUESTIONS or \
           filter_questions_by_docs(QUESTIONS, "") == QUESTIONS
    assert filter_questions_by_docs(QUESTIONS, "  ,  ") == QUESTIONS


def test_summarize_exposes_methods_and_ambiguous():
    rows = [
        {
            "arm": "anchor",
            "raw_response": "{}",
            "located": True,
            "value_in_span": True,
            "locate": {"method": "exact", "occurrences": 2},
            "answer_correct": True,
            "rep": 1,
        },
        {
            "arm": "anchor",
            "raw_response": "{}",
            "located": True,
            "value_in_span": False,
            "locate": {"method": "normalized", "occurrences": 1},
            "answer_correct": True,
            "rep": 1,
        },
        {
            "arm": "anchor",
            "raw_response": "{}",
            "located": False,
            "value_in_span": False,
            "locate": {"method": "not_found"},
            "answer_correct": False,
            "rep": 1,
        },
    ]
    s = summarize(rows)
    assert s["anchor_methods"] == {"exact": 1, "normalized": 1, "not_found": 1}
    assert s["anchor_ambiguous"] == 1


def test_format_anchor_breakdown_includes_methods_and_ambiguous():
    run = {
        "provider": "mock",
        "model": "sloppy",
        "corpus": "questions",
        "arms": ["quote", "anchor"],
        "variant": "base",
        "summary": {
            "n_anchor": 3,
            "anchor_methods": {"exact": 2, "not_found": 1},
            "anchor_ambiguous": 1,
            "anchor_located_rate": 0.667,
            "anchor_coverage": 0.667,
        },
    }
    lines = format_anchor_breakdown_lines([run])
    text = "\n".join(lines)
    assert "## Anchor methods and ambiguity" in text
    assert "`mock` `sloppy`" in text
    assert "exact 2" in text
    assert "ambiguous:** 1 / 2 located" in text


def test_format_anchor_breakdown_skips_quote_only():
    run = {
        "provider": "mock",
        "model": "faithful",
        "corpus": "questions",
        "arms": ["quote"],
        "summary": {"n_quote": 5, "quote_exact_rate": 1.0},
    }
    lines = format_anchor_breakdown_lines([run])
    text = "\n".join(lines)
    assert "No runs in this report include anchor-arm" in text
