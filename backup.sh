#!/bin/bash
# /opt/backup/backup.sh — Run twice daily via cron

BORG_REPO="/var/borg/repo"
STORAGE_PATH="/var/www/visa-consultancy"
DB_NAME="visa_consultancy"
STORJ_BUCKET="s3://borg-backup-visa"

# Create backup
borg create \
    --compression lz4 \
    "$BORG_REPO::$(date +%Y-%m-%d-%H%M)" \
    "$STORAGE_PATH" \
    --exclude "$STORAGE_PATH/uploads/*/tmp"

# Dump database
pg_dump "$DB_NAME" | borg create "$BORG_REPO::db-$(date +%Y-%m-%d-%H%M)" -

# Prune old backups (keep 7 daily, 4 weekly, 6 monthly)
borg prune --keep-daily=7 --keep-weekly=4 --keep-monthly=6 "$BORG_REPO"

# Sync to Storj
rclone sync "$BORG_REPO" "$STORJ_BUCKET" --transfers=4

# Log result
echo "[$(date)] Backup completed" >> /var/log/backup.log
