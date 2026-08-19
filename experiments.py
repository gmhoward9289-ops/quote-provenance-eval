"""Three controlled experiments, each changing one thing against a known baseline.

The 52-model sweep measured models. These test claims the *tooling* makes, which
is the more useful thing to be wrong about:

A. fewshot — granite3.3:8b scored 53% anchor coverage by returning descriptions
   of the value instead of text copied from the document. The base prompt
   already says "copied". Does a worked example do what the instruction alone
   did not? Controls (qwen2.5-coder:7b at 100%, exaone3.5:7.8b at 97%) guard
   against the example simply making everything better, or worse.

B. refusal — absent-value refusal ranged from 10% to 100% under the base prompt.
   Run the weakest refusers again with an emphatic refusal instruction. If they
   recover, "unsafe model" was partly "under-specified prompt", and that changes
   what the profile pages should say.

C. anchor2 — on the hard email thread every located anchor was ambiguous, so a
   value-miss there may be "right anchor, wrong occurrence". Ask for a second
   nearby phrase and pick the occurrence nearest it. This is the fix preflight
   recommends and has never been measured.

Every run writes its own results file (variant and arm are in the filename), so
nothing here overwrites the baseline it is being compared against.
"""
from __future__ import annotations

import subprocess
import sys
import time

PY = sys.executable
LOG = "results/experiments.log"

RUNS = [
    # (label, model, corpus, arm, variant)
    # A — does a worked example fix the describer?
    ("A/fewshot", "granite3.3:8b", None, "anchor", "fewshot"),
    ("A/control", "qwen2.5-coder:7b", None, "anchor", "fewshot"),
    ("A/control", "exaone3.5:7.8b", None, "anchor", "fewshot"),
    # B — does an emphatic refusal instruction fix the weak refusers?
    ("B/refusal", "tulu3:8b", "corpus/questions_absent.json", "both", "refusal"),
    ("B/refusal", "llama3.2:3b", "corpus/questions_absent.json", "both", "refusal"),
    ("B/refusal", "dolphin3:8b", "corpus/questions_absent.json", "both", "refusal"),
    ("B/refusal", "zephyr:7b", "corpus/questions_absent.json", "both", "refusal"),
    ("B/control", "exaone3.5:7.8b", "corpus/questions_absent.json", "both", "refusal"),
    # C — does a second anchor beat ambiguity on the repetitive corpus?
    ("C/anchor2", "qwen2.5-coder:7b", "corpus/questions_hard.json", "anchor2", "base"),
    ("C/anchor2", "exaone3.5:7.8b", "corpus/questions_hard.json", "anchor2", "base"),
    ("C/anchor2", "gemma2:9b", "corpus/questions_hard.json", "anchor2", "base"),
]

THINKING = ("gpt-oss", "qwen3", "deepseek-r1")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    import os
    env = dict(os.environ, OLLAMA_HOST="http://127.0.0.1:11434",
               OLLAMA_NUM_CTX="8192")
    log(f"=== {len(RUNS)} experiment runs queued")
    for label, model, corpus, arm, variant in RUNS:
        cmd = [PY, "eval.py", "run", "--provider", "ollama", "--model", model,
               "--repeats", "3", "--arm", arm, "--variant", variant]
        if corpus:
            cmd += ["--questions", corpus]
        e = dict(env)
        if any(t in model for t in THINKING):
            e["OLLAMA_THINK"] = "false"
        log(f"--- {label} {model} arm={arm} variant={variant}")
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200, env=e)
        if p.returncode != 0:
            log(f"    FAILED: {p.stderr.strip()[-300:]}")
        else:
            head = [l for l in p.stdout.splitlines() if "Headline" in l or "coverage" in l]
            log(f"    ok in {time.time() - t0:.0f}s. {head[-1][:150] if head else ''}")
        subprocess.run(["ollama", "stop", model], capture_output=True)
    log("=== experiments complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
