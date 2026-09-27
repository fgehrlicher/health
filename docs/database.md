# Food catalog database

The pre-deployment catalog has three tables, plus derived
[search views](#search-views):

| Table | What it stores |
| --- | --- |
| `foods` | Your food names, aliases, and preparation state. Red and beluga lentils can be separate foods. |
| `food_sources` | One BLS row, manual entry, photographed label, or estimate for a specific food, with its energy and nutrients per reference quantity. |
| `food_portions` | Named amounts of a food, such as a label's portion or package size. |

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
`food_sources.group_code` is an optional source-specific category. The BLS
importer fills it from the BLS code prefix; future manual or label sources
can leave it empty or use their own classification.

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

## Search views

`food_search_terms` and `food_search_vocabulary` are materialized views that
split food names, aliases, source names, codes, brands, and barcodes into
searchable words. They are derived data, not a third source of truth. Anything
that inserts or renames foods or sources must refresh them in the same
transaction, as the BLS importer and development fixture do:

```sql
REFRESH MATERIALIZED VIEW food_search_terms;
REFRESH MATERIALIZED VIEW food_search_vocabulary;
```

The schema enables the `pg_trgm` extension for typo matching. For a database
created before these views existed, reset it or apply the search section of
`db/schema.sql`.

At the first deployment, freeze `db/schema.sql`. Add ordered migrations only
for changes after that point.

## Import contract

Each importer owns content validation and duplicate detection. Before writing,
it should check required names and source identity, allowed source values,
unit conversion, nonnegative amounts, and missing versus zero.
It must link each source to the food it actually describes. The database
retains basic required fields, identities, and that direct link.

`food_sources.reference_quantity` and `reference_unit` describe the basis of
its values, commonly 100 g for BLS or 100 ml for a drink label. The nutrition
columns follow the EU nutrition declaration (LMIV), so a German label maps
onto them one to one:

| Column | Label row | BLS 4.0 |
| --- | --- | --- |
| `energy_kj`, `energy_kcal` | Energie | `ENERCJ`, `ENERCC` |
| `fat_g` | Fett | `FAT` |
| `saturated_fat_g` | davon gesättigte Fettsäuren | `FASAT` |
| `monounsaturated_fat_g` | davon einfach ungesättigte Fettsäuren (optional) | `FAMS` |
| `polyunsaturated_fat_g` | davon mehrfach ungesättigte Fettsäuren (optional) | `FAPU` |
| `carbs_g` | Kohlenhydrate (available; fiber excluded) | `CHO` |
| `sugars_g` | davon Zucker | `SUGAR` |
| `polyols_g` | davon mehrwertige Alkohole (optional) | `POLYL` |
| `starch_g` | davon Stärke (optional) | `STARCH` |
| `fiber_g` | Ballaststoffe (optional on labels) | `FIBT` |
| `protein_g` | Eiweiß | `PROT625` |
| `salt_g` | Salz | `NACL` |
| `alcohol_g` | – (labels state % vol) | `ALC` |

`NULL` means no usable numeric value; `0` is a reported or calculated zero.
Labels may print a small amount as "<0,5 g". Store the bound, e.g.
`fat_g = 0.5`, and list the column in `upper_bounds`; the value is then a
maximum, not a measurement. A label's plain "0 g" is stored as reported, although
EU rounding allows it for amounts up to 0.5 g.
Protein per 100 kcal is calculated when querying, not stored: divide protein
grams by positive kcal and multiply by 100. Zero or missing kcal yields an
unknown ratio, not infinity or zero.
The importer must interpret BLS trace, detection-limit, and missing markers
before writing. Their exact original forms remain in the source file, not in
the catalog; the import report should identify that file by checksum and
report nonnumeric values and warnings. Rebuilding an import requires both the
same source file and pipeline. The BLS importer pins the inspected workbook by
checksum.

Adding another nutrient requires a column: edit the base schema before
deployment, or add a migration after deployment. Vitamins and minerals are
deliberately not columns yet; see the [BLS import guide](bls4-import.md#other-bls-fields).

`food_portions` names amounts of a food, such as a label's "Portion" of 200 g
or the whole 400 g "Becher". `kind` is `package` for the sold unit, `serving`
for the label's portion, and `piece` or `household` for other measures.
Portions let "I ate one cup" become grams.

A barcode identifies at most one food (`foods_barcode_key`).

`food_sources.ingredients_text` keeps a label's ingredient list as printed,
unparsed. It sits on the source because a recipe change produces a new label
with new values and ingredients. BLS provides no ingredient lists.

For a photographed product label later, `source_name` can be `package label`.
The label image needs its own attachment storage when that feature is built.
The database does not store original user input or upstream dataset rows.

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
