"""Applies the Supabase migrations (``supabase/migrations/*.sql``) that a database has not had.

Runs as Railway's pre-deploy command, so each environment migrates its own Supabase project
before the new version starts (the office network blocks Postgres ports; Railway reaches
them). Applied versions are recorded in ``supabase_migrations.schema_migrations``, the table
the Supabase CLI uses, so ``supabase migration list`` agrees. An advisory lock keeps two
deploys from migrating at once; each migration runs in its own transaction.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from foresight.settings import PROJECT_ROOT
from foresight.utils.logging import get_logger

log = get_logger("migrate")
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
LOCK_ID = 7_402_118  # any constant shared by all deploys of this app


def pending(conn: psycopg.Connection, folder: Path = MIGRATIONS_DIR) -> list[Path]:
    conn.execute("create schema if not exists supabase_migrations")
    conn.execute("create table if not exists supabase_migrations.schema_migrations "
                 "(version text primary key, statements text[], name text)")
    done = {row[0] for row in conn.execute(
        "select version from supabase_migrations.schema_migrations")}
    return [p for p in sorted(folder.glob("*.sql")) if p.name.split("_", 1)[0] not in done]


def migrate(url: str, folder: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply the pending migrations; returns their file names."""
    applied = []
    with psycopg.connect(url, autocommit=True, connect_timeout=15,
                         prepare_threshold=None) as conn:
        conn.execute("select pg_advisory_lock(%s)", [LOCK_ID])
        try:
            for path in pending(conn, folder):
                version, _, name = path.stem.partition("_")
                sql = path.read_text(encoding="utf-8")
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("insert into supabase_migrations.schema_migrations "
                                 "(version, statements, name) values (%s, %s, %s)",
                                 [version, [sql], name])
                applied.append(path.name)
                log.info("migration %s applied", path.name)
        finally:
            conn.execute("select pg_advisory_unlock(%s)", [LOCK_ID])
    return applied


def main() -> int:
    """No database configured, or unreachable: the app falls back to the run folders, so the
    deploy goes on. A failing migration stops the deploy (the old version keeps running)."""
    from foresight.settings import load_settings
    from foresight.utils.logging import redact

    settings = load_settings()
    if not settings.database_url:
        print("SUPABASE_DB_URL is not set: nothing to migrate", flush=True)
        return 0
    try:
        applied = migrate(settings.database_url)
    except psycopg.OperationalError as exc:
        print(f"database unreachable, migrations skipped: {type(exc).__name__}", flush=True)
        return 0
    except Exception as exc:  # stops the deploy; never prints the database password
        print(f"migration failed: {type(exc).__name__}: {redact(exc)}", flush=True)
        return 1
    print(f"migrations applied: {', '.join(applied) or 'none (up to date)'}", flush=True)
    return 0
