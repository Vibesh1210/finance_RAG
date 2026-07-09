"""Minimal .env loader — avoids a python-dotenv dependency at Phase 0."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ; existing env vars win."""
    env_file = path or repo_root() / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
