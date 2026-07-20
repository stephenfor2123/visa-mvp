#!/usr/bin/env bash
# Install daily SQLite backup cron on the Alibaba VPS.
# Backups go to /var/backups/htexvisa/ (outside /opt/visa-mvp) so rsync of the
# repo cannot wipe them. Keeps 14 snapshots via scripts/backup.py.
#
# Usage on server:
#   bash /opt/visa-mvp/pm/infra/aliyun/install-sqlite-backup.sh
# Or from Mac:
#   ssh -i ~/.ssh/htex_aliyun root@47.77.178.213 'bash -s' < pm/infra/aliyun/install-sqlite-backup.sh

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/visa-mvp}"
BACKEND_DIR="$REPO_ROOT/backend"
BACKUP_DIR="/var/backups/htexvisa"
LOG_DIR="$BACKUP_DIR/logs"
CRON_MARKER="htexvisa-sqlite-backup"

log() { echo "[backup-install] $*"; }
die() { echo "[backup-install] ERROR: $*" >&2; exit 1; }

[ -d "$BACKEND_DIR" ] || die "missing $BACKEND_DIR"
[ -f "$BACKEND_DIR/scripts/backup.py" ] || die "missing scripts/backup.py — sync code first"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"
# Prefer docker live DB if present
LIVE_DB=""
[ -f "$BACKEND_DIR/.data/visa_mvp.db" ] && LIVE_DB="$BACKEND_DIR/.data/visa_mvp.db"
[ -z "$LIVE_DB" ] && [ -f "$BACKEND_DIR/data/visa_mvp.db" ] && LIVE_DB="$BACKEND_DIR/data/visa_mvp.db"
[ -n "$LIVE_DB" ] || die "no visa_mvp.db under .data/ or data/"

log "live DB: $LIVE_DB ($(stat -c%s "$LIVE_DB") bytes)"

# One-shot backup now
log "running immediate backup..."
cd "$BACKEND_DIR"
python3 scripts/backup.py --backup-dir "$BACKUP_DIR" | tee -a "$LOG_DIR/backup.log"

# Cron: 03:00 and 15:00 Asia/Shanghai (server is usually UTC+8)
CRON_LINE="0 3,15 * * * cd $BACKEND_DIR && /usr/bin/python3 scripts/backup.py --backup-dir $BACKUP_DIR >> $LOG_DIR/backup.log 2>&1  # $CRON_MARKER"

# Replace any previous marker lines, then append
TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "$CRON_MARKER" > "$TMP" || true
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

log "crontab installed:"
crontab -l | grep "$CRON_MARKER"
log "backups in: $BACKUP_DIR"
ls -lah "$BACKUP_DIR"/visa_mvp-*.db.gz 2>/dev/null | tail -5 || true
log "done."
