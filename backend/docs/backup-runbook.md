# Backup Runbook — Visa MVP Backend

## Overview

This runbook covers automated backup and restore procedures for the Visa MVP backend.
Two Python scripts handle the work — both rely on the Python stdlib only (no third-party deps):

| Script | Purpose |
|--------|---------|
| `scripts/backup.py` | Back up SQLite DB + uploads directory |
| `scripts/restore.py` | Restore both from a timestamped backup |

## What Gets Backed Up

| Asset | Source | Backup file pattern | Compression |
|-------|--------|---------------------|-------------|
| SQLite database | `data/visa_mvp.db` | `visa_mvp-<YYYYMMDD-HHMMSS>.db.gz` | gzip |
| Uploaded files (uploads/) | `data/materials/` | `uploads-<YYYYMMDD-HHMMSS>.tar.gz` | tar + gzip |

> **Naming note:** The spec called this directory `uploads/`. The project's
> actual path is `data/materials/`. We treat them as the same thing and emit
> `uploads-<ts>.tar.gz` so the artifact name matches the spec.

**Default backup location:** `backend/data/backups/` (7 rotating copies retained).
Override with `--backup-dir <path>`.

## Backup Strategy

### Retention Policy

- **Keep:** latest 7 full backups (db + uploads, paired by timestamp).
- **Automatic rotation:** `backup.py` deletes backups beyond the 7-count limit on each run.
- **No incremental backup** — each run is a full snapshot.

### Frequency Recommendation

| Environment | Cron expression | Cadence | Rationale |
|-------------|------------------|---------|-----------|
| **Production (recommended)** | `0 3 * * *` | Daily, 03:00 local | Low-traffic window, 24-hour RPO |
| **High-traffic prod** | `0 */6 * * *` | Every 6 hours | 6-hour RPO; safe on small VPS |
| **Staging / Dev** | `0 2 * * *` | Daily, 02:00 local | Sufficient for non-critical environments |

Adjust to match your **RPO (Recovery Point Objective)**. The backup is lightweight
(gzip + tar), so `0 */6 * * *` is safe even on a 1 vCPU VPS.

## Cron Setup

### Linux / macOS — cron

```cron
# Visa MVP backup — daily at 03:00 (recommended for prod)
# Replace /path/to/venv/bin/python with the actual venv interpreter
# Replace /path/to/visa-mvp/backend with the absolute path to the backend dir.
0 3 * * * cd /path/to/visa-mvp/backend && /path/to/venv/bin/python scripts/backup.py >> logs/backup.log 2>&1
```

Install:

```bash
crontab -e
# paste the line above, save and exit
crontab -l | grep backup    # verify it's loaded
```

If you don't have a venv, use the system Python:

```cron
0 3 * * * cd /path/to/visa-mvp/backend && python3 scripts/backup.py >> logs/backup.log 2>&1
```

The `cd` is required so the script can resolve `data/visa_mvp.db` and `data/materials/`
relative to the backend directory.

### macOS (launchd alternative)

If you prefer launchd over cron, see the previous W15 runbook. Both work;
cron is simpler for a single host.

### Linux (systemd timer — recommended for servers with systemd)

Create `/etc/systemd/system/visamvp-backup.service`:

```ini
[Unit]
Description=Visa MVP Backup

[Service]
Type=oneshot
WorkingDirectory=/path/to/visa-mvp/backend
ExecStart=/path/to/venv/bin/python /path/to/visa-mvp/backend/scripts/backup.py
StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/visamvp-backup.timer`:

```ini
[Unit]
Description=Visa MVP Backup Timer (daily at 03:00)

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now visamvp-backup.timer
journalctl -u visamvp-backup.service   # view log
```

## Manual Operations

### Run a Backup Manually

```bash
cd backend
python3 scripts/backup.py
```

Dry-run (preview without writing):

```bash
python3 scripts/backup.py --dry-run
```

Custom backup directory (e.g., mounted backup volume):

```bash
python3 scripts/backup.py --backup-dir /mnt/backup-drive/visa-mvp/
```

### List Available Backups

```bash
python3 scripts/restore.py --list
```

