from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import SignupForm, StaffForm
from .mixins import ADMIN, role_required
from .models import User


def forbidden(request, exception=None):
    return render(request, "403.html", status=403)


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Welcome to Brightloop. Your account is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@role_required(*ADMIN)
def staff_list(request):
    return render(request, "accounts/staff_list.html", {"staff": User.objects.filter(role=User.STAFF).order_by("email")})


@role_required(*ADMIN)
def staff_create(request):
    form = StaffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Staff account created.")
        return redirect("staff_list")
    return render(request, "form.html", {"form": form, "title": "New staff member", "back": "staff_list",
                                          "hint": "Only admins can create staff accounts."})


@login_required
def dashboard(request):
    from billing.models import Invoice
    from payments.models import Payment
    from subscriptions.models import Subscription

    u, today = request.user, timezone.localdate()
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=DecimalField())

    if u.role == User.CUSTOMER:
        cust = getattr(u, "customer", None)
        subs = Subscription.objects.filter(customer=cust).select_related("plan")
        invs = Invoice.objects.filter(customer=cust).exclude(status="cancelled")
        open_invs = invs.filter(status="confirmed")
        ctx = {
            "subs": subs[:5], "active_count": subs.filter(status="active").count(),
            "outstanding": open_invs.aggregate(t=Sum(balance))["t"] or Decimal("0"),
            "overdue_count": open_invs.filter(due_date__lt=today).count(),
            "recent": invs.order_by("-created_at")[:6],
        }
        return render(request, "dashboard_customer.html", ctx)

    active = Subscription.objects.filter(status="active").select_related("plan").prefetch_related("lines")
    mrr = sum((s.monthly_value() for s in active), Decimal("0"))
    open_invs = Invoice.objects.filter(status="confirmed")
    months = (Payment.objects.filter(date__gte=today - timedelta(days=180))
              .annotate(m=TruncMonth("date")).values("m").annotate(t=Sum("amount")).order_by("m"))
    months = list(months)[-6:]
    peak = max([m["t"] for m in months], default=Decimal("1")) or Decimal("1")
    for m in months:
        m["pct"] = max(int(m["t"] / peak * 100), 4)
    ctx = {
        "active_count": len(active), "mrr": mrr, "arr": mrr * 12,
        "outstanding": open_invs.aggregate(t=Sum(balance))["t"] or Decimal("0"),
        "revenue30": Payment.objects.filter(date__gte=today - timedelta(days=30)).aggregate(t=Sum("amount"))["t"] or Decimal("0"),
        "overdue": open_invs.filter(due_date__lt=today).select_related("customer").order_by("due_date")[:6],
        "overdue_count": open_invs.filter(due_date__lt=today).count(),
        "draft_count": Invoice.objects.filter(status="draft").count(),
        "recent": Invoice.objects.exclude(status="cancelled").select_related("customer").order_by("-created_at")[:6],
        "months": months,
    }
    return render(request, "dashboard.html", ctx)
