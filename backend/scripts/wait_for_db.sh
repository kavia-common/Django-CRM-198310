#!/bin/sh
# POSIX-compliant "wait for Postgres" helper.
# Uses pg_isready (preferred) if available; falls back to bash /dev/tcp if present.
#
# Expected env vars:
#   DBHOST, DBPORT, DBUSER, DBNAME
#
# Optional env vars:
#   WAIT_FOR_DB_TIMEOUT_SECONDS (default: 60)
#   WAIT_FOR_DB_SLEEP_SECONDS   (default: 2)

set -eu

: "${DBHOST:?DBHOST must be set}"
: "${DBPORT:?DBPORT must be set}"
: "${DBUSER:?DBUSER must be set}"
: "${DBNAME:?DBNAME must be set}"

TIMEOUT_SECONDS="${WAIT_FOR_DB_TIMEOUT_SECONDS:-60}"
SLEEP_SECONDS="${WAIT_FOR_DB_SLEEP_SECONDS:-2}"

start_ts="$(date +%s)"

echo "[wait_for_db] Waiting for Postgres at ${DBHOST}:${DBPORT} (db=${DBNAME} user=${DBUSER})..."
echo "[wait_for_db] Timeout: ${TIMEOUT_SECONDS}s, sleep: ${SLEEP_SECONDS}s"

# Prefer pg_isready if present (recommended)
if command -v pg_isready >/dev/null 2>&1; then
  while :; do
    if pg_isready -h "$DBHOST" -p "$DBPORT" -U "$DBUSER" -d "$DBNAME" >/dev/null 2>&1; then
      echo "[wait_for_db] Postgres is ready."
      exit 0
    fi

    now_ts="$(date +%s)"
    elapsed="$((now_ts - start_ts))"
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
      echo "[wait_for_db] ERROR: Timed out after ${TIMEOUT_SECONDS}s waiting for Postgres." >&2
      exit 1
    fi

    sleep "$SLEEP_SECONDS"
  done
fi

# Fallback: if /dev/tcp is supported (requires bash; may not exist in busybox sh)
if command -v bash >/dev/null 2>&1; then
  while :; do
    if bash -c ">/dev/tcp/${DBHOST}/${DBPORT}" >/dev/null 2>&1; then
      echo "[wait_for_db] Postgres TCP port is reachable (pg_isready not found)."
      exit 0
    fi

    now_ts="$(date +%s)"
    elapsed="$((now_ts - start_ts))"
    if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
      echo "[wait_for_db] ERROR: Timed out after ${TIMEOUT_SECONDS}s waiting for Postgres TCP port." >&2
      exit 1
    fi

    sleep "$SLEEP_SECONDS"
  done
fi

echo "[wait_for_db] ERROR: Neither pg_isready nor bash is available; cannot perform DB readiness check." >&2
exit 2
