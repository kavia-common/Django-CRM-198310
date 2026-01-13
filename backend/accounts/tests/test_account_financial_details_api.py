"""
Tests for ADMIN-only account financial/insurance endpoint.

Endpoint:
  PATCH /api/accounts/{id}/financial/
  GET   /api/accounts/{id}/financial/

Hardening requirements covered:
- 404 vs 403 semantics:
  - 404 if account does not exist OR is outside tenant scope.
  - 403 if account exists but requester is not ADMIN (including anonymous).
- Minimal error bodies on 403/404:
  - Must only include {"detail": "..."} and must not include keys like trace/model/pk.
- Redaction in responses for ADMIN:
  - Sensitive fields (e.g., policy_number) are masked deterministically.
  - Response includes redacted=true and redaction metadata.
- ActivityLog alignment:
  - Logs use module="accounts.financial" and do not include sensitive values in metadata.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from activity.models import ActivityLog
from accounts.models import Account
from common.models import Org, Profile, User
from common.serializer import OrgAwareRefreshToken


class AccountFinancialDetailsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.org_a = Org.objects.create(name="Org A")
        self.org_b = Org.objects.create(name="Org B")

        # Admin in org A
        self.admin_user = User.objects.create_user(
            email="admin_a@test.com", password="testpass123"
        )
        self.admin_profile = Profile.objects.create(
            user=self.admin_user,
            org=self.org_a,
            role="ADMIN",
            is_active=True,
            is_organization_admin=True,
        )

        # Non-admin in org A
        self.user_user = User.objects.create_user(
            email="user_a@test.com", password="testpass123"
        )
        self.user_profile = Profile.objects.create(
            user=self.user_user,
            org=self.org_a,
            role="USER",
            is_active=True,
            is_organization_admin=False,
        )

        # Admin in org B (used for tenant isolation test)
        self.admin_b_user = User.objects.create_user(
            email="admin_b@test.com", password="testpass123"
        )
        self.admin_b_profile = Profile.objects.create(
            user=self.admin_b_user,
            org=self.org_b,
            role="ADMIN",
            is_active=True,
            is_organization_admin=True,
        )

        self.account_a = Account.objects.create(name="Customer A", org=self.org_a)
        self.account_b = Account.objects.create(name="Customer B", org=self.org_b)

    def _auth_as(self, user, org):
        token = OrgAwareRefreshToken.for_user_and_org(user, org)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _clear_auth(self):
        self.client.credentials()

    def _assert_minimal_error_body(self, resp, expected_detail: str):
        data = resp.json()
        self.assertEqual(data, {"detail": expected_detail})
        # Ensure common leakage keys aren't present
        for key in ("trace", "traceback", "model", "pk", "id", "exception"):
            self.assertNotIn(key, data)

    def test_admin_can_patch_financial_details_and_response_is_redacted(self):
        self._auth_as(self.admin_user, self.org_a)

        payload = {
            "insurance_provider": "Acme Insurance",
            "policy_number": "POLICY-12345",
            "coverage_limit": "10000.00",
            "coverage_currency": "USD",
            "credit_limit": "5000.00",
            "billing_currency": "USD",
            "payment_terms_days": 30,
        }

        resp = self.client.patch(
            f"/api/accounts/{self.account_a.id}/financial/",
            data=payload,
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["insurance_provider"], "Acme Insurance")
        # policy_number must be masked
        self.assertNotEqual(data["policy_number"], "POLICY-12345")
        self.assertTrue(data["policy_number"].endswith("2345"))
        self.assertTrue(data.get("redacted") is True)
        self.assertIn("redaction", data)
        self.assertEqual(data["redaction"]["policy_number"], "masked_last4")

        # ActivityLog must exist (best-effort logging should succeed in tests)
        logs = ActivityLog.objects.filter(
            module="accounts.financial",
            action=ActivityLog.Action.UPDATE,
            record_id=str(self.account_a.id),
            org=self.org_a,
        )
        self.assertGreaterEqual(logs.count(), 1)
        self.assertEqual(logs.first().status, ActivityLog.Status.SUCCESS)

        # Ensure logger metadata does not contain the raw policy number
        if logs.first().metadata:
            self.assertNotIn("POLICY-12345", str(logs.first().metadata))

    def test_admin_get_returns_empty_shape_and_is_redacted(self):
        self._auth_as(self.admin_user, self.org_a)
        resp = self.client.get(f"/api/accounts/{self.account_a.id}/financial/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Must include redaction hints even when empty
        self.assertTrue(data.get("redacted") is True)
        self.assertIn("policy_number", data)

    def test_non_admin_gets_403_on_patch_minimal_body(self):
        self._auth_as(self.user_user, self.org_a)
        resp = self.client.patch(
            f"/api/accounts/{self.account_a.id}/financial/",
            data={"policy_number": "POLICY-999"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self._assert_minimal_error_body(resp, "Forbidden.")

    def test_non_admin_gets_403_on_get_minimal_body(self):
        self._auth_as(self.user_user, self.org_a)
        resp = self.client.get(f"/api/accounts/{self.account_a.id}/financial/")
        self.assertEqual(resp.status_code, 403)
        self._assert_minimal_error_body(resp, "Forbidden.")

    def test_anonymous_gets_403_on_get_minimal_body(self):
        self._clear_auth()
        resp = self.client.get(f"/api/accounts/{self.account_a.id}/financial/")
        self.assertEqual(resp.status_code, 403)
        self._assert_minimal_error_body(resp, "Forbidden.")

    def test_tenant_isolation_returns_404_even_for_admin(self):
        # Admin from org A should not be able to access org B account due to org scoping.
        self._auth_as(self.admin_user, self.org_a)
        resp = self.client.patch(
            f"/api/accounts/{self.account_b.id}/financial/",
            data={"policy_number": "POLICY-CROSSORG"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)
        self._assert_minimal_error_body(resp, "Not found.")

    def test_missing_account_returns_404_minimal_body(self):
        self._auth_as(self.admin_user, self.org_a)
        resp = self.client.get("/api/accounts/00000000-0000-0000-0000-000000000000/financial/")
        self.assertEqual(resp.status_code, 404)
        self._assert_minimal_error_body(resp, "Not found.")

    def test_admin_validation_error_is_field_level_and_scrubbed(self):
        self._auth_as(self.admin_user, self.org_a)

        # Invalid policy number format
        resp = self.client.patch(
            f"/api/accounts/{self.account_a.id}/financial/",
            data={"policy_number": "INVALID POLICY WITH SPACES"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()

        # Should include field-level errors only; no "error": True wrapper etc.
        self.assertIn("errors", data)
        self.assertIn("policy_number", data["errors"])

        # Ensure response doesn't include common leakage keys
        for key in ("trace", "traceback", "model", "pk", "exception"):
            self.assertNotIn(key, data)
        self.assertNotIn("AccountFinancialDetails", str(data))
