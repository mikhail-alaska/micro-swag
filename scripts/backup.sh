#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
. ./scripts/common.sh

primary=$(find_primary)
backup=${1:-../backups/swag-$(date +%Y%m%d-%H%M%S).sql}
mkdir -p "$(dirname "$backup")"
umask 077
docker compose exec -T "$primary" sh -ec \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' > "$backup"
printf 'Backup saved: %s\n' "$backup"
