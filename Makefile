-include .env

DATABASE_URL ?= postgres://health:health@127.0.0.1:5432/health
export DATABASE_URL

.PHONY: db-up db-down db-reset db-migrate db-backup db-restore db-status db-fixture db-verify api search-eval check

db-up:
	docker compose up --detach --wait postgres

db-down:
	docker compose down

# Deletes every food and log entry; run db-backup first if they matter.
db-reset:
	docker compose down --volumes
	$(MAKE) db-up
	$(MAKE) db-migrate

db-migrate:
	uv run --locked health-migrate

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
	docker compose exec -T postgres psql --username=health --dbname=health --command="SELECT to_regclass('public.foods') AS foods, to_regclass('public.food_sources') AS food_sources"

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
