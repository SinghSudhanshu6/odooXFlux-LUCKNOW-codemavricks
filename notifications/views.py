from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.mixins import ADMIN, STAFF, role_required
from accounts.utils import model_form_view, paginate
from audit.services import log
from billing.models import Invoice
from subscriptions.models import Subscription
from . import services
from .forms import ReminderRuleForm
from .models import Insight, ReminderLog, ReminderRule


@role_required(*STAFF)
def insights(request):
    services.generate_insights()
    open_ = Insight.objects.filter(resolved=False).select_related("customer", "subscription", "invoice")
    return render(request, "notifications/insights.html", {"insights": open_})


@role_required(*STAFF)
@require_POST
def insight_resolve(request, pk):
    ins = get_object_or_404(Insight, pk=pk)
    ins.resolved = True
    ins.save(update_fields=["resolved"])
    return redirect("insights")


@role_required(*STAFF)
def renewals(request):
    return render(request, "notifications/renewals.html", {"subs": services.expiring_subscriptions()})


@role_required(*STAFF)
@require_POST
def renewals_notify(request):
    sent = services.send_renewal_notices()
    messages.success(request, f"Renewal emails sent for {len(sent)} subscription(s).")
    return redirect("renewals")


@role_required(*STAFF)
def reminder_settings(request):
    services.ensure_default_rules()
    return render(request, "notifications/reminders.html", {
        "rules": ReminderRule.objects.all(),
        "logs": ReminderLog.objects.select_related("invoice", "rule", "invoice__customer")[:25]})


@role_required(*ADMIN)
def rule_create(request):
    return model_form_view(request, ReminderRuleForm, title="New reminder rule", back="reminder_settings",
                           hint="Use a negative offset for days before the due date.")


@role_required(*ADMIN)
def rule_edit(request, pk):
    r = get_object_or_404(ReminderRule, pk=pk)
    return model_form_view(request, ReminderRuleForm, instance=r, title=f"Edit {r.name}", back="reminder_settings")


@role_required(*STAFF)
@require_POST
def dunning_run(request):
    sent = services.run_dunning()
    log(request.user, "reminders run", None, f"{len(sent)} email(s)")
    messages.success(request, f"{len(sent)} reminder email(s) sent." if sent else "No reminders were due today.")
    return redirect("reminder_settings")


@role_required(*STAFF)
@require_POST
def remind_now(request, pk):
    inv = get_object_or_404(Invoice.objects.select_related("customer__user"), pk=pk)
    if inv.status != "confirmed" or inv.balance <= 0:
        messages.error(request, "Only confirmed invoices with a balance can be reminded.")
    else:
        rule = ReminderRule.objects.filter(active=True).order_by("-offset_days").first()
        if rule is None:
            services.ensure_default_rules()
            rule = ReminderRule.objects.filter(active=True).order_by("-offset_days").first()
        services._send(inv, rule)
        log(request.user, "manual reminder", inv)
        messages.success(request, f"Reminder emailed to {inv.customer.user.email}.")
    return redirect("invoice_detail", pk=pk)


@role_required(*STAFF)
@require_POST
def renew_one(request, pk):
    from subscriptions.services import renew_and_activate
    sub = get_object_or_404(Subscription, pk=pk)
    try:
        new = renew_and_activate(sub)
        log(request.user, "renewed", sub, f"new term {new.number}")
        messages.success(request, f"{new.number} created and activated for the next term.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("renewals")
