from rest_framework import serializers

from activity.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            # canonical fields
            "timestamp",
            "user",
            "action",
            "module",
            "record_id",
            "status",
            # compatibility fields
            "created_at",
            "actor",
            "actor_email",
            "org",
            "object_type",
            "object_id",
            "object_repr",
            "metadata",
            "ip_address",
            "user_agent",
        ]
        read_only_fields = fields

    def get_actor_email(self, obj):
        return getattr(obj.user, "email", None) or getattr(obj.actor, "email", None)
