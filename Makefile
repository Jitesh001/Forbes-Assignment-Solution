.PHONY: up down build seed test logs migrate shell

# Start the entire stack
up:
	docker compose up --build -d

# Stop and remove containers
down:
	docker compose down

# Build all containers
build:
	docker compose build

# Run database migrations
migrate:
	docker compose exec web python manage.py migrate --noinput

# Seed the database with parquet data
seed:
	docker compose exec web python manage.py seed_data

# Run all tests
test:
	docker compose exec web pytest -v

# Tail logs from all services
logs:
	docker compose logs -f

# Open Django shell
shell:
	docker compose exec web python manage.py shell

# Create a superuser
superuser:
	docker compose exec web python manage.py createsuperuser

# Full setup: build, start, migrate, seed
setup: up migrate seed
	@echo "Setup complete. API at http://localhost:8000/api/ | Frontend at http://localhost:3000"
