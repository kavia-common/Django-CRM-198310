# Full cold start + migrations + API tests — Run Report

## Overview & Purpose

This report documents an attempted **full cold start** of the BottleCRM stack (**Django + Postgres + Redis + Celery**) using the aligned environment files:

- `backend/.env` for Django web + celery services
- `db.env` for the Postgres container

It captures all observed failures during:
1) stack startup (in dependency order db → web → celery),
2) database migrations, and
3) API test execution.

## Value Proposition

A reproducible cold start and test run ensures:
- the Docker Compose stack can boot reliably in a new environment,
- migrations can fully create/upgrade schema (including RLS-related migrations), and
- the API test suite is runnable and provides regression coverage.

This report highlights what currently blocks that workflow.

## Features & Functionality

Actions attempted (per request):
- Validate Docker Compose availability and attempt cold start
- Run migrations with `manage.py migrate --noinput` (as entrypoint would)
- Run API tests (pytest and Django’s test runner)
- Capture and summarize:
  - startup failures / healthcheck failures
  - DB connectivity errors
  - migration failures
  - test failures and stack traces

## Architecture & Design

Target stack (expected):
- **Postgres** service using `db.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`)
- **Redis** service
- **Django web** service using `backend/.env` (`DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT`, etc.)
- **Celery worker** using `backend/.env`, depends on DB + Redis + Web

Compose file: `docker-compose.yml`
- web and celery override `DBHOST=db` in compose environment for container-to-container networking
- healthchecks exist for db/redis/web/celery

## Technical Requirements

To run the requested cold start as designed:
- Docker Engine + Docker Compose plugin must be available (`docker`, `docker compose`)
- Network access to pull images (postgres:16, redis:7, and build app image)
- Postgres must be reachable at the configured host/port for migrations/tests
- Test tooling:
  - `pytest`
  - `pytest-django` (if using pytest path)

## Configuration & Setup

Aligned env files used:
- `backend/.env`
  - currently uses placeholder DB settings:
    - `DBHOST="127.0.0.1"`
    - `DBPORT="5432"`
    - `DBNAME="bottlecrm"`
    - `DBUSER="postgres"`
    - `DBPASSWORD="postgres"`
- `db.env`
  - `POSTGRES_DB=bottlecrm`
  - `POSTGRES_USER=postgres`
  - `POSTGRES_PASSWORD=postgres`

Important: for Docker Compose, `docker-compose.yml` already sets `DBHOST="db"` for web/celery so containers use the correct internal hostname. When running locally (non-docker), `DBHOST=127.0.0.1` assumes Postgres is running on the same machine.

## Usage Examples

### 1) Docker cold start (expected command sequence)

From repo root:
- `docker compose down -v`
- `docker compose up -d db`
- wait for db healthcheck
- `docker compose up -d web`
- wait for web healthcheck
- `docker compose up -d celery`
- wait for celery healthcheck

### 2) Migrations (expected to be run by entrypoint)
- `python manage.py migrate --noinput`

### 3) API tests (one of the following)
- `pytest` (with pytest-django installed)
- `python manage.py test`

## Limitations & Assumptions

- This execution environment **does not have Docker installed**, so an actual Compose-based cold start could not be performed.
- The provided `.env` values are placeholders; DB connectivity will fail unless Postgres is actually running and reachable at the configured `DBHOST:DBPORT`.
- Because DB is unreachable, no meaningful migration application or endpoint-level integration tests could run.
- Some test modules appear out of sync with the current codebase (import errors during collection).

## Results

### A) Startup Order

Requested order: **db → web → celery**

#### Attempted: Docker Compose cold start
Command(s) attempted:
- `docker compose version`
- `docker ps`

Result:
- **FAIL**: Docker is not available in this environment.

Error:
- `bash: line 1: docker: command not found`

Impact:
- Cannot bring up db/web/celery containers, cannot use compose healthchecks/wait scripts here.

### B) Healthcheck Results

