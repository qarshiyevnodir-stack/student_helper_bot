"""Encrypted, portable PostgreSQL backups for the SlideGo bot.

The backup is deliberately one-way: it creates an encrypted pg_dump and uploads it
under a dedicated private R2 prefix. Restoring is a separate, operator-approved
procedure and is not implemented in the running bot.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
from typing import Any
from urllib.parse import unquote, urlparse

import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet, InvalidToken
import psycopg2


logger = logging.getLogger("slidego.database_backup")

BACKUP_TABLES = ("users", "transactions", "generations")
DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60
MIN_INTERVAL_SECONDS = 60 * 60
MAX_INTERVAL_SECONDS = 24 * 60 * 60
DEFAULT_PREFIX = "slidego-private-db-backups/v1"
LATEST_MANIFEST_NAME = "latest-verified.json"


class DatabaseBackupError(RuntimeError):
    """Raised when a backup cannot be produced or verified safely."""


class EmptyDatabaseRegression(DatabaseBackupError):
    """Raised when a once-populated table unexpectedly becomes empty."""


@dataclass(frozen=True)
class BackupSettings:
    database_url: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    encryption_key: bytes
    key_prefix: str


@dataclass(frozen=True)
class BackupReport:
    object_key: str
    created_at: str
    table_counts: dict[str, int]
    encrypted_sha256: str


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def backups_enabled() -> bool:
    """Returns whether the explicitly configured scheduled backup is enabled."""
    return _is_truthy(os.getenv("DATABASE_BACKUP_ENABLED"))


def backup_interval_seconds() -> int:
    """Returns a bounded interval so an accidental config cannot overload the DB."""
    raw_value = os.getenv("DATABASE_BACKUP_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))
    try:
        interval = int(raw_value)
    except ValueError as exc:
        raise DatabaseBackupError("DATABASE_BACKUP_INTERVAL_SECONDS butun son bo'lishi kerak") from exc
    if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        raise DatabaseBackupError(
            f"Backup oralig'i {MIN_INTERVAL_SECONDS} va {MAX_INTERVAL_SECONDS} soniya orasida bo'lishi kerak"
        )
    return interval


def load_settings() -> BackupSettings:
    """Loads and validates secrets without ever logging their values."""
    required = {
        "DATABASE_URL": os.getenv("DATABASE_URL", ""),
        "R2_ACCOUNT_ID": os.getenv("R2_ACCOUNT_ID", ""),
        "R2_ACCESS_KEY_ID": os.getenv("R2_ACCESS_KEY_ID", ""),
        "R2_SECRET_ACCESS_KEY": os.getenv("R2_SECRET_ACCESS_KEY", ""),
        "R2_BUCKET_NAME": os.getenv("R2_BUCKET_NAME", ""),
        "DATABASE_BACKUP_ENCRYPTION_SECRET": os.getenv("DATABASE_BACKUP_ENCRYPTION_SECRET", ""),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise DatabaseBackupError("Backup uchun kerakli private sozlama yo'q: " + ", ".join(missing))

    # Railway variable generator arbitrary high-entropy text produces. Derive an
    # exact Fernet key from it instead of exposing a hand-crafted base64 key.
    encryption_key = base64.urlsafe_b64encode(
        hashlib.sha256(required["DATABASE_BACKUP_ENCRYPTION_SECRET"].encode("utf-8")).digest()
    )
    Fernet(encryption_key)

    key_prefix = os.getenv("DATABASE_BACKUP_R2_PREFIX", DEFAULT_PREFIX).strip().strip("/")
    if not key_prefix or ".." in key_prefix or key_prefix.startswith("/"):
        raise DatabaseBackupError("DATABASE_BACKUP_R2_PREFIX noto'g'ri")

    return BackupSettings(
        database_url=required["DATABASE_URL"],
        r2_account_id=required["R2_ACCOUNT_ID"],
        r2_access_key_id=required["R2_ACCESS_KEY_ID"],
        r2_secret_access_key=required["R2_SECRET_ACCESS_KEY"],
        r2_bucket_name=required["R2_BUCKET_NAME"],
        encryption_key=encryption_key,
        key_prefix=key_prefix,
    )


def _table_counts(database_url: str) -> dict[str, int]:
    """Reads only aggregate table counts required to validate backup safety."""
    conn = psycopg2.connect(database_url, connect_timeout=15)
    try:
        with conn.cursor() as cursor:
            counts: dict[str, int] = {}
            for table in BACKUP_TABLES:
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                if cursor.fetchone()[0] is None:
                    raise DatabaseBackupError(f"Kerakli database jadvali topilmadi: {table}")
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = int(cursor.fetchone()[0])
            return counts
    finally:
        conn.close()


def _r2_client(settings: BackupSettings):
    """Creates a private R2 client; credentials remain in process memory only."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _latest_manifest_key(settings: BackupSettings) -> str:
    return f"{settings.key_prefix}/{LATEST_MANIFEST_NAME}"