Sample output:

```
Backups in: backend/data/backups

  Timestamp            DB                                  Uploads
  -------------------- ----------------------------------- -----------------------------------
  20260615-110129      visa_mvp-20260615-110129.db.gz      uploads-20260615-110129.tar.gz
  20260615-110058      visa_mvp-20260615-110058.db.gz      uploads-20260615-110058.tar.gz
```

### Restore from Backup

**Interactive restore** (prompts for confirmation):

```bash
python3 scripts/restore.py --timestamp 20260615-110129
# type 'yes' when prompted
```

**Restore latest backup automatically:**

```bash
python3 scripts/restore.py --auto-confirm
```

**Dry-run restore (no changes):**

```bash
python3 scripts/restore.py --timestamp 20260615-110129 --dry-run
```

> **Safety:** Before overwriting, `restore.py` automatically renames the
> current live DB and materials/ to `.pre_restore` suffix. You can delete them
> manually after verifying the restore succeeded.

## Recovery Procedures

### Full Restore (DB + Uploads)

1. Stop the application (if running):
   ```bash
   pkill -f uvicorn   # or your process manager
   ```
2. Identify the backup timestamp to restore:
   ```bash
   python3 scripts/restore.py --list
   ```
3. Run restore:
   ```bash
   python3 scripts/restore.py --timestamp 20260615-110129
   # type 'yes' when prompted
   ```
4. Restart the application:
   ```bash
   uvicorn app.main:app --reload ...
   ```

### Database-Only Restore (Uploads Intact)

Use the helper snippet below (the `restore.py` CLI always restores both — for
DB-only, decompress the `.db.gz` directly):

```bash
python3 -c "
import gzip, shutil
with gzip.open('data/backups/visa_mvp-20260615-110129.db.gz','rb') as f:
    with open('data/visa_mvp.db','wb') as out:
        shutil.copyfileobj(f, out)
"
```

### Uploads-Only Restore

```bash
mkdir -p data/materials.pre_restore && mv data/materials data/materials.pre_restore
tar -xzf data/backups/uploads-20260615-110129.tar.gz -C data/
```

### Verify Restore Integrity

```bash
# Check DB is readable
python3 -c "
import sqlite3
conn = sqlite3.connect('data/visa_mvp.db')
print('DB OK — tables:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])
"

# Check uploads directory is present
ls data/materials/ | wc -l
```

## Offsite Backup (Recommended)

Backups in `backend/data/backups/` are local. For production-grade resilience, copy them
to offsite storage:

```bash
# rsync to a remote server
rsync -avz backend/data/backups/ user@backup-server:/backups/visamvp/

# Or copy to an S3 bucket
aws s3 sync backend/data/backups/ s3://your-bucket/visamvp/backups/
```

Add the offsite copy command as a post-backup hook inside `backup.py` or as a
separate cron job immediately after `backup.py` succeeds.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No such file: data/visa_mvp.db` | DB doesn't exist yet | First run of the app will create it; backup.py skips gracefully |
| `WARNING: Source file not found: data/materials/` | No uploads yet | Skip is normal before first upload |
| Restore fails "type 'yes'" | Script waiting for input in non-interactive context | Use `--auto-confirm` flag |
| `backup.log` is empty | Cron didn't fire | Check `crontab -l`; verify `cd` to backend dir |
| Pre-restore copies accumulate | Restore ran but old copies were never cleaned | Manually delete `*.pre_restore` files after verifying restore |
| Backups accumulating beyond 7 | Rotation glob bug (legacy) | Already fixed — verify `backup.py` uses `{prefix}*` glob, not `{prefix}_*` |

## File Reference

| Path | Description |
|------|-------------|
| `backend/scripts/backup.py` | Backup entry point (stdlib only) |
| `backend/scripts/restore.py` | Restore entry point (stdlib only) |
| `backend/data/backups/` | Default backup output directory |
| `backend/data/visa_mvp.db` | Live SQLite database |
| `backend/data/materials/` | Live uploaded files (a.k.a. "uploads/") |
| `backend/docs/backup-runbook.md` | This document |