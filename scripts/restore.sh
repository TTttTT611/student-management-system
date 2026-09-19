#!/usr/bin/env bash
# Restore the database from a backup file (OVERWRITES existing data!)
# Usage: ./scripts/restore.sh backups/student_db_20260919_020000.sql.gz
#        USE_DOCKER=1 ./scripts/restore.sh backups/xxx.sql.gz
set -euo pipefail

[ $# -eq 1 ] || { echo "Usage: $0 <backup.sql.gz>"; exit 1; }
backup="$1"
[ -f "$backup" ] || { echo "File not found: $backup"; exit 1; }

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
USE_DOCKER="${USE_DOCKER:-0}"

url="${DATABASE_URL#mysql+pymysql://}"
userpass="${url%%@*}"; hostdb="${url#*@}"
DB_USER="${userpass%%:*}"; DB_PASS="${userpass#*:}"
hostport="${hostdb%%/*}"; DB_NAME="${hostdb#*/}"
DB_HOST="${hostport%%:*}"; DB_PORT="${hostport#*:}"; [ "$DB_PORT" = "$DB_HOST" ] && DB_PORT=3306

read -r -p "This will overwrite database '$DB_NAME' with $backup. Continue? (yes/no) " ans
[ "$ans" = "yes" ] || { echo "Cancelled"; exit 0; }

if [ "$USE_DOCKER" = "1" ]; then
  gunzip -c "$backup" | docker compose exec -T db mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME"
else
  gunzip -c "$backup" | MYSQL_PWD="$DB_PASS" mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" "$DB_NAME"
fi
echo "Restore complete"