def _load_previous_counts(client, settings: BackupSettings) -> dict[str, int] | None:
    """Returns counts from the last verified backup, if one exists."""
    try:
        response = client.get_object(
            Bucket=settings.r2_bucket_name,
            Key=_latest_manifest_key(settings),
        )
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise DatabaseBackupError("Oldingi backup manifestini R2 dan o'qib bo'lmadi") from exc

    try:
        manifest: dict[str, Any] = json.loads(response["Body"].read().decode("utf-8"))
        raw_counts = manifest["table_counts"]
        return {table: int(raw_counts[table]) for table in BACKUP_TABLES}
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatabaseBackupError("Oldingi backup manifesti noto'g'ri") from exc


def _reject_empty_regression(previous: dict[str, int] | None, current: dict[str, int]) -> None:
    """Never replaces a known non-empty backup baseline with an empty table backup."""
    if not previous:
        return
    regressed = [table for table in BACKUP_TABLES if previous.get(table, 0) > 0 and current.get(table, 0) == 0]
    if regressed:
        raise EmptyDatabaseRegression(
            "Oldingi tasdiqlangan backupdan keyin jadval kutilmaganda bo'sh bo'ldi: " + ", ".join(regressed)
        )


def _pg_dump_environment(database_url: str) -> dict[str, str]:
    """Builds libpq environment without putting the DB password into command arguments."""
    normalized = database_url.replace("postgres://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or not parsed.path.strip("/"):
        raise DatabaseBackupError("DATABASE_URL PostgreSQL ulanish manzili emas")

    environment = os.environ.copy()
    environment.update(
        {
            "PGHOST": parsed.hostname,
            "PGPORT": str(parsed.port or 5432),
            "PGUSER": unquote(parsed.username or ""),
            "PGPASSWORD": unquote(parsed.password or ""),
            "PGDATABASE": unquote(parsed.path.lstrip("/")),
        }
    )
    if not environment["PGUSER"] or not environment["PGPASSWORD"]:
        raise DatabaseBackupError("DATABASE_URL backup uchun kerakli login ma'lumotini bermadi")
    return environment


def _run_pg_dump(database_url: str, output_path: Path) -> None:
    """Creates a restoreable custom-format logical dump with a bounded timeout."""
    try:
        result = subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(output_path)],
            env=_pg_dump_environment(database_url),
            capture_output=True,
            text=True,
            timeout=15 * 60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise DatabaseBackupError("pg_dump containerda topilmadi") from exc
    except subprocess.TimeoutExpired as exc:
        raise DatabaseBackupError("pg_dump 15 daqiqada tugamadi") from exc

    if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        raise DatabaseBackupError("pg_dump muvaffaqiyatsiz tugadi")

    try:
        validation = subprocess.run(
            ["pg_restore", "--list", str(output_path)],
            capture_output=True,
            text=True,
            timeout=5 * 60,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise DatabaseBackupError("Backup formatini pg_restore bilan tekshirib bo'lmadi") from exc
    if validation.returncode != 0:
        raise DatabaseBackupError("pg_restore backup formatini tasdiqlamadi")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_object_key(settings: BackupSettings, created_at: datetime) -> str:
    timestamp = created_at.strftime("%Y/%m/%d/%Y%m%dT%H%M%SZ")
    return f"{settings.key_prefix}/backups/{timestamp}.dump.fernet"


def create_encrypted_backup() -> BackupReport:
    """Creates, verifies, encrypts and uploads one safe portable backup.

    No delete or restore operation is performed. The manifest is written only after
    the encrypted dump object upload succeeds.
    """
    settings = load_settings()
    current_counts = _table_counts(settings.database_url)
    client = _r2_client(settings)
    previous_counts = _load_previous_counts(client, settings)
    _reject_empty_regression(previous_counts, current_counts)

    created_time = datetime.now(timezone.utc)
    created_at = created_time.isoformat()
    object_key = _new_object_key(settings, created_time)

    with tempfile.TemporaryDirectory(prefix="slidego-pg-backup-") as temp_dir:
        raw_dump = Path(temp_dir) / "database.dump"
        encrypted_dump = Path(temp_dir) / "database.dump.fernet"
        _run_pg_dump(settings.database_url, raw_dump)
        plaintext_sha256 = _sha256_file(raw_dump)

        try:
            encrypted_dump.write_bytes(Fernet(settings.encryption_key).encrypt(raw_dump.read_bytes()))
        except (InvalidToken, OSError) as exc:
            raise DatabaseBackupError("Backupni shifrlab bo'lmadi") from exc

        encrypted_sha256 = _sha256_file(encrypted_dump)
        client.upload_file(
            str(encrypted_dump),
            settings.r2_bucket_name,
            object_key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": {
                    "backup-format": "pg-dump-custom-fernet-v1",
                    "encrypted-sha256": encrypted_sha256,
                    "plaintext-sha256": plaintext_sha256,
                },
            },
        )

    manifest = {
        "version": 1,
        "created_at": created_at,
        "object_key": object_key,
        "format": "pg-dump-custom-fernet-v1",
        "table_counts": current_counts,
        "encrypted_sha256": encrypted_sha256,
        "plaintext_sha256": plaintext_sha256,
    }
    try:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=_latest_manifest_key(settings),
            Body=json.dumps(manifest, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )
    except ClientError as exc:
        raise DatabaseBackupError("Backup yuklandi, lekin tasdiqlovchi manifest saqlanmadi") from exc

    return BackupReport(
        object_key=object_key,
        created_at=created_at,
        table_counts=current_counts,
        encrypted_sha256=encrypted_sha256,
    )
