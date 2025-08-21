#!/bin/bash

# PostgreSQL Backup Script
# Runs daily backups and keeps last 7 days

set -e

# Configuration
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-maler_kostenvoranschlag_prod}
DB_USER=${DB_USER:-postgres}
BACKUP_DIR=${BACKUP_DIR:-/backups}
RETENTION_DAYS=${RETENTION_DAYS:-7}

# Create backup directory if it doesn't exist
mkdir -p ${BACKUP_DIR}

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${DB_NAME}_${TIMESTAMP}.sql"

echo "Starting backup: ${BACKUP_FILE}"

# Perform backup
pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} \
    --no-password --clean --create --if-exists \
    --format=custom --compress=9 \
    --file="${BACKUP_FILE}.custom"

# Also create a plain SQL backup for easier inspection
pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} \
    --no-password --clean --create --if-exists \
    --file="${BACKUP_FILE}"

# Compress plain SQL backup
gzip "${BACKUP_FILE}"

echo "Backup completed: ${BACKUP_FILE}.gz and ${BACKUP_FILE}.custom"

# Clean up old backups
echo "Cleaning up backups older than ${RETENTION_DAYS} days..."
find ${BACKUP_DIR} -name "backup_${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
find ${BACKUP_DIR} -name "backup_${DB_NAME}_*.custom" -mtime +${RETENTION_DAYS} -delete

# Log backup status
echo "$(date): Backup completed successfully for database ${DB_NAME}" >> ${BACKUP_DIR}/backup.log

echo "Backup process finished"