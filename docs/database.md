# Food catalog database

The database has two PostgreSQL schemas. `catalog` holds five tables plus
derived [search views](#search-views); `log` holds the meals described in
[Consumption log](log.md). SQL names tables with their schema, e.g.
`catalog.foods` and `log.meals`; the `public` schema only holds the `pg_trgm`
extension.

| Table | What it stores |
| --- | --- |
| `foods` | Your food names, aliases, and preparation state. Red and beluga lentils can be separate foods. |
| `food_sources` | One BLS row, manual entry, photographed label, or estimate for a specific food, with its energy and nutrients per reference quantity. |
| `food_portions` | Named amounts of a food, such as a label's portion or package size. |
| `nutrients`, `food_source_nutrients` | Vitamins, minerals, and other nutrients beyond the label columns, per source. |

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
`psql` or your database client.

## Schema changes, resets, and backups

`db/schema.sql` is still a mutable baseline with no migrations: a schema change
means editing it and running `make db-reset`. That deletes the volume,
**including every registered food and logged meal**, and rebuilds from the
current schema. BLS data returns with the importer; everything else only from a
backup or by registering it again. Once real data must survive schema changes,
the baseline should be frozen and changes added as migrations.

- `make db-backup` writes a full dump to `backups/`, which Git ignores.
  `make db-restore FILE=backups/<file>.dump` replaces the database with it.
  Take one before a reset. Nothing runs backups automatically. Without
  migrations, a dump restores only into the schema it was taken from: after a
  schema change, older dumps are a record, not a restore path.
- `make db-down` stops PostgreSQL and keeps the data.

## Search views

`food_search_terms` and `food_search_vocabulary` are materialized views that
split food names, aliases, source names, codes, brands, and barcodes into
searchable words. They are derived data, not a third source of truth. Anything
that inserts or renames foods or sources must refresh them in the same
transaction, as the BLS importer, the API, and the development fixture do:

```sql
SELECT catalog.refresh_search();
```

A refresh rebuilds both views, about half a second for the full BLS catalog,
and blocks searches meanwhile.

The schema enables the `pg_trgm` extension for typo matching.

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

The label columns are fixed; other nutrients live in `food_source_nutrients`
(see below).

`nutrients` lists further nutrients, e.g. vitamins and minerals, with their
unit and INFOODS code (`VITD`), seeded by the schema. `food_source_nutrients`
holds one amount per source and nutrient in that unit; no row means unknown,
and `upper_bound` marks a declared maximum. Add a nutrient by inserting a
`nutrients` row, not a column.

`foods.preparation_state` is one of raw, boiled, stewed, braised, grilled,
fried, baked, deep-fried, dried, frozen, canned, smoked, poached, steamed,
roasted, gratinated, toasted, blanched, or cooked, or `NULL` when unknown.

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
FROM catalog.foods AS food
JOIN catalog.food_sources AS source ON source.food_id = food.id
WHERE food.slug = 'lentil-mature-dry';
```

The fixture has a fruit, grain, and legume from BLS 4.0 with energy and macros
per 100 g. The BLS importer handles missing and censored source values.
