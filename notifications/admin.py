from django.contrib import admin
from . import models
for m in (models.ReminderRule, models.ReminderLog, models.RenewalNotice, models.Insight):
    admin.site.register(m)
