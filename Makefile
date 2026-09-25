-include .env

DATABASE_URL ?= postgres://health:health@127.0.0.1:5432/health
export DATABASE_URL

.PHONY: db-up db-down db-reset db-bootstrap db-status db-fixture db-verify check

db-up:
	docker compose up --detach --wait postgres

db-down:
	docker compose down

db-reset:
	docker compose down --volumes
	$(MAKE) db-up

db-bootstrap:
	cargo run --quiet --bin health-db -- bootstrap

db-status:
	cargo run --quiet --bin health-db -- status

db-fixture:
	cargo run --quiet --bin health-db -- load-fixture

db-verify:
	cargo run --quiet --bin health-db -- verify

check:
	cargo fmt --check
	cargo clippy --all-targets --all-features -- -D warnings
	cargo test --all-targets --all-features
