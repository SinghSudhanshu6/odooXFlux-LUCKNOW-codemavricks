from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone

from billing.models import Invoice
from subscriptions.models import Subscription
from .models import Insight, ReminderLog, ReminderRule, RenewalNotice

DEFAULT_RULES = [
    ("3 days before due", -3, "Friendly reminder", "Informational", False, False),
    ("On due date", 0, "Payment due today", "Neutral", False, False),
    ("3 days overdue", 3, "First reminder: invoice overdue", "Polite", False, False),
    ("7 days overdue", 7, "Second reminder: invoice overdue", "Firm", True, False),
    ("14 days overdue", 14, "Final notice", "Urgent", False, True),
]
BODY = ("Hi {name},\n\nInvoice {invoice} has a balance of Rs {balance}, due {due}.\n"
        "You can view and pay it here: {link}\n\nThank you,\nBrightloop Billing")


def ensure_default_rules():
    if ReminderRule.objects.exists():
        return
    for name, off, subj, tone, task, risk in DEFAULT_RULES:
        ReminderRule.objects.create(name=name, offset_days=off, subject=f"{subj}: {{invoice}}", body=BODY,
                                    tone=tone, creates_task=task, flags_at_risk=risk)


def _send(invoice, rule):
    link = f"{settings.SITE_URL}/portal/invoices/{invoice.pk}/"
    ctx = dict(name=invoice.customer.name, invoice=invoice.number, balance=invoice.balance,
               due=f"{invoice.due_date:%d %b %Y}", link=link)
    send_mail(rule.subject.format(**ctx), rule.body.format(**ctx), None, [invoice.customer.user.email])


def run_dunning(today=None):
    """Safe to re-run: the unique (invoice, rule) log row means each rule fires once per invoice."""
    today = today or timezone.localdate()
    ensure_default_rules()
    sent = []
    for rule in ReminderRule.objects.filter(active=True):
        target_due = today - timedelta(days=rule.offset_days)
        invoices = (Invoice.objects.filter(status="confirmed", due_date=target_due, total__gt=F("amount_paid"))
                    .exclude(reminders__rule=rule).select_related("customer__user"))
        for inv in invoices:
            _send(inv, rule)
            ReminderLog.objects.create(invoice=inv, rule=rule)
            if rule.creates_task:
                Insight.objects.get_or_create(kind=Insight.TASK, customer=inv.customer, invoice=inv, resolved=False,
                                              defaults={"message": f"Follow up with {inv.customer.name} on {inv.number} ({rule.name})",
                                                        "severity": "medium"})
            if rule.flags_at_risk:
                Insight.objects.get_or_create(kind=Insight.CHURN, customer=inv.customer, invoice=inv, resolved=False,
                                              defaults={"message": f"{inv.customer.name} flagged at risk: {inv.number} is {rule.offset_days} days overdue",
                                                        "severity": "high"})
            sent.append((inv, rule))
    return sent


def generate_insights(today=None):
    """Rule-based alerts. Open insights that no longer apply are marked resolved."""
    today = today or timezone.localdate()
    keep = set()

    overdue = Invoice.objects.filter(status="confirmed", due_date__lt=today, total__gt=F("amount_paid")).select_related("customer")
    by_cust = {}
    for inv in overdue:
        by_cust.setdefault(inv.customer, []).append(inv)
    for cust, invs in by_cust.items():
        worst = max((today - i.due_date).days for i in invs)
        if len(invs) >= 2 or worst >= 14:
            why = f"{len(invs)} overdue invoice(s), oldest {worst} days"
            ins, _ = Insight.objects.get_or_create(kind=Insight.CHURN, customer=cust, subscription=None, invoice=None,
                                                   resolved=False, defaults={"message": f"Churn risk: {cust.name} has {why}", "severity": "high"})
            keep.add(ins.pk)

    soon = today + timedelta(days=30)
    for s in Subscription.objects.filter(status="active", expiry_date__lte=soon, expiry_date__gte=today).select_related("customer", "plan"):
        renewed = Subscription.objects.filter(customer=s.customer, plan=s.plan, start_date__gt=s.expiry_date).exists()
        if not renewed:
            days = (s.expiry_date - today).days
            ins, _ = Insight.objects.get_or_create(kind=Insight.RENEWAL, customer=s.customer, subscription=s, resolved=False,
                                                   defaults={"message": f"{s.number} expires in {days} days with no renewal started", "severity": "medium"})
            keep.add(ins.pk)

    for ins in Insight.objects.filter(resolved=False, kind__in=[Insight.CHURN, Insight.RENEWAL], invoice__isnull=True):
        if ins.pk not in keep:
            ins.resolved = True
            ins.save(update_fields=["resolved"])
    return len(keep)


def expiring_subscriptions(today=None, days=30):
    today = today or timezone.localdate()
    return (Subscription.objects.filter(status="active", expiry_date__gte=today, expiry_date__lte=today + timedelta(days=days))
            .select_related("customer", "plan").order_by("expiry_date"))


def send_renewal_notices(today=None):
    sent = []
    for s in expiring_subscriptions(today):
        if RenewalNotice.objects.filter(subscription=s).exists():
            continue
        send_mail(f"{s.number} renews soon",
                  f"Hi {s.customer.name},\n\nYour subscription {s.number} ends on {s.expiry_date:%d %b %Y}. "
                  f"Renew in one click from your portal: {settings.SITE_URL}/portal/subscriptions/{s.pk}/\n\nBrightloop Billing",
                  None, [s.customer.user.email])
        RenewalNotice.objects.create(subscription=s)
        sent.append(s)
    return sent
