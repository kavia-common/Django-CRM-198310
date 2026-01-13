# Cold Start Readiness Report — Django (BottleCRM) + PostgreSQL + Celery/Redis

This report is a **configuration-level cold start simulation analysis** for the Django backend. Because runtime environment variables are not available here, this analysis is based on static inspection of:

- `Django-CRM-198310/docker-compose.yml`
- `Django-CRM-198310/Dockerfile`
- `Django-CRM-198310/backend/crm/settings.py`
- `Django-CRM-198310/backend/crm/celery.py`
- `Django-CRM-198310/backend/crm/urls.py`
- `Django-CRM-198310/backend/README.md`

Goal: identify startup order assumptions, DB readiness checks, healthchecks, and likely cold-start race conditions/timeouts.

---

## 1) Expected Startup Order (Ideal)

For a reliable cold start on a fresh deployment (empty containers, fresh DB volume), the recommended sequencing is:

1. **PostgreSQL starts**
   - Postgres container becomes *ready* (not just “started”).
   - Readiness means `pg_isready` succeeds and server accepts connections.

2. **(Optional) DB bootstrap**
   - Create DB/user/schema if not pre-provisioned (often done by Postgres env vars and init scripts, or an init job).
   - For this app specifically: consider ensuring DB user is non-superuser if enforcing RLS strictly (see backend README RLS section).

3. **Django migrations run** (one-shot init step)
   - `python manage.py migrate` must succeed before the web server is considered “ready”.
   - If RLS migrations exist, they will run here and may have special requirements on DB permissions/user role.

4. **Django web process starts** (Gunicorn/Uvicorn/Django runserver)
   - Only after DB is reachable and migrations are applied.

5. **Redis starts** (if used as Celery broker/result backend)
   - Redis readiness means the port accepts connections (PING).

6. **Celery worker starts**
   - Only after: Redis is reachable and DB is reachable (Celery tasks import Django settings and frequently hit DB).

7. **Celery beat starts** (if enabled)
   - Only after: Redis and DB are reachable.
   - Beat schedules tasks; if worker isn’t ready, tasks may backlog; if DB isn’t ready, tasks may fail repeatedly.

**Note:** In production, steps 5–7 are usually parallelizable with explicit readiness gates (worker/beat can wait/retry), but in a cold start they should not “race” the DB/broker coming up.

---

## 2) What Exists Today (From Repo Config)

### 2.1 docker-compose.yml (current)

`Django-CRM-198310/docker-compose.yml` defines only:

- `db` service: `image: postgres`, with:
  - `env_file: ./db.env`
  - No ports exposed (not necessarily an issue internally)
  - No healthcheck
  - No persistent volume enabled (commented out)

- `web` service: `build: .`, `image: micropyramid/django-crm:1`, with:
  - `env_file: ./db.env`
  - `ports: "8001:8000"`
  - `depends_on: - db`

**Findings:**
- `depends_on` only enforces **start order**, not readiness. In Compose v2 format (and also in many modern Compose implementations), `depends_on` does **not** wait for Postgres to accept connections.
- There is **no explicit migration step**, and no process command is shown for `web` in the compose file. The startup behavior depends on the image entrypoint/CMD (not visible in this compose).
- There are **no Redis/Celery services** in the compose file. Yet Django settings require Celery broker env vars.

### 2.2 Missing env file referenced by compose

Compose references `./db.env`:

```yaml
env_file:
  - ./db.env
```

Repo context indicates `db.env` is not present. If absent at deploy time, Compose will fail or run without required env vars.

**Impact:** The backend will fail fast because `backend/crm/settings.py` requires multiple env vars via `os.environ[...]`.

### 2.3 Django settings: DB and critical env vars

In `backend/crm/settings.py`:

- `SECRET_KEY = os.environ["SECRET_KEY"]` (required)
- DB config requires:
  - `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT` (all required via `os.environ[...]`)
