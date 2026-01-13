# Constraint enforcement / migrations / API tests — Failure Report

## Summary
Requested work:
- Enforce **NOT NULL** and **Foreign Key (FK)** constraints across all Django apps **immediately** and **without data backfill**
- Run `migrate`
- Run backend API test suite
- Report migration failures, integrity violations, startup crashes, and broken endpoints

Current status:
- **Blocked**: Django cannot start due to missing required environment variables.
- As a result, this run **cannot**:
  - import settings
  - inspect models through Django
  - generate migrations (`makemigrations`)
  - apply migrations (`migrate`)
  - run API tests (`pytest`)

This report documents the precise failure and the exact variables/commands needed to proceed.

---

## 1) Startup crash (hard failure)
Attempted command:
```bash
cd backend
python manage.py makemigrations --check --dry-run
```

Observed failure:
- **KeyError: `SECRET_KEY`**
- Crash location: `backend/crm/settings.py` when evaluating:
  - `SECRET_KEY = os.environ["SECRET_KEY"]`

Trace excerpt:
```
KeyError: 'SECRET_KEY'
```

---

## 2) Required environment variables (hard-required by crm/settings.py)
These variables are accessed via `os.environ["..."]` (not optional) and must be present at runtime:

- `SECRET_KEY`
- `ENV_TYPE`
- `DOMAIN_NAME`
- `SWAGGER_ROOT_URL`
- `DEFAULT_FROM_EMAIL`
- `ADMIN_EMAIL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `DBNAME`
- `DBUSER`
- `DBPASSWORD`
- `DBHOST`
- `DBPORT`

Reference:
- `.env.example` exists at `backend/.env.example` and lists the same required keys.

### Minimal local/dev set (example)
Use the repo’s `.env.example` as the authoritative template; minimally you must fill:
- `SECRET_KEY`
- DB connection vars (`DBNAME`, `DBUSER`, `DBPASSWORD`, `DBHOST`, `DBPORT`)
- `ENV_TYPE` (e.g. `dev`)
- `DOMAIN_NAME`
- `SWAGGER_ROOT_URL`
- `DEFAULT_FROM_EMAIL`
- `ADMIN_EMAIL`

---

## 3) Database connectivity blocker
Even after `SECRET_KEY` is provided, migrations + tests require a reachable PostgreSQL instance configured via:

- `DBNAME`
- `DBUSER`
- `DBPASSWORD`
- `DBHOST`
- `DBPORT`

If DB is unreachable/misconfigured, expected failures:
- `django.db.utils.OperationalError` (connection refused / auth failed / no such database)

---

## 4) Commands to run once env vars + DB are configured
Run from `Django-CRM-198310/backend`:

### 4.1 Generate migrations reflecting strict constraint changes
```bash
python manage.py makemigrations
```

### 4.2 Apply all migrations
```bash
python manage.py migrate
```

### 4.3 Run backend tests (API tests)
Repo uses pytest with `DJANGO_SETTINGS_MODULE=crm.settings` (see `backend/pytest.ini`):
```bash
pytest -q
```

If you want maximum failure visibility:
```bash
pytest -q -x -vv
```

---

## 5) Likely integrity failures when enforcing NOT NULL immediately (no backfill)
Based on direct static review of model definitions, the following fields are currently `null=True` and are **high risk** if changed to `null=False` without backfilling existing rows:

### common/models.py
- `common.Org.name` is `null=True` (org name nullable)
- `common.Org.default_country` is `null=True`
- `common.Profile.phone` / `alternate_phone` are `null=True`
- `common.Profile.address` FK is `null=True`
- `common.Profile.date_of_joining` is `null=True`
- `common.Comment.commented_by` FK is `null=True`
- `common.CommentFiles.org` FK is `null=True` ("Temporarily nullable for migration")
- `common.Document.title` is `null=True`
- `common.APISettings.website` is `null=True`
- `common.SessionToken.refresh_token_jti` is `null=True`
- `common.SessionToken.ip_address` is `null=True`
- `common.SessionToken.user_agent` is `null=True`
- `common.SessionToken.revoked_at` is `null=True`
- `common.Activity.user` FK is `null=True`
- `common.ContactFormSubmission.ip_address`, `user_agent`, `referrer` are `null=True`
- `common.ContactFormSubmission.replied_by` FK is `null=True`
- `common.ContactFormSubmission.replied_at` is `null=True`

### accounts/models.py
- `accounts.Account.email` is `null=True`
- `accounts.Account.phone` is `null=True`
- `accounts.Account.website` is `null=True`
- `accounts.Account.industry` is `null=True`
- `accounts.Account.number_of_employees` is `null=True`
- `accounts.Account.annual_revenue` is `null=True`
- `accounts.Account.currency` is `null=True`
- Address fields are `null=True`
- `accounts.Account.description` is `null=True`

### contacts/models.py
- `contacts.Contact.email` is `null=True`
- `contacts.Contact.phone` is `null=True`
- `contacts.Contact.organization/title/department` are `null=True`
- `contacts.Contact.linkedin_url` is `null=True`
- Address fields are `null=True`
- `contacts.Contact.description` is `null=True`
- `contacts.Contact.account` FK is `null=True` (optional relationship)

### leads/models.py
Many optional lead fields are `null=True`, including:
- `Lead.title`, `salutation`, `first_name`, `last_name`, `email`, `phone`, etc.
- `Lead.stage` FK is `null=True` (explicitly optional to support status-based kanban)

### opportunity/models.py
- `Opportunity.account` FK is `null=True`
- `Opportunity.opportunity_type` is `null=True`
- `Opportunity.currency`, `amount`, `probability`, `closed_on`, `lead_source` are `null=True`
- `Opportunity.closed_by` FK is `null=True`

### cases/models.py
- `Case.case_type` is `null=True`
- `Case.account` FK is `null=True`
- `Case.closed_on`, `description` are `null=True`
- SLA timestamps and pipeline stage FK are `null=True`

### tasks/models.py
- Many fields are `null=True` on board task due dates/completed timestamps
- `BoardTask.account/contact/opportunity` FKs are `null=True`
- `Task.due_date` is `null=True`
- `Task.description` is `null=True`
- `Task.account/opportunity/case/lead` FKs are `null=True` (intentionally optional parent link)
- `Task.stage` FK is `null=True`

### invoices/models.py
A number of CRM-integrated FKs are nullable:
- `Invoice.account` is `null=True` (comment says required via serializer, but DB allows null)
- `Invoice.contact` is `null=True`
- `Invoice.opportunity` is `null=True`
- `Invoice.template` is `null=True`
- `Invoice.due_date` is `null=True`
- `Invoice.sent_at/viewed_at/paid_at/cancelled_at` are `null=True`
- `Invoice.details` is `null=True`
- `Invoice.billing_period`, `po_number` are `null=True`

Similarly for `Estimate` and `RecurringInvoice`:
- `account/contact/opportunity` are `null=True`

If these are flipped to NOT NULL without backfill, migrations will likely fail with:
- `IntegrityError: null value in column ... violates not-null constraint`

---

## 6) Foreign Key constraint enforcement notes
Django FKs normally create FK constraints at the DB level unless explicitly disabled or altered.
However, enforcing **NOT NULL on existing FK columns** or changing `on_delete` strategies may fail if:
- existing rows contain NULLs (when changing to non-nullable)
- existing rows reference missing targets (broken references)
- existing data conflicts with new constraints

These failures cannot be enumerated precisely without DB access and a successful Django boot.

---

## 7) What to do next (to unblock)
1) Populate required env vars (see `.env.example`).
2) Ensure PostgreSQL is reachable with those DB vars.
3) Re-run:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
   - `pytest -q`

At that point, we can:
- implement strict NOT NULL / FK enforcement changes as migrations,
- execute migrations and capture integrity violations,
- run API tests and report failing endpoints/tests.

---
Report generated automatically due to current environment-variable startup blocker.
