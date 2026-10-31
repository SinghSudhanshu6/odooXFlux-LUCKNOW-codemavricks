from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.mixins import ADMIN, ALL, STAFF, role_required, scope_customer
from accounts.utils import model_form_view, paginate
from . import services
from .forms import DiscountForm, TaxForm
from .models import Discount, Invoice, Tax

FILTERS = [("draft", "Draft"), ("confirmed", "Confirmed"), ("outstanding", "Outstanding"),
           ("partial", "Partially paid"), ("overdue", "Overdue"), ("paid", "Paid"), ("cancelled", "Cancelled")]


@role_required(*ALL)
def invoice_list(request):
    qs = scope_customer(request.user, Invoice.objects.select_related("customer", "subscription"))
    q, f, today = request.GET.get("q", "").strip(), request.GET.get("f", ""), timezone.localdate()
    if q:
        qs = qs.filter(number__icontains=q) | qs.filter(customer__name__icontains=q)
    if f in ("draft", "confirmed", "paid", "cancelled"):
        qs = qs.filter(status=f)
    elif f == "outstanding":
        qs = qs.filter(status="confirmed")
    elif f == "partial":
        qs = qs.filter(status="confirmed", amount_paid__gt=0)
    elif f == "overdue":
        qs = qs.filter(status="confirmed", due_date__lt=today)
    return render(request, "billing/invoice_list.html", {"page": paginate(request, qs), "q": q, "f": f, "filters": FILTERS})


def _get(request, pk):
    return get_object_or_404(scope_customer(request.user, Invoice.objects.select_related("customer", "subscription")), pk=pk)


@role_required(*ALL)
def invoice_detail(request, pk):
    inv = _get(request, pk)
    return render(request, "billing/invoice_detail.html", {
        "inv": inv, "lines": inv.lines.all(), "payments": inv.payments.select_related("recorded_by")})


@role_required(*STAFF)
@require_POST
def invoice_action(request, pk, action):
    inv = get_object_or_404(Invoice, pk=pk)
    try:
        if action == "send":
            services.send_invoice(inv)
            messages.success(request, f"{inv.number} emailed to {inv.customer.user.email}.")
        elif action in ("confirm", "cancel"):
            services.change_status(inv, {"confirm": "confirmed", "cancel": "cancelled"}[action])
            messages.success(request, f"{inv.number} is now {inv.status}.")
        else:
            raise ValidationError("Unknown action.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("invoice_detail", pk=pk)


@role_required(*ALL)
def invoice_pdf(request, pk):
    inv = _get(request, pk)
    resp = HttpResponse(services.invoice_pdf(inv), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{inv.number}.pdf"'
    return resp


@role_required(*STAFF)
@require_POST
def billing_run(request):
    created, errors = services.run_billing()
    if created:
        messages.success(request, f"Billing run created {len(created)} draft invoice(s).")
    else:
        messages.info(request, "Billing run finished. Nothing was due, so no invoices were created.")
    for pk, err in errors:
        messages.error(request, f"Subscription {pk} failed: {err}")
    return redirect("invoice_list")


@role_required(*STAFF)
def tax_list(request):
    return render(request, "billing/tax_list.html", {"taxes": Tax.objects.all()})


@role_required(*ADMIN)
def tax_create(request):
    return model_form_view(request, TaxForm, title="New tax", back="tax_list")


@role_required(*ADMIN)
def tax_edit(request, pk):
    t = get_object_or_404(Tax, pk=pk)
    return model_form_view(request, TaxForm, instance=t, title=f"Edit {t.name}", back="tax_list")


@role_required(*STAFF)
def discount_list(request):
    return render(request, "billing/discount_list.html", {"discounts": Discount.objects.all(), "today": timezone.localdate()})


@role_required(*ADMIN)
def discount_create(request):
    return model_form_view(request, DiscountForm, title="New discount rule", back="discount_list",
                           hint="Eligible discounts are applied to the next invoice automatically.")


@role_required(*ADMIN)
def discount_edit(request, pk):
    d = get_object_or_404(Discount, pk=pk)
    return model_form_view(request, DiscountForm, instance=d, title=f"Edit {d.name}", back="discount_list")
