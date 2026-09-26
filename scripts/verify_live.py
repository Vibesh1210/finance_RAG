"""[HUMAN] one-time check: committed CIK snapshot vs live SEC data.

Makes ONE network call to https://www.sec.gov/files/company_tickers.json using the
fair-access User-Agent from .env, re-derives the universe from the LIVE data through
the same pinned logic (including CIK_OVERRIDES), and diffs against the committed
universe.json. Prints a paste-ready ADR note. Never wired into CI
(fixtures-only rule).
"""

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from us_rag.env import load_env  # noqa: E402
from us_rag.universe import build_universe  # noqa: E402

load_env()
ua = os.environ.get("SEC_EDGAR_USER_AGENT", "")
if "@" not in ua:
    sys.exit("SEC_EDGAR_USER_AGENT with a contact email is required (see .env.example)")

resp = httpx.get(
    "https://www.sec.gov/files/company_tickers.json",
    headers={"User-Agent": ua},
    timeout=30,
)
resp.raise_for_status()

with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
    json.dump(resp.json(), tmp)
    live_path = Path(tmp.name)

derived_from_live = build_universe(live_path)
committed = (ROOT / "universe.json").read_text()
live_path.unlink()

if derived_from_live != committed:
    print("MISMATCH — universe derived from LIVE SEC data differs from committed universe.json.")
    print("Refresh the snapshot + universe deliberately, then record it in an ADR (docs/production/adr/):")
    print("  curl -H \"User-Agent: $SEC_EDGAR_USER_AGENT\" -o fixtures/company_tickers.json \\")
    print("       https://www.sec.gov/files/company_tickers.json")
    print("  uv run python scripts/build_universe.py")
    sys.exit(1)

print("OK — universe derived from live SEC data matches committed universe.json.")
print(
    f"ADR note: `{date.today()} — make verify-live: live derivation matches "
    "committed universe.json (10/10).`"
)
