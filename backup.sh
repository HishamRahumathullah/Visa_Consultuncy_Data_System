#!/bin/bash
# /opt/backup/backup.sh — Run twice daily via cron
# Example crontab: 0 */12 * * * /opt/backup/backup.sh

set -euo pipefail

# Configuration
export BORG_REPO="/var/borg/repo"
export BORG_PASSPHRASE="${BORG_PASSPHRASE:?Error: BORG_PASSPHRASE environment variable must be set}"
STORAGE_PATH="/var/www/visa-consultancy"
DB_NAME="visa_consultancy"
DB_USER="${DB_USER:-visauser}"
DB_HOST="${DB_HOST:-localhost}"
STORJ_BUCKET="s3://borg-backup-visa"
TIMESTAMP=$(date +%Y-%m-%d-%H%M)
LOG_FILE="/var/log/backup.log"

# Logging helper
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log "=== Backup started: $TIMESTAMP ==="

# Initialize borg repo if it doesn't exist
if [ ! -d "$BORG_REPO" ]; then
    log "Initializing Borg repository at $BORG_REPO"
    borg init --encryption=repokey "$BORG_REPO" || { log "ERROR: Failed to initialize Borg repo"; exit 1; }
fi

# Create application backup
log "Creating application backup..."
borg create \
    --compression lz4 \
    --exclude "$STORAGE_PATH/uploads/*/tmp" \
    --exclude "$STORAGE_PATH/static" \
    --exclude "$STORAGE_PATH/*.pyc" \
    --exclude "$STORAGE_PATH/__pycache__" \
    "$BORG_REPO::$TIMESTAMP" \
    "$STORAGE_PATH" || { log "ERROR: Borg create failed"; exit 1; }

# Dump database to temp file
DB_DUMP="/tmp/db-$TIMESTAMP.sql"
log "Dumping database $DB_NAME..."
pg_dump -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" > "$DB_DUMP" || { 
    log "ERROR: pg_dump failed"
    rm -f "$DB_DUMP"
    exit 1
}

# Archive database dump
log "Archiving database backup..."
borg create \
    --compression lz4 \
    "$BORG_REPO::db-$TIMESTAMP" \
    "$DB_DUMP" || { 
    log "ERROR: Borg DB archive failed"
    rm -f "$DB_DUMP"
    exit 1
}

# Clean up temp dump
rm -f "$DB_DUMP"

# Prune old backups
log "Pruning old backups..."
borg prune \
    --keep-daily=7 \
    --keep-weekly=4 \
    --keep-monthly=6 \
    "$BORG_REPO" || log "WARNING: Prune had issues (non-critical)"

# Compact borg repository
log "Compacting repository..."
borg compact "$BORG_REPO" || log "WARNING: Compact had issues (non-critical)"

# Sync to Storj
log "Syncing to Storj..."
rclone sync "$BORG_REPO" "$STORJ_BUCKET" \
    --transfers=4 \
    --checksum \
    --verbose || { log "ERROR: rclone sync failed"; exit 1; }

log "=== Backup completed successfully: $TIMESTAMP ==="
