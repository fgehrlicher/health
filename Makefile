-include .env

DATABASE_URL ?= postgres://health:health@127.0.0.1:5432/health
export DATABASE_URL

.PHONY: db-up db-down db-reset db-backup db-restore db-status api web web-types search-eval check check-db check-web check-e2e test-db

db-up:
	docker compose up --detach --wait postgres

db-down:
	docker compose down

# Deletes every food and log entry; run db-backup first if they matter.
db-reset:
	docker compose down --volumes
	$(MAKE) db-up

# Writes a full dump to backups/ (ignored by Git). Restore with
# make db-restore FILE=backups/<file>.dump
db-backup:
	mkdir -p backups
	docker compose exec -T postgres pg_dump --username=health --dbname=health --format=custom > backups/health-$$(date +%Y%m%d-%H%M%S).dump
	@ls -t backups/*.dump | head -1

db-restore:
	@test -n "$(FILE)" || (echo "usage: make db-restore FILE=backups/<file>.dump" && exit 1)
	docker compose exec -T postgres pg_restore --username=health --dbname=health --clean --if-exists --single-transaction < $(FILE)

db-status:
	docker compose exec -T postgres psql --username=health --dbname=health --command="SELECT to_regclass('catalog.foods') AS foods, to_regclass('log.meals') AS meals"

api:
	uv run --locked health-api

web:
	pnpm --dir web dev

# Regenerates web/openapi.json and the TypeScript API types from the API code.
web-types:
	uv run --locked python -c "import json; from health_api.app import app; print(json.dumps(app.openapi(), indent=2))" > web/openapi.json
	pnpm --dir web exec openapi-typescript openapi.json --default-non-nullable=false -o src/lib/api/schema.gen.ts

search-eval:
	uv run --locked catalog-search-eval

check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked pytest

# Rebuilds a throwaway database from db/schema.sql and imports BLS into it.
# Tests that write use it, never the real data.
TEST_DB ?= health_test
TEST_DATABASE_URL = $(patsubst %/health,%/$(TEST_DB),$(DATABASE_URL))
test-db:
	docker compose exec -T postgres psql --username=health --dbname=health --quiet --command="DROP DATABASE IF EXISTS $(TEST_DB)" --command="CREATE DATABASE $(TEST_DB)"
	docker compose exec -T postgres psql --username=health --dbname=$(TEST_DB) --quiet --set=ON_ERROR_STOP=1 < db/schema.sql
	DATABASE_URL=$(TEST_DATABASE_URL) uv run --locked bls4-import > /dev/null

# Every API test, including those that write, against the test database.
check-db: test-db
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run --locked pytest

# Frontend: types up to date, lint, format, type check, and production build.
check-web:
	uv run --locked python -c "import json; from health_api.app import app; print(json.dumps(app.openapi(), indent=2))" | diff -q - web/openapi.json > /dev/null || (echo "web/openapi.json is stale: run make web-types" && exit 1)
	pnpm --dir web lint
	pnpm --dir web check
	pnpm --dir web typecheck
	pnpm --dir web build > /dev/null

# Browser tests (desktop and phone) against their own API on the test database.
check-e2e: test-db
	uv sync --locked --quiet
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pnpm --dir web exec playwright test
