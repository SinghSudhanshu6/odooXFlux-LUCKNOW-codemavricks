from django.urls import path
from . import views as v

urlpatterns = [
    path("reports/dashboard/", v.dashboard, name="report_dashboard"),
    path("reports/analytics/", v.analytics, name="report_analytics"),
    path("reports/export/", v.export, name="report_export"),
]
