# Food catalog database

The pre-deployment catalog has two tables:

| Table | What it stores |
| --- | --- |
| `foods` | Your food names, aliases, and preparation state. Red and beluga lentils can be separate foods. |
| `food_sources` | One BLS row, manual entry, photographed label, or estimate for a specific food, with its energy and macros. |

Every source belongs to exactly one food through `food_sources.food_id`. The
generic BLS lentil row belongs to a generic lentils food. Red and beluga lentils
need their own source records if they are added as separate foods. A food can
have several sources whose values disagree; the application can decide which
value to use.

Ingredients and branded products share `foods`. Both are foods that recipes or
food logs should be able to reference. `kind`, `brand`, and `barcode` distinguish
products when label capture is added; a separate branded table would make those
references and searches more complicated without helping the first ingredient
import.

`source_name` is a readable label such as `BLS 4.0`. The BLS citation and
license are documented in the source research, not repeated in database rows.
There is no release history or migration history while this database has not
been deployed.

## Local setup

Requirements: Docker with Compose. The BLS importer additionally uses uv.

```sh
make db-up       # Start PostgreSQL; a new volume gets db/schema.sql automatically
make db-status   # Show whether the base schema is installed
make db-fixture  # Load three example BLS foods
make db-verify   # Check the example data
```

The default connection is
`postgres://health:health@127.0.0.1:5432/health`. Copy `.env.example` to
change the local port or password, and set `DATABASE_URL` accordingly. For an
otherwise empty PostgreSQL database outside Compose, apply `db/schema.sql` with
`psql` or your database client. Compose applies it when its volume is created;
there is no separate database-helper application to maintain.

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

Each importer owns content validation and duplicate detection. Before writing,
it should check required names and source identity, allowed source values,
unit conversion, nonnegative amounts, and missing versus zero.
It must link each source to the food it actually describes. The database
retains basic required fields, identities, and that direct link.

`food_sources.reference_quantity` and `reference_unit` describe the basis of
its values, commonly 100 g for BLS. V1 stores only these fixed-unit columns:

| Column | Meaning |
| --- | --- |
| `energy_kcal` | Energy in kcal |
| `protein_g`, `fat_g`, `carbs_g`, `fiber_g` | Protein, fat, available carbohydrate, and fiber in grams |

`NULL` means no usable numeric value; `0` is a reported or calculated zero.
The importer must interpret BLS trace, detection-limit, and missing markers
before writing. Their exact original forms remain in the source file, not in
the catalog; the import report should identify that file by checksum and
report nonnumeric values and warnings. Rebuilding an import requires both the
same source file and pipeline. The BLS importer pins the inspected workbook by
checksum.

Adding another selected nutrient requires a column. That is intentional for
the small initial set: edit the base schema before deployment, or add a
migration after deployment.

For a photographed product label later, `source_name` can be `package label`.
The label image needs its own attachment storage when that feature is built.
V1 does not store original user input or upstream dataset rows in PostgreSQL.

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
    source.fiber_g
FROM foods AS food
JOIN food_sources AS source ON source.food_id = food.id
WHERE food.slug = 'lentil-mature-dry';
```

The fixture has a fruit, grain, and legume from BLS 4.0 with energy and macros
per 100 g. The BLS importer handles missing and censored source values.
