"""Minimal migration runner: db/migrations/*.sql applied in filename order, once.

Deliberately primitive — no down-migrations (the store is append-only in spirit;
schema mistakes are corrected by new migrations, mirroring U11 for data).
"""

from __future__ import annotations

from pathlib import Path

from us_rag.db import connect
from us_rag.env import repo_root

MIGRATIONS_DIR = repo_root() / "db" / "migrations"


def migrate(url: str | None = None) -> list[str]:
    """Apply unapplied migrations in order; return the filenames applied."""
    applied: list[str] = []
    with connect(url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  filename TEXT PRIMARY KEY,"
            "  applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text())  # each migration file is one transaction
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            applied.append(path.name)
        conn.commit()
    return applied


if __name__ == "__main__":
    names = migrate()
    print(f"applied: {names or 'nothing (up to date)'}")
