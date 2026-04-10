"""
Management command to load rate data from the parquet seed file.

Usage:
    python manage.py seed_data
    python manage.py seed_data --file /path/to/rates_seed.parquet
    python manage.py seed_data --batch-size 10000
"""

import logging
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from rates.services import ingest_from_parquet

logger = logging.getLogger("rates")


class Command(BaseCommand):
    help = "Load rate data from a Snappy-compressed Parquet seed file into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=settings.SEED_FILE_PATH,
            help="Path to the parquet seed file (default: SEED_FILE_PATH from settings)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Number of rows per database batch insert (default: 5000)",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        batch_size = options["batch_size"]

        self.stdout.write(f"Starting seed from: {file_path}")
        self.stdout.write(f"Batch size: {batch_size}")

        try:
            stats = ingest_from_parquet(file_path, batch_size=batch_size)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Seed file not found: {file_path}"))
            sys.exit(1)
        except Exception as e:
            logger.exception("seed_data_failed")
            self.stderr.write(self.style.ERROR(f"Ingestion failed: {e}"))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(
            f"Ingestion complete — "
            f"total: {stats['total']}, "
            f"inserted/updated: {stats['inserted']}, "
            f"skipped (invalid): {stats['skipped_invalid']}, "
            f"skipped (duplicate): {stats['skipped_duplicate']}, "
            f"elapsed: {stats['elapsed_seconds']}s"
        ))
