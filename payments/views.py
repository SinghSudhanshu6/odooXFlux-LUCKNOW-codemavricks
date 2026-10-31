from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.mixins import STAFF, role_required
from accounts.utils import paginate
from billing.models import Invoice
from .forms import PaymentForm
from .models import Payment
from .services import record_payment


@role_required(*STAFF)
def payment_list(request):
    qs = Payment.objects.select_related("invoice", "invoice__customer", "recorded_by")
    method = request.GET.get("method", "")
    if method:
        qs = qs.filter(method=method)
    return render(request, "payments/list.html", {"page": paginate(request, qs), "method": method, "methods": Payment.METHODS})


@role_required(*STAFF)
def payment_new(request, pk):
    inv = get_object_or_404(Invoice.objects.select_related("customer"), pk=pk)
    form = PaymentForm(request.POST or None, initial={"date": timezone.localdate(), "amount": inv.balance})
    if request.method == "POST" and form.is_valid():
        try:
            record_payment(inv.pk, user=request.user, **form.cleaned_data)
            messages.success(request, "Payment recorded.")
            return redirect("invoice_detail", pk=inv.pk)
        except ValidationError as e:
            form.add_error("amount", e)
    return render(request, "payments/new.html", {"form": form, "inv": inv})
