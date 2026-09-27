-include .env

DATABASE_URL ?= postgres://health:health@127.0.0.1:5432/health
export DATABASE_URL

.PHONY: db-up db-down db-reset db-status db-fixture db-verify catalog check

db-up:
	docker compose up --detach --wait postgres

db-down:
	docker compose down

db-reset:
	docker compose down --volumes
	$(MAKE) db-up

db-status:
	docker compose exec -T postgres psql --username=health --dbname=health --command="SELECT to_regclass('public.foods') AS foods, to_regclass('public.food_sources') AS food_sources"

db-fixture:
	docker compose exec -T postgres psql --username=health --dbname=health --set=ON_ERROR_STOP=1 < db/fixtures/development.sql

db-verify:
	docker compose exec -T postgres psql --username=health --dbname=health --set=ON_ERROR_STOP=1 < db/fixtures/verify.sql

catalog:
	uv run --locked health-catalog

check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked pytest
