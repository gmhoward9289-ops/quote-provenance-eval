# Reef: anchor vs anchor2 sweep

Run on **reef** (`owner@192.168.68.20`) where Ollama is local. Pull latest `trust-but-anchor` first.

```bash
ssh owner@192.168.68.20
cd ~/dev/trust-but-anchor   # or quote-provenance-eval until renamed on reef
git pull
bash scripts/anchor2-sweep.sh
```

The sweep runs `granite3.3:8b`, `qwen2.5-coder:7b`, and `mistral:7b` on `corpus/questions_anchor2.json` with both `--arm anchor` and `--arm anchor2` (3 repeats each). Log: `results/anchor2-sweep.log`.

One-off:

```bash
python3 eval.py run --provider ollama --model granite3.3:8b --arm anchor2 \
  --questions corpus/questions_anchor2.json --repeats 3 --verbose
```

After the run, copy `results/run_*.json` back or `python3 eval.py report results/run_*anchor2*.json`.
