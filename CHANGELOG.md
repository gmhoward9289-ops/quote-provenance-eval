# Changelog

All notable changes to **trust-but-anchor** (library + eval harness).

## [Unreleased]

### Fixed

- **`summarize()` counts `arm=anchor2`** in `n_anchor` / `anchor_coverage` (was always `n_anchor=0` for dual-anchor runs)
- Report `n` column no longer shows `0/15` for anchor-only runs

### Changed

- Trap corpus grown to **15 questions** (`repeated_anchor_trap.txt` + `questions_anchor2.json`)
- Mock provider emits `anchor2` for `--arm anchor2`; `rescore.py` / confidence calibration include dual-anchor rows

## [0.1.0] - 2026-08-20

### Added

- **`trust_but_anchor` on PyPI** — `locate`, `locate_pair`, `score`, `analyze`, `score_quote`, `normalize`; CLI `tba-preflight`
- **Eval harness** — quote vs anchor arms, `--variant fewshot|refusal`, `--arm anchor2`, value-absent battery
- **52-model local sweep** with energy profiles ([results](https://www.swamplink.com/data/trust/))
- **Corpus** `questions_anchor2.json` + `repeated_anchor_trap.txt` for dual-anchor disambiguation
- **CI** — pytest, `validate_corpus.py`, mock smoke eval on PRs
- **Release workflow** — tag `v*` publishes to PyPI via OIDC (`release.yml`, environment `pypi`)

### Notes

- Eval harness (`eval.py`, corpus, `results/`) stays in the repo; only the locator stack ships in the wheel.
- Swamplink bare repo: `swamplink:/srv/git/trust-but-anchor.git`

[0.1.0]: https://github.com/gmhoward9289-ops/trust-but-anchor/releases/tag/v0.1.0
