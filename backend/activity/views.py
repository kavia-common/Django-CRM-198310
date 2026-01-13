from __future__ import annotations

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated

from activity.models import ActivityLog
from activity.serializer import ActivityLogSerializer
from common.permissions import HasOrgContext, IsOrgAdmin


class ActivityLogAdminPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 200


class ActivityLogAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ActivityLog admin API.

    Filters (all optional):
    - start: ISO datetime (inclusive), filters by timestamp >= start
    - end: ISO datetime (inclusive), filters by timestamp <= end
    - user: UUID (User id)
    - module: lowercase module name (leads, accounts, contacts, opportunities, cases, tasks, invoices, auth)
    - action: LOGIN|LOGOUT|CREATE|UPDATE|DELETE
    - status: success|failure
    - record_id: record primary key as string

    Tenant isolation:
    - Org-admins only see logs for request.org.
    - Superusers also default to request.org; cross-org querying is intentionally not exposed here.
    """

    permission_classes = (IsAuthenticated, HasOrgContext, IsOrgAdmin)
    serializer_class = ActivityLogSerializer
    pagination_class = ActivityLogAdminPagination

    def get_queryset(self):
        qs = ActivityLog.objects.all().select_related("user", "actor", "org")

        # Enforce org scoping always (safer default).
        qs = qs.filter(org=self.request.org)

        params = self.request.query_params

        start = params.get("start")
        end = params.get("end")
        user_id = params.get("user")
        module = params.get("module")
        action = params.get("action")
        status = params.get("status")
        record_id = params.get("record_id")

        if start:
            dt = parse_datetime(start)
            if dt:
                qs = qs.filter(timestamp__gte=dt)
        if end:
            dt = parse_datetime(end)
            if dt:
                qs = qs.filter(timestamp__lte=dt)

        if user_id:
            qs = qs.filter(user_id=user_id)

        if module:
            qs = qs.filter(module=module.strip().lower())

        if action:
            qs = qs.filter(action=action)

        if status:
            qs = qs.filter(status=status)

        if record_id:
            qs = qs.filter(record_id=str(record_id)[:64])

        return qs.order_by("-timestamp")

    @extend_schema(
        tags=["admin", "activity"],
        operation_id="admin_activity_logs_list",
        summary="List activity logs (admin)",
        description="Read-only activity logs for the current org with filtering and pagination.",
        parameters=[
            OpenApiParameter(
                name="start",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Start datetime (ISO-8601), inclusive",
            ),
            OpenApiParameter(
                name="end",
                type=str,
                location=OpenApiParameter.QUERY,
                description="End datetime (ISO-8601), inclusive",
            ),
            OpenApiParameter(
                name="user",
                type=str,
                location=OpenApiParameter.QUERY,
                description="User id (UUID)",
            ),
            OpenApiParameter(
                name="module",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Module (leads, accounts, contacts, opportunities, cases, tasks, invoices, auth)",
            ),
            OpenApiParameter(
                name="action",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Action (LOGIN, LOGOUT, CREATE, UPDATE, DELETE)",
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Status (success, failure)",
            ),
            OpenApiParameter(
                name="record_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Record primary key as string",
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Pagination limit (max 200)",
            ),
            OpenApiParameter(
                name="offset",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Pagination offset",
            ),
        ],
        responses={200: ActivityLogSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["admin", "activity"],
        operation_id="admin_activity_logs_retrieve",
        summary="Retrieve activity log (admin)",
        description="Retrieve a single activity log (read-only).",
        responses={200: ActivityLogSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
