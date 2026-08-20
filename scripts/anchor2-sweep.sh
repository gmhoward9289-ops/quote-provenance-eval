#!/usr/bin/env bash
# Anchor vs anchor2 on the repeated-anchor trap corpus. Run on reef (Ollama local).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
LOG="$ROOT/results/anchor2-sweep.log"
MODELS=(
  granite3.3:8b
  qwen2.5-coder:7b
  mistral:7b
)
echo "anchor2 sweep $(date -Iseconds)" | tee -a "$LOG"
for model in "${MODELS[@]}"; do
  for arm in anchor anchor2; do
    echo "==> $model $arm" | tee -a "$LOG"
    python3 eval.py run --provider ollama --model "$model" --arm "$arm" \
      --questions corpus/questions_anchor2.json --repeats 3 2>&1 | tee -a "$LOG"
  done
done
echo "done $(date -Iseconds)" | tee -a "$LOG"
