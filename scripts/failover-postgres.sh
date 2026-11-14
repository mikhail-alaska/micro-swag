#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
. ./scripts/common.sh

primary=$(find_primary)
if [ "$primary" = postgres ]; then
    standby=postgres_standby
else
    standby=postgres
fi

lsn=$(query_db "$primary" 'SELECT pg_current_wal_lsn()')
replayed=f
for attempt in $(seq 1 60); do
    replayed=$(query_db "$standby" "SELECT pg_last_wal_replay_lsn() >= '$lsn'::pg_lsn")
    [ "$replayed" = t ] && break
    sleep 1
done
if [ "$replayed" != t ]; then
    printf 'Standby has not caught up; primary was not stopped\n' >&2
    exit 1
fi

printf 'Stopping %s with SIGKILL; promoting %s\n' "$primary" "$standby"
started=$(date +%s)
docker compose kill -s SIGKILL "$primary"

# При следующем старте старый primary должен стать репликой.
docker compose run --rm --no-deps --entrypoint sh "$primary" -ec '
    printf "%s\n" "$1" > /var/lib/postgresql/data/upstream
    touch /var/lib/postgresql/data/rebuild
' sh "$standby"

query_db "$standby" 'SELECT pg_promote(true, 60)'
wait_backend
finished=$(date +%s)
printf 'PostgreSQL promotion and API health: %s seconds; primary=%s\n' "$((finished - started))" "$standby"

docker compose up -d --no-deps "$primary"
for attempt in $(seq 1 90); do
    role=$(query_db "$primary" 'SELECT pg_is_in_recovery()' 2>/dev/null) || role=unknown
    [ "$role" = t ] && break
    sleep 1
done
if [ "$role" != t ]; then
    printf 'Old primary did not rejoin as standby\n' >&2
    exit 1
fi
printf '%s has rejoined as standby; previous data is kept in its volume\n' "$primary"
