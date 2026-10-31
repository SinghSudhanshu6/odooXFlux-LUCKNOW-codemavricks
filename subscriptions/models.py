from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    DRAFT, QUOTATION, CONFIRMED, ACTIVE, CLOSED = "draft", "quotation", "confirmed", "active", "closed"
    STATUSES = [(DRAFT, "Draft"), (QUOTATION, "Quotation"), (CONFIRMED, "Confirmed"),
                (ACTIVE, "Active"), (CLOSED, "Closed")]
    TRANSITIONS = {DRAFT: [QUOTATION], QUOTATION: [CONFIRMED, DRAFT], CONFIRMED: [ACTIVE],
                   ACTIVE: [CLOSED], CLOSED: []}

    number = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey("catalog.Plan", on_delete=models.PROTECT, related_name="subscriptions")
    start_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField()
    payment_terms = models.PositiveIntegerField("Payment terms (days)", default=15)
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT, db_index=True)
    next_invoice_date = models.DateField(null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.number or f"Subscription #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"SUB-{self.pk:05d}"
            super().save(update_fields=["number"])

    @property
    def editable(self):
        return self.status in (self.DRAFT, self.QUOTATION)

    @property
    def total(self):
        return sum((l.amount for l in self.lines.all()), Decimal("0"))

    def monthly_value(self):
        return (self.total * self.plan.monthly_factor).quantize(Decimal("0.01"))

    def can_close(self):
        return self.plan.closable or self.expiry_date <= timezone.localdate()

    def transition(self, new):
        if new not in self.TRANSITIONS[self.status]:
            raise ValidationError(f"A {self.get_status_display().lower()} subscription cannot move to {new}.")
        if new == self.CLOSED and not self.can_close():
            raise ValidationError("This plan cannot be closed before its expiry date.")
        if new == self.ACTIVE and not self.next_invoice_date:
            self.next_invoice_date = self.start_date
        if new == self.CONFIRMED and not self.lines.exists():
            raise ValidationError("Add at least one line before confirming.")
        self.status = new
        self.save()

    def renew(self):
        if self.status != self.CLOSED or not self.plan.renewable:
            raise ValidationError("Only closed subscriptions on renewable plans can be renewed.")
        term = self.expiry_date - self.start_date
        start = self.expiry_date + timedelta(days=1)
        new = Subscription.objects.create(customer=self.customer, plan=self.plan, start_date=start,
                                          expiry_date=start + term, payment_terms=self.payment_terms,
                                          notes=f"Renewal of {self.number}")
        for l in self.lines.all():
            SubscriptionLine.objects.create(subscription=new, product=l.product, variant=l.variant,
                                            quantity=l.quantity, unit_price=l.unit_price, tax=l.tax, discount=l.discount)
        return new


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text="Leave blank to use product price + variant extra")
    tax = models.ForeignKey("billing.Tax", on_delete=models.SET_NULL, null=True, blank=True)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)

    def save(self, *args, **kwargs):
        if self.unit_price is None:
            self.unit_price = self.product.sales_price + (self.variant.extra_price if self.variant else 0)
        self.amount = max(self.quantity * self.unit_price - (self.discount or 0), Decimal("0"))
        super().save(*args, **kwargs)
