from django.core.management.base import BaseCommand
from billing.services import run_billing


class Command(BaseCommand):
    help = "Create invoices for every active subscription that is due. Safe to re-run."

    def handle(self, *args, **opts):
        created, errors = run_billing()
        self.stdout.write(self.style.SUCCESS(f"{len(created)} invoice(s) created, {len(errors)} error(s)."))
