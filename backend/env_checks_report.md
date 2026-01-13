# Django env + non-destructive checks report

## Goal
Create `backend/.env` with placeholder values so Django can import `crm.settings` and run non-destructive management commands, then capture outputs for:

- `python manage.py check --deploy`
- `python manage.py showmigrations --list`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py migrate --plan`

## What was changed
- Added `backend/.env` with safe dummy defaults for required settings keys:
  - `SECRET_KEY`, `ENV_TYPE`, DB settings (`DBNAME/DBUSER/DBPASSWORD/DBHOST/DBPORT`),
  - Celery URLs, email placeholders, and localhost defaults for hosts/CORS/CSRF.

## Command execution notes
Django loads environment variables via `python-dotenv` in `crm/settings.py`:

```py
from dotenv import load_dotenv
load_dotenv()
SECRET_KEY = os.environ["SECRET_KEY"]
...
```

This means commands **must be run with the working directory set to `backend/`** (so `load_dotenv()` finds `backend/.env` by default), e.g.:

```bash
cd backend
python manage.py check --deploy
```

## Results captured during this run (before `.env` existed)
At the time of command attempts, `backend/.env` did not yet exist, so settings import failed immediately.

### 1) `python backend/manage.py check --deploy`
**Status:** FAILED  
**Error:** `KeyError: 'SECRET_KEY'`  
**Output (excerpt):**
```
File ".../backend/crm/settings.py", line 13, in <module>
  SECRET_KEY = os.environ["SECRET_KEY"]
KeyError: 'SECRET_KEY'
```

### 2) `cd backend && python manage.py check --deploy`
**Status:** FAILED  
**Error:** `KeyError: 'SECRET_KEY'`  
(Same root cause: `.env` was not present yet.)

### 3) `cd backend && python manage.py showmigrations --list`
**Status:** FAILED  
**Error:** `KeyError: 'SECRET_KEY'`

### 4) `cd backend && python manage.py makemigrations --check --dry-run`
**Status:** FAILED  
**Error:** `KeyError: 'SECRET_KEY'`

### 5) `cd backend && python manage.py migrate --plan`
**Status:** FAILED  
**Error:** `KeyError: 'SECRET_KEY'`

## Expected next outcome after `.env` is present
After `backend/.env` is applied, Django should import settings successfully.

- `check --deploy` should run and likely emit warnings (expected with placeholder values, DEBUG off, and dev-ish hosts).
- `showmigrations` / `migrate --plan` may still fail if PostgreSQL is not running locally at `127.0.0.1:5432` with the provided credentials.
  - In that case the failure would be a DB connection/auth error (expected in environments without a running DB).

## Missing envs still detected
None should be missing for settings import after `.env` exists; the project uses hard `os.environ[...]` lookups for:

- `SECRET_KEY`
- `ENV_TYPE`
- `DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT`
- `DEFAULT_FROM_EMAIL`, `ADMIN_EMAIL`
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `DOMAIN_NAME`, `SWAGGER_ROOT_URL`

All are present in the new `.env`.

## Instructions for future agent
After this change is applied, re-run the checks from `backend/` and append the real outputs to this report:

```bash
cd backend
python manage.py check --deploy
python manage.py showmigrations --list
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

If DB connectivity fails, record the exact error and note that `showmigrations`/`migrate --plan` require a reachable PostgreSQL instance.
