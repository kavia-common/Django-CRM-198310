# PostgreSQL / Django migration verification report (non-destructive)

This file records the results of the dry-run style audit performed in the Kavia workspace.

## Summary
- Django settings require multiple environment variables at import-time (via `os.environ[...]`).
- In the current environment those variables were missing, preventing execution of:
  - `python manage.py check --deploy`
  - `python manage.py showmigrations --list`
  - `python manage.py makemigrations --check --dry-run`
  - `python manage.py migrate --plan`
- `docker-compose.yml` references `./db.env`, but that file is not present in this workspace.

## Required backend env vars (hard-required at import time)
- `SECRET_KEY`
- `ENV_TYPE`
- `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT`
- `DEFAULT_FROM_EMAIL`, `ADMIN_EMAIL`
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `DOMAIN_NAME`, `SWAGGER_ROOT_URL`

## PostgreSQL config notes
- Uses `django.db.backends.postgresql`
- No explicit SSL options in `DATABASES['default']`
- No explicit connection pooling or `CONN_MAX_AGE` configured (Django default is `0`)

## RLS notes
- Project uses PostgreSQL Row-Level Security.
- Database user must NOT be a superuser; superusers bypass RLS.

## Next steps
1. Provide the env vars above (recommended location: `backend/.env` since settings calls `load_dotenv()`).
2. Ensure database connectivity/permissions are correct for the chosen DB user.
3. Re-run the commands listed above to produce migration graph / plan output.
