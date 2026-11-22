"""Lightweight forward-only schema sync for the SQLite database.

`Base.metadata.create_all` happily creates *new* tables but never adds columns to
tables that already exist. The shipped `shopping_platform.db` predates several
fields, so on startup we introspect the live schema and `ALTER TABLE` anything
missing. Safe to run on every boot: it is a no-op once the columns exist.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

# (table, column, DDL type + default) for every column added after v1 of the schema.
ADDED_COLUMNS: List[Tuple[str, str, str]] = [
    ("orders", "payment_method", "VARCHAR(32) DEFAULT 'UPI'"),
    ("orders", "payment_status", "VARCHAR(32) DEFAULT 'PENDING'"),
    ("orders", "transaction_reference", "VARCHAR(64)"),
]


def _existing_columns(engine: Engine, table: str) -> Dict[str, str]:
    """Returns {column_name: declared_type} for an existing table."""
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1]: row[2] or "" for row in rows}


def _table_exists(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table},
        ).fetchone()
    return row is not None


def sync_schema(engine: Engine) -> List[str]:
    """Adds any missing columns. Returns the list of applied changes."""
    applied: List[str] = []

    for table, column, ddl in ADDED_COLUMNS:
        if not _table_exists(engine, table):
            continue  # create_all will build it with the full column set
        if column in _existing_columns(engine, table):
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        applied.append(f"{table}.{column}")

    return applied