- `ENV_TYPE = os.environ["ENV_TYPE"]` required
- `DEFAULT_FROM_EMAIL`, `ADMIN_EMAIL` required
- Celery required:
  - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` required
- Swagger required:
  - `DOMAIN_NAME = os.environ["DOMAIN_NAME"]`
  - `SWAGGER_ROOT_URL = os.environ["SWAGGER_ROOT_URL"]`

**Cold start implication:** any missing env var will crash Django at import time (before it can serve any endpoint including health checks).

### 2.4 Celery config

`backend/crm/celery.py` configures:
- `DJANGO_SETTINGS_MODULE=crm.settings`
- Beat schedules tasks (recurring invoices, overdue checks, etc.)

**Cold start implication:** Celery Beat/Worker startup will import Django settings and crash if env vars/DB connectivity are missing. Also, scheduled tasks typically require DB readiness.

### 2.5 Existing health endpoint (app-level)

`backend/crm/urls.py` includes:

- `GET /healthz/` serving a static template: `TemplateView(template_name="healthz.html")`

**What it provides:**
- A basic “web process up” indicator (only if Django server started successfully).

**What it does NOT provide:**
- No DB connectivity check
- No Redis connectivity check
- No migrations readiness signal

So `/healthz/` is a **liveness-ish** indicator, not a full readiness probe.

### 2.6 Dockerfile (current)

`Django-CRM-198310/Dockerfile`:
- Installs python + dependencies, creates venv, installs requirements + gunicorn.
- Does **not** define `CMD`/`ENTRYPOINT`.

**Cold start implication:** The runtime command comes from elsewhere (docker-compose `command:` or base image metadata). Since compose does not define `command:`, the resulting runtime behavior is ambiguous from static inspection. If there is no default CMD in the built image, the container may exit immediately.

---

## 3) Missing or Weak Readiness/Health Controls

### 3.1 No Postgres healthcheck

There is **no** `healthcheck:` for the `db` service, e.g.:

- `pg_isready -U ...`

Without this, orchestration cannot accurately gate downstream startup on DB readiness.

### 3.2 No “wait for DB” gate in web startup

No `wait-for-db` script is referenced in compose or Dockerfile.

**Typical failure mode on cold start:**
- Django starts before Postgres is accepting connections.
- Django crashes with `psycopg2.OperationalError: could not connect to server`.
- Container restarts, flaps, or stays down until DB is ready.

### 3.3 No explicit migrations-on-start or init job

No dedicated migration job is configured. That means either:

- The container entrypoint runs migrations implicitly (unknown), or
- Migrations must be run manually (not suitable for automated deploy), or
- Web starts without migrations and fails on first DB access.

### 3.4 Celery/Redis are not defined in compose

Django settings require Celery broker/result backend, and README expects Redis. But compose file defines only `db` and `web`.

**Typical failure mode:**
- Celery worker/beat not deployed at all (missed functionality)
- Or if added later without readiness gates, worker starts before Redis or DB and crashloops.

---

## 4) Likely Cold Start Race Conditions / Failure Scenarios

### Scenario A: Postgres not ready → Django fails at startup
- Compose starts `db`, then starts `web` immediately (`depends_on` only).
- If Django tries to connect during startup (migrations, app initialization, first request), it can fail.

**Symptoms:**
- `OperationalError`, connection refused/timeouts
- CrashLoopBackOff (k8s) / restarting container (compose)

### Scenario B: Missing `db.env` → web (and db) cannot configure correctly
- Compose references `./db.env` which appears missing.
- Django settings require env vars and will raise `KeyError` on import.

**Symptoms:**
- Container exits immediately with KeyError for `SECRET_KEY`, `DBNAME`, etc.

### Scenario C: Migrations/RLS migrations run too early or under wrong DB role
The backend has strong RLS guidance: superusers bypass RLS. If migrations expect certain permissions or rely on RLS functions:

- If DB user is misconfigured (superuser vs non-superuser), security properties may not hold.
- If migrations enable RLS policies, they may require elevated privileges.

**Symptoms:**
- Migration failures
- RLS not enforced even though app expects it

### Scenario D: Celery starts without Redis or DB readiness
Celery imports Django settings (and tasks often use DB). If `CELERY_BROKER_URL` points at Redis but Redis isn’t ready:

**Symptoms:**
- Repeated broker connection errors
- Worker crash loops
- Beat scheduling tasks that cannot execute reliably

### Scenario E: Health endpoint reports “up” while DB is down
Current `/healthz/` is a TemplateView. If Django is running but DB is broken, `/healthz/` still returns 200.

**Symptoms:**
- Orchestrator routes traffic to a “ready” service that will error on DB calls.

---

## 5) Concrete Recommendations (Compose + Deploy Practices)

Below are targeted recommendations to eliminate cold start races. (Not implementing here; this is guidance.)

### 5.1 Add Postgres healthcheck and gate web startup on it

Add to `db`:

- Healthcheck using `pg_isready`:
  - `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`

Then use `depends_on` **with health condition** (supported in newer compose specs; classic v2 has limitations). If not supported, use a wait script in `web` entrypoint.

### 5.2 Add a wait-for-db script for Django and Celery

Use one of:
- `wait-for-it.sh`
- `dockerize`
- a small python/bash loop that attempts TCP connect + `psql`/`pg_isready`

**Best practice:**
- Wait for DB socket acceptance
- Then run `python manage.py migrate`
- Then start gunicorn

### 5.3 Introduce a dedicated “migrate” one-shot service

Recommended pattern:

- `migrate` service runs `python manage.py migrate` once
- `web` depends on migrate completion
- Optionally `manage_rls --verify-user` or other RLS setup as part of init flow

This prevents multiple web replicas from racing migrations.

### 5.4 Add Redis + Celery services to compose (or deployment manifests)

At minimum:

- `redis` service with healthcheck (`redis-cli ping`)
- `celery_worker` service depending on `redis` and `db` readiness
- `celery_beat` service similarly gated

### 5.5 Improve readiness endpoint(s)

Current `/healthz/` is a static template. Keep it as liveness, but add a readiness endpoint that checks:

- DB connectivity (simple `SELECT 1`)
- Optional: migration state (e.g., `django_migrations` table reachable)
- Optional: Redis connectivity if Celery is required for core features

In k8s terms:
- `/healthz/` -> livenessProbe
- `/readyz/` -> readinessProbe

### 5.6 Timeouts and connection management

From static inspection:
- No explicit `CONN_MAX_AGE` is set in Django DB settings; default is `0` (no persistent connections).

Consider setting:
- `CONN_MAX_AGE` to a small value in production to reduce connection churn on cold start spikes.

(If using PgBouncer/connection pooling, configure accordingly.)

### 5.7 Ensure container command/entrypoint is explicit

The Dockerfile has no `CMD`. Compose also does not specify `command:`.

Recommendation:
- Define the command explicitly in compose or Dockerfile to avoid ambiguity (e.g., gunicorn command, bind port 8000).

---

## 6) Readiness Scorecard (Static)

| Area | Status | Notes |
|------|--------|------|
| Postgres healthcheck | Missing | No `healthcheck:` in compose |
| Web waits for DB | Missing | `depends_on` only, no wait script |
| Migrations automated | Unclear / likely missing | No migrate job in compose; unknown entrypoint |
| Redis service | Missing (in compose) | Django settings expect Celery broker env |
| Celery worker/beat | Missing (in compose) | Celery configured in code, but no process definition |
| App-level liveness endpoint | Present | `/healthz/` static template |
| App-level readiness endpoint | Missing | `/healthz/` doesn’t check DB/Redis |
| Env file referenced exists | Likely missing | `./db.env` referenced but not present |

---

## 7) Priority Fix List (Recommended Next Steps)

1. **Create/provide env file(s)** required by compose (or convert to `.env` + explicit `environment:`).
2. **Define explicit startup command** for `web` (gunicorn) and include DB wait + migrations.
3. **Add Postgres healthcheck** and gate dependencies on readiness.
4. **Add Redis + Celery worker/beat services** with readiness gates.
5. **Add a real readiness endpoint** checking DB (and Redis if required).

---

## Appendix: Key Evidence (File References)

- `docker-compose.yml`: only `db` and `web`; `web depends_on db`; env_file `./db.env` for both.
- `backend/crm/settings.py`: requires `SECRET_KEY`, `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT`, `ENV_TYPE`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, etc. via `os.environ[...]`.
- `backend/crm/urls.py`: `/healthz/` exists but is a TemplateView (no DB check).
- `backend/crm/celery.py`: defines beat schedule; imports Django settings module.
- `Dockerfile`: installs dependencies but no `CMD`/`ENTRYPOINT`.

---
Report generated via static analysis; no runtime verification performed.
