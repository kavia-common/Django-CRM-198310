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
    user: Any | None,
    action: str,
    module: str,
    record_id: str = "",
    status: str = ActivityLog.Status.SUCCESS,
    object_type: str = "",
    object_id: str = "",
    object_repr: str = "",
    metadata: dict[str, Any] | None = None,
    org: Any | None = None,
    request: Any | None = None,
) -> None:
    """
    PUBLIC_INTERFACE
    Create an ActivityLog entry.

    Required fields are always attempted:
      timestamp (auto), user, action, module, record_id, status

    Backward compatibility:
      legacy fields (actor/object_type/object_id) are populated when possible.

    This function is intentionally non-blocking: any exception will be caught and logged.
    """
    try:
        req = request or get_current_request()
        resolved_org = org or _resolve_org(req, None)

        # Normalize module for consistency
        module_norm = (module or "").strip().lower()[:32]

        actor = user if getattr(user, "is_authenticated", False) else None

        ActivityLog.objects.create(
            # required/canonical
            user=actor,
            action=action,
            module=module_norm,
            record_id=str(record_id or "")[:64],
            status=status,
            # legacy
            actor=actor,
            object_type=(object_type or module_norm or "")[:100],
            object_id=str(object_id or record_id or "")[:64],
            object_repr=(object_repr or "")[:255],
            # scope & context
            org=resolved_org,
            metadata=metadata or {},
            ip_address=_get_client_ip(req),
            user_agent=(req.META.get("HTTP_USER_AGENT", "")[:500] if req else ""),
        )
    except Exception as e:
        # Non-blocking by design
        logger.debug(f"ActivityLog write failed (ignored): {e}")


# PUBLIC_INTERFACE
def log_model_event(
    *,
    instance: Any,
    action: str,
    module: str,
    status: str = ActivityLog.Status.SUCCESS,
    request: Any | None = None,
) -> None:
    """
    PUBLIC_INTERFACE
    Convenience wrapper for CRUD model events (create/update/delete).

    `instance` must be a saved model instance with a primary key.
    """
    try:
        req = request or get_current_request()
        actor = getattr(req, "user", None) if req else None
        resolved_org = _resolve_org(req, instance)

        module_norm = (module or instance.__class__.__name__).strip().lower()[:32]
        record_id = str(getattr(instance, "pk", "") or "")[:64]

        ActivityLog.objects.create(
            # required/canonical
            user=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            module=module_norm,
            record_id=record_id,
            status=status,
            # legacy
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            object_type=instance.__class__.__name__,
            object_id=record_id,
            object_repr=_safe_obj_repr(instance),
            # scope & context
            org=resolved_org,
            metadata={},
            ip_address=_get_client_ip(req),
            user_agent=(req.META.get("HTTP_USER_AGENT", "")[:500] if req else ""),
        )
    except Exception as e:
        logger.debug(f"ActivityLog model event write failed (ignored): {e}")
