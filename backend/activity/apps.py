from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "activity"

    def ready(self):
        # Register signal handlers
        import activity.signals  # noqa: F401
