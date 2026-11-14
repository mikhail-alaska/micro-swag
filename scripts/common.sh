#!/bin/sh

query_db() {
    node=$1
    sql=$2
    docker compose exec -T "$node" sh -ec \
        'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"' sh "$sql"
}

find_primary() {
    for node in postgres postgres_standby; do
        role=$(query_db "$node" 'SELECT pg_is_in_recovery()' 2>/dev/null) || continue
        if [ "$role" = f ]; then
            printf '%s\n' "$node"
            return 0
        fi
    done
    printf 'Writable PostgreSQL node not found\n' >&2
    return 1
}

wait_backend() {
    for attempt in $(seq 1 60); do
        if docker compose exec -T backend python -c \
            'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)' \
            >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    printf 'Backend did not recover in time\n' >&2
    return 1
}
