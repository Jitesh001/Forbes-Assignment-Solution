# Database Schema

## Tables

### `rates`

The primary table storing cleaned, normalised interest-rate records.

| Column         | Type             | Constraints              | Description                                      |
| -------------- | ---------------- | ------------------------ | ------------------------------------------------ |
| `id`           | `bigint`         | PK, auto-increment       | Surrogate primary key                             |
| `provider`     | `varchar(100)`   | NOT NULL, indexed         | Normalised provider name (e.g. "HSBC", "Chase")   |
| `rate_type`    | `varchar(50)`    | NOT NULL, indexed         | One of 5 enum values (see below)                  |
| `rate_value`   | `decimal(7,4)`   | NOT NULL                  | Interest rate as a percentage (0.0000–99.9999)    |
| `effective_date` | `date`         | NOT NULL, indexed         | The date the rate became effective                |
| `currency`     | `varchar(3)`     | NOT NULL, default `'USD'` | ISO currency code, normalised to uppercase        |
| `source_url`   | `varchar(500)`   | nullable                  | URL the rate was scraped from                     |
| `raw_response_id` | `uuid`        | FK → `raw_responses.id`, nullable | Link to the raw source data           |
| `ingested_at`  | `timestamptz`    | NOT NULL, auto, indexed   | When this record was written to the database      |

#### Rate type enum values

- `30yr_fixed_mortgage`
- `15yr_fixed_mortgage`
- `5yr_arm_mortgage`
- `savings_1yr_fixed`
- `savings_easy_access`

#### Constraints

- **`uq_provider_type_date`** — `UNIQUE(provider, rate_type, effective_date)` — ensures idempotent ingestion. A given provider can only have one rate per type per day. Re-ingestion upserts (updates rate_value) rather than inserting duplicates.

#### Indexes

| Name                           | Columns                                      | Purpose                                                              |
| ------------------------------ | -------------------------------------------- | -------------------------------------------------------------------- |
| `idx_provider_type_date_desc`  | `(provider, rate_type, effective_date DESC)`  | Powers `GET /rates/latest/` — latest rate per provider+type          |
| `idx_type_date_desc`           | `(rate_type, effective_date DESC)`            | Powers `GET /rates/latest/?type=` — filtered latest by type          |
| `idx_ingested_at_desc`         | `(ingested_at DESC)`                          | Powers "all records ingested in a 24-hour window" query              |
| Individual column indexes      | `provider`, `rate_type`, `effective_date`     | General-purpose filtering                                            |

---

### `raw_responses`

Audit table storing the original, unmodified data from each ingestion source. Enables replay of failed parses and traceability.

| Column       | Type           | Constraints              | Description                                     |
| ------------ | -------------- | ------------------------ | ----------------------------------------------- |
| `id`         | `uuid`         | PK                        | Matches `raw_response_id` from the source data  |
| `source_url` | `varchar(500)` | nullable                  | The URL this data was fetched from              |
| `payload`    | `jsonb`        | NOT NULL                  | Complete raw response body as JSON              |
| `created_at` | `timestamptz`  | NOT NULL, auto, indexed   | When the raw response was stored                |

---

## Query patterns supported

### 1. Latest rate per provider

```sql
SELECT * FROM rates r
WHERE r.effective_date = (
    SELECT MAX(r2.effective_date) FROM rates r2
    WHERE r2.provider = r.provider AND r2.rate_type = r.rate_type
)
ORDER BY r.provider, r.rate_type;
```

Uses `idx_provider_type_date_desc` for the subquery.

### 2. Rate change over the last 30 days for a given type

```sql
SELECT * FROM rates
WHERE rate_type = '30yr_fixed_mortgage'
  AND effective_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY effective_date;
```

Uses `idx_type_date_desc`.

### 3. All records ingested in a given 24-hour window

```sql
SELECT * FROM rates
WHERE ingested_at >= '2025-03-01 00:00:00+00'
  AND ingested_at < '2025-03-02 00:00:00+00'
ORDER BY ingested_at;
```

Uses `idx_ingested_at_desc`.

---

## Tradeoffs considered

- **Unique constraint on `(provider, rate_type, effective_date)`** vs. allowing multiple rows per day: Chose uniqueness because the assessment requires idempotent ingestion and the business model is "one canonical rate per provider per type per day." If intra-day rate changes were needed, we'd add a time component.
- **`jsonb` for `raw_responses.payload`** vs. `text`: JSON allows structured querying of raw data for debugging. The slight storage overhead is acceptable for an audit table.
- **Separate `raw_responses` table** vs. inline JSON on `rates`: Keeps the `rates` table lean for read-heavy queries while preserving full source data for replay.
- **`decimal(7,4)`** vs. `float`: Decimal avoids floating-point precision issues inherent to financial data. 4 decimal places cover all observed precision in the seed data.
