"""Tiny gate runner. A gate is a plain script: `python gates/phase_NN.py`; exit 0 = pass.

Plain python (not pytest) so a gate's output reads as a checklist and its exit code
is the whole contract — CI and `make gate` need nothing else.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def run_gate(name: str, checks: list[tuple[str, Callable[[], None]]]) -> None:
    print(f"=== GATE {name} ===")
    failures = 0
    for label, fn in checks:
        try:
            fn()
            print(f"  PASS  {label}")
        except Exception as exc:  # a gate reports every failure, not just the first
            failures += 1
            print(f"  FAIL  {label}: {exc}")
    if failures:
        print(f"=== {name}: {failures} check(s) FAILED ===")
        sys.exit(1)
    print(f"=== {name}: all {len(checks)} checks passed ===")
