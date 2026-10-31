from django.conf import settings
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    METHODS = [("upi", "UPI"), ("bank", "Bank transfer"), ("card", "Card"), ("cash", "Cash"),
               ("cheque", "Cheque"), ("other", "Other")]
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=10, choices=METHODS, default="upi")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.localdate, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
