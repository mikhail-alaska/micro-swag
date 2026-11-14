#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set app_password="$APP_DB_PASSWORD" \
    --set replication_password="$REPLICATION_PASSWORD" \
    -f /opt/swag/init.sql

printf '\nhost replication replicator all scram-sha-256\n' >> "$PGDATA/pg_hba.conf"
