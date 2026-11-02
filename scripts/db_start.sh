#!/usr/bin/env bash
# Initialise (first run only) and start the project-local PostgreSQL server.
set -euo pipefail
source "$(dirname "$0")/env.sh"

if [ ! -d "$PGDATA_DIR" ]; then
  initdb -D "$PGDATA_DIR" -U "$PGUSER" --auth=trust --encoding=UTF8 --locale=C >/dev/null
fi

if pg_ctl -D "$PGDATA_DIR" status >/dev/null 2>&1; then
  echo "PostgreSQL already running on port $PGPORT"
else
  pg_ctl -D "$PGDATA_DIR" -l "$PGDATA_DIR/server.log" -o "-p $PGPORT -k /tmp" -w start
fi

psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PGDATABASE'" | grep -q 1 \
  || createdb "$PGDATABASE"
echo "Database '$PGDATABASE' ready at $PGHOST:$PGPORT (user $PGUSER)"
