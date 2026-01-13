import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.base import BaseModel


class ActivityLog(BaseModel):
    """
    Centralized activity log entry for auth and CRUD operations.

    Required fields for each log (per product requirement):
    - timestamp
    - user
    - action (LOGIN|LOGOUT|CREATE|UPDATE|DELETE)
    - module (lowercase module name, e.g. leads, invoices, auth)
    - record_id (stringified PK)
    - status (success|failure)

    Notes on multi-tenancy / RLS:
    - For org-scoped events, `org` MUST be set.
    - The table name is `activity_log` and should be included in RLS policies
      if your deployment enforces RLS broadly. This app does not attempt to
      enable/alter RLS policies automatically.

    Backward compatibility:
    - We keep legacy fields (actor/object_type/object_id/created_at) to avoid breaking
      any existing consumers and endpoints, but new code should prefer the required
      fields above.
    """

    class Action(models.TextChoices):
        LOGIN = "LOGIN", _("Login")
        LOGOUT = "LOGOUT", _("Logout")
        CREATE = "CREATE", _("Create")
        UPDATE = "UPDATE", _("Update")
        DELETE = "DELETE", _("Delete")

    class Status(models.TextChoices):
        SUCCESS = "success", _("Success")
        FAILURE = "failure", _("Failure")

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True, primary_key=True
    )

    # --- Required fields (canonical) ---
    # timestamp: keep as a dedicated field to satisfy requirement even though BaseModel has created_at.
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # user: nullable for system actions
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs_v2",
        help_text="Authenticated user that performed the action (nullable for system actions).",
    )

    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)

    module = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Lowercase module name (e.g., leads, accounts, invoices, auth).",
    )

    record_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Record primary key as string (UUID or int).",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SUCCESS,
        db_index=True,
        help_text="Outcome status for the attempted action.",
    )

    # --- Existing fields preserved for compatibility ---
    # Actor (auth user)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="Legacy: authenticated user that performed the action (if any). Prefer `user`.",
    )

    # Multi-tenant scope
    org = models.ForeignKey(
        "common.Org",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="Organization/tenant scope. Null allowed for platform-level events.",
    )

    # What object was affected (not a FK on purpose; keep logs durable)
    object_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Legacy: logical object type (e.g., Lead, Account, Invoice). Prefer `module`.",
    )
    object_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Legacy: object primary key as string (UUID or int). Prefer `record_id`.",
    )
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Human-friendly representation at the time of logging.",
    )

    # Extra structured context
    metadata = models.JSONField(default=dict, blank=True)

    # Request context when available
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        db_table = "activity_log"
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["org", "-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["module", "record_id"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["status", "-timestamp"]),
        ]

    def __str__(self) -> str:
        actor_email = getattr(self.user, "email", None) or getattr(self.actor, "email", None)
        actor_display = actor_email or str(self.user_id or self.actor_id) or "anonymous"
        return f"{self.action} {self.module}:{self.record_id} [{self.status}] by {actor_display}"
