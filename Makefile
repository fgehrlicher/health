-include .env

DATABASE_URL ?= postgres://health:health@127.0.0.1:5432/health
export DATABASE_URL

.PHONY: db-up db-down db-reset db-backup db-restore db-status db-fixture db-verify api search-eval check check-db

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

db-fixture:
	docker compose exec -T postgres psql --username=health --dbname=health --set=ON_ERROR_STOP=1 < db/fixtures/development.sql

db-verify:
	docker compose exec -T postgres psql --username=health --dbname=health --set=ON_ERROR_STOP=1 < db/fixtures/verify.sql

api:
	uv run --locked health-api

search-eval:
	uv run --locked catalog-search-eval

check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked pytest

# Rebuilds a throwaway database from db/schema.sql, imports BLS, and runs every
# test against it, including the ones that write. Never touches the real data.
TEST_DB ?= health_test
TEST_DATABASE_URL = $(patsubst %/health,%/$(TEST_DB),$(DATABASE_URL))
check-db:
	docker compose exec -T postgres psql --username=health --dbname=health --quiet --command="DROP DATABASE IF EXISTS $(TEST_DB)" --command="CREATE DATABASE $(TEST_DB)"
	docker compose exec -T postgres psql --username=health --dbname=$(TEST_DB) --quiet --set=ON_ERROR_STOP=1 < db/schema.sql
	DATABASE_URL=$(TEST_DATABASE_URL) uv run --locked bls4-import > /dev/null
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run --locked pytest
