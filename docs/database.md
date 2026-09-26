# Food catalog database

The pre-deployment catalog has two tables:

| Table | What it stores |
| --- | --- |
| `foods` | Your food names, aliases, and preparation state. Red and beluga lentils can be separate foods. |
| `food_sources` | One BLS row, manual entry, photographed label, or estimate for a specific food, with its nutrition and original context. |

Every source belongs to exactly one food through `food_sources.food_id`. The
generic BLS lentil row belongs to a generic lentils food. Red and beluga lentils
need their own source records if they are added as separate foods. A food can
have several sources whose values disagree; the application can decide which
value to use.

`source_name` is a readable label such as `BLS 4.0`. The BLS citation and
license are documented in the source research, not repeated in database rows.
There is no release history or migration history while this database has not
been deployed.

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
source values, unit conversion, nonnegative amounts, and missing versus zero.
It must link each source to the food it actually describes. The database
retains basic required fields, identities, and that direct link.

`food_sources.reference_quantity` and `reference_unit` describe the basis of
its nutrient values, commonly 100 g for BLS. The selected nutrients are direct
columns with fixed units:

| Column | Meaning |
| --- | --- |
| `energy_kcal` | Energy in kcal |
| `protein_g`, `fat_g`, `carbs_g`, `fiber_g` | Protein, fat, available carbohydrate, and fiber in grams |
| `vitamin_b12_ug`, `beta_carotene_ug` | B12 and beta carotene in micrograms |
| `vitamin_c_mg` | Vitamin C in milligrams |

`NULL` means no usable numeric value; `0` is an actual reported or logical
zero. For BLS, `raw_data.nutrients` retains each original value, unit, marker,
provenance category, and reference. This distinguishes missing, trace, and
detection-limit values even when their numeric column is null. A later
estimate can put its range and confidence in `raw_data` alongside the chosen
numeric amount.

Adding another selected nutrient requires a column. That is intentional for
the small initial set: edit the base schema before deployment, or add a
migration after deployment.

For a photographed product label, `source_name` can be `package label` and
`capture_method` can be `llm_label_extraction`. An estimate can use
`agent estimate` and `llm_estimation`; a manual entry can use `manual entry` and
`manual_entry`. The source record can retain original input in `raw_input` or
`raw_data`; a future attachment record can point to the photo itself.

## Query example

```sql
SELECT
    food.name,
    source.source_name,
    source.external_id,
    source.reference_quantity,
    source.reference_unit,
    source.energy_kcal,
    source.protein_g,
    source.fat_g,
    source.carbs_g,
    source.fiber_g,
    source.raw_data #>> '{nutrients,VITB12,provenance}' AS b12_provenance
FROM foods AS food
JOIN food_sources AS source ON source.food_id = food.id
WHERE food.slug = 'lentil-mature-dry';
```

The fixture has a fruit, grain, and legume from BLS 4.0. It includes missing,
below-limit, and logical-zero values so the importer can later exercise those
cases without turning them into invented numbers.
