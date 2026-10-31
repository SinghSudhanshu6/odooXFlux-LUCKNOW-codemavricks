from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from reports.services import snapshot_range


class Command(BaseCommand):
    help = "Store the MRR movement for today, or backfill with --days N."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=0)

    def handle(self, *a, days=0, **o):
        today = timezone.localdate()
        snapshot_range(today - timedelta(days=days), today)
        self.stdout.write(self.style.SUCCESS(f"MRR snapshots stored for {days + 1} day(s)."))
