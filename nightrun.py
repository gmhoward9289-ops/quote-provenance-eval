"""All-night model sweep: provenance quality AND energy cost, per model.

Runs ON reef (16 GB RTX 4080 SUPER), not over a tunnel, so it survives the
session that started it. For each model it:

  1. pulls the model if absent (skips cleanly if the tag doesn't exist)
  2. benchmarks it: prompt/response throughput straight from Ollama's own
     timing fields, GPU residency from /api/ps (size vs size_vram — the only
     honest way to tell whether a model actually fits), and GPU power sampled
     from nvidia-smi throughout
  3. runs the three provenance corpora (main / hard / absent) with power
     sampled the same way
  4. unloads the model and moves on

The point of measuring power next to quality: the interesting question for
local extraction isn't "which model is best" but "which model is best per
watt-hour", and that number has never been published next to a provenance
score. Throughput comes from Ollama's eval_count/eval_duration rather than a
wall-clock guess; energy comes from real samples, not a TDP number off a spec
sheet.

Everything is append-only JSONL so a crash at 3am costs one model, not a night.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

HOST = "http://127.0.0.1:11434"
ROOT = os.path.dirname(os.path.abspath(__file__))
METRICS = os.path.join(ROOT, "results", "power_metrics.jsonl")
LOG = os.path.join(ROOT, "results", "nightrun.log")
NUM_CTX = "8192"
MIN_FREE_GB = 80  # keep this much headroom on the model drive

# Reasoning models can dump everything into the thinking channel and return
# empty content, which honest scoring counts as unparseable. Disable it.
THINKING = ("gpt-oss", "qwen3", "deepseek-r1", "marco-o1", "magistral", "phi4-reasoning")

MODELS = [
    # already on disk — cheap, run first. gpt-oss/gemma2/qwen3.5 were mid-sweep
    # over the tunnel when this took over; gemma4 has quality numbers already
    # but no power numbers, so it re-runs for the energy figures.
    "gpt-oss:20b", "gemma2:9b", "qwen3.5:9b", "gemma4:12b",
    "llama3.1:8b", "phi4:14b", "qwen2.5:14b", "qwen2.5-coder:7b",
    # broad pulls, roughly small -> large
    "llama3.2:3b", "phi3.5:3.8b", "granite3.3:8b", "mistral:7b",
    "qwen2.5:7b", "aya-expanse:8b", "tulu3:8b", "glm4:9b",
    "exaone3.5:7.8b", "command-r7b", "falcon3:10b", "olmo2:13b",
    "mistral-nemo:12b", "gemma3:12b", "deepseek-r1:8b", "qwen3:8b",
    "yi:9b", "solar:10.7b", "dolphin3:8b", "granite3.1-moe:3b",
    "deepseek-coder-v2:16b", "nemotron-mini:4b",
]

BENCH_PROMPT = ("Summarize the following in exactly three sentences.\n\n"
                "The transmission upgrade programme reported consolidated "
                "revenue of $2,847.3 million for fiscal 2025, an increase of "
                "11.2 percent over the prior year, driven principally by "
                "higher throughput in the eastern corridor and the "
                "commissioning of two additional substations in the third "
                "quarter. Operating margin improved to 18.4 percent.") * 3


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def emit(rec: dict) -> None:
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(METRICS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


class PowerSampler(threading.Thread):
    """Poll nvidia-smi for power/utilisation/VRAM until stopped."""

    def __init__(self, interval: float = 2.0):
        super().__init__(daemon=True)
        self.interval = interval
        # NOT self._stop: threading.Thread already has an internal _stop()
        # method that _bootstrap_inner calls when the thread finishes, and
        # shadowing it with an Event kills every sampler with
        # "'Event' object is not callable".
        self._halt = threading.Event()
        self.samples: list[tuple[float, float, float]] = []

    def run(self) -> None:
        q = ("nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used "
             "--format=csv,noheader,nounits")
        while not self._halt.is_set():
            try:
                out = subprocess.run(q.split(), capture_output=True, text=True,
                                     timeout=10).stdout.strip()
                w, u, m = (float(x) for x in out.split(",")[:3])
                self.samples.append((w, u, m))
            except Exception:
                pass
            self._halt.wait(self.interval)

    def stop(self) -> dict:
        self._halt.set()
        self.join(timeout=15)
        if not self.samples:
            return {}
        watts = [s[0] for s in self.samples]
        util = [s[1] for s in self.samples]
        vram = [s[2] for s in self.samples]
        # Busy samples only: idle tail between requests drags the mean down and
        # would flatter every model equally but unequally wrong.
        busy = [w for w, u, _ in self.samples if u >= 20]
        return {
            "n_samples": len(self.samples),
            "watts_mean": round(sum(watts) / len(watts), 1),
            "watts_peak": round(max(watts), 1),
            "watts_mean_busy": round(sum(busy) / len(busy), 1) if busy else None,
            "gpu_util_mean": round(sum(util) / len(util), 1),
            "vram_used_mb_peak": round(max(vram)),
        }


def ollama(args: list[str], timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(["ollama", *args], capture_output=True, text=True,
                          timeout=timeout)


def api(path: str, payload: dict | None = None, timeout: int = 600) -> dict:
    url = f"{HOST}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def free_gb() -> float:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-PSDrive Z).Free"], capture_output=True, text=True,
            timeout=30).stdout.strip()
        return float(out) / (1024 ** 3)
    except Exception:
        return 999.0


def residency(model: str) -> dict:
    """size vs size_vram from /api/ps — never infer this from `ollama ls`."""
    try:
        for m in api("/api/ps").get("models", []):
            if m.get("name", "").startswith(model.split(":")[0]):
                size, vram = m.get("size", 0), m.get("size_vram", 0)
                return {"size_gb": round(size / 1e9, 2),
                        "size_vram_gb": round(vram / 1e9, 2),
                        "gpu_resident_pct": round(100 * vram / size, 1) if size else None}
    except Exception:
        pass
    return {}


def bench(model: str, think_off: bool) -> dict:
    payload = {"model": model, "stream": False,
               "options": {"temperature": 0, "num_ctx": int(NUM_CTX)},
               "messages": [{"role": "user", "content": BENCH_PROMPT}]}
    if think_off:
        payload["think"] = False
    t0 = time.time()
    d = api("/api/chat", payload)
    wall = time.time() - t0
    pc, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 0)
    ec, ed = d.get("eval_count", 0), d.get("eval_duration", 0)
    return {
        "wall_s": round(wall, 2),
        "load_s": round(d.get("load_duration", 0) / 1e9, 2),
        "prompt_tokens": pc,
        "output_tokens": ec,
        "prompt_tok_s": round(pc / (pd / 1e9), 1) if pd else None,
        "output_tok_s": round(ec / (ed / 1e9), 1) if ed else None,
        **residency(model),
    }


def run_eval(model: str, corpus: str | None, env: dict) -> bool:
    cmd = [sys.executable, "eval.py", "run", "--provider", "ollama",
           "--model", model, "--repeats", "3"]
    if corpus:
        cmd += ["--questions", corpus]
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=14400)
    if p.returncode != 0:
        log(f"    eval FAILED ({corpus or 'main'}): {p.stderr.strip()[-300:]}")
        return False
    return True


def main() -> int:
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    have = ollama(["ls"]).stdout
    log(f"=== nightrun start — {len(MODELS)} models queued")

    for model in MODELS:
        try:
            if model.split(":")[0] not in have or model not in have:
                if free_gb() < MIN_FREE_GB:
                    log(f"!! only {free_gb():.0f} GB free — stopping pulls")
                    break
                log(f"pulling {model} ...")
                p = ollama(["pull", model])
                if p.returncode != 0:
                    log(f"  SKIP {model}: pull failed ({p.stderr.strip()[:160]})")
                    emit({"model": model, "status": "pull_failed"})
                    continue

            think_off = any(t in model for t in THINKING)
            env = dict(os.environ, OLLAMA_HOST=HOST, OLLAMA_NUM_CTX=NUM_CTX)
            if think_off:
                env["OLLAMA_THINK"] = "false"

            log(f"--- {model} (think_off={think_off})")
            sampler = PowerSampler()
            sampler.start()
            try:
                b = bench(model, think_off)
            except Exception as e:
                sampler.stop()
                log(f"  SKIP {model}: bench failed ({e})")
                emit({"model": model, "status": "bench_failed", "error": str(e)})
                ollama(["stop", model])
                continue
            power = sampler.stop()
            # Energy per 1k output tokens is the comparable figure: watts alone
            # rewards a slow model for sipping power while producing nothing.
            wh_per_1k = None
            if b.get("output_tok_s") and power.get("watts_mean_busy"):
                wh_per_1k = round(
                    power["watts_mean_busy"] * (1000 / b["output_tok_s"]) / 3600, 3)
            emit({"model": model, "phase": "bench", "status": "ok",
                  **b, **power, "wh_per_1k_output_tokens": wh_per_1k})
            log(f"  bench: {b.get('output_tok_s')} tok/s out, "
                f"{b.get('gpu_resident_pct')}% GPU-resident, "
                f"{power.get('watts_mean_busy')} W busy, {wh_per_1k} Wh/1k tok")

            for corpus in (None, "corpus/questions_hard.json",
                           "corpus/questions_absent.json"):
                name = corpus or "main"
                s = PowerSampler()
                s.start()
                t0 = time.time()
                ok = run_eval(model, corpus, env)
                pw = s.stop()
                emit({"model": model, "phase": "eval", "corpus": name,
                      "ok": ok, "elapsed_s": round(time.time() - t0, 1), **pw})
                log(f"  eval {name}: {'ok' if ok else 'FAILED'} "
                    f"in {time.time() - t0:.0f}s, {pw.get('watts_mean_busy')} W")

            ollama(["stop", model])
            log(f"  done {model}; {free_gb():.0f} GB free")
        except Exception as e:
            log(f"!! {model} crashed: {e}")
            emit({"model": model, "status": "crashed", "error": str(e)})
            try:
                ollama(["stop", model])
            except Exception:
                pass

    log("=== nightrun complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
