"""
Core ingestion service — handles data cleaning, normalization, and persistence.
Separated from the management command so it can be reused by the Celery task and API.
"""

import logging
import time
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Rate, RawResponse

logger = logging.getLogger("rates")

# --- Normalization maps ---

PROVIDER_NORMALIZATION = {
    "hsbc": "HSBC",
    "chase": "Chase",
    "bank of america": "Bank of America",
    "truist": "Truist",
    "us bancorp": "US Bancorp",
    "td bank": "TD Bank",
    "pnc bank": "PNC Bank",
    "capital one": "Capital One",
    "citibank": "Citibank",
    "wells fargo": "Wells Fargo",
}

CURRENCY_NORMALIZATION = {
    "usd": "USD",
    "us dollar": "USD",
    "eur": "EUR",
    "gbp": "GBP",
}

VALID_RATE_TYPES = {choice.value for choice in Rate.RateType}


def normalize_provider(name: str) -> str:
    return PROVIDER_NORMALIZATION.get(name.strip().lower(), name.strip().title())


def normalize_currency(currency: str) -> str:
    return CURRENCY_NORMALIZATION.get(currency.strip().lower(), currency.strip().upper())


def validate_rate_value(value) -> Decimal | None:
    """Return a valid Decimal rate or None if invalid."""
    if pd.isna(value):
        return None
    try:
        dec = Decimal(str(value)).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError):
        return None
    if dec < 0 or dec > 100:
        return None
    return dec


def ingest_from_parquet(file_path: str, batch_size: int = 5000) -> dict:
    """
    Load parquet seed file, clean, normalize, and bulk-upsert into the database.

    Returns a summary dict with counts of processed, inserted, skipped, and errored rows.
    """
    start = time.monotonic()
    logger.info("ingestion_started", extra={"file_path": file_path})

    df = pd.read_parquet(file_path)
    total_rows = len(df)
    logger.info("parquet_loaded", extra={"total_rows": total_rows})

    stats = {"total": total_rows, "inserted": 0, "skipped_invalid": 0, "skipped_duplicate": 0}

    # --- Pre-processing: clean and deduplicate in pandas ---
    df["provider_clean"] = df["provider"].apply(normalize_provider)
    df["currency_clean"] = df["currency"].apply(normalize_currency)
    df["rate_value_clean"] = df["rate_value"].apply(validate_rate_value)

    # Drop rows with invalid rate values
    invalid_mask = df["rate_value_clean"].isna()
    stats["skipped_invalid"] = int(invalid_mask.sum())
    df = df[~invalid_mask].copy()

    # Drop rows with invalid rate types
    invalid_type_mask = ~df["rate_type"].isin(VALID_RATE_TYPES)
    stats["skipped_invalid"] += int(invalid_type_mask.sum())
    df = df[~invalid_type_mask].copy()

    # Deduplicate: keep the row with the latest ingestion_ts per (provider, rate_type, effective_date)
    df = df.sort_values("ingestion_ts", ascending=False)
    df = df.drop_duplicates(subset=["provider_clean", "rate_type", "effective_date"], keep="first")
    stats["skipped_duplicate"] = total_rows - stats["skipped_invalid"] - len(df)

    logger.info(
        "deduplication_complete",
        extra={"remaining_rows": len(df), "skipped_duplicates": stats["skipped_duplicate"]},
    )

    # --- Batch insert ---
    rows = df.to_dict("records")
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        _upsert_batch(batch, stats)
        if (i // batch_size) % 10 == 0:
            logger.info(
                "batch_progress",
                extra={"processed": min(i + batch_size, len(rows)), "total": len(rows)},
            )

    elapsed = time.monotonic() - start
    stats["elapsed_seconds"] = round(elapsed, 2)
    logger.info("ingestion_completed", extra=stats)
    return stats


def _upsert_batch(batch: list[dict], stats: dict) -> None:
    """Insert a batch of rows, handling duplicates via ON CONFLICT DO UPDATE."""
    raw_responses = []
    rates = []

    for row in batch:
        raw = RawResponse(
            id=row["raw_response_id"],
            source_url=row.get("source_url", ""),
            payload={
                "provider": row["provider"],
                "rate_type": row["rate_type"],
                "rate_value": str(row["rate_value"]),
                "effective_date": str(row["effective_date"]),
                "currency": row["currency"],
            },
        )
        raw_responses.append(raw)

        rate = Rate(
            provider=row["provider_clean"],
            rate_type=row["rate_type"],
            rate_value=row["rate_value_clean"],
            effective_date=row["effective_date"],
            currency=row["currency_clean"],
            source_url=row.get("source_url", ""),
            raw_response_id=row["raw_response_id"],
        )
        rates.append(rate)

    with transaction.atomic():
        # Bulk create raw responses, ignoring conflicts on PK
        RawResponse.objects.bulk_create(raw_responses, ignore_conflicts=True)

        # Bulk upsert rates — on conflict update rate_value and ingested_at
        Rate.objects.bulk_create(
            rates,
            update_conflicts=True,
            unique_fields=["provider", "rate_type", "effective_date"],
            update_fields=["rate_value", "currency", "source_url", "raw_response"],
        )
    stats["inserted"] += len(rates)


def ingest_single_record(data: dict) -> Rate:
    """
    Ingest a single rate record from the API webhook.
    Used by POST /rates/ingest/.
    """
    # Convert Decimal/date values to strings for JSON serialization
    serializable_data = {
        k: str(v) if hasattr(v, "quantize") or hasattr(v, "isoformat") else v
        for k, v in data.items()
    }
    raw = RawResponse.objects.create(
        source_url=data.get("source_url", ""),
        payload=serializable_data,
    )

    rate, created = Rate.objects.update_or_create(
        provider=normalize_provider(data["provider"]),
        rate_type=data["rate_type"],
        effective_date=data["effective_date"],
        defaults={
            "rate_value": validate_rate_value(data["rate_value"]),
            "currency": normalize_currency(data.get("currency", "USD")),
            "source_url": data.get("source_url", ""),
            "raw_response": raw,
        },
    )
    logger.info(
        "single_record_ingested",
        extra={
            "provider": rate.provider,
            "rate_type": rate.rate_type,
            "was_created": created,
        },
    )
    return rate
