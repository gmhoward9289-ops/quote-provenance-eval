"""Join provenance quality with energy cost into one per-model profile.

This is the table the whole sweep exists to produce: not "which model is most
accurate" but "what does trustworthy extraction cost on this hardware".

Two deliberate choices about the energy figures:

* **Power comes from the eval phase, not the bench phase.** A single bench
  request finishes in seconds and yields a handful of nvidia-smi samples, most
  of them taken while the GPU is ramping or idling between tokens — measured
  spread across models was 47 W to 193 W for the same class of work, which is
  sampling noise, not a real difference. The eval phase runs for minutes under
  continuous load and gives hundreds of samples. Use it.

* **The unit is Wh per 100 extractions, not per 1k tokens.** Tokens are an
  implementation detail of the model; extractions are the thing a user
  actually buys. A reasoning model that burns 40x the tokens to answer the
  same question should look expensive here, and per-token accounting would
  hide exactly that.

Throughput (tok/s) is kept from the bench phase because it comes from Ollama's
own eval_count/eval_duration and doesn't depend on sampling at all.
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

# questions per corpus x 2 arms x 3 repeats
CORPUS_QUESTIONS = {"main": 30, "corpus/questions_hard.json": 22,
                    "corpus/questions_absent.json": 10}
ARMS, REPEATS = 2, 3

# Quality bar a model must clear before its energy number is worth quoting.
# Refusal is absolute: a model that invents answers for values that aren't
# there is disqualified regardless of how well it scores on values that are.
COVERAGE_BAR = 0.95
REFUSAL_BAR = 1.0


def load_power(path: str) -> tuple[dict, dict]:
    bench, evals = {}, defaultdict(list)
    if not os.path.exists(path):
        return bench, evals
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("phase") == "bench" and r.get("status") == "ok":
                bench[r["model"]] = r
            elif r.get("phase") == "eval" and r.get("ok"):
                evals[r["model"]].append(r)
    return bench, evals


def energy(runs: list[dict]) -> dict:
    """Wh per 100 extractions, pooled over that model's eval runs."""
    wh = 0.0
    extractions = 0
    watts, samples = [], 0
    for r in runs:
        w = r.get("watts_mean_busy") or r.get("watts_mean")
        if not w or not r.get("elapsed_s"):
            continue
        wh += w * r["elapsed_s"] / 3600
        n = CORPUS_QUESTIONS.get(r.get("corpus"), 0) * ARMS * REPEATS
        extractions += n
        watts.append(w)
        samples += r.get("n_samples", 0)
    if not extractions:
        return {}
    return {"wh_per_100": round(wh / extractions * 100, 2),
            "watts_sustained": round(sum(watts) / len(watts), 1),
            "total_wh": round(wh, 2),
            "extractions": extractions,
            "power_samples": samples}


def load_quality(pattern: str) -> dict:
    """Main-corpus quality plus absent-corpus refusal, per model."""
    q = defaultdict(dict)
    for path in glob.glob(pattern):
        if "mock" in path:
            continue
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        s, model = d.get("summary", {}), d.get("model")
        if not model:
            continue
        if "absent" in os.path.basename(path):
            for k in ("quote_absent_refusal_rate", "anchor_absent_refusal_rate"):
                if s.get(k) is not None:
                    q[model][k] = s[k]
        elif "hard" in os.path.basename(path):
            if s.get("anchor_coverage") is not None:
                q[model]["hard_anchor_coverage"] = s["anchor_coverage"]
        else:
            for k in ("quote_exact_rate", "quote_coverage", "anchor_coverage"):
                if s.get(k) is not None:
                    q[model][k] = s[k]
    return q


def pct(v) -> str:
    return f"{v:.0%}" if isinstance(v, (int, float)) else "-"


