# Rate Tracker

A production-shaped application that ingests, stores, exposes and visualises interest-rate data. Built with Django REST Framework, PostgreSQL, Redis, Celery, and Vue.js.

## Prerequisites

- **Docker** and **Docker Compose** (v2)
- **Git**
- No other local dependencies required — everything runs in containers.

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd rate-tracker

# 2. Copy environment file
cp .env.example .env

# 3. Start all services
docker compose up --build -d

# 4. Run database migrations
docker compose exec web python manage.py migrate

# 5. Seed the database (~1M rows, takes 1-2 minutes)
docker compose exec web python manage.py seed_data

# 6. Create an admin user (optional, for Django admin panel)
docker compose exec web python manage.py createsuperuser

# 7. Open the app
# API:       http://localhost:8000/api/rates/latest/
# Frontend:  http://localhost:3000
# Admin:     http://localhost:8000/admin/
```

Or use the Makefile shorthand:

```bash
cp .env.example .env
make setup    # builds, starts, migrates, seeds
```

## How to Run Tests

```bash
# Run all tests inside the container
docker compose exec web pytest -v

# Run a specific test class
docker compose exec web pytest rates/tests.py::TestIngestAPI -v
```

## API Endpoints

### `GET /api/rates/latest/`
Returns the most recent rate per provider. Optional `?type=` filter.

```bash
curl http://localhost:8000/api/rates/latest/
curl http://localhost:8000/api/rates/latest/?type=30yr_fixed_mortgage
```

### `GET /api/rates/history/`
Paginated time-series. Requires `provider` and `type` params. Supports `from`/`to` date filters.

```bash
curl "http://localhost:8000/api/rates/history/?provider=Chase&type=30yr_fixed_mortgage&from=2025-01-01&to=2025-12-31"
```

### `POST /api/rates/ingest/`
Authenticated webhook. Requires `Authorization: Bearer <token>` header.

```bash
curl -X POST http://localhost:8000/api/rates/ingest/ \
  -H "Authorization: Bearer dev-ingest-token-change-me" \
  -H "Content-Type: application/json" \
  -d '{"provider": "Chase", "rate_type": "30yr_fixed_mortgage", "rate_value": "6.75", "effective_date": "2025-03-15"}'
```

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────────┐
│ Vue.js   │────▶│ Django   │────▶│ PostgreSQL   │
│ Frontend │     │ DRF API  │     │              │
│ :3000    │     │ :8000    │     │ :5432        │
└──────────┘     └────┬─────┘     └──────────────┘
                      │
                 ┌────▼─────┐     ┌──────────────┐
                 │ Redis    │◀────│ Celery       │
                 │ Cache    │     │ Worker+Beat  │
                 │ :6379    │     │              │
                 └──────────┘     └──────────────┘
```

## Key Design Decisions

See [DECISIONS.md](DECISIONS.md) for detailed reasoning on:
- Idempotency strategy for handling duplicate/dirty data
- Why Celery Beat over cron
- Cache invalidation approach
- What I'd change with more time

See [schema.md](schema.md) for database schema documentation including index rationale.

## Project Structure

```
├── config/              # Django project settings, URLs, Celery config
├── rates/               # Main Django app
│   ├── management/      # seed_data command
│   ├── migrations/      # Database migrations
│   ├── models.py        # Rate, RawResponse models
│   ├── serializers.py   # DRF serializers
│   ├── services.py      # Core ingestion logic
│   ├── views.py         # API views
│   ├── tasks.py         # Celery tasks
│   ├── authentication.py # Bearer token auth
│   └── tests.py         # All tests
├── frontend/            # Vue.js 3 + TailwindCSS
│   ├── src/
│   │   ├── components/  # RateTable, RateHistoryChart
│   │   ├── composables/ # useRates
│   │   └── api/         # Axios API client
│   └── Dockerfile
├── docker-compose.yml   # Full stack orchestration
├── Dockerfile           # Django container
├── Makefile             # Convenience commands
├── DECISIONS.md         # Engineering decisions
├── schema.md            # Database schema docs
└── .env.example         # Environment template
```

## Environment Variables

All configuration is via environment variables. See `.env.example` for the full list. The application fails fast with a clear error message if required variables are missing.

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | Yes (production) | Django secret key |
| `POSTGRES_DB` | Yes | Database name |
| `POSTGRES_USER` | Yes | Database user |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `POSTGRES_HOST` | Yes | Database host |
| `REDIS_URL` | Yes | Redis connection string |
| `INGEST_BEARER_TOKEN` | Yes | Auth token for POST /rates/ingest/ |

## Stopping

```bash
docker compose down          # stop containers
docker compose down -v       # stop + remove volumes (deletes DB data)
```
