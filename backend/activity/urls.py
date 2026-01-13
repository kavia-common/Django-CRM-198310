from django.urls import include, path
from rest_framework.routers import DefaultRouter

from activity.views import ActivityLogAdminViewSet

app_name = "activity"

router = DefaultRouter()
router.register(r"admin/activity-logs", ActivityLogAdminViewSet, basename="admin-activity-logs")

urlpatterns = [
    # Admin APIs (under /api/admin/activity-logs/ via router prefix below)
    path("", include(router.urls)),
]
