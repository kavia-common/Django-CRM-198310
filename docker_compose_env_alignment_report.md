# Docker Compose env alignment report (backend/.env + db.env)

## What changed
- **App services (`web`, `celery`) now load env from:** `./backend/.env`
- **Database service (`db`) now loads env from:** `./db.env` (new placeholder file)
- **Postgres healthcheck** now references `POSTGRES_*` variables (the ones actually available in the `db` container).

## Why this is needed
- Django settings expect **DB-prefixed** variables:
  - `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT`
- The official `postgres` image expects **POSTGRES-prefixed** variables:
  - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

Using one shared env file for both services causes missing/incorrect variables during cold start and healthchecks.

## Current paths used
- `docker-compose.yml`
  - `web.env_file: ./backend/.env`
  - `celery.env_file: ./backend/.env`
  - `db.env_file: ./db.env`
- Placeholder DB env file:
  - `db.env`

## Notable behavior / follow-ups (manual)
1. **DBHOST override inside compose**
   - `backend/.env` currently defaults `DBHOST` to `127.0.0.1` (good for non-docker local usage).
   - In docker-compose we explicitly set:
     - `DBHOST=db` for `web` and `celery`
   - This is required so containers connect to the `db` service over the compose network.

2. **Keep credentials in sync**
   - If you change DB credentials, update both:
     - `backend/.env` (`DBNAME`, `DBUSER`, `DBPASSWORD`)
     - `db.env` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`)

3. **DBPORT**
   - Django uses `DBPORT` from `backend/.env` (defaults to `5432` there).
   - Postgres container listens on `5432` internally by default; compose healthcheck assumes `5432`.

## Variables expected by app services (loaded from backend/.env)
- `SECRET_KEY`
- `ENV_TYPE`
- `DBNAME`
- `DBUSER`
- `DBPASSWORD`
- `DBHOST` (overridden to `db` in compose for containers)
- `DBPORT`
- `DEFAULT_FROM_EMAIL`
- `ADMIN_EMAIL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `DOMAIN_NAME`
- `SWAGGER_ROOT_URL`
