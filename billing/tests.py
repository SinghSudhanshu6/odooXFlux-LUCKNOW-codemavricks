from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Customer, User
from accounts.validators import PasswordPolicyValidator
from billing.models import Discount, Invoice, Tax
from billing.services import change_status, run_billing
from catalog.models import Plan, Product, ProductVariant
from payments.services import record_payment
from subscriptions.models import Subscription, SubscriptionLine


class BillingFlow(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        u = User.objects.create_user("c@x.test", "Customer@123", name="Cee")
        self.cust = Customer.objects.create(user=u, name="Cee")
        self.admin = User.objects.create_superuser("a@x.test", "Admin@12345")
        tax = Tax.objects.create(name="GST", rate_percent=18)
        prod = Product.objects.create(name="ERP", sales_price=1000)
        var = ProductVariant.objects.create(product=prod, attribute="Brand", value="Odoo", extra_price=560)
        plan = Plan.objects.create(name="M", price=1, billing_period="monthly")
        self.sub = Subscription.objects.create(customer=self.cust, plan=plan, start_date=self.today - timedelta(days=65),
                                               expiry_date=self.today + timedelta(days=300))
        self.line = SubscriptionLine.objects.create(subscription=self.sub, product=prod, variant=var, quantity=2, tax=tax)
        self.sub.status, self.sub.next_invoice_date = "active", self.sub.start_date
        self.sub.save()

    def test_variant_adds_560(self):
        self.assertEqual(self.line.unit_price, Decimal("1560.00"))

    def test_catch_up_and_idempotent(self):
        created, errors = run_billing(self.today)
        self.assertEqual((len(created), errors), (3, []))
        again, _ = run_billing(self.today)
        self.assertEqual(again, [])
        self.assertEqual(Invoice.objects.count(), 3)

    def test_tax_and_discount(self):
        Discount.objects.create(name="10", kind="percent", value=10, usage_limit=1)
        created, _ = run_billing(self.today)
        first = Invoice.objects.order_by("period_start").first()
        # 2 x 1560 = 3120; 10% = 312; net 2808; tax 505.44; total 3313.44
        self.assertEqual(first.total, Decimal("3313.44"))
        self.assertEqual(Invoice.objects.filter(discount_total__gt=0).count(), 1)  # usage limit of 1 respected

    def test_payments_and_overpayment(self):
        run_billing(self.today)
        inv = Invoice.objects.first()
        change_status(inv, "confirmed")
        record_payment(inv.pk, method="upi", amount=Decimal("100"), date=self.today)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "confirmed")
        with self.assertRaises(ValidationError):
            record_payment(inv.pk, method="upi", amount=inv.total, date=self.today)
        record_payment(inv.pk, method="upi", amount=inv.balance, date=self.today)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "paid")

    def test_lifecycle_rules(self):
        with self.assertRaises(ValidationError):
            self.sub.transition("draft")


class Access(TestCase):
    def setUp(self):
        mk = lambda e: Customer.objects.create(user=User.objects.create_user(e, "Customer@123"), name=e)
        self.a, self.b = mk("a@x.test"), mk("b@x.test")
        plan = Plan.objects.create(name="M", price=1)
        s = Subscription.objects.create(customer=self.b, plan=plan, expiry_date=timezone.localdate() + timedelta(days=30))
        self.sub = s

    def test_customer_cannot_see_others(self):
        self.client.login(username="a@x.test", password="Customer@123")
        self.assertEqual(self.client.get(reverse("subscription_detail", args=[self.sub.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("product_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("staff_create")).status_code, 403)

    def test_signup_rules(self):
        data = {"name": "N", "email": "A@X.test", "password1": "weakpass", "password2": "weakpass"}
        self.assertEqual(self.client.post(reverse("signup"), data).status_code, 200)  # weak + duplicate (case-insens.)
        self.assertEqual(User.objects.filter(email__iexact="a@x.test").count(), 1)

    def test_password_policy(self):
        v = PasswordPolicyValidator()
        for bad in ("short1!A", "alllowercase!1", "ALLUPPERCASE!1", "NoSpecial12345"):
            with self.assertRaises(ValidationError):
                v.validate(bad)
        v.validate("Good-pass1")
