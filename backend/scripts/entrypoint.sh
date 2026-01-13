#!/bin/sh
# POSIX-compliant entrypoint used for both web and celery containers.
# Responsibilities:
#  1) Wait for Postgres (DBHOST/DBPORT/DBUSER/DBNAME)
#  2) Optionally run migrations for web (or when RUN_MIGRATIONS=true)
#     - First attempt: `migrate --plan` for visibility (if supported)
#     - Then apply: `migrate --noinput`
#  3) Exec the provided CMD
#
# Notes:
# - This script intentionally fails fast on missing DB env vars because the app
#   cannot start without a valid database connection string.

set -eu

# Ensure scripts are executable even if git checkout lost mode bits.
# (chmod might fail on read-only FS; ignore error.)
chmod +x /app/backend/scripts/wait_for_db.sh /app/backend/scripts/entrypoint.sh 2>/dev/null || true

/app/backend/scripts/wait_for_db.sh

RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "[entrypoint] Running Django migration plan (if supported)..."
  # `migrate --plan` is available on modern Django versions, but we defensively
  # fall back to plain migrate if it's not supported in this project/version.
  if python /app/backend/manage.py migrate --plan >/dev/null 2>&1; then
    python /app/backend/manage.py migrate --plan
  else
    echo "[entrypoint] NOTE: migrate --plan not supported; continuing without plan output."
  fi

  echo "[entrypoint] Applying Django migrations..."
  python /app/backend/manage.py migrate --noinput
fi

echo "[entrypoint] Starting: $*"
exec "$@"
