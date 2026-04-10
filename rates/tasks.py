"""Celery tasks for scheduled rate ingestion."""

import logging

from celery import shared_task
from django.conf import settings

from .services import ingest_from_parquet

logger = logging.getLogger("rates")


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_ingestion(self):
    """
    Periodic task: re-ingest from the seed file.
    In production this would call an HTTP scraper; for this assessment
    it re-processes the parquet file to demonstrate idempotent re-runs.
    """
    try:
        stats = ingest_from_parquet(settings.SEED_FILE_PATH)
        logger.info("scheduled_ingestion_complete", extra=stats)
        return stats
    except Exception as exc:
        logger.exception("scheduled_ingestion_failed")
        raise self.retry(exc=exc)
