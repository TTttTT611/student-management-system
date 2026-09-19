#!/usr/bin/env bash
# Back up the MySQL database into BACKUP_DIR, keeping the last KEEP_DAYS days.
# Usage:
#   ./scripts/backup.sh                      # reads DATABASE_URL from .env
#   DATABASE_URL=mysql+pymysql://u:p@h:3306/db ./scripts/backup.sh
#   USE_DOCKER=1 ./scripts/backup.sh         # docker compose deployments: run mysqldump inside the db container
# Schedule daily at 02:00 with `crontab -e`:
#   0 2 * * * cd /opt/student-management && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
USE_DOCKER="${USE_DOCKER:-0}"

# Parse mysql+pymysql://user:pass@host:port/db
url="${DATABASE_URL#mysql+pymysql://}"
userpass="${url%%@*}"; hostdb="${url#*@}"
DB_USER="${userpass%%:*}"; DB_PASS="${userpass#*:}"
hostport="${hostdb%%/*}"; DB_NAME="${hostdb#*/}"
DB_HOST="${hostport%%:*}"; DB_PORT="${hostport#*:}"; [ "$DB_PORT" = "$DB_HOST" ] && DB_PORT=3306

mkdir -p "$BACKUP_DIR"
file="$BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"

if [ "$USE_DOCKER" = "1" ]; then
  docker compose exec -T db mysqldump -u"$DB_USER" -p"$DB_PASS" --single-transaction --routines "$DB_NAME" | gzip > "$file"
else
  MYSQL_PWD="$DB_PASS" mysqldump -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" --single-transaction --routines "$DB_NAME" | gzip > "$file"
fi

echo "$(date '+%F %T') backup written: $file ($(du -h "$file" | cut -f1))"
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$KEEP_DAYS" -delete
