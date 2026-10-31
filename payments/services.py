from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from billing.models import Invoice
from .models import Payment


def record_payment(invoice_id, *, method, amount, date, note="", user=None):
    amount = Decimal(amount)
    with transaction.atomic():
        inv = Invoice.objects.select_for_update().get(pk=invoice_id)
        if inv.status != Invoice.CONFIRMED:
            raise ValidationError("Payments can only be recorded against confirmed invoices.")
        if amount <= 0:
            raise ValidationError("Enter an amount greater than zero.")
        if amount > inv.balance:
            raise ValidationError(f"Overpayment blocked. The balance is {inv.balance}.")
        pay = Payment.objects.create(invoice=inv, method=method, amount=amount, date=date, note=note, recorded_by=user)
        inv.amount_paid = inv.payments.aggregate(t=Sum("amount"))["t"]
        if inv.amount_paid >= inv.total:
            inv.status = Invoice.PAID
        inv.save(update_fields=["amount_paid", "status"])
        return pay
