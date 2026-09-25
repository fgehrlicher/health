# Food catalog database

The first database slice stores canonical foods, source observations, optional
dataset releases, and nutrient observations. It intentionally excludes
recipes, consumption, and agent-facing mutation tools.

## Local setup

Requirements:

- Docker with the Compose plugin
- Rust 1.94 or newer

Start PostgreSQL:

```sh
make db-up
```

The Compose service installs `db/schema.sql` automatically when it creates a
fresh database volume. To install the same schema into another empty database,
set `DATABASE_URL` and run:

```sh
make db-bootstrap
```

Inspect schema status:

```sh
make db-status
```

Load and verify the small development fixture:

```sh
make db-fixture
make db-verify
```

The default connection is
`postgres://health:health@127.0.0.1:5432/health`. Copy `.env.example` when a
different host port or local password is needed, and set `DATABASE_URL` for the
Rust command accordingly.

`make db-down` stops the service while retaining its named volume. `make
db-reset` deliberately deletes the local database volume and creates a fresh
database from the base schema.

## Schema workflow before the first deployment

`db/schema.sql` is the canonical schema and may be edited directly while the
project has no deployed database. There is deliberately no migration history
yet. After a schema change, recreate the disposable development database so it
is tested from an empty state:

```sh
make db-reset
make db-fixture
make db-verify
```

At the first deployment, freeze this file as the baseline. Every later schema
change must be an ordered migration from that deployed baseline; the migration
runner and migration directory should be introduced then.

The useful commands are:

```sh
cargo run --bin health-db -- bootstrap
cargo run --bin health-db -- status
cargo run --bin health-db -- load-fixture
cargo run --bin health-db -- verify
```

The development fixture is idempotent and separate from the base schema.
Production imports must go through the later ingestion CLI rather than becoming
schema initialization data.

## Schema boundaries

- `data_sources` identifies source families such as BLS, a user entry, a
  photographed package label, or an agent estimate.
- `source_releases` records immutable versions for sources that have releases,
  such as BLS. A manual entry or package photo does not need a fabricated
  release.
- `source_foods` is one food observation from a source. It retains upstream
  identity, timestamps, raw input, and raw structured data where available.
- `foods` and `food_aliases` provide application-owned canonical identity.
- `food_source_mappings` records whether a source record is exact, equivalent,
  or an explicit proxy. A proxy requires a rationale.
- `nutrient_profiles` declares the source record, reference amount,
  and acquisition method.
- `nutrient_values` keeps source evidence and normalized values separate. It
  retains the source nutrient identifier, unit, original value, provenance,
  and reference alongside the normalized amount, uncertainty range, missing or
  limit state, derivation, optional confidence, and any normalization or errata
  note.

An LLM label parser is an acquisition method, not the nutritional source. A
photographed label therefore uses a `package_label` source and
`llm_label_extraction` acquisition method. An estimate made by an LLM is
different: it uses an `agent_estimate` source and `llm_estimation` acquisition
method. Values absent from a label remain missing.

There is deliberately no database-level concept of the current or best value.
Different sources may disagree, and the preferred source may differ per
nutrient. Selection rules belong in a later domain layer once those rules are
known.

`preparation_state` remains free text for now. Raw, dried, boiled, and other
nutritionally meaningful forms are separate canonical foods, but the schema
does not pretend the full preparation vocabulary is already known.

## Querying nutrition observations

`food_nutrient_observations` returns all mapped observations without hiding
alternatives or provenance:

```sql
SELECT
    food_name,
    source_relationship,
    nutrient_code,
    source_nutrient_id,
    source_value,
    source_unit_code,
    source_provenance,
    normalized_amount,
    normalized_amount_lower_bound,
    normalized_amount_upper_bound,
    confidence,
    normalized_unit_code,
    value_state,
    derivation_method,
    normalization_method,
    source_slug,
    source_version,
    source_food_record_id,
    source_food_external_id
FROM food_nutrient_observations
WHERE food_slug = 'lentil-mature-dry'
ORDER BY nutrient_code;
```

The fixture contains a raw fruit, grain, and legume from BLS 4.0. It also
contains an explicit missing value, a below-detection-or-quantification value,
and logical zeros so those states can be exercised without collapsing them to
numeric zero.