Not executable (Docker unavailable), therefore:
- db healthcheck: not run
- redis healthcheck: not run
- web healthcheck: not run
- celery healthcheck: not run

### C) Migration Output

Attempted to run migrations locally (outside Docker) using `backend/.env` placeholders:

Command:
- `python manage.py migrate --noinput`

Result:
- **FAIL** (DB connection refused)

Key error:
- `psycopg2.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused`
- Re-raised as:
  - `django.db.utils.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused`

Cause:
- No Postgres is running/listening at `127.0.0.1:5432` in this environment.

### D) Test Results

#### 1) pytest (initial attempt)
Command:
- `pytest -q`

Result:
- **FAIL during collection**: Django settings not configured.
- Warning:
  - `PytestConfigWarning: Unknown config option: DJANGO_SETTINGS_MODULE`
- Errors:
  - `django.core.exceptions.ImproperlyConfigured: Requested setting REST_FRAMEWORK, but settings are not configured...`

Root cause:
- `pytest-django` was not installed, so pytest didn’t understand `DJANGO_SETTINGS_MODULE` in `pytest.ini`.

#### 2) pytest (after installing pytest + pytest-django)
Installed:
- `pip install pytest pytest-django`

Command:
- `pytest -q`

Result:
- **FAIL during collection** due to code/test mismatch.

Error:
- `ImportError: cannot import name 'Company' from 'common.models'`

Failing import site:
- `backend/invoices/tests.py`:
  - `from common.models import Address, Attachments, Comment, Company, Teams, User`

Observed code state:
- `backend/common/models.py` defines `Org` (organization), not `Company`.
- Therefore, tests referencing `Company` appear stale relative to current models.

Impact:
- pytest cannot proceed to DB-dependent tests because it cannot even collect tests.

#### 3) Django test runner (manage.py test)
Command:
- `python manage.py test -v 2`

Result:
- **FAIL** with 10 import errors (tests discovered but cannot import modules/symbols).

Notable errors:
- `accounts.tests_celery_tasks`: cannot import `send_scheduled_emails` from `accounts.tasks`
- `cases.tests_celery_tasks`: `ModuleNotFoundError: No module named 'cases.tests'`
- `common.tests.test_multitenancy`: imports `pytest` directly; fails if pytest not installed in environment (initially)
- `invoices.tests`: cannot import `Company` from `common.models`
- multiple `*_tests_celery_tasks` refer to `*.tests` modules that do not exist.

Impact:
- Even with a working DB, these tests currently do not run cleanly because of import-level issues.

## Next Steps

### 1) Minimal environment adjustments needed to proceed with migrations/tests

To run migrations:
- Ensure Postgres is running and reachable at `DBHOST:DBPORT`.
  - If running Postgres locally: start it and keep `DBHOST=127.0.0.1`.
  - If running via Docker Compose: rely on compose overrides (`DBHOST=db`) and run inside the container.

If you want local (non-docker) migrations in this environment:
- Provide a reachable Postgres endpoint and set:
  - `DBHOST=<reachable_host>`
  - `DBPORT=<reachable_port>`

### 2) Make tests discoverable/runnable

Current blockers are *import errors*, independent of DB:
- Update/port stale tests that reference `Company` to use the current `Org`/Profile model structure, or reintroduce a `Company` model alias if intended.
- Fix/remove celery task tests that import nonexistent `*.tests` modules.
- Ensure task functions referenced in tests actually exist (or update test expectations).

### 3) Docker-based cold start validation

To complete the requested compose cold start:
- Run this report workflow in an environment with Docker available.
- Commands should be run from repo root with:
  - `docker compose up -d db`
  - wait for db to be healthy
  - `docker compose up -d web`
  - wait for web to be healthy
  - `docker compose up -d celery`
  - wait for celery to be healthy

### 4) Additional note

`python manage.py check --deploy` runs successfully (but emits many warnings related to schema generation and security defaults). This does not block startup but indicates areas to address for production readiness.
