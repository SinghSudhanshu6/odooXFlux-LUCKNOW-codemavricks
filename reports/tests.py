import hashlib, hmac, json
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Customer, User
from billing.models import Invoice, Tax
from billing.services import change_status, invoice_pdf, preview_billing, run_billing
from catalog.models import Plan, Product
from notifications.services import ensure_default_rules, generate_insights, run_dunning
from payments import gateway
from payments.models import PaymentTransaction
from reports.services import snapshot_for
from subscriptions.models import Subscription, SubscriptionLine
from subscriptions.services import change_quantity


class Base(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        u = User.objects.create_user("c@x.test", "Customer@123", name="Cee")
        self.cust = Customer.objects.create(user=u, name="Cee", state="Karnataka")
        self.admin = User.objects.create_superuser("a@x.test", "Admin@12345")
        self.tax = Tax.objects.create(name="GST", rate_percent=18)
        self.prod = Product.objects.create(name="Seat", sales_price=1000)
        self.plan = Plan.objects.create(name="M", price=1, billing_period="monthly")
        self.sub = Subscription.objects.create(customer=self.cust, plan=self.plan, start_date=self.today - timedelta(days=10),
                                               expiry_date=self.today + timedelta(days=20))
        self.line = SubscriptionLine.objects.create(subscription=self.sub, product=self.prod, quantity=10, tax=self.tax)
        self.sub.transition("quotation"); self.sub.transition("confirmed"); self.sub.transition("active")
        self.sub.next_invoice_date = self.today - timedelta(days=10); self.sub.save()


class Dunning(Base):
    def _confirmed_invoice(self, due_offset):
        run_billing(self.today)
        inv = Invoice.objects.first()
        change_status(inv, "confirmed")
        inv.due_date = self.today - timedelta(days=due_offset); inv.save()
        return inv

    def test_sends_once_and_not_for_paid(self):
        inv = self._confirmed_invoice(3)
        self.assertEqual(len(run_dunning(self.today)), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(run_dunning(self.today), [])  # re-run sends nothing new
        inv.status = "paid"; inv.save()
        inv.reminders.all().delete()
        self.assertEqual(run_dunning(self.today), [])

    def test_final_notice_flags_risk(self):
        self._confirmed_invoice(14)
        run_dunning(self.today)
        self.assertTrue(self.cust.insights.filter(kind="churn", severity="high").exists())

    def test_insights_resolve_when_paid(self):
        inv = self._confirmed_invoice(20)
        self.assertGreaterEqual(generate_insights(self.today), 1)
        inv.status = "paid"; inv.save()
        generate_insights(self.today)
        self.assertFalse(self.cust.insights.filter(kind="churn", resolved=False).exists())


class Proration(Base):
    def test_upgrade_prorates_and_bills_once(self):
        run_billing(self.today)  # cycle starts 10 days ago, ends in ~20
        self.sub.refresh_from_db()
        start = self.sub.next_invoice_date - self.plan.delta
        ch = change_quantity(self.sub.pk, self.line.pk, 12, start)  # effective at cycle start: full fraction
        self.assertEqual(ch.proration_amount, Decimal("2000.00"))
        self.assertEqual(ch.change_type, "upgrade")
        self.sub.next_invoice_date = self.today
        self.sub.save()
        created, _ = run_billing(self.today + timedelta(days=0))
        inv = created[-1]
        self.assertTrue(inv.lines.filter(description__startswith="Proration").exists())
        ch.refresh_from_db()
        self.assertTrue(ch.billed)

    def test_downgrade_is_credit_and_min_qty(self):
        run_billing(self.today)
        self.sub.refresh_from_db()
        start = self.sub.next_invoice_date - self.plan.delta
        ch = change_quantity(self.sub.pk, self.line.pk, 8, start)
        self.assertEqual(ch.proration_amount, Decimal("-2000.00"))
        self.plan.min_qty = 5; self.plan.save()
        with self.assertRaises(ValidationError):
            change_quantity(self.sub.pk, self.line.pk, 2, start)

    def test_mrr_movement_reconciles(self):
        snap = snapshot_for(self.today)
        self.assertEqual(snap.closing_mrr, self.sub.monthly_value())
        self.assertEqual(snap.new, self.sub.monthly_value())  # activated today
        ch = change_quantity(self.sub.pk, self.line.pk, 12, self.today)
        snap2 = snapshot_for(self.today)
        self.assertEqual(snap2.expansion, ch.new_mrr - ch.old_mrr)


class Preview(Base):
    def test_preview_writes_nothing(self):
        rows, errors = preview_billing(self.today)
        self.assertEqual(len(rows), 1)
        self.assertEqual(Invoice.objects.count(), 0)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.next_invoice_date, self.today - timedelta(days=10))
        self.assertEqual(len(run_billing(self.today)[0]), 1)  # real run still works afterwards


class Razorpay(Base):
    def _ready_invoice(self):
        run_billing(self.today)
        inv = Invoice.objects.first()
        change_status(inv, "confirmed")
        return inv

    def test_valid_signature_records_payment_once(self):
        inv = self._ready_invoice()
        txn = gateway.create_order(inv)
        sig = gateway.sign(txn.order_id, "pay_1")
        gateway.confirm_checkout(txn.order_id, "pay_1", sig)
        gateway.confirm_checkout(txn.order_id, "pay_1", sig)  # replay
        inv.refresh_from_db()
        self.assertEqual(inv.status, "paid")
        self.assertEqual(inv.payments.count(), 1)

    def test_tampered_signature_rejected(self):
        inv = self._ready_invoice()
        txn = gateway.create_order(inv)
        with self.assertRaises(ValidationError):
            gateway.confirm_checkout(txn.order_id, "pay_1", "0" * 64)
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.payments.count()), ("confirmed", 0))

    @override_settings(RAZORPAY_WEBHOOK_SECRET="whsec")
    def test_webhook_dedupes_and_verifies(self):
        inv = self._ready_invoice()
        txn = gateway.create_order(inv)
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_9", "order_id": txn.order_id}}}}).encode()
        good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
        self.assertEqual(self.client.post(reverse("razorpay_webhook"), body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE="bad").status_code, 400)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("razorpay_webhook"), body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=good).status_code, 200)
        self.assertEqual(inv.payments.count(), 1)

    def test_portal_pay_flow_and_ownership(self):
        inv = self._ready_invoice()
        other = User.objects.create_user("o@x.test", "Customer@123")
        Customer.objects.create(user=other, name="Other")
        self.client.login(username="o@x.test", password="Customer@123")
        self.assertEqual(self.client.get(reverse("portal_pay", args=[inv.pk])).status_code, 404)
        self.client.logout(); self.client.login(username="c@x.test", password="Customer@123")
        r = self.client.get(reverse("portal_pay", args=[inv.pk]))
        self.assertContains(r, "Simulate test payment")
        oid = PaymentTransaction.objects.get().order_id
        self.client.post(reverse("razorpay_demo"), {"order_id": oid})
        inv.refresh_from_db()
        self.assertEqual(inv.status, "paid")


class Portal(Base):
    def test_customer_close_and_renew(self):
        self.client.login(username="c@x.test", password="Customer@123")
        r = self.client.post(reverse("portal_subscription_action", args=[self.sub.pk, "renew"]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Subscription.objects.filter(customer=self.cust, status="active").count(), 2)
        self.client.post(reverse("portal_subscription_action", args=[self.sub.pk, "close"]))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "closed")

    def test_staff_redirect_and_perms(self):
        self.client.login(username="c@x.test", password="Customer@123")
        self.assertEqual(self.client.get(reverse("subscription_list")).status_code, 302)
        for name in ("audit_list", "report_dashboard", "report_analytics", "insights", "reminder_settings"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_gst_split_and_pdf(self):
        run_billing(self.today)
        inv = Invoice.objects.first()
        change_status(inv, "confirmed")
        from billing.services import gst_split
        self.assertEqual([n for n, _ in gst_split(inv)], ["IGST"])  # Karnataka != Rajasthan
        self.cust.state = "Rajasthan"; self.cust.save(); inv.refresh_from_db()
        self.assertEqual([n for n, _ in gst_split(inv)], ["CGST", "SGST"])
        self.assertTrue(invoice_pdf(inv).startswith(b"%PDF"))
