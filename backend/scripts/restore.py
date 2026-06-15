#!/usr/bin/env python3
"""
Restore script for Visa MVP backend.
Restores: SQLite database (data/visa_mvp.db) + uploads directory (data/materials/)
from a backup taken by scripts/backup.py.

Backup file naming convention (set by backup.py):
  - visa_mvp-<YYYYMMDD-HHMMSS>.db.gz
  - uploads-<YYYYMMDD-HHMMSS>.tar.gz

Safety:
  - Backs up the current live database/uploads before overwriting (with .pre_restore suffix).
  - Requires explicit confirmation before overwriting anything.
  - Restores both db and uploads together (same timestamp).

Usage:
    python scripts/restore.py [--list] [--timestamp <YYYYMMDD-HHMMSS>] [--dry-run] [--backup-dir <path>]
"""

import argparse
import gzip
import os
import re
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

DB_PATH = BACKEND_DIR / "data" / "visa_mvp.db"
UPLOADS_PATH = BACKEND_DIR / "data" / "materials"
DEFAULT_BACKUP_DIR = BACKEND_DIR / "data" / "backups"

# Filename pattern: visa_mvp-<ts>.db.gz  /  uploads-<ts>.tar.gz
_TS_RE = re.compile(r"^\d{8}-\d{6}$")


def list_backups(backup_dir: Path) -> dict[str, dict]:
    """
    Scan backup_dir for visa_mvp-<ts>.db.gz and uploads-<ts>.tar.gz.
    Returns dict keyed by timestamp: { ts: { "db": Path, "uploads": Path } }
    """
    if not backup_dir.exists():
        return {}

    result: dict[str, dict] = {}
    for f in sorted(backup_dir.iterdir()):
        name = f.name
        # visa_mvp-<ts>.db.gz  ->  stem is "visa_mvp-<ts>.db"
        if name.startswith("visa_mvp-") and name.endswith(".db.gz"):
            ts = name[len("visa_mvp-"):-len(".db.gz")]
            if _TS_RE.match(ts):
                result.setdefault(ts, {})["db"] = f
        # uploads-<ts>.tar.gz
        elif name.startswith("uploads-") and name.endswith(".tar.gz"):
            ts = name[len("uploads-"):-len(".tar.gz")]
            if _TS_RE.match(ts):
                result.setdefault(ts, {})["uploads"] = f
    return result


def print_backup_summary(backups: dict[str, dict]) -> None:
    if not backups:
        print("  No backups found.")
        return

    print(f"\n  {'Timestamp':<20} {'DB':<35} {'Uploads':<35}")
    print(f"  {'-'*20} {'-'*35} {'-'*35}")
    for ts in sorted(backups.keys()):
        files = backups[ts]
        db = files.get("db", "—")
        ups = files.get("uploads", "—")
        print(
            f"  {ts:<20} "
            f"{str(db.name) if db != '—' else '—':<35} "
            f"{str(ups.name) if ups != '—' else '—':<35}"
        )


def restore_db(backup_file: Path, dry_run: bool = False) -> None:
    """Decompress gzip backup back to DB_PATH."""
    # Safety: rename live DB before overwriting
    if DB_PATH.exists() and not dry_run:
        pre_restore = DB_PATH.with_suffix(".db.pre_restore")
        print(f"  Moving current DB -> {pre_restore.name}")
        shutil.move(DB_PATH, pre_restore)

    if dry_run:
        print(f"[DRY-RUN] Would decompress {backup_file} -> {DB_PATH}")
        return

    with gzip.open(backup_file, "rb") as f_in:
        with open(DB_PATH, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    size = DB_PATH.stat().st_size
    print(f"  Database restored: {DB_PATH} ({size:,} bytes)")


def restore_uploads(backup_file: Path, dry_run: bool = False) -> None:
    """Extract tar.gz archive back to data/materials/ (full replace)."""
    # Safety: rename live uploads dir before extracting
    if UPLOADS_PATH.exists() and not dry_run:
        pre_restore = UPLOADS_PATH.with_suffix(".pre_restore")
        print(f"  Moving current uploads/ -> {pre_restore.name}/")
        shutil.move(UPLOADS_PATH, pre_restore)

    if dry_run:
        print(f"[DRY-RUN] Would extract tar.gz {backup_file} -> {UPLOADS_PATH}/")
        return

    # Ensure parent exists, then extract. tarfile will create the archive's top dir.
    UPLOADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(backup_file, "r:gz") as tar:
        tar.extractall(path=UPLOADS_PATH.parent)

    size = backup_file.stat().st_size
    print(f"  Uploads restored from: {backup_file.name} ({size:,} bytes)")


def run_restore(
    ts: Optional[str],
    dry_run: bool = False,
    backup_dir: Optional[Path] = None,
    auto_confirm: bool = False,
) -> None:
    bdir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    backups = list_backups(bdir)

    if not backups:
        print(f"No backups found in {bdir}")
        sys.exit(1)

    # If no timestamp given, pick the most recent one
    if not ts:
        ts = sorted(backups.keys())[-1]
        print(f"No timestamp specified — using most recent: {ts}")
    elif ts not in backups:
        print(f"No backup found for timestamp: {ts}")
        print("\nAvailable timestamps:")
        print_backup_summary(backups)
        sys.exit(1)

    files = backups[ts]

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Restore plan:")
    print(f"  Backup directory : {bdir}")
    print(f"  Timestamp        : {ts}")
    if files.get("db"):
        print(f"  Database backup  : {files['db'].name}")
    else:
        print(f"  Database backup  : (not found — skipping DB restore)")
    if files.get("uploads"):
        print(f"  Uploads backup   : {files['uploads'].name}")
    else:
        print(f"  Uploads backup   : (not found — skipping uploads restore)")

    if dry_run:
        print("\n[Dry-run complete — no changes made]")
        return

    if not auto_confirm:
        print("\n[WARNING] This will OVERWRITE the current database and uploads directory.")
        print("          A pre-restore copy will be saved with .pre_restore suffix.")
        reply = input("          Type 'yes' to confirm: ").strip().lower()
        if reply != "yes":
            print("Aborted.")
            sys.exit(0)

    print("\nRestoring...")
    if files.get("db"):
        restore_db(files["db"], dry_run=dry_run)
    if files.get("uploads"):
        restore_uploads(files["uploads"], dry_run=dry_run)

    print("\nRestore completed. Please restart the application if it was running.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore Visa MVP from backup.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups and exit.",
    )
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="Timestamp key (YYYYMMDD-HHMMSS) of the backup to restore. "
        "Defaults to latest if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show restore plan without making changes.",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skip confirmation prompt (for scripted use). DANGEROUS — use with care.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help=f"Backup directory to restore from (default: {DEFAULT_BACKUP_DIR})",
    )
    args = parser.parse_args()

    bdir = Path(args.backup_dir) if args.backup_dir else DEFAULT_BACKUP_DIR

    if args.list:
        backups = list_backups(bdir)
        print(f"\nBackups in: {bdir}")
        print_backup_summary(backups)
        return

    run_restore(
        ts=args.timestamp,
        dry_run=args.dry_run,
        backup_dir=args.backup_dir,
        auto_confirm=args.auto_confirm,
    )


if __name__ == "__main__":
    main()