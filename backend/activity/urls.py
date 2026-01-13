from django.urls import path

from activity.views import ActivityLogListView

app_name = "activity"

urlpatterns = [
    path("activity-logs/", ActivityLogListView.as_view(), name="activity_logs"),
]
