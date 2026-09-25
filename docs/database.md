# Food catalog database

The pre-deployment catalog has four tables:

| Table | What it stores |
| --- | --- |
| `foods` | Your food names, aliases, and preparation state. Red and beluga lentils can be separate foods. |
| `food_sources` | One BLS row, manual entry, photographed label, or estimate, with its original context. |
| `food_source_links` | Which source supports which food, including a reason when a generic source is used as a proxy. |
| `nutrient_values` | Nutrients from a source, including the original value and provenance. |

A single BLS lentil source can link to both red and beluga lentils as an explicit
proxy. A food can also have several sources whose values disagree. The database
does not choose a preferred value; that decision belongs in the application.

`source_name` is a readable label such as `BLS 4.0`; `citation` and `license`
retain attribution. There is no release history or migration history while this
database has not been deployed.

## Local setup

Requirements: Docker with Compose and Rust 1.94 or newer.

```sh
make db-up       # Start PostgreSQL; a new volume gets db/schema.sql automatically
make db-status   # Show whether the base schema is installed
make db-fixture  # Load three example BLS foods
make db-verify   # Check the example data
```

The default connection is
`postgres://health:health@127.0.0.1:5432/health`. Copy `.env.example` to
change the local port or password, and set `DATABASE_URL` accordingly. For an
otherwise empty PostgreSQL database outside Compose, run `make db-bootstrap`.

`make db-down` stops PostgreSQL and retains the data. `make db-reset` deletes
this project's local database volume and creates a new one from the current
base schema. Imported foods can be recreated, so while developing the schema:

```sh
make db-reset
make db-fixture
make db-verify
```

At the first deployment, freeze `db/schema.sql`. Add ordered migrations only
for changes after that point.

## Import contract

The planned Rust ingestion CLI owns content validation and duplicate detection.
Before writing, it should check required names and source identity, allowed
source and relationship values, units and nutrient codes, nonnegative amounts,
range ordering, missing versus zero, and a reason for proxy links. The database
retains basic required fields, identities, and links between records.

`food_sources.reference_quantity` and `reference_unit` describe the basis of
all its nutrient values, commonly 100 g for BLS. `nutrient_values.amount` and
`unit` contain a usable normalized value. `source_value`, `source_unit`,
`source_provenance`, and `source_reference` preserve what the source said.
Missing, trace, and detection-limit values have a null amount and a distinct
`value_state`. Optional bounds and confidence support estimates.

For a photographed product label, `source_kind` is `package_label` and
`capture_method` can be `llm_label_extraction`. For an LLM estimate, use
`agent_estimate` and `llm_estimation`. A manual ingredient can use `user_entry`
and `manual_entry`. The source record can retain original input in `raw_input`
or `raw_data`; a future attachment record can point to the photo itself.

## Query example

```sql
SELECT
    food.name,
    link.relationship,
    source.source_name,
    source.external_id,
    source.reference_quantity,
    source.reference_unit,
    value.nutrient_code,
    value.amount,
    value.unit,
    value.value_state,
    value.source_value,
    value.source_provenance
FROM foods AS food
JOIN food_source_links AS link ON link.food_id = food.id
JOIN food_sources AS source ON source.id = link.food_source_id
JOIN nutrient_values AS value ON value.food_source_id = source.id
WHERE food.slug = 'lentil-mature-dry'
ORDER BY source.source_name, value.nutrient_code;
```

The fixture has a fruit, grain, and legume from BLS 4.0. It includes missing,
below-limit, and logical-zero values so the importer can later exercise those
cases without turning them into invented numbers.
