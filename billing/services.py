"""Billing, tax and discount engines + invoice lifecycle."""
import io
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
import logging

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from subscriptions.models import Subscription
from .models import Discount, Invoice, InvoiceLine

log = logging.getLogger(__name__)
CENT = Decimal("0.01")


def money(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


# ---- discount engine -------------------------------------------------------
def best_discount(product, qty, base, on_date):
    """Return (discount, amount) for the single best eligible rule on a line."""
    best, best_amt = None, Decimal("0")
    for d in Discount.objects.filter(active=True).prefetch_related("products"):
        if not d.is_live(on_date) or qty < d.min_qty or base < d.min_purchase:
            continue
        scoped = list(d.products.all())
        if scoped and product not in scoped:
            continue
        amt = base * d.value / 100 if d.kind == Discount.PERCENT else min(d.value, base)
        amt = money(min(amt, base))
        if amt > best_amt:
            best, best_amt = d, amt
    return best, best_amt


# ---- invoice generation ----------------------------------------------------
def _build(invoice, sub, on_date):
    subtotal = disc_total = tax_total = Decimal("0")
    for l in sub.lines.select_related("product", "variant", "tax"):
        gross = money(l.quantity * l.unit_price)
        manual = money(l.discount or 0)
        rule, rule_amt = best_discount(l.product, l.quantity, gross - manual, on_date)
        discount = manual + rule_amt
        net = gross - discount
        rate = l.tax.rate_percent if l.tax else Decimal("0")
        tax = money(net * rate / 100)
        desc = l.product.name + (f" ({l.variant.value})" if l.variant else "")
        InvoiceLine.objects.create(invoice=invoice, description=desc, quantity=l.quantity,
                                   unit_price=l.unit_price, discount=discount, tax_rate=rate,
                                   tax_amount=tax, amount=net)
        subtotal += gross
        disc_total += discount
        tax_total += tax
        if rule:
            Discount.objects.filter(pk=rule.pk).update(used_count=F("used_count") + 1)
    invoice.subtotal, invoice.discount_total, invoice.tax_total = subtotal, disc_total, tax_total
    invoice.total = subtotal - disc_total + tax_total
    invoice.number = f"INV-{invoice.pk:06d}"
    invoice.save()


def generate_invoice(sub_id, today=None):
    """One billing step. Returns (state, invoice): state is created | skipped | done."""
    today = today or timezone.localdate()
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().select_related("plan", "customer").get(pk=sub_id)
        if sub.status != "active" or not sub.next_invoice_date or sub.next_invoice_date > today:
            return "done", None
        start = sub.next_invoice_date
        if start > sub.expiry_date:
            if sub.plan.auto_close:
                sub.status = "closed"
            sub.next_invoice_date = None
            sub.save()
            return "done", None
        nxt = start + sub.plan.delta
        invoice, created = Invoice.objects.get_or_create(
            subscription=sub, period_start=start,
            defaults={"customer": sub.customer, "period_end": nxt - timedelta(days=1),
                      "due_date": start + timedelta(days=sub.payment_terms)})
        if created:
            _build(invoice, sub, today)
        sub.next_invoice_date = nxt
        sub.save(update_fields=["next_invoice_date"])
        return ("created" if created else "skipped"), (invoice if created else None)


def run_billing(today=None):
    """Idempotent daily run with catch-up for missed days."""
    today = today or timezone.localdate()
    created, errors = [], []
    ids = list(Subscription.objects.filter(status="active", next_invoice_date__lte=today).values_list("pk", flat=True))
    for pk in ids:
        try:
            for _ in range(1000):
                state, inv = generate_invoice(pk, today)
                if state == "done":
                    break
                if inv:
                    created.append(inv)
        except Exception as exc:  # one failure never blocks the batch
            log.exception("Billing failed for subscription %s", pk)
            errors.append((pk, str(exc)))
    return created, errors


# ---- lifecycle -------------------------------------------------------------
def change_status(invoice, new):
    if new not in Invoice.TRANSITIONS[invoice.status]:
        raise ValidationError(f"A {invoice.status} invoice cannot become {new}.")
    if new == "cancelled" and invoice.amount_paid > 0:
        raise ValidationError("Invoices with payments cannot be cancelled.")
    invoice.status = new
    invoice.save(update_fields=["status"])


def send_invoice(invoice):
    if invoice.status not in ("confirmed", "paid"):
        raise ValidationError("Confirm the invoice before sending it.")
    user = invoice.customer.user
    send_mail(f"Invoice {invoice.number} from Brightloop",
              f"Hi {invoice.customer.name},\n\nInvoice {invoice.number} for Rs {invoice.total} is due on "
              f"{invoice.due_date:%d %b %Y}. Balance: Rs {invoice.balance}.\n\nThank you,\nBrightloop Billing",
              None, [user.email])
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=["sent_at"])


def invoice_pdf(invoice):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFillColor(colors.HexColor("#0B1020")); c.rect(0, h - 90, w, 90, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 20); c.drawString(40, h - 50, "Brightloop")
    c.setFont("Helvetica", 10); c.drawRightString(w - 40, h - 45, f"Invoice {invoice.number}")
    c.drawRightString(w - 40, h - 60, f"Status: {invoice.get_status_display()}")
    c.setFillColor(colors.black); y = h - 125
    c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Billed to"); c.setFont("Helvetica", 10)
    cust = invoice.customer
    for line in (cust.name, cust.company, cust.tax_id and f"GSTIN: {cust.tax_id}"):
        if line:
            y -= 14; c.drawString(40, y, line)
    c.drawRightString(w - 40, h - 125, f"Period: {invoice.period_start:%d %b %Y} - {invoice.period_end:%d %b %Y}")
    c.drawRightString(w - 40, h - 139, f"Due: {invoice.due_date:%d %b %Y}")
    y -= 40
    c.setFillColor(colors.HexColor("#E8EAF6")); c.rect(40, y - 6, w - 80, 20, fill=1, stroke=0)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 10)
    for x, t in ((46, "Item"), (290, "Qty"), (340, "Price"), (410, "Tax"), (w - 46, "Amount")):
        (c.drawRightString if t == "Amount" else c.drawString)(x, y, t)
    c.setFont("Helvetica", 10)
    for l in invoice.lines.all():
        y -= 22
        c.drawString(46, y, l.description[:40]); c.drawString(290, y, str(l.quantity))
        c.drawString(340, y, f"{l.unit_price:,.2f}"); c.drawString(410, y, f"{l.tax_rate}%")
        c.drawRightString(w - 46, y, f"{l.amount:,.2f}")
    y -= 34
    for label, val in (("Subtotal", invoice.subtotal), ("Discount", -invoice.discount_total),
                       ("Tax", invoice.tax_total), ("Total", invoice.total), ("Paid", invoice.amount_paid),
                       ("Balance due", invoice.balance)):
        c.setFont("Helvetica-Bold" if label in ("Total", "Balance due") else "Helvetica", 10)
        c.drawString(360, y, label); c.drawRightString(w - 46, y, f"Rs {val:,.2f}"); y -= 16
    c.showPage(); c.save()
    return buf.getvalue()
