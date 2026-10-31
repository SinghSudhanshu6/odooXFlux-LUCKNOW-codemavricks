from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Customer, User
from billing.models import Discount, Tax
from billing.services import change_status, run_billing
from catalog.models import Plan, Product, ProductVariant, QuotationTemplate, TemplateLine
from payments.services import record_payment
from subscriptions.models import Subscription, SubscriptionLine


class Command(BaseCommand):
    help = "Create demo users, catalog, subscriptions and invoices."

    def handle(self, *a, **o):
        if User.objects.filter(email="admin@brightloop.test").exists():
            return self.stdout.write("Demo data already present.")
        today = timezone.localdate()
        admin = User.objects.create_superuser("admin@brightloop.test", "Admin@12345", name="Asha Admin")
        User.objects.create_user("staff@brightloop.test", "Staff@12345", name="Sam Staff", role="staff")
        custs = []
        for email, name, company in (("acme@brightloop.test", "Riya Mehta", "Acme Retail"),
                                     ("zen@brightloop.test", "Kabir Rao", "Zen Logistics"),
                                     ("nova@brightloop.test", "Isha Jain", "Nova Studio")):
            u = User.objects.create_user(email, "Customer@123", name=name)
            custs.append(Customer.objects.create(user=u, name=name, company=company, phone="9800000000"))

        gst18 = Tax.objects.create(name="GST 18%", rate_percent=18)
        Tax.objects.create(name="GST 5%", rate_percent=5)
        erp = Product.objects.create(name="Odoo ERP seat", product_type="software", sales_price=1500, cost_price=700)
        brand = ProductVariant.objects.create(product=erp, attribute="Brand", value="Odoo", extra_price=560)
        crm = Product.objects.create(name="CRM Suite", product_type="software", sales_price=900, cost_price=300)
        sup = Product.objects.create(name="Priority support", product_type="service", sales_price=2500, cost_price=1200)
        monthly = Plan.objects.create(name="Pro", price=1999, billing_period="monthly", min_qty=1)
        yearly = Plan.objects.create(name="Business", price=19999, billing_period="yearly", min_qty=1, auto_close=True)
        Plan.objects.create(name="Weekly pilot", price=499, billing_period="weekly", closable=True, renewable=False)
        Discount.objects.create(name="Launch 10% off", kind="percent", value=10, min_purchase=1000,
                                end_date=today + timedelta(days=60), usage_limit=50)
        t = QuotationTemplate.objects.create(name="Starter bundle", plan=monthly, validity_days=30)
        TemplateLine.objects.create(template=t, product=erp, variant=brand, quantity=2)
        TemplateLine.objects.create(template=t, product=sup, quantity=1)

        def sub(cust, plan, start, lines, status="active"):
            s = Subscription.objects.create(customer=cust, plan=plan, start_date=start,
                                            expiry_date=start + timedelta(days=365), payment_terms=15)
            for prod, var, qty in lines:
                SubscriptionLine.objects.create(subscription=s, product=prod, variant=var, quantity=qty, tax=gst18)
            s.status, s.next_invoice_date = status, start
            s.save()
            return s

        sub(custs[0], monthly, today - timedelta(days=75), [(erp, brand, 3), (sup, None, 1)])
        sub(custs[1], monthly, today - timedelta(days=40), [(crm, None, 5)])
        sub(custs[2], yearly, today - timedelta(days=10), [(erp, brand, 2)])
        sub(custs[1], monthly, today + timedelta(days=5), [(sup, None, 1)], status="quotation")
        created, _ = run_billing()
        for i, inv in enumerate(created):
            if i % 3 != 0:
                change_status(inv, "confirmed")
        confirmed = [i for i in created if i.status == "confirmed"]
        if confirmed:
            record_payment(confirmed[0].pk, method="upi", amount=confirmed[0].total, date=today, user=admin)
        if len(confirmed) > 1:
            record_payment(confirmed[1].pk, method="bank", amount=Decimal("1000"), date=today, note="Part payment", user=admin)
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("admin@brightloop.test / Admin@12345 | staff@brightloop.test / Staff@12345 | acme@brightloop.test / Customer@123")
