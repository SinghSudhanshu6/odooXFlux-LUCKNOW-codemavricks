from django.urls import path
from . import views as v

urlpatterns = [
    path("insights/", v.insights, name="insights"),
    path("insights/<int:pk>/resolve/", v.insight_resolve, name="insight_resolve"),
    path("renewals/", v.renewals, name="renewals"),
    path("renewals/<int:pk>/renew/", v.renew_one, name="renew_one"),
    path("renewals/notify/", v.renewals_notify, name="renewals_notify"),
    path("settings/reminders/", v.reminder_settings, name="reminder_settings"),
    path("settings/reminders/new/", v.rule_create, name="rule_create"),
    path("settings/reminders/<int:pk>/edit/", v.rule_edit, name="rule_edit"),
    path("settings/reminders/run/", v.dunning_run, name="dunning_run"),
    path("invoices/<int:pk>/remind/", v.remind_now, name="remind_now"),
]
