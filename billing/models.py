from decimal import Decimal
from django.db import models
from django.utils import timezone


class Tax(models.Model):
    name = models.CharField(max_length=60)
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "taxes"

    def __str__(self):
        return f"{self.name} ({self.rate_percent}%)"


class Discount(models.Model):
    PERCENT, FIXED = "percent", "fixed"
    KINDS = [(PERCENT, "Percent"), (FIXED, "Fixed amount")]
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=8, choices=KINDS, default=PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_purchase = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_qty = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    used_count = models.PositiveIntegerField(default=0, editable=False)
    products = models.ManyToManyField("catalog.Product", blank=True, help_text="Leave empty to apply to every product")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name

    def is_live(self, on_date):
        if not self.active:
            return False
        if self.start_date and on_date < self.start_date:
            return False
        if self.end_date and on_date > self.end_date:
            return False
        return not (self.usage_limit is not None and self.used_count >= self.usage_limit)


class Invoice(models.Model):
    DRAFT, CONFIRMED, PAID, CANCELLED = "draft", "confirmed", "paid", "cancelled"
    STATUSES = [(DRAFT, "Draft"), (CONFIRMED, "Confirmed"), (PAID, "Paid"), (CANCELLED, "Cancelled")]
    TRANSITIONS = {DRAFT: [CONFIRMED, CANCELLED], CONFIRMED: [PAID, CANCELLED], PAID: [], CANCELLED: []}

    number = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT, related_name="invoices")
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="invoices")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT, db_index=True)
    due_date = models.DateField(db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["subscription", "period_start"], name="one_invoice_per_period")]

    def __str__(self):
        return self.number or f"Invoice #{self.pk}"

    @property
    def balance(self):
        return self.total - self.amount_paid

    @property
    def is_overdue(self):
        return self.status == self.CONFIRMED and self.due_date < timezone.localdate() and self.balance > 0

    @property
    def display_status(self):
        return "overdue" if self.is_overdue else self.status


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # net of discount, before tax
