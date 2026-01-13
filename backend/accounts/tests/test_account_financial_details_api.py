"""
Tests for ADMIN-only account financial/insurance endpoint.

Endpoint:
  PATCH /api/accounts/{id}/financial/
  GET   /api/accounts/{id}/financial/

Requirements covered:
- ADMIN can update and receives 200 with updated fields.
- Non-admin roles receive 403 for read/write.
- Tenant isolation: cannot access/update outside their org.
- ActivityLog entries created with action=UPDATE, module=customer_finance, record_id=<account_id>, status.
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

    def test_admin_can_patch_financial_details(self):
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
        self.assertEqual(data["policy_number"], "POLICY-12345")
        self.assertEqual(data["coverage_currency"], "USD")
        self.assertEqual(data["billing_currency"], "USD")
        self.assertEqual(data["payment_terms_days"], 30)

        # ActivityLog must exist (best-effort logging should succeed in tests)
        logs = ActivityLog.objects.filter(
            module="customer_finance",
            action=ActivityLog.Action.UPDATE,
            record_id=str(self.account_a.id),
            org=self.org_a,
        )
        self.assertGreaterEqual(logs.count(), 1)
        self.assertEqual(logs.first().status, ActivityLog.Status.SUCCESS)

    def test_non_admin_gets_403_on_patch(self):
        self._auth_as(self.user_user, self.org_a)
        resp = self.client.patch(
            f"/api/accounts/{self.account_a.id}/financial/",
            data={"policy_number": "POLICY-999"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_gets_403_on_get(self):
        self._auth_as(self.user_user, self.org_a)
        resp = self.client.get(f"/api/accounts/{self.account_a.id}/financial/")
        self.assertEqual(resp.status_code, 403)

    def test_tenant_isolation_admin_cannot_update_other_org_account(self):
        # Admin from org A should not be able to access org B account due to org scoping.
        self._auth_as(self.admin_user, self.org_a)
        resp = self.client.patch(
            f"/api/accounts/{self.account_b.id}/financial/",
            data={"policy_number": "POLICY-CROSSORG"},
            format="json",
        )
        # get_object_or_404 scoped to org returns 404 (preferred for isolation)
        self.assertEqual(resp.status_code, 404)

    def test_admin_get_returns_empty_shape_when_missing(self):
        self._auth_as(self.admin_user, self.org_a)
        resp = self.client.get(f"/api/accounts/{self.account_a.id}/financial/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should return keys even if values are blank/None (serializer on unsaved instance)
        self.assertIn("policy_number", data)
        self.assertIn("coverage_limit", data)
"""
