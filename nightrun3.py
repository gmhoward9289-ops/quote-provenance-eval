"""Third batch: batch 2's remainder, minus the models that can't fit.

Batch 2 was stopped part-way through `qwq:32b`, which benched at 3.2 tok/s
with only 65% of its weights on the GPU — a reasoning model past the VRAM
cliff, which would have run for most of the night and starved everything
behind it. The bench line alone characterises that failure mode; running the
full corpora for it would have bought a more precise number for one model at
the cost of fifteen others.

Dropped for the same reason, without running them:
  qwq:32b        ~20 GB, reasoning, 65% resident, 3.2 tok/s measured
  llama3.3:70b   ~43 GB on a 16 GB card, hopeless
  gemma3:27b     ~17 GB, over the cliff

The cliff itself is already documented by two measured points: mistral-small:22b
(88% VRAM, 100% "resident", 9x the energy of an equal-quality 7.8B) and qwq:32b
(65% resident, 3.2 tok/s). A third would add nothing.
"""
from __future__ import annotations

import nightrun

nightrun.MODELS = [
    "llama3.2:1b", "gemma3:4b", "codegemma:7b", "internlm2:7b",
    "hermes3:8b", "smollm2:1.7b", "starling-lm:7b", "openchat:7b",
    "neural-chat:7b", "zephyr:7b", "vicuna:13b", "wizardlm2:7b",
    "sailor2:8b", "reader-lm:1.5b", "bespoke-minicheck:7b",
]

if __name__ == "__main__":
    raise SystemExit(nightrun.main())
