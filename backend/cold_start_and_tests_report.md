# Cold start readiness + tests report (healthchecks/wait-for-db)

Date: 2026-01-13

## Scope

Requested changes implemented:

1. Added a POSIX-compliant wait-for-db script: `backend/scripts/wait_for_db.sh`
2. Added an entrypoint wrapper for web/celery: `backend/scripts/entrypoint.sh`
3. Updated `docker-compose.yml`:
   - Postgres healthcheck using `pg_isready`
   - Redis service + healthcheck
   - `depends_on` uses `condition: service_healthy` for web/celery
   - web healthcheck uses existing endpoint `GET /healthz/` (template-based)
   - web runs migrations before server via `RUN_MIGRATIONS=true` and entrypoint
   - celery waits for DB before starting
4. Updated `Dockerfile` to include `postgresql-client` (for `pg_isready`) and set a default entrypoint to `/app/backend/scripts/entrypoint.sh`

No API contracts were changed. Health endpoint already existed at `/healthz/`.

## Cold start simulation attempt (non-destructive where possible)

### Tooling availability
- `docker` / `docker compose` not available in this execution environment, so an actual container cold start could not be run here.
- Python 3.12.3 was available, so we attempted Django commands locally in an isolated venv.

### Local venv setup
Command:
- `cd backend && python3 -m venv /tmp/bottlecrm_venv && . /tmp/bottlecrm_venv/bin/activate && pip -q install -r requirements.txt`

Result: succeeded.

### `manage.py check`
Command:
- `cd backend && . /tmp/bottlecrm_venv/bin/activate && python manage.py check`

Result: **FAILED**

Error (stdout/stderr excerpt):
- `KeyError: 'SECRET_KEY'` raised in `backend/crm/settings.py` at `SECRET_KEY = os.environ["SECRET_KEY"]`

### Blocker: missing required environment variables

Because settings use `os.environ[...]` (hard requirement), Django cannot start without these env vars:

- `SECRET_KEY`
- `ENV_TYPE`
- `DBNAME`
- `DBUSER`
- `DBPASSWORD`
- `DBHOST`
- `DBPORT`
- `DEFAULT_FROM_EMAIL`
- `ADMIN_EMAIL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `DOMAIN_NAME`
- `SWAGGER_ROOT_URL`

These match the documented example in `backend/.env.example`.

### Migrations/test suite
Not attempted because `manage.py check` cannot run until required env vars are provided.

If env vars are provided, the next intended sequence for a safe cold-start verification would be:

- `python manage.py check`
- `python manage.py showmigrations`
- `python manage.py migrate --plan`
- `pytest`

## Notes about docker-compose env files

The repo’s original `docker-compose.yml` referenced `./db.env`, but this file was not present in the workspace at the time of this run.

To use docker-compose successfully, you must provide `db.env` (or change compose to point at an existing env file). The env file must include at least the required variables listed above.

## Summary of failures

1. **Django cold-start readiness**: blocked by missing required env var `SECRET_KEY` (and others).
2. **Docker cold start**: cannot be executed in this environment because Docker tooling is unavailable.
3. **db.env**: referenced by compose, but not present in repo (must be created by deployer/operator).

## What to provide to unblock

- A `db.env` file (or equivalent env injection) containing all required variables listed above, including valid Postgres connection details and a Django `SECRET_KEY`.

Once provided, rerun:

- `python manage.py check`
- `python manage.py migrate --plan`
- `pytest`
