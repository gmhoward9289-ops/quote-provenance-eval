"""Shim — implementation lives in trust_but_anchor.preflight."""
from trust_but_anchor.preflight import analyze, format_report, main  # noqa: F401

if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
