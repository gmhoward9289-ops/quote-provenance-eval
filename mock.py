"""Mock provider: simulates a model with controllable sloppiness so the whole
pipeline can be tested without API keys. Deterministic per (question, profile).

Profiles (pass as --model):
  faithful — mostly exact quotes; occasional normalization slips
  sloppy   — the interesting one; roughly matches the failure mix that
             motivated this eval
  chaotic  — worst case; heavy paraphrase and fabrication
"""
from __future__ import annotations

import json
import random

_STRAIGHTEN = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})

_SYNONYMS = {
    "reached": "hit",
    "approximately": "about",
    "occurred": "happened",
    "during": "in",
    "versus": "vs",
    "estimated": "projected",
    "possessed,": "had,",
    "generated": "produced",
}

PROFILES = {
    "faithful": [("exact", 0.85), ("unicode", 0.05), ("whitespace", 0.05), ("drop_word", 0.05)],
    "sloppy":   [("exact", 0.55), ("unicode", 0.15), ("whitespace", 0.10), ("drop_word", 0.10),
                 ("paraphrase", 0.07), ("fabricate", 0.03)],
    "chaotic":  [("exact", 0.30), ("unicode", 0.15), ("whitespace", 0.15), ("drop_word", 0.15),
                 ("paraphrase", 0.15), ("fabricate", 0.10)],
}


def _pick_mode(profile: str, rng: random.Random) -> str:
    modes = PROFILES[profile]
    x = rng.random()
    acc = 0.0
    for mode, w in modes:
        acc += w
        if x <= acc:
            return mode
    return modes[-1][0]


def _corrupt(text: str, mode: str, rng: random.Random, answer: str) -> str:
    words = text.split()
    if mode == "exact":
        return text
    if mode == "unicode":
        return text.translate(_STRAIGHTEN)
    if mode == "whitespace":
        if len(words) > 3:
            i = rng.randrange(1, len(words) - 1)
            words.insert(i, "")  # double space
        return " ".join(words).rstrip(".")
    if mode == "drop_word":
        if len(words) > 5:
            words.pop(rng.randrange(1, len(words) - 2))
        return " ".join(words)
    if mode == "paraphrase":
        out = [_SYNONYMS.get(w.lower(), w) for w in words]
        out = [w for w in out if w.lower() not in ("the", "a", "an")]
        return " ".join(out)
    if mode == "fabricate":
        return f"The document clearly states that the figure in question was {answer}."
    return text


_ABSENT_REFUSE_P = {"faithful": 1.0, "sloppy": 0.8, "chaotic": 0.5}


def mock_response(question: dict, arm: str, profile: str) -> str:
    if profile not in PROFILES:
        raise ValueError(f"unknown mock profile {profile!r}; choose from {list(PROFILES)}")
    rng = random.Random(f"{question['id']}:{profile}:{arm}")

    if question.get("expect_absent"):
        key = "quote" if arm == "quote" else "anchor"
        if rng.random() <= _ABSENT_REFUSE_P[profile]:
            return json.dumps({"answer": "NOT_FOUND", key: "", "_mock_mode": "refuse"})
        # the scary failure: a confident invented value backed by a real
        # (but irrelevant) span from the document
        fake = f"${rng.randrange(10, 99)}.{rng.randrange(1, 9)} million"
        span = question.get("distractor_quote", "the figure was confirmed in the appendix")
        if arm == "anchor":
            span = " ".join(span.split()[:5])
        return json.dumps({"answer": fake, key: span, "_mock_mode": "fabricate_absent"})

    mode = _pick_mode(profile, rng)
    answer = question["expect_value"]

    if arm == "quote":
        quote = _corrupt(question["gt_quote"], mode, rng, answer)
        return json.dumps({"answer": answer, "quote": quote, "_mock_mode": mode})

    # anchor / anchor2: pick 4-6 consecutive words near the value, then corrupt
    words = question["gt_quote"].split()
    n = min(len(words), rng.randrange(4, 7))
    start = rng.randrange(0, max(1, len(words) - n + 1))
    anchor = " ".join(words[start:start + n])
    if mode == "fabricate":
        anchor = "somewhere in the appendix table"
    else:
        anchor = _corrupt(anchor, mode, rng, answer)
    payload = {"answer": answer, "anchor": anchor, "_mock_mode": mode}
    if arm == "anchor2":
        # second phrase elsewhere in the same gt sentence (or a short suffix)
        rest = words[start + n:] or words[:start] or words[-3:]
        n2 = min(len(rest), rng.randrange(3, 6) if len(rest) >= 3 else len(rest) or 1)
        anchor2 = " ".join(rest[:n2]) if rest else " ".join(words[-3:])
        if mode == "fabricate":
            anchor2 = "appendix cross-reference note"
        else:
            anchor2 = _corrupt(anchor2, mode, rng, answer)
        payload["anchor2"] = anchor2
    return json.dumps(payload)
