"""
Unit-level tests for ActivityLog.

These tests are intentionally conservative:
- They validate the logging utility and CRUD signals in a basic scenario.
- They do not attempt to validate PostgreSQL RLS policies (those are covered elsewhere).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Account
from activity.models import ActivityLog
from common.models import Org, Profile, User


class TestActivityLogCRUDSignals(TestCase):
    def setUp(self):
        self.org = Org.objects.create(name="Org 1")
        self.user = User.objects.create_user(email="admin@test.com", password="testpass123")
        self.profile = Profile.objects.create(user=self.user, org=self.org, role="ADMIN", is_active=True)

    def test_account_create_emits_activity_log_best_effort(self):
        """
        Creating an Account should emit a CREATE ActivityLog entry via signals.

        Note: Signals rely on CRUM request context for actor/ip. In this test, we only assert
        that a log row exists for the object (actor may be null).
        """
        account = Account.objects.create(name="A1", org=self.org)

        logs = ActivityLog.objects.filter(object_type="Account", object_id=str(account.id), action="CREATE")
        assert logs.count() >= 1

    def test_account_update_emits_activity_log_best_effort(self):
        account = Account.objects.create(name="A1", org=self.org)
        account.name = "A1-updated"
        account.save()

        logs = ActivityLog.objects.filter(object_type="Account", object_id=str(account.id), action="UPDATE")
        assert logs.count() >= 1

    def test_account_delete_emits_activity_log_best_effort(self):
        account = Account.objects.create(name="A1", org=self.org)
        account_id = str(account.id)
        account.delete()

        logs = ActivityLog.objects.filter(object_type="Account", object_id=account_id, action="DELETE")
        assert logs.count() >= 1


@pytest.mark.django_db
def test_activity_logs_endpoint_requires_admin_permissions():
    """
    Endpoint should require auth and org-admin. We only check unauthenticated here.
    """
    client = APIClient()
    resp = client.get("/api/activity/activity-logs/")
    assert resp.status_code in (401, 403)
