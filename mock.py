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


def mock_response(question: dict, arm: str, profile: str) -> str:
    if profile not in PROFILES:
        raise ValueError(f"unknown mock profile {profile!r}; choose from {list(PROFILES)}")
    rng = random.Random(f"{question['id']}:{profile}:{arm}")
    mode = _pick_mode(profile, rng)
    answer = question["expect_value"]

    if arm == "quote":
        quote = _corrupt(question["gt_quote"], mode, rng, answer)
        return json.dumps({"answer": answer, "quote": quote, "_mock_mode": mode})

    # anchor arm: pick 4-6 consecutive words near the value, then corrupt
    words = question["gt_quote"].split()
    n = min(len(words), rng.randrange(4, 7))
    start = rng.randrange(0, max(1, len(words) - n + 1))
    anchor = " ".join(words[start:start + n])
    if mode == "fabricate":
        anchor = "somewhere in the appendix table"
    else:
        anchor = _corrupt(anchor, mode, rng, answer)
    return json.dumps({"answer": answer, "anchor": anchor, "_mock_mode": mode})
