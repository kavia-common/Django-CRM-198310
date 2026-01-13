# Cold-start readiness report (latest)

Date: 2026-01-13  
Scope: `docker-compose.yml` healthchecks + startup sequencing, `backend/scripts/entrypoint.sh` DB wait + migration plan behavior.  
Environment note: Docker is not available in this execution environment (`docker: command not found`), so this is a *simulation* based on static validation of compose/scripts and known runtime expectations.

## What was changed
1. **Startup order enforced**: `celery` now depends on `web` being healthy (in addition to `db` and `redis`), achieving:
   - Postgres (`db`) healthy
   - Redis (`redis`) healthy
   - Web (`web`) healthy
   - Celery (`celery`) starts

2. **Celery healthcheck added**:
   - Uses a lightweight process-based check (`ps aux | grep ...`) to confirm the worker process is present.
   - This avoids needing a `celery inspect ping` configuration which can fail in deployments where inspect is disabled or broker auth differs.

3. **Migrations before app start**:
   - `entrypoint.sh` continues to wait for DB readiness via `wait_for_db.sh`.
   - For `RUN_MIGRATIONS=true` it now:
     - attempts `python manage.py migrate --plan` (if supported) and prints the plan,
     - falls back gracefully if `--plan` is unavailable,
     - then runs `python manage.py migrate --noinput`.

## Healthcheck summary (current)
### Postgres (`db`)
- Healthcheck: `pg_isready -U $DBUSER -d $DBNAME -h 127.0.0.1 -p $DBPORT`
- Interval/timeout/retries: 5s / 3s / 20 (start_period 10s)
- Notes:
  - Uses variables from `db.env` (compose `env_file`), not `backend/.env`.

### Web (`web`)
- Depends on: `db` healthy, `redis` healthy
- Healthcheck: `curl -fsS http://127.0.0.1:8000/healthz/`
- Interval/timeout/retries: 10s / 3s / 20 (start_period 20s)

### Celery (`celery`)
- Depends on: `db` healthy, `redis` healthy, `web` healthy
- Healthcheck: process-based `ps`/`grep` check
- Interval/timeout/retries: 10s / 5s / 20 (start_period 20s)

## Cold-start simulation outcomes with placeholder `backend/.env`
### Critical mismatch: compose uses `./db.env`, not `backend/.env`
- `docker-compose.yml` uses `env_file: ./db.env` for `db`, `web`, `celery`.
- Therefore, *the placeholder file `backend/.env` will not be loaded* unless you update compose or copy values into `db.env`.
- If `db.env` is missing or incomplete, `wait_for_db.sh` will fail fast due to required env vars:
  - `DBHOST`, `DBPORT`, `DBUSER`, `DBNAME` must be set.

### Expected blockers if placeholder values are used as-is
1. **DBHOST must be service name inside compose network**
   - In a compose network, `DBHOST` should typically be `db`, not `127.0.0.1`.
   - Placeholder `backend/.env` uses `DBHOST=127.0.0.1`, which will fail inside containers.
   - Recommended: `DBHOST=db`, `DBPORT=5432`.

2. **Celery broker URLs must be in-network**
   - Placeholder `backend/.env` uses `redis://localhost:6379/0`.
   - Inside containers, `localhost` refers to the container itself, not the `redis` service.
   - Recommended: `CELERY_BROKER_URL=redis://redis:6379/0` and same for result backend.

3. **Migration runtime blockers**
   - `python manage.py migrate --plan` support depends on Django version.
   - The entrypoint now safely falls back if `--plan` is unsupported, so this should not prevent startup.
   - Actual migration application may still fail if:
     - DB credentials are wrong,
     - DB user lacks privileges,
     - required Postgres extensions are missing (e.g., if migrations depend on extensions),
     - RLS setup expects manual steps (see `RLS_SETUP.md`).

## Recommended tuning parameters (if health flaps in real runs)
- `db.healthcheck.start_period`: increase to `20s` if Postgres init is slow on first boot.
- `web.healthcheck.start_period`: `30s` if migrations + server warmup exceed 20s.
- `wait_for_db` settings (container env):
  - `WAIT_FOR_DB_TIMEOUT_SECONDS=120`
  - `WAIT_FOR_DB_SLEEP_SECONDS=2`

## Suggested next steps to actually cold-start locally
1. Ensure `db.env` exists and contains **container-correct** values:
   - `DBHOST=db`
   - `DBPORT=5432`
   - `DBUSER=...`, `DBNAME=...`, `DBPASSWORD=...`
   - `CELERY_BROKER_URL=redis://redis:6379/0`
   - `CELERY_RESULT_BACKEND=redis://redis:6379/0`
2. Run:
   - `docker compose up --build`
3. If web healthcheck fails, inspect:
   - whether `/healthz/` is mounted and reachable (it is checked on `127.0.0.1:8000` inside container)
   - migration output in web logs

## Conclusion
- With the updated compose ordering and entrypoint migration behavior, the system is **structurally ready** for a clean cold-start.
- The **most likely cold-start failure with placeholders** is *incorrect in-container hostnames* (`127.0.0.1` / `localhost`) and the fact compose loads `db.env` rather than `backend/.env`.
- Once env values are aligned for container networking, services should start in the intended order: `db -> web -> celery`.
