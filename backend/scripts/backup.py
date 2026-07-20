#!/usr/bin/env python3
"""
Backup script for Visa MVP backend.
Backs up: SQLite database (data/visa_mvp.db) + uploads directory (data/materials/).

Retention: keeps the latest 7 backups (by timestamp prefix).
Default output: data/backups/ (rotates the 7 most recent timestamped pairs).

Usage:
    python scripts/backup.py [--dry-run] [--backup-dir <path>]
"""

import argparse
import gzip
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Configuration ---
# Resolve relative to this script's location (backend/scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

# Docker prod mounts SQLite at backend/.data/visa_mvp.db (see docker-compose.yml).
# Local/dev default is backend/data/visa_mvp.db. Prefer the live file that exists.
def resolve_db_path() -> Path:
    candidates = [
        BACKEND_DIR / ".data" / "visa_mvp.db",  # docker bind mount (prod)
        BACKEND_DIR / "data" / "visa_mvp.db",   # local / legacy
    ]
    for p in candidates:
        if p.is_file() and p.stat().st_size > 0:
            return p
    return candidates[0]


DB_PATH = resolve_db_path()
# Project's uploaded files live under data/materials/. The parent spec called this
# "uploads/" colloquially — same path, just a different name.
UPLOADS_PATH = BACKEND_DIR / "data" / "materials"
# Prefer a path OUTSIDE the git/rsync tree so a careless --delete sync
# cannot wipe backups together with the app. Fall back to data/backups/.
_OFFSITE = Path("/var/backups/htexvisa")
DEFAULT_BACKUP_DIR = _OFFSITE if _OFFSITE.parent.is_dir() else (BACKEND_DIR / "data" / "backups")
RETENTION_COUNT = 14  # early-stage: keep two weeks of daily snapshots


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def backup_file(src: Path, dest: Path, dry_run: bool = False) -> Path:
    """Copy a file with gzip compression. Returns path to the gzipped backup."""
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    ensure_dir(dest.parent)

    if dry_run:
        print(f"[DRY-RUN] Would gzip {src} -> {dest}")
        return dest

    with open(src, "rb") as f_in, gzip.open(dest, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)

    return dest


def backup_directory(src_dir: Path, dest_file: Path, dry_run: bool = False) -> Path:
    """Tar + gzip a directory tree. Returns path to the archive."""
    if not src_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    ensure_dir(dest_file.parent)

    if dry_run:
        print(f"[DRY-RUN] Would tar.gz {src_dir} -> {dest_file}")
        return dest_file

    # --format=ustar ensures portability across *nix systems
    import tarfile

    with tarfile.open(dest_file, "w:gz", format=tarfile.USTAR_FORMAT) as tar:
        tar.add(src_dir, arcname=src_dir.name)

    return dest_file


def rotate_backups(backup_dir: Path, prefix: str, keep: int) -> None:
    """Delete oldest backups beyond `keep` count for the given prefix."""
    if not backup_dir.exists():
        return

    backups = sorted(
        backup_dir.glob(f"{prefix}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for old in backups[keep:]:
        print(f"  Removing old backup: {old.name}")
        old.unlink()


def run_backup(dry_run: bool = False, backup_dir: Optional[Path] = None) -> None:
    bdir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
    ts = timestamp()
    ensure_dir(bdir)

    db_src = resolve_db_path()
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Backup started at {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  Source database:  {db_src}")
    print(f"  Backup directory: {bdir}")

    # --- 1. Database backup ---
    db_dest = bdir / f"visa_mvp-{ts}.db.gz"
    try:
        backup_file(db_src, db_dest, dry_run=dry_run)
        if not dry_run:
            size = db_dest.stat().st_size
            print(f"  Database backed up: {db_dest.name} ({size:,} bytes)")
        else:
            print(f"  Database backed up: {db_dest.name}")
    except FileNotFoundError as e:
        print(f"  WARNING: {e}", file=sys.stderr)

    # --- 2. Uploads backup ---
    uploads_dest = bdir / f"uploads-{ts}.tar.gz"
    try:
        backup_directory(UPLOADS_PATH, uploads_dest, dry_run=dry_run)
        if not dry_run:
            size = uploads_dest.stat().st_size
            print(f"  Uploads backed up: {uploads_dest.name} ({size:,} bytes)")
        else:
            print(f"  Uploads backed up: {uploads_dest.name}")
    except FileNotFoundError as e:
        print(f"  WARNING: {e}", file=sys.stderr)

    # --- 3. Rotation ---
    print(f"\n  Rotating backups (keep {RETENTION_COUNT}):")
    rotate_backups(bdir, "visa_mvp-", RETENTION_COUNT)
    rotate_backups(bdir, "uploads-", RETENTION_COUNT)

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Backup completed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Visa MVP database and materials.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help=f"Backup destination directory (default: {DEFAULT_BACKUP_DIR})",
    )
    args = parser.parse_args()

    run_backup(dry_run=args.dry_run, backup_dir=args.backup_dir)


if __name__ == "__main__":
    main()