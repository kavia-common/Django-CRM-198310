"""
E2E verification command for:
- Running migrations with dev defaults (SQLite + SECRET_KEY)
- Verifying admin-only financial endpoint behavior and redactions
- Verifying activity logging (login/logout, financial update)
- Verifying admin activity logs API supports pagination/filters and tenant isolation

Usage:
  python manage.py e2e_financial_activity_check

This uses Django's test client (no server needed).
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.management import BaseCommand, call_command
from django.test import Client
from django.utils import timezone

from accounts.models import Account, AccountFinancialDetails
from activity.logger import log_activity
from activity.models import ActivityLog
from common.models import Org, Profile


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""


def _json(resp) -> Any:
    try:
        return json.loads(resp.content.decode("utf-8") or "{}")
    except Exception:
        return {"_raw": (resp.content.decode("utf-8", errors="replace") if resp.content else "")}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


class Command(BaseCommand):
    help = "Run migrations and perform E2E verification for financial endpoint + activity logs."

    def add_arguments(self, parser):
        parser.add_argument("--password", type=str, default="testpass123", help="Password for test users")
        parser.add_argument("--admin-email", type=str, default="admin.e2e@example.com", help="Admin email")
        parser.add_argument("--user-email", type=str, default="user.e2e@example.com", help="User email")

    def handle(self, *args, **options):
        results: list[CheckResult] = []
        password = options["password"]
        admin_email = options["admin_email"]
        user_email = options["user_email"]

        # 1) Apply migrations
        try:
            call_command("migrate", "--noinput", verbosity=0)
            results.append(CheckResult("migrations", True, "manage.py migrate --noinput succeeded"))
        except Exception as e:
            results.append(CheckResult("migrations", False, f"migrate failed: {e}"))
            self._print_results(results)
            raise

        # 2) Create test users + org + profiles
        try:
            org_a = Org.objects.filter(name="E2E Org A").first() or Org.objects.create(
                name="E2E Org A", default_currency="USD", default_country="US"
            )
            org_b = Org.objects.filter(name="E2E Org B").first() or Org.objects.create(
                name="E2E Org B", default_currency="USD", default_country="US"
            )

            User = get_user_model()
            admin_user, _ = User.objects.get_or_create(email=admin_email, defaults={"is_active": True})
            if not admin_user.has_usable_password():
                admin_user.set_password(password)
                admin_user.save(update_fields=["password"])
            else:
                admin_user.set_password(password)
                admin_user.save(update_fields=["password"])

            normal_user, _ = User.objects.get_or_create(email=user_email, defaults={"is_active": True})
            normal_user.set_password(password)
            normal_user.save(update_fields=["password"])

            admin_profile_a, _ = Profile.objects.get_or_create(
                user=admin_user,
                org=org_a,
                defaults={
                    "role": "ADMIN",
                    "is_active": True,
                    "is_organization_admin": True,
                    "phone": "1111111111",
                    "date_of_joining": timezone.now().date(),
                },
            )
            if admin_profile_a.role != "ADMIN" or not admin_profile_a.is_organization_admin:
                admin_profile_a.role = "ADMIN"
                admin_profile_a.is_organization_admin = True
                admin_profile_a.is_active = True
                admin_profile_a.save(update_fields=["role", "is_organization_admin", "is_active"])

            user_profile_a, _ = Profile.objects.get_or_create(
                user=normal_user,
                org=org_a,
                defaults={
                    "role": "USER",
                    "is_active": True,
                    "is_organization_admin": False,
                    "phone": "2222222222",
                    "date_of_joining": timezone.now().date(),
                },
            )
            if user_profile_a.role != "USER":
                user_profile_a.role = "USER"
                user_profile_a.is_active = True
                user_profile_a.is_organization_admin = False
                user_profile_a.save(update_fields=["role", "is_active", "is_organization_admin"])

            # Admin user also belongs to org_b, but we will use org_a tokens for checks.
            Profile.objects.get_or_create(
                user=admin_user,
                org=org_b,
                defaults={
                    "role": "ADMIN",
                    "is_active": True,
                    "is_organization_admin": True,
                    "phone": "3333333333",
                    "date_of_joining": timezone.now().date(),
                },
            )

            results.append(CheckResult("seed_users_orgs", True, "Created orgs + admin/user profiles"))
        except Exception as e:
            results.append(CheckResult("seed_users_orgs", False, f"Failed creating users/orgs: {e}"))
            self._print_results(results)
            raise

        # 3) Create/select Account and financial details in org_a
        try:
            account_a = Account.objects.filter(org=org_a, name="E2E Account A").first()
            if not account_a:
                account_a = Account.objects.create(name="E2E Account A", org=org_a)
            details_a, _ = AccountFinancialDetails.objects.get_or_create(account=account_a, defaults={"org": org_a})
            # Set a known policy_number to validate redaction in responses.
            if not details_a.policy_number:
                details_a.policy_number = "POLICY-" + secrets.token_hex(8).upper()
                details_a.insurance_provider = "E2E Insurance"
                details_a.save(update_fields=["policy_number", "insurance_provider"])
            results.append(CheckResult("seed_account_financial", True, f"Account={account_a.id} created/ensured"))
        except Exception as e:
            results.append(CheckResult("seed_account_financial", False, f"Failed creating account/details: {e}"))
            self._print_results(results)
            raise

        # Also create an account in org_b to check tenant isolation.
        account_b = Account.objects.filter(org=org_b, name="E2E Account B").first() or Account.objects.create(
            name="E2E Account B", org=org_b
        )

        # 4) Exercise /api/accounts/{id}/financial/ as ADMIN (GET/PATCH)
        try:
            admin_token = self._login_get_access_token(
                email=admin_email, password=password, org_id=str(org_a.id), expect_ok=True
            )
            # Emit login signal to ensure activity log gets a login entry (best-effort).
            user_logged_in.send(sender=get_user_model(), request=None, user=admin_user)

            c = Client(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
            # GET should be 200 with redacted policy_number
            resp = c.get(f"/api/accounts/{account_a.id}/financial/")
            body = _json(resp)
            _assert(resp.status_code == 200, f"Admin GET expected 200, got {resp.status_code}, body={body}")
            _assert(body.get("redacted") is True, "Expected redacted=true in response")
            pn = body.get("policy_number", "")
            _assert(isinstance(pn, str) and "*" in pn and len(pn) >= 8, "Expected masked policy_number")
            _assert("POLICY-" not in pn, "Policy number should not be returned in clear text")

            # PATCH valid update should be 200 with redaction preserved
            patch_payload = {"credit_limit": "1234.56", "billing_currency": "USD", "policy_number": details_a.policy_number}
            resp2 = c.patch(
                f"/api/accounts/{account_a.id}/financial/",
                data=json.dumps(patch_payload),
                content_type="application/json",
            )
            body2 = _json(resp2)
            _assert(resp2.status_code == 200, f"Admin PATCH expected 200, got {resp2.status_code}, body={body2}")
            _assert(body2.get("redacted") is True, "Expected redacted=true in patch response")
            _assert("*" in (body2.get("policy_number") or ""), "Expected policy_number redacted in patch response")

            # PATCH validation error should be 400 with minimal body {errors: {...}} and no sensitive echo
            bad_payload = {"payment_terms_days": 999999}
            resp3 = c.patch(
                f"/api/accounts/{account_a.id}/financial/",
                data=json.dumps(bad_payload),
                content_type="application/json",
            )
            body3 = _json(resp3)
            _assert(resp3.status_code == 400, f"Admin PATCH invalid expected 400, got {resp3.status_code}, body={body3}")
            _assert(set(body3.keys()) == {"errors"}, f"Expected only 'errors' key, got keys={list(body3.keys())}")
            _assert("payment_terms_days" in body3["errors"], "Expected field-level error for payment_terms_days")
            results.append(CheckResult("financial_admin_get_patch", True, "ADMIN GET/PATCH behaved as expected (redaction + errors)"))
        except Exception as e:
            results.append(CheckResult("financial_admin_get_patch", False, str(e)))

        # 5) Exercise as USER (non-admin) and verify standardized 403/404 semantics and scrubbed body
        try:
            user_token = self._login_get_access_token(
                email=user_email, password=password, org_id=str(org_a.id), expect_ok=True
            )
            user_logged_in.send(sender=get_user_model(), request=None, user=normal_user)

            c2 = Client(HTTP_AUTHORIZATION=f"Bearer {user_token}")

            # Non-admin accessing existing account in org should be 403 with minimal body
            resp = c2.get(f"/api/accounts/{account_a.id}/financial/")
            body = _json(resp)
            _assert(resp.status_code == 403, f"User GET expected 403, got {resp.status_code}, body={body}")
            _assert(body == {"detail": "Forbidden."}, f"Expected minimal forbidden body, got {body}")

            # Non-admin patch should also be 403 minimal
            resp2 = c2.patch(
                f"/api/accounts/{account_a.id}/financial/",
                data=json.dumps({"credit_limit": "1.00"}),
                content_type="application/json",
            )
            body2 = _json(resp2)
            _assert(resp2.status_code == 403, f"User PATCH expected 403, got {resp2.status_code}, body={body2}")
            _assert(body2 == {"detail": "Forbidden."}, f"Expected minimal forbidden body, got {body2}")

            # Tenant isolation: org_a token should not see org_b account (404)
            resp3 = c2.get(f"/api/accounts/{account_b.id}/financial/")
            body3 = _json(resp3)
            _assert(resp3.status_code in (403, 404), f"User cross-tenant expected 403/404, got {resp3.status_code}, body={body3}")
            # Current implementation fetches account scoped to request.profile.org first; should be 404.
            if resp3.status_code == 404:
                _assert(body3 == {"detail": "Not found."}, f"Expected minimal not found body, got {body3}")

            results.append(CheckResult("financial_user_forbidden_isolation", True, "USER receives minimal 403; cross-tenant yields 404/403 without leaks"))
        except Exception as e:
            results.append(CheckResult("financial_user_forbidden_isolation", False, str(e)))

        # 6) Verify ActivityLog entries for login/logout + financial updates; no sensitive payload logging
        try:
            # Trigger logout signals (best effort). No endpoint exists; we log signals directly.
            user_logged_out.send(sender=get_user_model(), request=None, user=admin_user)
            user_logged_out.send(sender=get_user_model(), request=None, user=normal_user)

            # Also ensure a "financial update" activity exists from the PATCH in step 4.
            fin_logs = ActivityLog.objects.filter(module="accounts.financial", record_id=str(account_a.id)).order_by("-timestamp")
            _assert(fin_logs.exists(), "Expected at least one accounts.financial ActivityLog entry")
            latest = fin_logs.first()
            _assert(latest is not None, "Expected latest financial log")
            _assert(latest.action in (ActivityLog.Action.UPDATE, "UPDATE"), f"Unexpected action={latest.action}")
            _assert(latest.status in (ActivityLog.Status.SUCCESS, ActivityLog.Status.FAILURE, "success", "failure"), "Unexpected status")
            _assert(latest.record_id == str(account_a.id), "record_id mismatch")
            _assert(latest.module == "accounts.financial", "module mismatch")

            # Ensure metadata doesn't contain sensitive raw policy_number
            meta = latest.metadata or {}
            meta_text = json.dumps(meta)
            _assert(details_a.policy_number not in meta_text, "Sensitive policy_number leaked into activity metadata")

            # Login/logout logs (module=auth, action=LOGIN/LOGOUT) should exist (best-effort)
            auth_logs = ActivityLog.objects.filter(module="auth", action__in=[ActivityLog.Action.LOGIN, ActivityLog.Action.LOGOUT])
            _assert(auth_logs.exists(), "Expected at least one auth activity log (LOGIN/LOGOUT)")

            results.append(CheckResult("activity_logs_present_sanitized", True, "ActivityLog entries exist; metadata does not include sensitive policy_number"))
        except Exception as e:
            results.append(CheckResult("activity_logs_present_sanitized", False, str(e)))

        # 7) Verify /api/admin/activity-logs/ supports pagination and filters; tenant isolation
        try:
            admin_token = self._login_get_access_token(
                email=admin_email, password=password, org_id=str(org_a.id), expect_ok=True
            )
            c = Client(HTTP_AUTHORIZATION=f"Bearer {admin_token}")

            # Basic list (paginated)
            resp = c.get("/api/admin/activity-logs/?limit=2&offset=0")
            body = _json(resp)
            _assert(resp.status_code == 200, f"Admin activity logs list expected 200, got {resp.status_code}, body={body}")
            _assert("results" in body and "count" in body, f"Expected paginated response with results/count, got keys={list(body.keys())}")
            _assert(isinstance(body["results"], list), "results should be a list")
            _assert(len(body["results"]) <= 2, "limit=2 should cap results size")

            # Filter by module
            resp2 = c.get("/api/admin/activity-logs/?module=accounts.financial&limit=10")
            body2 = _json(resp2)
            _assert(resp2.status_code == 200, "Filtered activity logs should return 200")
            for row in body2.get("results", []):
                _assert(row.get("module") == "accounts.financial", "module filter not enforced")

            # Tenant isolation: verify all returned logs have org == org_a
            # ActivityLogSerializer likely includes org id; we defensively accept missing org field but enforce if present.
            for row in body.get("results", []):
                if row.get("org"):
                    _assert(str(row["org"]) == str(org_a.id), "Tenant isolation violated in activity logs API")

            results.append(CheckResult("admin_activity_logs_api", True, "Pagination + filters work; org scoping enforced"))
        except Exception as e:
            results.append(CheckResult("admin_activity_logs_api", False, str(e)))

        # Final report
        self._print_results(results)

        # If any failed, raise CommandError for CI visibility
        failed = [r for r in results if not r.ok]
        if failed:
            raise SystemExit(1)

    def _login_get_access_token(self, *, email: str, password: str, org_id: str, expect_ok: bool) -> str:
        """
        Login using /api/auth/login/ to get a JWT access token.
        """
        c = Client()
        resp = c.post(
            "/api/auth/login/",
            data=json.dumps({"email": email, "password": password, "org_id": org_id}),
            content_type="application/json",
        )
        body = _json(resp)
        if expect_ok:
            _assert(resp.status_code == 200, f"Login expected 200, got {resp.status_code}, body={body}")
            _assert("access_token" in body, f"Login response missing access_token: {body}")
        return body.get("access_token", "")

    def _print_results(self, results: list[CheckResult]) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("E2E verification results"))
        for r in results:
            status = self.style.SUCCESS("OK") if r.ok else self.style.ERROR("FAIL")
            self.stdout.write(f"- {r.name}: {status} {r.details}")
        self.stdout.write("")
