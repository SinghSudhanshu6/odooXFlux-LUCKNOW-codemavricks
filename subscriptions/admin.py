from django.contrib import admin
from .models import Subscription, SubscriptionLine


class LineInline(admin.TabularInline):
    model = SubscriptionLine
    extra = 0


@admin.register(Subscription)
class SubAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "plan", "status", "next_invoice_date")
    list_filter = ("status",)
    inlines = [LineInline]
