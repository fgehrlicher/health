# Current state

What the system does today. It describes what exists, not what comes next.

## Summary

A local food catalog in PostgreSQL. It holds every generic food from the German
BLS 4.0 dataset and branded products registered from label photos. A local web
page browses it; an HTTP API lets an agent search, look up barcodes, and register
products. There is no consumption log yet: the system knows foods, not what you
ate.

## Components

| Part | What it is | Details |
| --- | --- | --- |
| Database | PostgreSQL 18 in Docker Compose; schema in [`db/schema.sql`](../db/schema.sql), no migrations yet | [Database](database.md) |
| BLS importer | `uv run --locked bls4-import`: downloads, verifies, and imports BLS 4.0 with its erratum | [BLS 4.0 import](bls4-import.md) |
| Catalog API and browser | `make catalog`: FastAPI on `127.0.0.1:8000`, table UI, search, registration | [Catalog](catalog.md) |
| Search quality check | `make search-eval`: 71 real queries with expected BLS codes | [Catalog: Search](catalog.md#search) |

Everything is Python managed by one uv workspace (`importers/*`, `tools/*`).
`make check` runs lint, format check, and tests; database tests run when
`TEST_DATABASE_URL` is set.

## Data model

- **`foods`**: the catalog entry: name, aliases, `kind` (`generic` from BLS,
  `branded` from labels), brand, barcode (unique), preparation state.
- **`food_sources`**: nutrition evidence for a food, e.g. one BLS row or one
  label. Holds the 14 EU label fields (kJ, kcal, fat and its "davon" rows,
  carbohydrate and its "davon" rows, fiber, protein, salt, alcohol), the
  reference quantity, values declared as "<", and the printed ingredient list.
  A food can have several sources; they are never merged.
- **`nutrients`** and **`food_source_nutrients`**: 26 further nutrients per
  source: vitamins, minerals, omega-3/6, EPA, DHA, cholesterol, water, lactose.
- **`food_portions`**: named amounts such as a label's 200 g "Portion" and
  400 g "Becher".
- **Search views**: materialized word lists behind the ranked search, refreshed
  after every write.

Unknown values are `NULL` (or absent rows), never zero. All values are per the
source's stated reference quantity, usually 100 g.

## Data in the local database

| | Count |
| --- | --- |
| Generic BLS 4.0 foods | 7,140, with 180,808 further nutrient values |
| Foods with a preparation state from their name | 3,699 |
| Branded foods | 1: Milbona High Protein Quark-Creme Pfirsich-Maracuja, with label nutrition, ingredients, legal name, and two portions |

BLS data can be rebuilt at any time with the importer. **Registered branded
foods exist only in the local database volume**: there is no export or backup,
and `make db-reset` deletes them.

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

The agent itself reads the photos. The rules it should follow are in
[Registering branded foods](catalog.md#registering-branded-foods).

## Not built

- Recording what was eaten, when, and how much; daily totals.
- Recipes, meal prep, and batches.
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
