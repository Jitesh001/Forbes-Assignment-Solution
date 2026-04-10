# DECISIONS.md

A record of engineering thinking behind the Rate Tracker implementation.

---

## 1. Assumptions

- **One canonical rate per provider per type per day.** The seed data contains ~1M rows but only ~50K unique (provider, rate_type, effective_date) combinations. I assumed the business model is "latest known rate per day" and deduplicated accordingly, keeping the row with the most recent `ingestion_ts`.
- **Provider names should be normalised.** The seed data contains 12 unique provider strings representing 10 actual providers (e.g. "hsbc", "Hsbc", "HSBC" are all HSBC). I normalise to a canonical casing on ingest rather than storing raw values, because downstream consumers (API, frontend, grouping queries) need consistent keys.
- **Currency is always stored as ISO 3-letter code.** The seed data has "USD", "usd", and "US Dollar" — all normalised to "USD" on ingest. This is a lossy transformation but appropriate because the API and database should use a single canonical format.
- **Negative rates and null rates are invalid.** The seed data has 200 null rate_values and 15 negative rates. These are treated as data quality errors and skipped during ingestion, with counts logged for observability.
- **The seed file is the "source of truth" for this assessment.** In production, data would come from HTTP scraping. The ingestion pipeline is designed so that swapping `pd.read_parquet()` for an HTTP fetch requires changing only the data acquisition step, not the cleaning or persistence logic.

## 2. Idempotency Strategy

The seed file contains several data quality issues that the ingestion worker handles:

### Problem: Duplicate (provider, rate_type, effective_date) tuples
~1M rows collapse to ~50K unique combinations. Multiple rows have the same provider+type+date but different rate_values.

**Strategy:** Deduplicate in pandas *before* hitting the database — sort by `ingestion_ts` descending and keep the first (most recent) row per (normalised_provider, rate_type, effective_date). This means we always take the latest known rate for a given day.

### Problem: Provider name casing inconsistencies
"hsbc", "Hsbc", "HSBC" would create 3 separate rows if not normalised.

**Strategy:** Apply a normalisation map on ingest (lowercase lookup → canonical form). Unknown providers fall back to `.title()`. Normalisation happens before deduplication so that "hsbc" and "HSBC" on the same date correctly collapse to one row.

### Problem: Currency format inconsistencies
"USD", "usd", "US Dollar" represent the same currency.

**Strategy:** Map to ISO 3-letter uppercase codes. This is applied before database write.

### Problem: Null and negative rate values
200 rows with null values, 15 with negative values.

**Strategy:** Skip these rows entirely. They are logged with a count for operator visibility. The `validate_rate_value` function rejects nulls, negatives, and values over 100%.

### Problem: Re-running ingestion on the same data
If `seed_data` is run twice, it must not create duplicates.

**Strategy:** The `(provider, rate_type, effective_date)` unique constraint ensures database-level idempotency. `bulk_create(update_conflicts=True)` performs an upsert — if the row exists, it updates `rate_value`, `currency`, `source_url`, and `raw_response`. The result is identical whether the command runs once or ten times.

## 3. One Tradeoff Made Consciously

**Chose Celery Beat over django-crontab or a bare cron job for scheduling.**

Option A (Celery Beat): Adds two containers (worker + beat) to docker-compose. More moving parts, but the scheduler runs inside the application, is configured in Python (not crontab syntax), retries on failure (3 retries with 5-minute backoff), and is observable via Celery's logging. No host-level cron configuration needed.

Option B (cron + management command): Simpler deployment — one cron line calling `python manage.py seed_data`. But: no retry logic, no structured logging of task state, requires host access to configure cron, and failures are silent unless you parse cron mail.

I chose Celery because the assessment explicitly values observability and idempotency. Celery gives us structured task logging, automatic retries, and a path to horizontal scaling (add workers) that cron doesn't offer. The tradeoff is operational complexity — two extra containers and a Redis dependency — but Redis is already needed for API response caching, so the marginal cost is only the worker/beat containers.

## 4. One Thing I Would Change With More Time

**Replace the 60-second polling refresh with server-sent events (SSE) or WebSocket push.**

Currently the Vue.js frontend polls `GET /rates/latest/` every 60 seconds using `setInterval`. This works but has two problems:

1. **Stale data for up to 59 seconds** after a new rate is ingested via the webhook.
2. **Unnecessary requests** when no data has changed — the API still processes the query and checks the cache.

With more time, I would add a Django Channels WebSocket endpoint (or SSE via `StreamingHttpResponse`) that pushes a notification whenever `POST /rates/ingest/` writes a new record. The frontend would hold a persistent connection and only re-fetch when notified. This eliminates both staleness and wasted requests.

I'd also add a `Last-Modified` / `ETag` header to the cached response so the frontend can make conditional requests (`If-None-Match`) and avoid re-rendering when data hasn't changed — useful even with polling as a fallback transport.

---

## Additional design notes

### Cache invalidation strategy
The `GET /rates/latest/` response is cached in Redis for 5 minutes, keyed by rate_type filter (`rates:latest:all`, `rates:latest:30yr_fixed_mortgage`, etc.). When `POST /rates/ingest/` writes a new record, it explicitly deletes the `all` key and the key matching the ingested rate's type. This is an eager invalidation pattern — slightly aggressive (a write to Chase 30yr invalidates the cache even for users viewing savings rates) but simple and correct. The 5-minute TTL provides a safety net against cache keys that somehow miss invalidation.

### Structured logging
All logging uses `python-json-logger` with a JSON formatter. Every log line includes `timestamp`, `level`, and structured `extra` fields. The ingestion worker logs `ingestion_started`, `batch_progress`, and `ingestion_completed` events with row counts. Slow API queries (>200ms) emit a `slow_query` warning. No `print()` statements exist in the codebase.

### Authentication model
The ingest endpoint uses a single bearer token from `INGEST_BEARER_TOKEN` env var, checked via a custom DRF authentication class. This is appropriate for service-to-service auth in an internal tool. For production with multiple consumers, I'd switch to per-client API keys stored in the database with scoped permissions.
