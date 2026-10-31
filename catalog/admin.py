from django.contrib import admin
from . import models

for m in (models.Product, models.ProductVariant, models.Plan, models.QuotationTemplate, models.TemplateLine):
    admin.site.register(m)
