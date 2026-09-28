# Current state

What the system does today. It describes what exists, not what comes next.

## Summary

A local food catalog and consumption log in PostgreSQL. The catalog holds every
generic food from the German BLS 4.0 dataset and branded products registered
from label photos. The log records what was eaten, with nutrition calculated
only from catalog values. A local web page browses the catalog; an HTTP API lets
an agent search, look up barcodes, register products, and log meals.

## Components

| Part | What it is | Details |
| --- | --- | --- |
| Database | PostgreSQL 18 in Docker Compose; one mutable schema [`db/schema.sql`](../db/schema.sql), no migrations; `make db-backup` | [Database](database.md#schema-changes-resets-and-backups) |
| BLS importer | `uv run --locked bls4-import`: downloads, verifies, and imports BLS 4.0 with its erratum | [BLS 4.0 import](bls4-import.md) |
| Health API and browser | `make api`: the single backend, FastAPI on `127.0.0.1:8000`, in [`api/`](../api/) | |
| – catalog | Search, food details, barcode lookup, registration, table UI | [Catalog](catalog.md) |
| – consumption log | Endpoints under `/api/log`; tables in the `log` schema | [Consumption log](log.md) |
| Search quality check | `make search-eval`: 71 real queries with expected BLS codes | [Catalog: Search](catalog.md#search) |

Everything is Python managed by one uv workspace (`api`, `importers/*`).
`make check` runs lint, format check, and tests without a database.
`make check-db` builds a throwaway `health_test` database from the schema,
imports BLS, and runs every test against it; tests never touch the real data.

## Data model

Two PostgreSQL schemas: `catalog` for foods and their nutrition, `log` for what
was eaten.

- **`catalog.foods`**: the catalog entry: name, aliases, `kind` (`generic` from BLS,
  `branded` from labels), brand, barcode (unique), preparation state.
- **`catalog.food_sources`**: nutrition evidence for a food, e.g. one BLS row or one
  label. Holds the 14 EU label fields (kJ, kcal, fat and its "davon" rows,
  carbohydrate and its "davon" rows, fiber, protein, salt, alcohol), the
  reference quantity, values declared as "<", and the printed ingredient list.
  A food can have several sources; they are never merged.
- **`catalog.nutrients`** and **`catalog.food_source_nutrients`**: 26 further nutrients per
  source: vitamins, minerals, omega-3/6, EPA, DHA, cholesterol, water, lactose.
- **`catalog.food_portions`**: named amounts such as a label's 200 g "Portion" and
  400 g "Becher".
- **Search views**: materialized word lists behind the ranked search, refreshed
  after every write.
- **`log.meals`** and **`log.meal_items`**: meals (time, optional kind:
  breakfast, lunch, dinner, snack) with items of "this much of this": a catalog
  source, an amount, and whether it was estimated. Nutrition is calculated from
  the catalog when read, never stored in the log.

Unknown values are `NULL` (or absent rows), never zero. All values are per the
source's stated reference quantity, usually 100 g.

## Data in the local database

| | Count |
| --- | --- |
| Generic BLS 4.0 foods | 7,140, with 180,808 further nutrient values |
| Foods with a preparation state from their name | 3,699 |
| Branded foods | 1: Milbona High Protein Quark-Creme Pfirsich-Maracuja, registered through the API from the photos in `test-data/`: label nutrition, ingredients, legal name, and two portions |
| Logged meals | 0 |

BLS data can be rebuilt at any time with the importer. Registered foods and
meals exist only in the local database volume and in manual backups
(`make db-backup`); nothing backs up automatically, and `make db-reset`, the
only way to change the schema, deletes them.

## What an agent can do

Through the HTTP API ([reference](catalog.md#api)):

1. Find a food by barcode (`GET /api/foods/barcode/{code}`) or ranked search
   (`GET /api/foods?q=`), which handles German and English names, typos, word
   order, and compounds.
2. Read a food with all sources, further nutrients, portions, and ingredients
   (`GET /api/foods/{slug}`).
3. Register a branded product from a label (`POST /api/foods`, with
   `dry_run=true` first). Validation rejects wrong barcode check digits,
   store-internal barcodes, and label values that contradict each other, such
   as kcal that do not match the macros; it warns about missing mandatory rows.
4. Add a label's legal name or ingredient list later, e.g. from a second photo
   of a round cup (`PATCH /api/foods/{slug}/sources/{id}`).
5. Log a meal (`POST /api/log/meals`): an optional kind and items of catalog
   food plus amount or label portion, each optionally marked estimated. A meal
   without items is unknown. Fill in or correct it later, and read a day's
   totals with measured, estimated, and unknown kept apart ([details](log.md)).

The agent itself reads the photos. The rules it should follow are in
[Registering branded foods](catalog.md#registering-branded-foods).

## Not built

- Recipes, meal prep, batches, and reusable meals ("my usual breakfast").
- Portion sizes for generic foods ("1 egg", "1 slice of bread"): BLS has none,
  so such amounts must be given in grams, marked estimated if guessed.
- Vitamins and minerals in log totals (they are in the catalog).
- A connection for an agent: no MCP server or tool definitions, no agent
  instructions beyond the API documentation.
- Login or any access control. The server listens on `127.0.0.1` only.
- Correcting registered foods beyond legal name and ingredients: no edit or
  delete of nutrition values, no second label version for a known barcode, no
  adding portions or aliases after registration.
- Registering foods without a label, such as bakery goods or homemade dishes.
- Vitamins and minerals from labels (the API accepts only the 14 label fields).
- Storing label photos, their checksums, or when a label was observed; the
  health mark (e.g. `DE NI 33000 EU`) has no field.
- Open Food Facts lookups.

## Known data limitations

- BLS 4.0 values are mostly recipe calculations; about 5% of protein and fat
  values are laboratory analyses.
- Values the BLS erratum marks as wrong without a replacement are stored as
  unknown until BLS 4.1, including raw anchovy fat and energy and 157 recipes'
  vitamin A, iodine, or calcium ([details](bls4-import.md#values-and-limits)).
- Search finds the intended food first for 56% of test queries and within the
  top five for 80%. Most misses are synonyms not in BLS names, such as
  `porridge` or `ground beef`.
- `test-data/` holds the quark label photos. It is not tracked by Git and not
  ignored; the photos contain GPS coordinates.

## Background

- [Product and technical vision](VISION.md)
- [Research: choosing the ingredient data source](spikes/01-ingredient-data-source/README.md)
