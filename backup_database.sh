#!/bin/bash

# FastSub PostgreSQL automatic backup

BACKUP_DIR="$HOME/fastsub_backups"
DB_NAME="fastsub"
DB_USER="fastsub_user"
DB_HOST="localhost"
DB_PORT="5432"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Timestamp
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Backup filename
BACKUP_FILE="$BACKUP_DIR/fastsub_$TIMESTAMP.sql.gz"

echo "Starting FastSub PostgreSQL backup..."

# Create compressed PostgreSQL backup
pg_dump \
    -U "$DB_USER" \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -d "$DB_NAME" \
    | gzip > "$BACKUP_FILE"

# Check if backup succeeded
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "Backup successful!"
    echo "Saved to: $BACKUP_FILE"
else
    echo "Backup failed!"
    rm -f "$BACKUP_FILE"
    exit 1
fi
