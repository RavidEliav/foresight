"""Supabase Postgres access for the run registry (server-side only, ADR-027).

Connects with the Session pooler URL (IPv4, from Railway and local networks). One short
connection per call: runs finish a few times an hour and the Trends page caches its reads.
"""

from __future__ import annotations

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from foresight.registry.record import RUN_COLUMNS

STAGE_COLUMNS = ("run_id", "name", "position", "status", "crew_status", "seconds",
                 "crew_seconds", "tokens")
JSON_COLUMNS = {"gates", "manifest"}
# The Trends page needs everything except the full manifest
LIST_COLUMNS = tuple(c for c in RUN_COLUMNS if c != "manifest")


@contextmanager
def connect(url: str):
    """Bounded: no registry call may hang a run or a page (statement timeout, keepalives)."""
    with psycopg.connect(url, connect_timeout=8, prepare_threshold=None,
                         application_name="foresight", keepalives=1, keepalives_idle=10,
                         keepalives_interval=5, keepalives_count=2) as conn:
        conn.execute("set statement_timeout = 10000")
        yield conn


def ping(url: str) -> None:
    with connect(url) as conn:
        conn.execute("select 1")


def _value(column: str, value):
    return Jsonb(value) if column in JSON_COLUMNS and value is not None else value


def upsert_run(url: str, run: dict, stages: list[dict]) -> None:
    """Insert or replace the run and its stages in one transaction."""
    columns = ", ".join(RUN_COLUMNS)
    placeholders = ", ".join(["%s"] * len(RUN_COLUMNS))
    updates = ", ".join(f"{c} = excluded.{c}" for c in RUN_COLUMNS if c != "run_id")
    with connect(url) as conn, conn.transaction():
        conn.execute(
            f"insert into foresight.runs ({columns}) values ({placeholders}) "
            f"on conflict (run_id) do update set {updates}, recorded_at = now()",
            [_value(c, run.get(c)) for c in RUN_COLUMNS])
        conn.execute("delete from foresight.stages where run_id = %s", [run["run_id"]])
        if stages:
            with conn.cursor() as cur:
                cur.executemany(
                    f"insert into foresight.stages ({', '.join(STAGE_COLUMNS)}) "
                    f"values ({', '.join(['%s'] * len(STAGE_COLUMNS))})",
                    [[run["run_id"], *(s.get(c) for c in STAGE_COLUMNS[1:])] for s in stages])


def fetch_runs(url: str, limit: int = 500) -> list[dict]:
    """Recorded runs, newest first (timestamps as ISO text, like the file-based rows)."""
    with connect(url) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"select {', '.join(LIST_COLUMNS)} from foresight.runs "
                    "order by started_at desc nulls last limit %s", [limit])
        rows = cur.fetchall()
    for row in rows:
        for key in ("started_at", "finished_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
    return rows


def fetch_stages(url: str, run_ids: list[str]) -> list[dict]:
    with connect(url) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"select {', '.join(STAGE_COLUMNS)} from foresight.stages "
                    "where run_id = any(%s) order by run_id, position", [run_ids])
        return cur.fetchall()
