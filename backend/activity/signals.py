"""
Signal handlers for centralized ActivityLog.

Requirements:
- Auth events: best-effort login/logout using Django auth signals.
- CRUD events: post_save/post_delete for major CRM modules.
- Must not change primary business behavior (logging is side-effect-only).
- Must not weaken tenant isolation (org derived from middleware request context or instance.org).

Implementation notes:
- We intentionally import model classes for sender registration (string senders are not valid for signals).
- Any failure during logging is swallowed to preserve API behavior.
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
    """Log auth login event (best-effort)."""
    try:
        log_activity(
            user=user,
            action=ActivityLog.Action.LOGIN,
            module="auth",
            record_id=str(getattr(user, "id", "") or ""),
            status=ActivityLog.Status.SUCCESS,
            object_type="User",
            object_id=str(getattr(user, "id", "") or ""),
            object_repr=getattr(user, "email", "") or str(getattr(user, "id", "") or ""),
            metadata=_actor_metadata(user),
            request=request,
            org=getattr(request, "org", None)
            or getattr(getattr(request, "profile", None), "org", None),
        )
    except Exception as e:
        logger.debug(f"Login activity signal failed (ignored): {e}")


@receiver(user_logged_out)
def activity_user_logged_out(sender, request, user, **kwargs):
    """Log auth logout event (best-effort)."""
    try:
        log_activity(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=ActivityLog.Action.LOGOUT,
            module="auth",
            record_id=str(getattr(user, "id", "") or "") if user else "",
            status=ActivityLog.Status.SUCCESS,
            object_type="User",
            object_id=str(getattr(user, "id", "") or "") if user else "",
            object_repr=getattr(user, "email", "") if user else "",
            metadata=_actor_metadata(user),
            request=request,
            org=getattr(request, "org", None)
            or getattr(getattr(request, "profile", None), "org", None),
        )
    except Exception as e:
        logger.debug(f"Logout activity signal failed (ignored): {e}")


# ---- CRUD logging for major modules ----
# Import models for signal sender binding.
try:
    from accounts.models import Account
    from cases.models import Case
    from contacts.models import Contact
    from invoices.models import Invoice
    from leads.models import Lead
    from opportunity.models import Opportunity
    from tasks.models import Task
except Exception as e:  # pragma: no cover (import issues should not crash app boot)
    Account = Case = Contact = Invoice = Lead = Opportunity = Task = None  # type: ignore
    logger.debug(f"Activity CRUD signal model import failed (ignored): {e}")


def _should_log_instance(instance) -> bool:
    """Return True when instance looks loggable (has a PK)."""
    return instance is not None and getattr(instance, "pk", None) is not None


def _crud_action(created: bool) -> str:
    return ActivityLog.Action.CREATE if created else ActivityLog.Action.UPDATE


def _register_crud_signals(model_cls, module_name: str) -> None:
    """Register post_save/post_delete handlers for a model class."""
    if model_cls is None:
        return

    @receiver(post_save, sender=model_cls, weak=False)
    def _post_save(sender, instance, created, **kwargs):  # noqa: B902
        try:
            if not _should_log_instance(instance):
                return
            req = get_current_request()
            log_model_event(
                instance=instance,
                action=_crud_action(created),
                module=module_name,
                status=ActivityLog.Status.SUCCESS,
                request=req,
            )
        except Exception as e:
            logger.debug(f"CRUD post_save activity failed (ignored): {e}")

    @receiver(post_delete, sender=model_cls, weak=False)
    def _post_delete(sender, instance, **kwargs):  # noqa: B902
        try:
            if not _should_log_instance(instance):
                return
            req = get_current_request()
            log_model_event(
                instance=instance,
                action=ActivityLog.Action.DELETE,
                module=module_name,
                status=ActivityLog.Status.SUCCESS,
                request=req,
            )
        except Exception as e:
            logger.debug(f"CRUD post_delete activity failed (ignored): {e}")


_register_crud_signals(Lead, "leads")
_register_crud_signals(Account, "accounts")
_register_crud_signals(Contact, "contacts")
_register_crud_signals(Opportunity, "opportunities")
_register_crud_signals(Case, "cases")
_register_crud_signals(Task, "tasks")
_register_crud_signals(Invoice, "invoices")
