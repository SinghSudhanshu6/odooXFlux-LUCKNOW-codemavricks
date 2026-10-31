from django.contrib import admin
from .models import Discount, Invoice, InvoiceLine, Tax


class LineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "status", "total", "amount_paid", "due_date")
    list_filter = ("status",)
    inlines = [LineInline]


admin.site.register(Tax)
admin.site.register(Discount)
