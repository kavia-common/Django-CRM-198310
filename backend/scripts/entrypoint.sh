#!/bin/sh
# POSIX-compliant entrypoint used for both web and celery containers.
# Responsibilities:
#  1) Wait for Postgres (DBHOST/DBPORT/DBUSER/DBNAME)
#  2) Optionally run migrations for web (or when RUN_MIGRATIONS=true)
#  3) Exec the provided CMD

set -eu

# Ensure scripts are executable even if git checkout lost mode bits.
# (chmod might fail on read-only FS; ignore error.)
chmod +x /app/backend/scripts/wait_for_db.sh /app/backend/scripts/entrypoint.sh 2>/dev/null || true

/app/backend/scripts/wait_for_db.sh

RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "[entrypoint] Running Django migrations..."
  python /app/backend/manage.py migrate --noinput
fi

echo "[entrypoint] Starting: $*"
exec "$@"
