"""
Centralized activity logging helpers.

Design goals:
- Non-blocking: logging failures must never break the primary request flow.
- Tenant-safe: use org from the request/profile or instance, do not infer from headers.
- Minimal coupling: callable from signals, views, and management commands.

This module intentionally does not attempt to bypass RLS. If org context is missing
and the DB enforces RLS, inserts may fail; those failures are swallowed here.
"""

from __future__ import annotations

import logging
from typing import Any

from crum import get_current_request
from django.contrib.auth import get_user_model

from activity.models import ActivityLog

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str | None:
    """Best-effort client IP extraction."""
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return (request.META.get("REMOTE_ADDR") or None)[:64] if request.META.get("REMOTE_ADDR") else None


def _safe_obj_repr(instance: Any) -> str:
    """Generate a stable, short representation for an instance."""
    try:
        rep = str(instance)
    except Exception:
        rep = instance.__class__.__name__
    return (rep or "")[:255]


def _resolve_org(request, instance) -> Any:
    """
    Resolve org/tenant in a way that respects existing multi-tenant patterns.

    Priority:
    1) request.org (set by middleware from signed JWT/API key)
    2) request.profile.org
    3) instance.org if present
    """
    if request is not None:
        org = getattr(request, "org", None)
        if org is not None:
            return org
        profile = getattr(request, "profile", None)
        if profile is not None and getattr(profile, "org", None) is not None:
            return profile.org

    if instance is not None and hasattr(instance, "org"):
        return getattr(instance, "org", None)

    return None


# PUBLIC_INTERFACE
def log_activity(
    *,
    actor: Any | None,
    action: str,
    object_type: str,
    object_id: str = "",
    object_repr: str = "",
    metadata: dict[str, Any] | None = None,
    org: Any | None = None,
    request: Any | None = None,
) -> None:
    """
    PUBLIC_INTERFACE
    Create an ActivityLog entry.

    This function is intentionally non-blocking: any exception will be caught and logged.
    """
    try:
        req = request or get_current_request()
        resolved_org = org or _resolve_org(req, None)

        ActivityLog.objects.create(
            actor=actor if isinstance(actor, get_user_model()) or actor is None else actor,
            org=resolved_org,
            action=action,
            object_type=object_type,
            object_id=str(object_id or ""),
            object_repr=(object_repr or "")[:255],
            metadata=metadata or {},
            ip_address=_get_client_ip(req),
            user_agent=(req.META.get("HTTP_USER_AGENT", "")[:500] if req else ""),
        )
    except Exception as e:
        # Non-blocking by design
        logger.debug(f"ActivityLog write failed (ignored): {e}")


# PUBLIC_INTERFACE
def log_model_event(*, instance: Any, action: str, request: Any | None = None) -> None:
    """
    PUBLIC_INTERFACE
    Convenience wrapper for CRUD model events (create/update/delete).

    `instance` must be a saved model instance with a primary key.
    """
    try:
        req = request or get_current_request()
        actor = getattr(req, "user", None) if req else None
        resolved_org = _resolve_org(req, instance)

        ActivityLog.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            org=resolved_org,
            action=action,
            object_type=instance.__class__.__name__,
            object_id=str(getattr(instance, "pk", "") or ""),
            object_repr=_safe_obj_repr(instance),
            metadata={},
            ip_address=_get_client_ip(req),
            user_agent=(req.META.get("HTTP_USER_AGENT", "")[:500] if req else ""),
        )
    except Exception as e:
        logger.debug(f"ActivityLog model event write failed (ignored): {e}")
