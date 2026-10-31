from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from subscriptions.models import Subscription, SubscriptionChange
from .models import MRRSnapshot

ZERO = Decimal("0")


def snapshot_for(day, subs=None):
    """Compute (and upsert) the MRR movement for one day from subscription events."""
    subs = subs if subs is not None else list(Subscription.objects.select_related("plan").prefetch_related("lines")
                                              .exclude(activated_at=None))
    new = sum((s.monthly_value() for s in subs if s.activated_at == day), ZERO)
    churned = sum((s.monthly_value() for s in subs if s.closed_at == day), ZERO)
    closing = sum((s.monthly_value() for s in subs
                   if s.activated_at and s.activated_at <= day and (s.closed_at is None or s.closed_at > day)), ZERO)
    exp = con = ZERO
    for ch in SubscriptionChange.objects.filter(effective_date=day):
        diff = ch.new_mrr - ch.old_mrr
        if diff > 0:
            exp += diff
        else:
            con += -diff
    snap, _ = MRRSnapshot.objects.update_or_create(
        date=day, defaults=dict(new=new, expansion=exp, contraction=con, churned=churned, closing_mrr=closing))
    return snap


def snapshot_range(start, end):
    subs = list(Subscription.objects.select_related("plan").prefetch_related("lines").exclude(activated_at=None))
    day = start
    while day <= end:
        snapshot_for(day, subs)
        day += timedelta(days=1)


def month_buckets(snaps):
    """Group snapshots by month for the movement chart."""
    out = {}
    for s in snaps:
        key = s.date.replace(day=1)
        b = out.setdefault(key, dict(month=key, new=ZERO, expansion=ZERO, contraction=ZERO, churned=ZERO, closing=ZERO))
        b["new"] += s.new; b["expansion"] += s.expansion; b["contraction"] += s.contraction; b["churned"] += s.churned
        b["closing"] = s.closing_mrr
    rows = [out[k] for k in sorted(out)]
    for r in rows:
        r["net"] = r["new"] + r["expansion"] - r["contraction"] - r["churned"]
    return rows


def kpis(start, end):
    today = timezone.localdate()
    active = list(Subscription.objects.filter(status="active").select_related("plan").prefetch_related("lines"))
    mrr = sum((s.monthly_value() for s in active), ZERO)
    paying = len({s.customer_id for s in active})
    snaps = list(MRRSnapshot.objects.filter(date__gte=start, date__lte=end))
    opening = MRRSnapshot.objects.filter(date__lt=start).order_by("-date").first()
    opening_mrr = opening.closing_mrr if opening else (snaps[0].closing_mrr - snaps[0].net_new if snaps else ZERO)
    churned = sum((s.churned for s in snaps), ZERO)
    return {
        "mrr": mrr, "arr": mrr * 12, "arpa": (mrr / paying).quantize(Decimal("0.01")) if paying else ZERO,
        "paying": paying, "churn_rate": (churned / opening_mrr * 100).quantize(Decimal("0.1")) if opening_mrr else ZERO,
        "churned": churned, "opening": opening_mrr,
        "net_new": sum((s.net_new for s in snaps), ZERO), "snaps": snaps,
    }
