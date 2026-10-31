from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.db import models


class Product(models.Model):
    TYPES = [("service", "Service"), ("software", "Software"), ("physical", "Physical")]
    name = models.CharField(max_length=150)
    product_type = models.CharField(max_length=10, choices=TYPES, default="service")
    sales_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=60, help_text="e.g. Brand")
    value = models.CharField(max_length=60, help_text="e.g. Odoo")
    extra_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.product.name} / {self.attribute}: {self.value}"


class Plan(models.Model):
    PERIODS = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("yearly", "Yearly")]
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    billing_period = models.CharField(max_length=10, choices=PERIODS, default="monthly")
    min_qty = models.PositiveIntegerField("Minimum quantity", default=1)
    start_date = models.DateField("Available from", null=True, blank=True)
    end_date = models.DateField("Available to", null=True, blank=True)
    auto_close = models.BooleanField("Auto-close at end", default=False)
    closable = models.BooleanField("Closable early", default=True)
    pausable = models.BooleanField(default=False)
    renewable = models.BooleanField(default=True)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} ({self.get_billing_period_display()})"

    @property
    def delta(self):
        return {"daily": relativedelta(days=1), "weekly": relativedelta(weeks=1),
                "monthly": relativedelta(months=1), "yearly": relativedelta(years=1)}[self.billing_period]

    @property
    def monthly_factor(self):
        return {"daily": Decimal(365) / 12, "weekly": Decimal(52) / 12,
                "monthly": Decimal(1), "yearly": Decimal(1) / 12}[self.billing_period]


class QuotationTemplate(models.Model):
    name = models.CharField(max_length=120)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="templates")
    validity_days = models.PositiveIntegerField(default=30)

    def __str__(self):
        return self.name


class TemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
