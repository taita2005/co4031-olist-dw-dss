#!/usr/bin/env bash
# Stop the project-local PostgreSQL server.
set -euo pipefail
source "$(dirname "$0")/env.sh"
pg_ctl -D "$PGDATA_DIR" -m fast stop
