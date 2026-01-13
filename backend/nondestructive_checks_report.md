# Non-destructive Django checks report

Container/workspace: `Django-CRM-198310`  
Working directory: `backend/`  
Env sourcing approach: `set -a; . ./.env; set +a` (used placeholder `backend/.env`)

> Note: Commands were executed as requested and are non-destructive. Some operations (showmigrations/migrate plan) require DB connectivity to read applied migration state, and will fail if PostgreSQL is unreachable.

---

## 1) `python manage.py check`

**Command**
```bash
cd Django-CRM-198310/backend && set -a && [ -f .env ] && . ./.env || true && set +a && python manage.py check
```

**Exit code:** 0

**Output**
```
/home/kavia/workspace/code-generation/Django-CRM-198310/backend/leads/forms.py:6: SyntaxWarning: invalid escape sequence '\.'
  email_regex = "^[_a-zA-Z0-9-]+(\.[_a-zA-Z0-9-]+)*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*(\.[a-zA-Z]{2,4})$"
System check identified no issues (0 silenced).
```

**Conclusion**
- Django settings successfully imported with placeholder env.
- System checks passed.
- There is a `SyntaxWarning` in `leads/forms.py` (regex string escape), but it did not fail the check.

---

## 2) `python manage.py showmigrations --list`

**Command**
```bash
cd Django-CRM-198310/backend && set -a && [ -f .env ] && . ./.env || true && set +a && python manage.py showmigrations --list
```

**Exit code:** 1

**Output (traceback)**
```
Traceback (most recent call last):
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
    self.connect()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
    self.connection = self.get_new_connection(conn_params)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
    connection = self.Database.connect(**conn_params)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
psycopg2.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/kavia/workspace/code-generation/Django-CRM-198310/backend/manage.py", line 24, in <module>
    execute_from_command_line(sys.argv)
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/base.py", line 416, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/base.py", line 460, in execute
    output = self.handle(*args, **options)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/commands/showmigrations.py", line 67, in handle
    return self.show_list(connection, options["app_label"])
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/commands/showmigrations.py", line 86, in show_list
    loader = MigrationLoader(connection, ignore_no_migrations=True)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 58, in __init__
    self.build_graph()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 235, in build_graph
    self.applied_migrations = recorder.applied_migrations()
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 89, in applied_migrations
    if self.has_table():
       ^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 63, in has_table
    with self.connection.cursor() as cursor:
         ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 320, in cursor
    return self._cursor()
           ^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 296, in _cursor
    self.ensure_connection()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 278, in ensure_connection
    with self.wrap_database_errors:
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/utils.py", line 91, in __exit__
    raise dj_exc_value.with_traceback(traceback) from exc_value
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
    self.connect()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
    self.connection = self.get_new_connection(conn_params)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
    connection = self.Database.connect(**conn_params)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
django.db.utils.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

**Conclusion**
- Failure cause: PostgreSQL is unreachable at `127.0.0.1:5432` (`Connection refused`).
- This indicates the DB server is not running locally (or not accessible from this environment), or `DB_HOST/DB_PORT` in `.env` points to a non-reachable address.

---

## 3) `python manage.py migrate --plan`

**Command**
```bash
cd Django-CRM-198310/backend && set -a && [ -f .env ] && . ./.env || true && set +a && python manage.py migrate --plan
```

**Exit code:** 1

**Output (traceback)**
```
Traceback (most recent call last):
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
    self.connect()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
    self.connection = self.get_new_connection(conn_params)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
    connection = self.Database.connect(**conn_params)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
psycopg2.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?


The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/kavia/workspace/code-generation/Django-CRM-198310/backend/manage.py", line 24, in <module>
    execute_from_command_line(sys.argv)
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/base.py", line 416, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/base.py", line 460, in execute
    output = self.handle(*args, **options)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/base.py", line 107, in wrapper
    res = handle_func(*args, **kwargs)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/core/management/commands/migrate.py", line 114, in handle
    executor = MigrationExecutor(connection, self.migration_progress_callback)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/executor.py", line 18, in __init__
    self.loader = MigrationLoader(self.connection)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 58, in __init__
    self.build_graph()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 235, in build_graph
    self.applied_migrations = recorder.applied_migrations()
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 89, in applied_migrations
    if self.has_table():
       ^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 63, in has_table
    with self.connection.cursor() as cursor:
         ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 320, in cursor
    return self._cursor()
           ^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 296, in _cursor
    self.ensure_connection()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 278, in ensure_connection
    with self.wrap_database_errors:
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/utils.py", line 91, in __exit__
    raise dj_exc_value.with_traceback(traceback) from exc_value
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
    self.connect()
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
    self.connection = self.get_new_connection(conn_params)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
    connection = self.Database.connect(**conn_params)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/kavia/.local/lib/python3.12/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
django.db.utils.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

**Conclusion**
- `--plan` is supported by the installed Django, but the plan cannot be computed without connecting to the DB to determine which migrations are already applied.
- Failure cause matches #2: PostgreSQL connection refused at `127.0.0.1:5432`.

---

## Overall conclusions

1. **Settings import / env placeholders:** OK (no missing `SECRET_KEY` or immediate settings import failure observed).
2. **Django project health:** `manage.py check` reports **no issues** (aside from one `SyntaxWarning`).
3. **Database connectivity:** **Not reachable** at `127.0.0.1:5432`. Both `showmigrations` and `migrate --plan` fail because they need DB access to read migration state.
4. **Exact failure mode:** `psycopg2.OperationalError` / `django.db.utils.OperationalError` with message:  
   `connection to server at "127.0.0.1", port 5432 failed: Connection refused`

---
