from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.mixins import role_required, scope_customer
from accounts.utils import paginate
from audit.services import log
from billing.models import Invoice
from payments import gateway
from subscriptions.models import Subscription
from subscriptions.services import renew_and_activate

CUSTOMER = ("customer",)


def _sub(request, pk):
    return get_object_or_404(scope_customer(request.user, Subscription.objects.select_related("plan", "customer")), pk=pk)


def _inv(request, pk):
    return get_object_or_404(scope_customer(request.user, Invoice.objects.select_related("customer", "subscription")), pk=pk)


@role_required(*CUSTOMER)
def subscriptions(request):
    qs = scope_customer(request.user, Subscription.objects.select_related("plan"))
    return render(request, "portal/subscriptions.html", {"page": paginate(request, qs, 12)})


@role_required(*CUSTOMER)
def subscription(request, pk):
    s = _sub(request, pk)
    return render(request, "portal/subscription.html", {
        "sub": s, "lines": s.lines.select_related("product", "variant", "tax"), "invoices": s.invoices.exclude(status="draft").order_by("-period_start"),
        "can_renew": s.plan.renewable and s.status in ("active", "closed"), "can_close": s.status == "active" and s.can_close()})


@role_required(*CUSTOMER)
@require_POST
def subscription_action(request, pk, action):
    s = _sub(request, pk)
    try:
        if action == "close":
            s.transition("closed")
            log(request.user, "closed by customer", s)
            messages.success(request, f"{s.number} has been closed.")
        elif action == "renew":
            new = renew_and_activate(s)
            log(request.user, "renewed by customer", s, f"new term {new.number}")
            messages.success(request, f"Renewed. Your new term {new.number} starts {new.start_date:%d %b %Y}.")
            return redirect("portal_subscription", pk=new.pk)
        else:
            raise ValidationError("Unknown action.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("portal_subscription", pk=pk)


@role_required(*CUSTOMER)
def invoices(request):
    qs = scope_customer(request.user, Invoice.objects.exclude(status="draft").select_related("subscription"))
    return render(request, "portal/invoices.html", {"page": paginate(request, qs, 15)})


@role_required(*CUSTOMER)
def invoice(request, pk):
    inv = _inv(request, pk)
    if inv.status == "draft":
        return redirect("portal_invoices")
    return render(request, "portal/invoice.html", {"inv": inv, "lines": inv.lines.all(), "payments": inv.payments.all(),
                                                    "can_pay": inv.status == "confirmed" and inv.balance > 0})


@role_required(*CUSTOMER)
def pay(request, pk):
    inv = _inv(request, pk)
    try:
        txn = gateway.create_order(inv)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return redirect("portal_invoice", pk=pk)
    return render(request, "portal/pay.html", {"inv": inv, "txn": txn, "demo": gateway.is_demo(),
                                                "key": settings.RAZORPAY_KEY_ID, "paise": int(txn.amount * 100)})


@role_required(*CUSTOMER)
def profile(request):
    from .forms import ProfileForm
    cust = request.user.customer
    form = ProfileForm(request.POST or None, instance=cust)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.user.name = cust.name
        request.user.save(update_fields=["name"])
        messages.success(request, "Profile updated.")
        return redirect("portal_profile")
    return render(request, "portal/profile.html", {"form": form})
