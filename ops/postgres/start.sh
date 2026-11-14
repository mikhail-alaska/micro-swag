#!/bin/sh
set -eu

data_root=/var/lib/postgresql/data
mkdir -p "$PGDATA"
chown postgres:postgres "$data_root" "$PGDATA"

if [ -n "${UPSTREAM:-}" ] && [ ! -f "$data_root/upstream" ]; then
    printf '%s\n' "$UPSTREAM" > "$data_root/upstream"
fi

if [ -f "$data_root/upstream" ]; then
    upstream=$(cat "$data_root/upstream")
    if [ ! -f "$PGDATA/PG_VERSION" ] || [ -f "$data_root/rebuild" ]; then
        if [ -d "$PGDATA" ]; then
            mv "$PGDATA" "$data_root/previous-$(date +%s)"
        fi
        mkdir -p "$PGDATA"
        chown postgres:postgres "$PGDATA"
        export PGPASSWORD="$REPLICATION_PASSWORD"
        gosu postgres pg_basebackup -h "$upstream" -U replicator \
            -D "$PGDATA" -R -X stream --checkpoint=fast
        rm -f "$data_root/rebuild"
    fi
fi

export PGPASSWORD="$REPLICATION_PASSWORD"
exec docker-entrypoint.sh postgres \
    -c wal_level=replica \
    -c max_wal_senders=10 \
    -c max_connections=40 \
    -c shared_buffers=32MB \
    -c hot_standby=on
