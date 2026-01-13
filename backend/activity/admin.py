from django.contrib import admin

from activity.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "org",
        "actor",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "ip_address",
    )
    list_filter = ("action", "object_type", "org", "created_at")
    search_fields = ("actor__email", "object_type", "object_id", "object_repr", "ip_address")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "actor",
        "org",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "metadata",
        "ip_address",
        "user_agent",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
