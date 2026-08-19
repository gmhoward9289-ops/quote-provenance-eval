"""Second sweep batch: families the first pass didn't cover.

Same machinery as nightrun.py — this only swaps the model list, so results,
power metrics and logs all append to the same files. Tags that don't exist
are logged and skipped, so an optimistic list costs nothing but a failed pull.
"""
from __future__ import annotations

import nightrun

nightrun.MODELS = [
    # NB: aya-expanse:8b, command-r7b and mistral-nemo:12b are deliberately
    # absent — batch 1 already covers them, and a duplicate run costs ~30
    # minutes of GPU that an untested model could have had.
    # Mistral family beyond the 7b already measured
    "mistral-small:22b", "ministral:8b",
    # IBM Granite line
    "granite3.2:8b", "granite3.1-dense:8b", "granite3-moe:3b",
    # Qwen line, remaining sizes and variants
    "qwen2.5:3b", "qwen2.5-coder:14b", "qwen3:14b", "qwq:32b",
    # Meta / Google remainder
    "llama3.2:1b", "llama3.3:70b", "gemma3:4b", "gemma3:27b", "codegemma:7b",
    # Others worth a data point
    "internlm2:7b", "hermes3:8b", "smollm2:1.7b", "starling-lm:7b",
    "openchat:7b", "neural-chat:7b", "zephyr:7b", "vicuna:13b",
    "wizardlm2:7b", "sailor2:8b", "reader-lm:1.5b", "bespoke-minicheck:7b",
]

if __name__ == "__main__":
    raise SystemExit(nightrun.main())
