"""Derive universe.json from the committed SEC snapshot — offline, deterministic."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from us_rag.universe import build_universe  # noqa: E402

out = ROOT / "universe.json"
out.write_text(build_universe(ROOT / "fixtures" / "company_tickers.json"))
print(f"wrote {out}")
