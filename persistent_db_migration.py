"""One-time, fail-closed logical Postgres migration helper for SlideGo.

This is deliberately not a background job. It runs only when explicitly enabled by
`DATABASE_MIGRATION_MODE=true`, while the bot's financial maintenance mode is on.
It never modifies the source database; it only restores into an empty target.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
from typing import Mapping

import psycopg2
from psycopg2 import sql


REQUIRED_TABLES = (
    "users",
    "transactions",
    "generations",
    "system_metadata",
)


class PersistentDatabaseMigrationError(RuntimeError):
    """Safe error type that never embeds a database connection URL."""


def _normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _table_counts(database_url: str, tables: tuple[str, ...] = REQUIRED_TABLES) -> dict[str, int]:
    """Return non-sensitive row counts for the protected tables."""
    try:
        conn = psycopg2.connect(_normalise_url(database_url), connect_timeout=20)
    except Exception as exc:
        raise PersistentDatabaseMigrationError("Database connection check failed") from exc

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ANY(%s)
                """,
                (list(tables),),
            )
            existing = {row[0] for row in cursor.fetchall()}
            if set(tables) - existing:
                missing = ", ".join(sorted(set(tables) - existing))
                raise PersistentDatabaseMigrationError(
                    f"Required source table is missing: {missing}"
                )

            counts: dict[str, int] = {}
            for table in tables:
                cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                counts[table] = int(cursor.fetchone()[0])
            return counts
    finally:
        conn.close()


def _has_any_public_table(database_url: str) -> bool:
    try:
        conn = psycopg2.connect(_normalise_url(database_url), connect_timeout=20)
    except Exception as exc:
        raise PersistentDatabaseMigrationError("Target database connection check failed") from exc

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                )
                """
            )
            return bool(cursor.fetchone()[0])
    finally:
        conn.close()


def _run(command: list[str], environment: Mapping[str, str]) -> None:
    """Run pg client without logging command arguments or sensitive URLs."""
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            env=dict(environment),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PersistentDatabaseMigrationError("Postgres migration utility did not complete") from exc
    if completed.returncode != 0:
        raise PersistentDatabaseMigrationError(
            f"Postgres migration utility failed with exit code {completed.returncode}"
        )


def copy_to_empty_persistent_target(
    source_url: str,
    target_url: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, int]:
    """Copy the source into a new empty target and verify protected table counts.

    A mismatch deliberately leaves the bot stopped. No application connection is
    changed here, and the source remains available for rollback.
    """
    source_url = _normalise_url(source_url or "")
    target_url = _normalise_url(target_url or "")
    if not source_url or not target_url:
        raise PersistentDatabaseMigrationError("Both source and target database URLs are required")
    if source_url == target_url:
        raise PersistentDatabaseMigrationError("Source and target database cannot be the same")

    source_counts = _table_counts(source_url)
    if _has_any_public_table(target_url):
        raise PersistentDatabaseMigrationError(
            "Target database is not empty; refusing to overwrite it"
        )

    safe_environment = dict(os.environ if environment is None else environment)
    safe_environment.setdefault("PGCONNECT_TIMEOUT", "20")
    with tempfile.TemporaryDirectory(prefix="slidego-pg-migration-") as tmp_dir:
        dump_path = Path(tmp_dir) / "slidego-before-persistent-volume.dump"
        _run([
            "pg_dump",
            source_url,
            "--format=custom",
            "--no-owner",
            "--no-acl",
            f"--file={dump_path}",
        ], safe_environment)
        _run([
            "pg_restore",
            f"--dbname={target_url}",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            str(dump_path),
        ], safe_environment)

    target_counts = _table_counts(target_url)
    if target_counts != source_counts:
        raise PersistentDatabaseMigrationError(
            "Protected table counts did not match after restore"
        )
    return target_counts
