from __future__ import annotations

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activity.models import ActivityLog
from activity.serializer import ActivityLogSerializer
from common.permissions import HasOrgContext, IsOrgAdmin


class ActivityLogListView(APIView):
    """
    Read-only activity log endpoint for admins.

    Filters (all optional):
    - start: ISO datetime (inclusive)
    - end: ISO datetime (inclusive)
    - actor: UUID (User id)
    - object_type: string (Lead/Account/Invoice/etc.)
    - action: LOGIN/LOGOUT/CREATE/UPDATE/DELETE
    - org: UUID (Org id) - only allowed for superusers; otherwise ignored and forced to request.org
    """

    permission_classes = (IsAuthenticated, HasOrgContext, IsOrgAdmin)

    @extend_schema(
        tags=["activity"],
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
                name="actor",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Actor user id (UUID)",
            ),
            OpenApiParameter(
                name="object_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Object type (Lead, Account, Contact, Opportunity, Case, Task, Invoice, User)",
            ),
            OpenApiParameter(
                name="action",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Action (LOGIN, LOGOUT, CREATE, UPDATE, DELETE)",
            ),
            OpenApiParameter(
                name="org",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Organization id (UUID). Only superusers can query across orgs.",
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Max records to return (default 100, max 500)",
            ),
        ],
        responses={200: ActivityLogSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        qs = ActivityLog.objects.all()

        # Enforce org scoping: org-admins only see their org.
        org = request.org
        if request.user.is_superuser:
            org_param = request.query_params.get("org")
            if org_param:
                qs = qs.filter(org_id=org_param)
            else:
                # superuser without org param: default to current org context to be safe
                qs = qs.filter(org=org)
        else:
            qs = qs.filter(org=org)

        start = request.query_params.get("start")
        end = request.query_params.get("end")
        actor = request.query_params.get("actor")
        object_type = request.query_params.get("object_type")
        action = request.query_params.get("action")

        if start:
            dt = parse_datetime(start)
            if dt:
                qs = qs.filter(created_at__gte=dt)
        if end:
            dt = parse_datetime(end)
            if dt:
                qs = qs.filter(created_at__lte=dt)

        if actor:
            qs = qs.filter(actor_id=actor)
        if object_type:
            qs = qs.filter(object_type=object_type)
        if action:
            qs = qs.filter(action=action)

        limit = min(int(request.query_params.get("limit", 100)), 500)
        qs = qs.select_related("actor", "org").order_by("-created_at")[:limit]

        data = ActivityLogSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data})
