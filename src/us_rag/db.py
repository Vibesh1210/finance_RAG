"""Database connection helper — single place the DATABASE_URL convention lives."""

from __future__ import annotations

import os

import psycopg

from us_rag.env import load_env

DEFAULT_URL = "postgresql://usrag:usrag@localhost:5433/usrag"


def database_url() -> str:
    load_env()
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def connect(url: str | None = None, *, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(url or database_url(), autocommit=autocommit, connect_timeout=5)
