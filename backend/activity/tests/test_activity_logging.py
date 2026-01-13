"""
Tests for ActivityLog required fields and admin API.

We keep tests intentionally conservative to avoid depending on PostgreSQL RLS.
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from activity.models import ActivityLog
from common.models import Org, Profile, User
from leads.models import Lead
from invoices.models import Invoice


class TestActivityLogFieldsAndCRUDSignals(TestCase):
    def setUp(self):
        self.org = Org.objects.create(name="Org 1")
        self.user = User.objects.create_user(email="admin@test.com", password="testpass123")
        self.profile = Profile.objects.create(
            user=self.user, org=self.org, role="ADMIN", is_active=True, is_organization_admin=True
        )

    def _assert_required_fields(self, log: ActivityLog):
        assert log.timestamp is not None
        # user is allowed to be null for system actions, but should be set when available
        assert log.action in {
            ActivityLog.Action.LOGIN,
            ActivityLog.Action.LOGOUT,
            ActivityLog.Action.CREATE,
            ActivityLog.Action.UPDATE,
            ActivityLog.Action.DELETE,
        }
        assert isinstance(log.module, str) and log.module == log.module.lower() and len(log.module) > 0
        assert isinstance(log.record_id, str)
        assert log.status in {ActivityLog.Status.SUCCESS, ActivityLog.Status.FAILURE}

    def test_lead_crud_emits_logs_with_required_fields(self):
        lead = Lead.objects.create(
            first_name="John",
            last_name="Doe",
            title="Mr",
            email="john@example.com",
            org=self.org,
            created_by=self.user,
        )
        lead_id = str(lead.id)

        # create
        create_logs = ActivityLog.objects.filter(module="leads", record_id=lead_id, action="CREATE")
        assert create_logs.count() >= 1
        self._assert_required_fields(create_logs.first())

        # update
        lead.first_name = "Johnny"
        lead.save()
        update_logs = ActivityLog.objects.filter(module="leads", record_id=lead_id, action="UPDATE")
        assert update_logs.count() >= 1
        self._assert_required_fields(update_logs.first())

        # delete
        lead.delete()
        delete_logs = ActivityLog.objects.filter(module="leads", record_id=lead_id, action="DELETE")
        assert delete_logs.count() >= 1
        self._assert_required_fields(delete_logs.first())

    def test_invoice_crud_emits_logs_with_required_fields(self):
        invoice = Invoice.objects.create(
            invoice_title="Inv1",
            status="Draft",
            org=self.org,
        )
        invoice_id = str(invoice.id)

        create_logs = ActivityLog.objects.filter(module="invoices", record_id=invoice_id, action="CREATE")
        assert create_logs.count() >= 1
        self._assert_required_fields(create_logs.first())

        invoice.invoice_title = "Inv1 updated"
        invoice.save()
        update_logs = ActivityLog.objects.filter(module="invoices", record_id=invoice_id, action="UPDATE")
        assert update_logs.count() >= 1
        self._assert_required_fields(update_logs.first())

        invoice.delete()
        delete_logs = ActivityLog.objects.filter(module="invoices", record_id=invoice_id, action="DELETE")
        assert delete_logs.count() >= 1
        self._assert_required_fields(delete_logs.first())


@pytest.mark.django_db
def test_admin_activity_logs_endpoint_requires_auth():
    client = APIClient()
    resp = client.get("/api/admin/activity-logs/")
    assert resp.status_code in (401, 403)
