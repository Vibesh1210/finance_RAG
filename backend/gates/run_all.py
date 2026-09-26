"""Run every existing phase gate in order; stop on first failure (the regression rule:
completing phase N never excuses breaking phase N-1)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

gates = sorted(ROOT.glob("backend/gates/phase_*.py"))
if not gates:
    sys.exit("no gates found")
for gate in gates:
    print(f"\n>>> {gate.name}", flush=True)
    if subprocess.run([sys.executable, str(gate)], cwd=ROOT).returncode != 0:
        sys.exit(1)
print(f"\nAll {len(gates)} gate(s) green.")