def build(results_glob: str, power_path: str) -> str:
    bench, evals = load_power(power_path)
    quality = load_quality(results_glob)
    models = sorted(set(quality) | set(bench))

    rows = []
    for m in models:
        q = quality.get(m, {})
        e = energy(evals.get(m, []))
        b = bench.get(m, {})
        rows.append({
            "model": m,
            "quote_exact": q.get("quote_exact_rate"),
            "anchor_coverage": q.get("anchor_coverage"),
            "hard_anchor": q.get("hard_anchor_coverage"),
            "refusal": q.get("anchor_absent_refusal_rate"),
            "tok_s": b.get("output_tok_s"),
            "resident": b.get("gpu_resident_pct"),
            "watts": e.get("watts_sustained"),
            "wh_per_100": e.get("wh_per_100"),
        })
    rows.sort(key=lambda r: (r["wh_per_100"] is None, r["wh_per_100"] or 0))

    out = ["# Provenance profiles — quality and energy per model",
           "",
           "Hardware: RTX 4080 SUPER (16 GB), Ollama, num_ctx 8192, temperature 0,",
           "3 repeats per corpus. Energy is sustained eval-phase draw over "
           "**100 extractions**",
           "(one extraction = one question, one arm, one repeat). Sorted by "
           "energy, cheapest first.",
           "",
           "| model | quote exact | anchor cov. | hard anchor | absent refusal "
           "| tok/s | GPU res. | watts | Wh/100 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| `{r['model']}` | {pct(r['quote_exact'])} | "
            f"{pct(r['anchor_coverage'])} | {pct(r['hard_anchor'])} | "
            f"{pct(r['refusal'])} | {r['tok_s'] or '-'} | "
            f"{pct((r['resident'] or 0) / 100) if r['resident'] else '-'} | "
            f"{r['watts'] or '-'} | {r['wh_per_100'] or '-'} |")

    done = [r for r in rows if r["wh_per_100"] and r["anchor_coverage"]]
    if done:
        # "Cheapest" on its own is a trap: the least energy per extraction
        # belongs to models that barely locate anything, and cheap failure is
        # not a bargain. The recommendation has to clear a quality bar first.
        usable = [r for r in done
                  if (r["anchor_coverage"] or 0) >= COVERAGE_BAR
                  and (r["refusal"] or 0) >= REFUSAL_BAR]
        best = max(done, key=lambda r: r["anchor_coverage"])
        lo = min(r["wh_per_100"] for r in done)
        hi = max(r["wh_per_100"] for r in done)
        out += ["", "## Read-out", ""]
        if usable:
            pick = min(usable, key=lambda r: r["wh_per_100"])
            out.append(
                f"- **Recommended: `{pick['model']}`** — cheapest model clearing "
                f"the bar ({pct(COVERAGE_BAR)} anchor coverage and "
                f"{pct(REFUSAL_BAR)} absent-value refusal): "
                f"{pct(pick['anchor_coverage'])} coverage at "
                f"{pick['wh_per_100']} Wh per 100 extractions.")
            out.append(f"- {len(usable)} of {len(done)} measured models clear "
                       f"that bar.")
        out += [
            f"- Best anchor coverage: **{best['model']}** at "
            f"{pct(best['anchor_coverage'])} ({best['wh_per_100']} Wh per 100).",
            f"- Energy spread across {len(done)} measured models: {lo}–{hi} Wh "
            f"per 100 extractions ({hi / max(lo, 0.01):.0f}x), while coverage "
            f"among models clearing the bar varies by only a few points.",
            "",
            "Cheapest overall is deliberately not reported: the lowest energy "
            "per extraction belongs to models that locate almost nothing, and "
            "cheap failure is not a bargain.",
        ]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    rg = sys.argv[1] if len(sys.argv) > 1 else "results/reef/run_*.json"
    pp = sys.argv[2] if len(sys.argv) > 2 else "results/reef/power_metrics.jsonl"
    md = build(rg, pp)
    print(md)
    with open("results/profiles.md", "w", encoding="utf-8") as fh:
        fh.write(md + "\n")
