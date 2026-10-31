from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.services import run_billing
from notifications import services as n
from reports.services import snapshot_for


class Command(BaseCommand):
    help = "Daily job: billing, reminders, renewal notices, insights, MRR snapshot. Safe to re-run."

    def handle(self, *a, **o):
        today = timezone.localdate()
        created, errors = run_billing(today)
        sent = n.run_dunning(today)
        renew = n.send_renewal_notices(today)
        insights = n.generate_insights(today)
        snapshot_for(today)
        self.stdout.write(self.style.SUCCESS(
            f"{len(created)} invoice(s), {len(errors)} error(s), {len(sent)} reminder(s), "
            f"{len(renew)} renewal notice(s), {insights} open insight(s), MRR snapshot saved."))
