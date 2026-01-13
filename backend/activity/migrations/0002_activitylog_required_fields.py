from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_required_fields(apps, schema_editor):
    ActivityLog = apps.get_model("activity", "ActivityLog")

    # Backfill in small batches; keep it simple and DB-friendly.
    qs = ActivityLog.objects.all().only("id", "created_at", "actor_id", "action", "object_type", "object_id")
    for log in qs.iterator(chunk_size=1000):
        updates = {}
        if getattr(log, "timestamp", None) is None:
            updates["timestamp"] = log.created_at
        if getattr(log, "user_id", None) is None and getattr(log, "actor_id", None):
            updates["user_id"] = log.actor_id
        if not getattr(log, "module", ""):
            # Best-effort: infer from object_type; default to 'unknown'
            object_type = (getattr(log, "object_type", "") or "").strip().lower()
            # Map common model names to modules
            mapping = {
                "lead": "leads",
                "account": "accounts",
                "contact": "contacts",
                "opportunity": "opportunities",
                "case": "cases",
                "task": "tasks",
                "invoice": "invoices",
                "user": "auth",
            }
            updates["module"] = mapping.get(object_type, object_type[:32] or "unknown")
        if not getattr(log, "record_id", ""):
            updates["record_id"] = (getattr(log, "object_id", "") or "")[:64]
        if not getattr(log, "status", ""):
            updates["status"] = "success"

        if updates:
            ActivityLog.objects.filter(id=log.id).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        ("activity", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="activitylog",
            name="timestamp",
            field=models.DateTimeField(auto_now_add=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="activitylog",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Authenticated user that performed the action (nullable for system actions).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="activity_logs_v2",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="activitylog",
            name="module",
            field=models.CharField(
                db_index=True,
                default="unknown",
                help_text="Lowercase module name (e.g., leads, accounts, invoices, auth).",
                max_length=32,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="activitylog",
            name="record_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Record primary key as string (UUID or int).",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="activitylog",
            name="status",
            field=models.CharField(
                choices=[("success", "Success"), ("failure", "Failure")],
                db_index=True,
                default="success",
                help_text="Outcome status for the attempted action.",
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_required_fields, migrations.RunPython.noop),
        # Make timestamp non-nullable after backfill
        migrations.AlterField(
            model_name="activitylog",
            name="timestamp",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
