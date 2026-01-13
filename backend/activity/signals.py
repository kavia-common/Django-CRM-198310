"""
Signal handlers for centralized ActivityLog.

- Auth events: best-effort login/logout using Django auth signals.
- CRUD events: post_save/post_delete for major CRM modules.

Important:
- Must not change primary business behavior.
- Must not weaken tenant isolation (org derived from middleware request context or instance.org).
"""

from __future__ import annotations

import logging

from crum import get_current_request
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from activity.logger import log_activity, log_model_event
from activity.models import ActivityLog

logger = logging.getLogger(__name__)


def _actor_metadata(user) -> dict:
    if not user:
        return {}
    return {
        "user_id": str(getattr(user, "id", "")),
        "email": getattr(user, "email", ""),
    }


@receiver(user_logged_in)
def activity_user_logged_in(sender, request, user, **kwargs):
    """Log auth login event."""
    try:
        log_activity(
            actor=user,
            action=ActivityLog.Action.LOGIN,
            object_type="User",
            object_id=str(user.id),
            object_repr=getattr(user, "email", "") or str(user.id),
            metadata=_actor_metadata(user),
            request=request,
            org=getattr(request, "org", None) or getattr(getattr(request, "profile", None), "org", None),
        )
    except Exception as e:
        logger.debug(f"Login activity signal failed (ignored): {e}")


@receiver(user_logged_out)
def activity_user_logged_out(sender, request, user, **kwargs):
    """Log auth logout event."""
    try:
        # Logout may happen without org context; keep best-effort.
        log_activity(
            actor=user if getattr(user, "is_authenticated", False) else None,
            action=ActivityLog.Action.LOGOUT,
            object_type="User",
            object_id=str(getattr(user, "id", "")) if user else "",
            object_repr=getattr(user, "email", "") if user else "",
            metadata=_actor_metadata(user),
            request=request,
            org=getattr(request, "org", None) or getattr(getattr(request, "profile", None), "org", None),
        )
    except Exception as e:
        logger.debug(f"Logout activity signal failed (ignored): {e}")


# ---- CRUD logging for major modules ----

CRUD_MODELS = [
    ("accounts.Account", "Account"),
    ("leads.Lead", "Lead"),
    ("contacts.Contact", "Contact"),
    ("opportunity.Opportunity", "Opportunity"),
    ("cases.Case", "Case"),
    ("tasks.Task", "Task"),
    ("invoices.Invoice", "Invoice"),
]


def _should_log_instance(instance) -> bool:
    """
    Avoid logging for irrelevant objects (e.g., inactive or missing PK).
    Keep it conservative: if we can't prove it's valid, skip.
    """
    if instance is None or getattr(instance, "pk", None) is None:
        return False
    return True


def _crud_action(created: bool) -> str:
    return ActivityLog.Action.CREATE if created else ActivityLog.Action.UPDATE


for dotted_path, label in CRUD_MODELS:

    @receiver(post_save, sender=dotted_path, weak=False)  # type: ignore[misc]
    def _post_save(sender, instance, created, **kwargs):  # noqa: B902
        try:
            if not _should_log_instance(instance):
                return

            # Ensure request context is used when available for actor/ip/ua.
            req = get_current_request()
            log_model_event(instance=instance, action=_crud_action(created), request=req)
        except Exception as e:
            logger.debug(f"CRUD post_save activity failed (ignored): {e}")

    @receiver(post_delete, sender=dotted_path, weak=False)  # type: ignore[misc]
    def _post_delete(sender, instance, **kwargs):  # noqa: B902
        try:
            if not _should_log_instance(instance):
                return
            req = get_current_request()
            log_model_event(instance=instance, action=ActivityLog.Action.DELETE, request=req)
        except Exception as e:
            logger.debug(f"CRUD post_delete activity failed (ignored): {e}")
