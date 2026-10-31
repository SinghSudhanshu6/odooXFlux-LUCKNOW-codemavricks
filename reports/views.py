import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Customer
from accounts.mixins import ADMIN, STAFF, role_required
from billing.models import Invoice
from catalog.models import Plan
from notifications.models import Insight
from payments.models import Payment
from subscriptions.models import Subscription
from . import services


def _parse(request):
    today = timezone.localdate()
    def d(key, default):
        try:
            return timezone.datetime.strptime(request.GET.get(key, ""), "%Y-%m-%d").date()
        except ValueError:
            return default
    return d("from", today - timedelta(days=180)), d("to", today)


def _filtered(request):
    """Apply the dashboard filters. Returns the querysets and the filter values."""
    start, end = _parse(request)
    f = {k: request.GET.get(k, "") for k in ("customer", "plan", "status", "method")}
    invoices = Invoice.objects.select_related("customer").filter(due_date__gte=start, due_date__lte=end)
    payments = Payment.objects.select_related("invoice__customer").filter(date__gte=start, date__lte=end)
    subs = Subscription.objects.select_related("customer", "plan")
    if f["customer"]:
        invoices = invoices.filter(customer_id=f["customer"]); payments = payments.filter(invoice__customer_id=f["customer"])
        subs = subs.filter(customer_id=f["customer"])
    if f["plan"]:
        invoices = invoices.filter(subscription__plan_id=f["plan"]); payments = payments.filter(invoice__subscription__plan_id=f["plan"])
        subs = subs.filter(plan_id=f["plan"])
    if f["status"]:
        subs = subs.filter(status=f["status"])
    if f["method"]:
        payments = payments.filter(method=f["method"])
    return start, end, f, invoices, payments, subs


@role_required(*STAFF)
def dashboard(request):
    start, end, f, invoices, payments, subs = _filtered(request)
    today = timezone.localdate()
    bal = ExpressionWrapper(F("total") - F("amount_paid"), output_field=DecimalField())
    confirmed = invoices.filter(status="confirmed")
    active = list(subs.filter(status="active").prefetch_related("lines"))
    mrr = sum((s.monthly_value() for s in active), Decimal("0"))

    rev = {r["m"]: r["t"] for r in payments.annotate(m=TruncMonth("date")).values("m").annotate(t=Sum("amount"))}
    months = sorted(rev)
    peak = max(rev.values(), default=Decimal("1")) or Decimal("1")
    trend = [{"m": m, "t": rev[m], "pct": max(int(rev[m] / peak * 100), 4)} for m in months]
    new_by = {}
    for s in subs.exclude(activated_at=None).filter(activated_at__gte=start, activated_at__lte=end):
        new_by[s.activated_at.replace(day=1)] = new_by.get(s.activated_at.replace(day=1), 0) + 1
    closed_by = {}
    for s in subs.exclude(closed_at=None).filter(closed_at__gte=start, closed_at__lte=end):
        closed_by[s.closed_at.replace(day=1)] = closed_by.get(s.closed_at.replace(day=1), 0) + 1
    sub_trend = [{"m": m, "new": new_by.get(m, 0), "closed": closed_by.get(m, 0)} for m in sorted(set(new_by) | set(closed_by))]

    ctx = {
        "start": start, "end": end, "f": f,
        "customers": Customer.objects.all(), "plans": Plan.objects.all(), "statuses": Subscription.STATUSES, "methods": Payment.METHODS,
        "active_count": len(active), "mrr": mrr, "arr": mrr * 12,
        "collected": payments.aggregate(t=Sum("amount"))["t"] or Decimal("0"),
        "outstanding": confirmed.aggregate(t=Sum(bal))["t"] or Decimal("0"),
        "overdue": confirmed.filter(due_date__lt=today).order_by("due_date")[:10],
        "overdue_count": confirmed.filter(due_date__lt=today).count(),
        "paid_count": invoices.filter(status="paid").count(),
        "trend": trend, "sub_trend": sub_trend,
        "insights": Insight.objects.filter(resolved=False).select_related("customer")[:6],
        "qs": request.GET.urlencode(),
    }
    return render(request, "reports/dashboard.html", ctx)


@role_required(*ADMIN)
def analytics(request):
    start, end = _parse(request)
    k = services.kpis(start, end)
    rows = services.month_buckets(k["snaps"])
    peak = max([max(r["new"] + r["expansion"], r["contraction"] + r["churned"]) for r in rows], default=Decimal("1")) or Decimal("1")
    for r in rows:
        r["up_pct"] = int((r["new"] + r["expansion"]) / peak * 100)
        r["down_pct"] = int((r["contraction"] + r["churned"]) / peak * 100)
    series = [{"d": s.date.isoformat(), "v": float(s.closing_mrr)} for s in k["snaps"]]
    return render(request, "reports/analytics.html", {"k": k, "rows": rows, "start": start, "end": end, "series": series})


@role_required(*ADMIN)
def export(request):
    fmt = request.GET.get("format", "csv")
    start, end, f, invoices, payments, subs = _filtered(request)
    rows = [("Invoice", "Customer", "Status", "Due date", "Total", "Paid", "Balance")]
    for i in invoices.order_by("due_date"):
        rows.append((i.number, i.customer.name, i.display_status, i.due_date.isoformat(), i.total, i.amount_paid, i.balance))
    if fmt == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="Invoice report")
        st = getSampleStyleSheet()
        tbl = Table([[str(c) for c in r] for r in rows], repeatRows=1)
        tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1020")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                 ("GRID", (0, 0), (-1, -1), .25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        total = sum((i.total for i in invoices), Decimal("0"))
        doc.build([Paragraph(f"Brightloop invoice report, {start:%d %b %Y} to {end:%d %b %Y}", st["Title"]),
                   Paragraph(f"{invoices.count()} invoices, total Rs {total:,.2f}", st["Normal"]), Spacer(1, 12), tbl])
        resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = 'attachment; filename="brightloop-report.pdf"'
        return resp
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="brightloop-report.csv"'
    csv.writer(resp).writerows(rows)
    return resp
