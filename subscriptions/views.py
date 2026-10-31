from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.mixins import ALL, STAFF, role_required, scope_customer
from accounts.utils import paginate
from catalog.models import QuotationTemplate
from .forms import FromTemplateForm, LineFormSet, SubscriptionForm
from .models import Subscription, SubscriptionLine

ACTIONS = {"quote": "quotation", "confirm": "confirmed", "activate": "active", "close": "closed", "draft": "draft"}


@role_required(*ALL)
def subscription_list(request):
    qs = scope_customer(request.user, Subscription.objects.select_related("customer", "plan"))
    q, status = request.GET.get("q", "").strip(), request.GET.get("status", "")
    if q:
        qs = qs.filter(number__icontains=q) | qs.filter(customer__name__icontains=q) | qs.filter(customer__company__icontains=q)
    if status:
        qs = qs.filter(status=status)
    return render(request, "subscriptions/list.html", {
        "page": paginate(request, qs), "q": q, "status": status, "statuses": Subscription.STATUSES})


@role_required(*ALL)
def subscription_detail(request, pk):
    sub = get_object_or_404(scope_customer(request.user, Subscription.objects.select_related("customer", "plan")), pk=pk)
    return render(request, "subscriptions/detail.html", {
        "sub": sub, "lines": sub.lines.select_related("product", "variant", "tax"),
        "invoices": sub.invoices.order_by("-period_start")})


def _save(request, sub, title):
    form = SubscriptionForm(request.POST or None, instance=sub)
    formset = LineFormSet(request.POST or None, instance=sub or Subscription())
    if request.method == "POST" and form.is_valid():
        formset.plan = form.cleaned_data["plan"]
        if formset.is_valid():
            with transaction.atomic():
                obj = form.save()
                formset.instance = obj
                formset.save()
            messages.success(request, f"{obj.number} saved.")
            return redirect("subscription_detail", pk=obj.pk)
    return render(request, "subscriptions/form.html", {"form": form, "formset": formset, "title": title})


@role_required(*STAFF)
def subscription_create(request):
    return _save(request, None, "New subscription")


@role_required(*STAFF)
def subscription_edit(request, pk):
    sub = get_object_or_404(Subscription, pk=pk)
    if not sub.editable:
        messages.error(request, "Only draft or quotation subscriptions can be edited.")
        return redirect("subscription_detail", pk=pk)
    return _save(request, sub, f"Edit {sub.number}")


@role_required(*STAFF)
@require_POST
def subscription_action(request, pk, action):
    sub = get_object_or_404(Subscription, pk=pk)
    try:
        if action == "renew":
            new = sub.renew()
            messages.success(request, f"Renewal {new.number} created as a draft.")
            return redirect("subscription_detail", pk=new.pk)
        if action not in ACTIONS:
            raise ValidationError("Unknown action.")
        sub.transition(ACTIONS[action])
        messages.success(request, f"{sub.number} is now {sub.get_status_display().lower()}.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("subscription_detail", pk=pk)


@role_required(*STAFF)
def from_template(request, template_id):
    t = get_object_or_404(QuotationTemplate.objects.select_related("plan"), pk=template_id)
    form = FromTemplateForm(request.POST or None, initial={"start_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        if not t.lines.exists():
            messages.error(request, "This template has no lines yet.")
            return redirect("template_detail", pk=t.pk)
        with transaction.atomic():
            start = form.cleaned_data["start_date"]
            sub = Subscription.objects.create(
                customer=form.cleaned_data["customer"], plan=t.plan, start_date=start,
                expiry_date=start + timedelta(days=t.validity_days), status=Subscription.QUOTATION,
                notes=f"From template: {t.name}")
            for l in t.lines.all():
                SubscriptionLine.objects.create(subscription=sub, product=l.product, variant=l.variant,
                                                quantity=max(l.quantity, t.plan.min_qty))
        messages.success(request, f"{sub.number} created as a quotation.")
        return redirect("subscription_detail", pk=sub.pk)
    return render(request, "form.html", {"form": form, "title": f"Use template: {t.name}",
                                          "back": "template_list", "submit": "Create quotation"})
