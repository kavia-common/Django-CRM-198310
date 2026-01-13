import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.base import BaseModel


class ActivityLog(BaseModel):
    """
    Centralized activity log entry for auth and CRUD operations.

    Notes on multi-tenancy / RLS:
    - For org-scoped events, `org` MUST be set.
    - The table name is `activity_log` and should be included in RLS policies
      if your deployment enforces RLS broadly. This app does not attempt to
      enable/alter RLS policies automatically.
    """

    class Action(models.TextChoices):
        LOGIN = "LOGIN", _("Login")
        LOGOUT = "LOGOUT", _("Logout")
        CREATE = "CREATE", _("Create")
        UPDATE = "UPDATE", _("Update")
        DELETE = "DELETE", _("Delete")

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True, primary_key=True
    )

    # Actor (auth user)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        help_text="The authenticated user that performed the action (if any).",
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

    # What happened
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)

    # What object was affected (not a FK on purpose; keep logs durable)
    object_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Logical object type (e.g., Lead, Account, Invoice).",
    )
    object_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Object primary key as string (UUID or int).",
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
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["org", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        actor = getattr(self.actor, "email", None) or str(self.actor_id) or "anonymous"
        return f"{self.action} {self.object_type} {self.object_id} by {actor}"
