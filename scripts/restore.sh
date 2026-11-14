#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
. ./scripts/common.sh

backup=${1:?Usage: scripts/restore.sh backup.sql [new_database]}
database=${2:-swag_restore_$(date +%Y%m%d_%H%M%S)}
case "$database" in
    ''|*[!a-z0-9_]*|postgres|template0|template1)
        printf 'Use a new database name containing lowercase letters, numbers and underscores\n' >&2
        exit 1 ;;
esac
[ -f "$backup" ] || { printf 'Backup file not found\n' >&2; exit 1; }

primary=$(find_primary)
active_db=$(docker compose exec -T "$primary" printenv POSTGRES_DB)
if [ "$database" = "$active_db" ]; then
    printf 'Restore creates a separate database; refusing to overwrite the application database\n' >&2
    exit 1
fi

docker compose exec -T "$primary" sh -ec 'createdb -U "$POSTGRES_USER" "$1"' sh "$database"
docker compose exec -T "$primary" sh -ec \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$database" < "$backup"
docker compose exec -T "$primary" sh -ec \
    'psql -U "$POSTGRES_USER" -d "$1" -c "SELECT count(*) AS restored_clicks FROM clicks"' sh "$database"
printf 'Restored into separate database: %s\n' "$database"
