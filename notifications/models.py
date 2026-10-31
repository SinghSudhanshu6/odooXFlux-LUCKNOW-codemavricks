from django.db import models


class ReminderRule(models.Model):
    name = models.CharField(max_length=80)
    offset_days = models.IntegerField(help_text="Negative = days before the due date, 0 = on the due date, positive = days overdue")
    subject = models.CharField(max_length=150)
    body = models.TextField(help_text="Placeholders: {name} {invoice} {balance} {due} {link}")
    tone = models.CharField(max_length=20, default="Informational")
    creates_task = models.BooleanField(default=False, help_text="Create a follow-up task for staff")
    flags_at_risk = models.BooleanField(default=False, help_text="Flag the customer as at risk")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["offset_days"]

    def __str__(self):
        return self.name


class ReminderLog(models.Model):
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.CASCADE, related_name="reminders")
    rule = models.ForeignKey(ReminderRule, on_delete=models.CASCADE, related_name="logs")
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="sent")

    class Meta:
        ordering = ["-sent_at"]
        constraints = [models.UniqueConstraint(fields=["invoice", "rule"], name="one_reminder_per_rule")]


class RenewalNotice(models.Model):
    subscription = models.OneToOneField("subscriptions.Subscription", on_delete=models.CASCADE, related_name="renewal_notice")
    sent_at = models.DateTimeField(auto_now_add=True)


class Insight(models.Model):
    CHURN, RENEWAL, TASK = "churn", "renewal", "task"
    KINDS = [(CHURN, "Churn risk"), (RENEWAL, "Renewal"), (TASK, "Follow-up task")]
    kind = models.CharField(max_length=10, choices=KINDS, db_index=True)
    customer = models.ForeignKey("accounts.Customer", on_delete=models.CASCADE, related_name="insights")
    subscription = models.ForeignKey("subscriptions.Subscription", null=True, blank=True, on_delete=models.CASCADE)
    invoice = models.ForeignKey("billing.Invoice", null=True, blank=True, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    severity = models.CharField(max_length=10, default="medium")
    resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
