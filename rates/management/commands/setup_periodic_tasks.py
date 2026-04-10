"""Management command to ensure required periodic tasks exist."""

from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Create periodic Celery Beat tasks if they do not already exist."

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=10,
            period=IntervalSchedule.MINUTES,
        )

        _, created = PeriodicTask.objects.get_or_create(
            name="run-rate-ingestion",
            defaults={
                "task": "rates.tasks.run_ingestion",
                "interval": schedule,
                "enabled": True,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Created periodic task 'run-rate-ingestion' (every 10 min)"))
        else:
            self.stdout.write(self.style.SUCCESS("Periodic task 'run-rate-ingestion' already exists"))
